import pytest

import airthings

pytestmark = pytest.mark.asyncio


async def test_auth_fail(aiohttp_session):
    with pytest.raises(airthings.APIError):
        await airthings.auth.auth_request(aiohttp_session, airthings.LoginDetails("invalid", ""))


async def test_auth_manager(auth_manager: airthings.AuthManagerABC):
    assert await auth_manager.get_access_token()
