import asyncio
import dataclasses
import logging
from datetime import datetime, timedelta
from typing import Optional

import aiohttp

from .consts import LOGIN_URL, REFRESH_URL
from .errors import APIError
from .types import JSONObj

logger = logging.getLogger(__name__)

__all__ = ["LoginDetails", "TokenDetails", "AuthManager"]


@dataclasses.dataclass()
class LoginDetails:
    email: str
    password: str

    def _payload(self) -> JSONObj:
        return {"email": self.email, "password": self.password}


@dataclasses.dataclass()
class TokenDetails:
    access_token: str
    id_token: str
    refresh_token: str
    expires_in: int
    expires_at: datetime = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        self.expires_at = datetime.now() + timedelta(seconds=self.expires_in)

    @classmethod
    def from_payload(cls, payload: JSONObj):
        return cls(
            access_token=payload["accessToken"],
            id_token=payload["idToken"],
            refresh_token=payload["refreshToken"],
            expires_in=payload["expiresIn"],
        )

    @property
    def expired(self) -> bool:
        return datetime.now() >= self.expires_at


async def refresh_request(
    session: aiohttp.ClientSession, token_details: TokenDetails
) -> TokenDetails:
    logger.debug("performing token refresh request with %s", token_details)
    body = {"refreshToken": token_details.refresh_token}
    async with session.post(REFRESH_URL, json=body) as resp:
        data = await resp.json()
        if resp.status != 200:
            raise APIError.from_response(resp, data)

    return TokenDetails.from_payload(data)


async def login_request(
    session: aiohttp.ClientSession, login: LoginDetails
) -> TokenDetails:
    logger.debug("performing login request with %s", login)
    async with session.post(LOGIN_URL, json=login._payload()) as resp:
        data = await resp.json()
        if resp.status != 200:
            raise APIError.from_response(resp, data)

    return TokenDetails.from_payload(data)


class AuthManager:
    session: aiohttp.ClientSession
    _login: LoginDetails
    _token: Optional[TokenDetails]

    def __init__(
        self, session: aiohttp.ClientSession, login_details: LoginDetails
    ) -> None:
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
        if self._token is None:
            self._token = await login_request(self.session, self._login)
        else:
            self._token = await refresh_request(self.session, self._token)

    async def force_renew_token(self) -> None:
        async with self._lock:
            await self._force_renew_token()

    async def _maybe_renew_token(self) -> bool:
        async with self._lock:
            if not self._should_renew_token():
                return False

            await self._force_renew_token()
            return True

    async def get_token_details(self) -> TokenDetails:
        await self._maybe_renew_token()
        return self._token

    async def get_access_token(self) -> str:
        details = await self.get_token_details()
        return details.access_token
