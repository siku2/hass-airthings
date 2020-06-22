import asyncio
import logging
from datetime import timedelta
from typing import Dict, List, Optional

import aiohttp

from .auth import AuthManager, LoginDetails
from .consts import ME_URL
from .errors import APIError
from .event_system import EventSystem
from .types import JSONAny
from . import models

__all__ = [
    "DeviceState",
    "AirthingsAPI",
]

logger = logging.getLogger(__name__)


def create_session(api_key: str) -> aiohttp.ClientSession:
    return aiohttp.ClientSession(
        headers={"X-API-Key": api_key, "User-Agent": f"hass-airthings/1.1",}
    )


class DeviceState(EventSystem):
    info: models.Device

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.info!r})"

    @classmethod
    def _from_device(cls, info: models.Device):
        self = cls()
        self.info = info
        return self

    @property
    def serial_number(self) -> str:
        self.info.serial_number

    @property
    def sensors(self) -> List[models.Sensor]:
        self.info.sensors

    def get_sensor(self, sensor_type: str) -> Optional[models.Sensor]:
        self.info.get_sensor(sensor_type)

    async def _update(self, info: models.Device) -> bool:
        self.info = info
        self.dispatch_async("updated")

    async def _after_remove(self) -> None:
        self.dispatch_async("removed")


class AirthingsAPI(EventSystem):
    session: aiohttp.ClientSession
    auth: AuthManager

    __states: Dict[str, DeviceState]
    __states_lock: asyncio.Lock
    __update_tasks: List[asyncio.Task]

    def __init__(self, session: aiohttp.ClientSession, auth: AuthManager) -> None:
        super().__init__()

        self.session = session
        self.auth = auth

        self.__states = {}
        self.__states_lock = asyncio.Lock()
        self.__update_tasks = []

    @classmethod
    async def login(cls, api_key: str, login: LoginDetails):
        session = create_session(api_key)
        auth = AuthManager(session, login)
        await auth.force_renew_token()
        return cls(session, auth)

    async def _request(self, method: str, url: str, **kwargs) -> JSONAny:
        try:
            headers = kwargs["headers"]
        except KeyError:
            headers = kwargs["headers"] = {}

        headers["Authorization"] = await self.auth.get_access_token()

        async with self.session.request(method, url, **kwargs) as resp:
            data = await resp.json()
            if resp.status != 200:
                raise APIError.from_response(resp, data)

        return data

    async def get_me(self) -> models.Me:
        data = await self._request("get", ME_URL)
        try:
            return models.Me.from_payload(data)
        except Exception:
            logger.exception("failed to construct Me from payload: %s", data)
            raise

    async def __diff_devices(self, devices: List[models.Device]) -> None:
        states = self.__states

        # remove outdated devices
        removed_sns = set(states.keys()) - set(
            device.serial_number for device in devices
        )
        for sn in removed_sns:
            state = states.pop(sn)
            self.dispatch_async("device_removed", state)
            await state._after_remove()

        # update and add new devices
        for info in devices:
            sn = info.serial_number
            try:
                state = states[sn]
            except KeyError:
                state = states[sn] = DeviceState._from_device(info)
                logger.info("found new state: %s", state)
                self.dispatch_async("device_added", state)
            else:
                await state._update(info)

    async def _update_states(self, devices: List[models.Device]) -> None:
        async with self.__states_lock:
            await self.__diff_devices(devices)

    async def __update_states_once(self) -> None:
        logger.debug("updating states")
        me = await self.get_me()
        await self._update_states(me.devices)

    async def __update_states_loop(self, interval: timedelta) -> None:
        interval_s = interval.total_seconds()
        while True:
            try:
                await self.__update_states_once()
            except Exception:
                logger.exception("states update failed")

            await asyncio.sleep(interval_s)

    @property
    def _auto_update_running(self) -> bool:
        return all(not t.done() for t in self.__update_tasks)

    def start_auto_update(self, update_interval: timedelta) -> None:
        if self._auto_update_running:
            raise RuntimeError("auto update already running")

        self.__update_tasks = [
            asyncio.create_task(self.__update_states_loop(update_interval)),
        ]

