import pytest

from airthings import web_api

pytestmark = pytest.mark.asyncio


async def test_something(aiohttp_session, auth_manager):
    api = web_api.WebAPI(aiohttp_session, auth_manager)
    print(await api.me())
    assert False
