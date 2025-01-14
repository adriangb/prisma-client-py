# TODO: this should be shared between all tests
import asyncio
import inspect
from contextvars import ContextVar

import pytest

from prisma import Client
from prisma.utils import async_run


client_ctx: ContextVar['Client'] = ContextVar('client_ctx', default=Client())


@pytest.fixture(name='client', scope='session')
def client_fixture() -> Client:
    client = client_ctx.get()
    async_run(client.connect())
    async_run(cleanup_client(client))
    return client


@pytest.fixture(scope='session')
def event_loop() -> asyncio.AbstractEventLoop:
    return asyncio.get_event_loop()


def pytest_runtest_setup(item: pytest.Function) -> None:
    client = client_ctx.get()
    if client.is_connected():
        async_run(cleanup_client(client))


async def cleanup_client(client: Client) -> None:
    for _, item in inspect.getmembers(client):
        if item.__class__.__name__.endswith('Actions'):
            await item.delete_many()
