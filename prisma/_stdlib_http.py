import json
from typing import Optional, Any, Dict, Tuple, Union

import http.client as http
from urllib.parse import urlparse

from ._types import Method
from .http_abstract import AbstractResponse, AbstractHTTP


__all__ = ('HTTP', 'Response', 'client')


class Session:
    """Wrapper around http.HTTP(S)Connection handling multiple different netlocs and parsing URLs"""

    def __init__(self) -> None:
        # NOTE: it is outside the scope of this library to handle
        # limiting the number of open connections
        self.connections = (
            {}
        )  # type: Dict[Tuple[str, str], Union[http.HTTPConnection, http.HTTPSConnection]]

    def request(
        self,
        method: Method,
        url: str,
        data: Optional[str] = None,
        raise_for_status: bool = False,
        **kwargs: Any,
    ) -> http.HTTPResponse:
        parsed = urlparse(url)

        conn = self._get_connection(parsed.netloc, parsed.scheme)
        conn.request(method, parsed.path, data, kwargs.get('headers', {}))
        resp = conn.getresponse()

        if raise_for_status and not 300 > resp.status >= 200:
            # TODO
            raise RuntimeError(resp.status)

        return resp

    def _get_connection(
        self, netloc: str, scheme: str
    ) -> Union[http.HTTPConnection, http.HTTPSConnection]:
        key = (netloc, scheme)
        conn = self.connections.get(key)
        if conn is not None:
            return conn

        if scheme == 'http':
            conn = http.HTTPConnection(netloc)
        elif scheme == 'https':
            conn = http.HTTPSConnection(netloc)
        else:
            raise ValueError(
                f'Unexpected scheme: "{scheme}", only http and https are supported.'
            )

        self.connections[key] = conn
        return conn

    def close(self) -> None:
        for conn in self.connections.values():
            conn.close()

    def __del__(self) -> None:
        self.close()


class HTTP(AbstractHTTP[Session, http.HTTPResponse]):
    # pylint: disable=attribute-defined-outside-init

    library = 'stdlib'

    def download(self, url: str, dest: str) -> None:
        resp = self.request('GET', url, raise_for_status=True)
        with open(dest, 'wb') as fd:
            # TODO: read and wrte in chunks
            fd.write(resp.raw())

    def request(self, method: Method, url: str, **kwargs: Any) -> 'Response':
        return Response(self.session.request(method, url, **kwargs))

    def close(self) -> None:
        if not self.closed:
            self.session.close()
            self.session = None  # type: ignore[assignment]

    def open(self) -> None:
        self.session = Session()

    def __del__(self) -> None:
        self.close()


client = HTTP()


class Response(AbstractResponse[http.HTTPResponse]):
    @property
    def status(self) -> int:
        return self.original.status

    def json(self) -> Any:
        return json.loads(self.text())

    def text(self) -> Any:
        return str(self.original.read(), 'utf-8')

    def raw(self) -> Any:
        return self.original.read()
