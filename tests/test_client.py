import pytest
from prisma import Client, errors


@pytest.mark.asyncio
async def test_catches_not_connected() -> None:
    """Trying to make a query before connecting raises an error"""
    client = Client()
    with pytest.raises(errors.ClientNotConnectedError) as exc:
        await client.post.delete_many()

    assert 'await client.connect()' in str(exc)


@pytest.mark.asyncio
async def test_create_many_invalid_provider(client: Client) -> None:
    """Trying to call create_many() fails as SQLite does not support it"""
    with pytest.raises(errors.UnsupportedDatabaseError) as exc:
        await client.user.create_many([{'name': 'Robert'}])

    assert exc.match(r'create_many\(\) is not supported by sqlite')
