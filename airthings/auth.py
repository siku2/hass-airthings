import abc
import asyncio
import dataclasses
import logging
from datetime import datetime, timedelta
from typing import Optional

import aiohttp

from .consts import TOKEN_URL
from .errors import APIError

logger = logging.getLogger(__name__)

__all__ = ["LoginDetails", "TokenDetails",
           "AuthManagerABC", "AuthManager"]


@dataclasses.dataclass()
class LoginDetails:
    username: str
    password: str


@dataclasses.dataclass()
class TokenDetails:
    access_token: str
    token_type: str
    expires_in: int
    expires_at: datetime = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        self.expires_at = datetime.now() + timedelta(seconds=self.expires_in)

    @property
    def expired(self) -> bool:
        return datetime.now() >= self.expires_at


async def auth_request(session: aiohttp.ClientSession, login: LoginDetails) -> TokenDetails:
    logger.debug("performing auth request with %s", login)
    body = {
        "username": login.username,
        "password": login.password,
        "grant_type": "password",
        "client_id": "accounts",
    }
    async with session.post(TOKEN_URL, json=body) as resp:
        data = await resp.json()
        if resp.status != 200:
            raise APIError.from_response(resp, data)

    return TokenDetails(**data)


class AuthManagerABC(abc.ABC):
    __slots__ = ()

    @property
    @abc.abstractmethod
    def login_details(self) -> LoginDetails:
        ...

    @login_details.setter
    @abc.abstractmethod
    def login_details(self, value: LoginDetails) -> None:
        ...

    @abc.abstractmethod
    async def force_renew_token(self) -> None:
        ...

    @abc.abstractmethod
    async def maybe_renew_token(self) -> bool:
        ...

    @abc.abstractmethod
    async def get_token_details(self) -> TokenDetails:
        ...

    @abc.abstractmethod
    async def get_access_token(self) -> str:
        ...


class AuthManager(AuthManagerABC):
    session: aiohttp.ClientSession
    _login: LoginDetails
    _token: Optional[TokenDetails]

    def __init__(self, session: aiohttp.ClientSession, login_details: LoginDetails) -> None:
        self.session = session
        self._token = None
        self._login = login_details

        self._lock = asyncio.Lock()

    def __str__(self) -> str:
        return f"{type(self).__qualname__}({self.login_details})"

    @property
    def login_details(self) -> LoginDetails:
        return self._login

    @login_details.setter
    def login_details(self, value: LoginDetails) -> None:
        self._token = None
        self._login = value

    def _should_renew_token(self) -> bool:
        return self._token is None or self._token.expired

    async def _force_renew_token(self) -> None:
        self._token = await auth_request(self.session, self._login)

    async def force_renew_token(self) -> None:
        async with self._lock:
            await self._force_renew_token()

    async def maybe_renew_token(self) -> bool:
        async with self._lock:
            if not self._should_renew_token():
                return False

            await self._force_renew_token()
            return True

    async def get_token_details(self) -> TokenDetails:
        await self.maybe_renew_token()
        return self._token

    async def get_access_token(self) -> str:
        details = await self.get_token_details()
        return details.access_token
