import enum
import importlib
from pathlib import Path
from importlib import machinery
from contextvars import ContextVar
from typing import Any, Optional, List, Union, Iterator, TYPE_CHECKING
from pydantic import BaseModel, Extra, Field as FieldInfo, conint, validator

from .utils import pascalize, camelize, decamelize


# NOTE: this does not represent all the data that is passed by prisma

ATOMIC_FIELD_TYPES = ['Int', 'Float', 'Boolean']

# TODO: Json probably isn't right
TYPE_MAPPING = {
    'String': 'str',
    'DateTime': 'datetime.datetime',
    'Boolean': 'bool',
    'Int': 'int',
    'Float': 'float',
    'Json': 'dict',
}
FILTER_TYPES = ['String', 'Datetime', 'Boolean', 'Int', 'Float']

data_ctx: ContextVar['Data'] = ContextVar('data_ctx')


def get_config() -> 'Config':
    return data_ctx.get().generator.config


class TransformChoices(str, enum.Enum):
    none = 'none'
    snake_case = 'snake_case'
    camel_case = 'camelCase'
    pascal_case = 'PascalCase'


class HttpChoices(str, enum.Enum):
    stdlib = 'stdlib'
    aiohttp = 'aiohttp'
    requests = 'requests'


class Module(BaseModel):
    spec: machinery.ModuleSpec

    class Config:
        arbitrary_types_allowed = True

    @validator('spec', pre=True, allow_reuse=True)
    @classmethod
    def spec_validator(cls, value: Optional[str]) -> machinery.ModuleSpec:
        spec: Optional[machinery.ModuleSpec] = None

        if value is None:
            value = '.prisma/partials.py'

        path = Path.cwd().joinpath(value)
        if path.exists():
            spec = importlib.util.spec_from_file_location(
                'prisma.partial_type_generator', value
            )
        elif value.startswith('.'):
            raise ValueError(
                f'No file found at {value} and relative imports are not allowed.'
            )
        else:
            try:
                spec = importlib.util.find_spec(value)
            except ModuleNotFoundError:
                spec = None

        if spec is None:
            raise ValueError(f'Could not find a python file or module at {value}')

        return spec

    def run(self) -> None:
        importlib.invalidate_caches()
        mod = importlib.util.module_from_spec(self.spec)
        assert self.spec.loader is not None, 'Expected an import loader to exist.'

        # TODO: why does mypy think loader has no exec_module attribute?
        # it was added in python3.4
        try:
            self.spec.loader.exec_module(mod)  # type: ignore[attr-defined]
        except:
            print('An exception ocurred while running the partial type generator')
            raise


class Data(BaseModel):
    """Root model for the data that prisma provides to the generator."""

    datamodel: str
    version: str
    generator: 'Generator'
    dmmf: 'DMMF' = FieldInfo(alias='dmmf')
    schema_path: str = FieldInfo(alias='schemaPath')

    # TODO
    data_sources: Any = FieldInfo(alias='dataSources')
    other_generators: List[Any] = FieldInfo(alias='otherGenerators')

    @classmethod
    def parse_obj(cls, obj: Any) -> 'Data':
        data = super().parse_obj(obj)
        data_ctx.set(data)
        return data


class Generator(BaseModel):
    name: str
    output: str
    provider: str
    config: 'Config'
    binary_targets: List[str] = FieldInfo(alias='binaryTargets')
    preview_features: List[str] = FieldInfo(alias='previewFeatures')


class Config(BaseModel):
    """Custom generator config options."""

    if TYPE_CHECKING:
        recursive_type_depth: int
    else:
        recursive_type_depth: conint(ge=2) = FieldInfo(
            alias='recursiveTypeDepth', default=5
        )

    transform_fields: Optional[TransformChoices] = FieldInfo(alias='transformFields')

    # NOTE: we do not set the default based off of
    #       the library the user has installed so
    #       that the same schema will always generate
    #       the same type of client independent of the
    #       state of the system.
    http: HttpChoices = HttpChoices.aiohttp
    partial_type_generator: Optional[Module] = FieldInfo(alias='partialTypeGenerator')

    class Config:
        extra = Extra.forbid
        use_enum_values = True
        allow_population_by_field_name = True

    @validator('http', always=True, allow_reuse=True)
    @classmethod
    def http_matches_installed_library(cls, value: HttpChoices) -> str:
        # pylint: disable=unused-import, import-outside-toplevel
        try:
            if value == HttpChoices.aiohttp:
                import aiohttp
            elif value == HttpChoices.requests:
                import requests
            elif value == HttpChoices.stdlib:
                pass
            else:  # pragma: no cover
                raise RuntimeError(f'Unhandled validator check for {value}')
        except (ModuleNotFoundError, ImportError) as exc:
            # pylint: disable=line-too-long
            raise ValueError(
                f'Missing library for "{value}"\n  '
                'Did you specify the correct target library in your `schema.prisma` file?\n  '
                'See https://github.com/RobertCraigie/prisma-client-py/blob/master/docs/config.md#http-libraries'
            ) from exc

        return value

    @validator('partial_type_generator', pre=True, always=True, allow_reuse=True)
    @classmethod
    def partial_type_generator_converter(cls, value: Optional[str]) -> Optional[Module]:
        try:
            return Module(spec=value)
        except ValueError:
            if value is None:
                # no config value passed and the default location was not found
                return None
            raise


class DMMF(BaseModel):
    datamodel: 'Datamodel'

    # TODO
    prisma_schema: Any = FieldInfo(alias='schema')


class Datamodel(BaseModel):
    enums: List['Enum']
    models: List['Model']


class Enum(BaseModel):
    name: str
    db_name: Optional[str] = FieldInfo(alias='dbName')
    values: List['EnumValue']


class EnumValue(BaseModel):
    name: str
    db_name: Optional[str] = FieldInfo(alias='dbName')


class Model(BaseModel):
    name: str
    is_embedded: bool = FieldInfo(alias='isEmbedded')
    db_name: Optional[str] = FieldInfo(alias='dbName')
    is_generated: bool = FieldInfo(alias='isGenerated')
    all_fields: List['Field'] = FieldInfo(alias='fields')

    @property
    def related_models(self) -> Iterator['Model']:
        models = data_ctx.get().dmmf.datamodel.models
        for field in self.relational_fields:
            for model in models:
                if field.type == model.name:
                    yield model

    @property
    def relational_fields(self) -> Iterator['Field']:
        for field in self.all_fields:
            if field.relation_name:
                yield field

    @property
    def scalar_fields(self) -> Iterator['Field']:
        for field in self.all_fields:
            if not field.relation_name:
                yield field

    @property
    def atomic_fields(self) -> Iterator['Field']:
        for field in self.all_fields:
            if field.type in ATOMIC_FIELD_TYPES:
                yield field


class Field(BaseModel):
    name: str

    # TODO: switch to enums
    kind: str
    type: str

    is_id: bool = FieldInfo(alias='isId')
    is_list: bool = FieldInfo(alias='isList')
    is_unique: bool = FieldInfo(alias='isUnique')
    is_required: bool = FieldInfo(alias='isRequired')
    is_read_only: bool = FieldInfo(alias='isReadOnly')
    is_generated: bool = FieldInfo(alias='isGenerated')
    is_updated_at: bool = FieldInfo(alias='isUpdatedAt')

    default: Optional[Union['DefaultValue', str]]
    has_default_value: bool = FieldInfo(alias='hasDefaultValue')

    relation_name: Optional[str] = FieldInfo(alias='relationName')
    relation_on_delete: Optional[str] = FieldInfo(alias='relationOnDelete')
    relation_to_fields: Optional[List[str]] = FieldInfo(alias='relationToFields')
    relation_from_fields: Optional[List[str]] = FieldInfo(alias='relationFromFields')

    # TODO: cache the properties
    @property
    def python_type(self) -> str:
        type_ = self._actual_python_type
        if self.is_list:
            return f'List[{type_}]'
        return type_

    @property
    def python_type_as_string(self) -> str:
        type_ = self._actual_python_type
        if self.is_list:
            type_ = type_.replace('\'', '\\\'')
            return f'\'List[{type_}]\''

        if not type_.startswith('\''):
            type_ = f'\'{type_}\''

        return type_

    @property
    def _actual_python_type(self) -> str:
        if self.kind == 'enum':
            return f'\'types.{self.type}Enum\''

        if self.kind == 'object':
            return f'\'models.{self.type}\''

        try:
            return TYPE_MAPPING[self.type]
        except KeyError as exc:
            # TODO: handle this better
            raise RuntimeError(
                f'Could not parse {self.name} due to unknown type: {self.type}',
            ) from exc

    @property
    def create_input_type(self) -> str:
        if self.kind != 'object':
            return self.python_type

        if self.is_list:
            return f'\'{self.type}CreateManyNestedWithoutRelationsInput\''

        return f'\'{self.type}CreateNestedWithoutRelationsInput\''

    @property
    def where_input_type(self) -> str:
        typ = self.type
        if typ in FILTER_TYPES:
            return f'Union[{self._actual_python_type}, \'types.{typ}Filter\']'
        return self.python_type

    @property
    def relational_args_type(self) -> str:
        if self.is_list:
            return f'FindMany{self.type}Args'
        return f'{self.type}Args'

    @property
    def python_case(self) -> str:
        transform = get_config().transform_fields
        if transform == TransformChoices.camel_case:
            return camelize(self.name)

        if transform == TransformChoices.pascal_case:
            return pascalize(self.name)

        if transform == TransformChoices.none:
            return self.name

        return decamelize(self.name)

    @property
    def required_on_create(self) -> bool:
        return (
            self.is_required
            and not self.is_updated_at
            and not self.has_default_value
            and not self.relation_name
        )

    @property
    def is_optional(self) -> bool:
        return not (self.is_required and not self.relation_name)

    @property
    def is_atomic(self) -> bool:
        return self.type in ATOMIC_FIELD_TYPES

    @property
    def atomic_type(self) -> str:
        if not self.is_atomic:
            raise TypeError('Field is not atomic')

        if self.is_list:
            return f'List[{self.python_type}]'

        return self.python_type

    def get_update_input_type(self, model: str) -> str:
        if self.is_atomic:
            return f'Union[\'{model}Update{self.name}Input\', {self.atomic_type}]'

        if self.kind == 'object':
            if self.is_list:
                return f'\'{self.type}UpdateManyWithoutRelationsInput\''
            return f'\'{self.type}UpdateOneWithoutRelationsInput\''

        return self.python_type


class DefaultValue(BaseModel):
    args: Any
    name: str


Enum.update_forward_refs()
DMMF.update_forward_refs()
Data.update_forward_refs()
Field.update_forward_refs()
Model.update_forward_refs()
Datamodel.update_forward_refs()
Generator.update_forward_refs()
