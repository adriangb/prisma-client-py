import pytest
from prisma import Client


@pytest.mark.asyncio
async def test_create(client: Client) -> None:
    user = await client.user.create({
        'name': 'Robert',
        'emails': ['robert@craigie.dev', 'rob@craigie.dev']
    })
    assert user.emails == ['robert@craigie.dev', 'rob@craigie.dev']


@pytest.mark.asyncio
async def test_order_by(client: Client) -> None:
    total = await client.user.create_many(
        [{'name': 'Robert', 'emails': ['a', 'b']}, {'name': 'Tegan', 'emails': ['c']}]
    )
    assert total == 2

    users = await client.user.find_many(order={'emails': 'desc'})
    assert len(users) == 2
    assert users[0].name == 'Tegan'
    assert users[1].name == 'Robert'

    users = await client.user.find_many(order={'emails': 'asc'})
    assert len(users) == 2
    assert users[0].name == 'Robert'
    assert users[1].name == 'Tegan'


@pytest.mark.asyncio
async def test_filtering(client: Client) -> None:
    assert False, 'TODO'
