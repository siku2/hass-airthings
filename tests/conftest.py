import os

import aiohttp
import pytest

import airthings


@pytest.fixture()
async def aiohttp_session(event_loop):
    async with aiohttp.ClientSession(loop=event_loop) as sess:
        yield sess


@pytest.fixture(scope="session")
def login_details():
    env = os.environ
    try:
        username = env["AIRTHINGS_USERNAME"]
        password = env["AIRTHINGS_PASSWORD"]
    except KeyError:
        pytest.skip("missing airthings credentials")
    else:
        return airthings.LoginDetails(username, password)


@pytest.fixture()
async def auth_manager(aiohttp_session, login_details):
    yield airthings.AuthManager(aiohttp_session, login_details)
