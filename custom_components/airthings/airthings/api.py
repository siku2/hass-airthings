import asyncio
import dataclasses
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterator, List, Optional, Tuple

import aiohttp

from .auth import AuthManager, LoginDetails
from .consts import LATEST_SAMPLES_URL_TEMPLATE, SERIAL_NUMBERS_URL
from .errors import APIError
from .event_system import EventSystem
from .types import JSONAny, JSONObj

__all__ = ["Sensor", "SensorValue", "Sample",
           "DeviceInfo", "DeviceState",
           "AirthingsAPI",
           "MODEL_WAVE_SN", "MODEL_MINI_SN", "MODEL_PLUS_SN", "MODEL_SECOND_GEN_SN"]

logger = logging.getLogger(__name__)


def _parse_utc_dt(date_str: str) -> datetime:
    naive = datetime.fromisoformat(date_str)
    return naive.replace(tzinfo=timezone.utc)


def _format_utc_dt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(tzinfo=None).isoformat()


@dataclasses.dataclass()
class Sensor:
    type: str
    offset_type: int
    values: List[float]

    @classmethod
    def from_payload(cls, payload: JSONObj):
        return cls(
            type=payload["type"],
            offset_type=payload["offsetType"],
            values=payload["values"],
        )


@dataclasses.dataclass()
class SensorValue:
    __slots__ = ("value", "timestamp")

    value: float
    timestamp: datetime

    def __post_init__(self) -> None:
        self.value = round(self.value, 2)

    def __str__(self) -> str:
        return str(self.value)


@dataclasses.dataclass()
class Sample:
    segment_id: uuid.UUID
    segment_name: str
    room: str
    location: str
    lat: float
    lng: float
    last_record: datetime
    segment_start: datetime
    next_page_start: datetime
    more_data_available: bool
    offsets: List[List[timedelta]]
    ids_for_offsets: Optional[List[List[int]]]
    sensors: List[Sensor]

    @classmethod
    def from_payload(cls, payload: JSONObj):
        return cls(
            segment_id=uuid.UUID(payload["segmentId"]),
            segment_name=payload["segmentName"],
            room=payload["room"],
            location=payload["location"],
            lat=payload["lat"],
            lng=payload["lng"],
            last_record=_parse_utc_dt(payload["lastRecord"]),
            segment_start=_parse_utc_dt(payload["segmentStart"]),
            next_page_start=_parse_utc_dt(payload["nextPageStart"]),
            more_data_available=payload["moreDataAvailable"],
            offsets=[[timedelta(seconds=o) for o in t] for t in payload["offsets"]],
            ids_for_offsets=payload.get("idsForOffsets"),
            sensors=[Sensor.from_payload(p) for p in payload["sensors"]],
        )

    def timestamp_for_value_index(self, offset_type: int, index: int) -> datetime:
        offset = self.offsets[offset_type][index]
        return self.segment_start + offset

    def get_offset_index(self, offset_type: int, dt: datetime) -> int:
        td = dt - self.segment_start
        for i, offset in enumerate(self.offsets[offset_type]):
            if td <= offset:
                return i
        raise ValueError

    def iter_sensor_types(self) -> Iterator[str]:
        for sensor in self.sensors:
            yield sensor.type

    def get_sensor(self, type: str) -> Sensor:
        for sensor in self.sensors:
            if sensor.type == type:
                return sensor
        raise ValueError

    def iter_sensor_values(self, type: str, *, reverse=False) -> Iterator[SensorValue]:
        sensor = self.get_sensor(type)
        if reverse:
            value_iter = reversed(sensor.values)
        else:
            value_iter = iter(sensor.values)

        for i, v in enumerate(value_iter):
            timestamp = self.timestamp_for_value_index(sensor.offset_type, i)
            yield SensorValue(v, timestamp)


def create_session(api_key: str) -> aiohttp.ClientSession:
    return aiohttp.ClientSession(headers={
        "X-API-Key": api_key,
        "User-Agent": f"hass-airthings/1.0",
    })


MODEL_WAVE_SN = "2900"
MODEL_MINI_SN = "2920"
MODEL_PLUS_SN = "2930"
MODEL_SECOND_GEN_SN = "2950"

SN_TO_MODEL = {
    MODEL_WAVE_SN: "Wave",
    MODEL_MINI_SN: "Wave Mini",
    MODEL_PLUS_SN: "Wave Plus",
    MODEL_SECOND_GEN_SN: "Wave 2nd gen"
}


@dataclasses.dataclass()
class DeviceInfo:
    serial_number: str
    room: str
    location: str

    def __str__(self) -> str:
        return f"{self.room}#{self.serial_number}"

    @property
    def model_name(self) -> str:
        return SN_TO_MODEL[self.serial_number[:4]]

    def _update_from_sample(self, sample: Sample) -> None:
        self.room = sample.room
        self.location = sample.location

    @classmethod
    def from_sample(cls, sn: str, sample: Sample):
        return cls(sn, sample.room, sample.location)


class DeviceState(EventSystem):
    info: DeviceInfo
    values: Dict[str, SensorValue]

    _api: "AirthingsAPI"
    _next_page_start: datetime

    def __str__(self) -> str:
        values_str = ",".join(f"{k}={v}" for k, v in self.values.items())
        return f"{self.info}: {values_str}"

    @classmethod
    def from_sample(cls, api: "AirthingsAPI", sn: str, sample: Sample):
        self = cls()
        self.info = DeviceInfo.from_sample(sn, sample)
        self.values = {}
        self._api = api
        self._update_from_sample(sample)
        return self

    @classmethod
    async def get(cls, api: "AirthingsAPI", sn: str):
        from_dt = datetime.now() - timedelta(days=1)
        sample = await api.get_latest_sample(sn, from_dt=from_dt)
        return cls.from_sample(api, sn, sample)

    def _update_from_sample(self, sample: Sample) -> None:
        self.info._update_from_sample(sample)
        self._next_page_start = sample.next_page_start

        for st in sample.iter_sensor_types():
            try:
                newest_value = next(sample.iter_sensor_values(st, reverse=True))
            except StopIteration:
                continue

            self.values[st] = newest_value

    async def update(self) -> bool:
        sample = await self._api.get_latest_sample(self.info.serial_number, from_dt=self._next_page_start)
        if sample.last_record <= self._next_page_start:
            return False

        self._update_from_sample(sample)
        self.dispatch_async("updated")


class AirthingsAPI(EventSystem):
    session: aiohttp.ClientSession
    auth: AuthManager

    __states: Dict[str, DeviceState]
    __states_lock: asyncio.Lock

    def __init__(self, session: aiohttp.ClientSession, auth: AuthManager) -> None:
        super().__init__()

        self.session = session
        self.auth = auth

        self.__states = {}
        self.__states_lock = asyncio.Lock()

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

    async def get_serial_numbers(self) -> List[str]:
        data = await self._request("get", SERIAL_NUMBERS_URL)
        try:
            return data["serialNumbers"]
        except KeyError:
            return []

    async def get_latest_sample(self, sn: str, *,
                                include_ids: Optional[bool] = True,
                                from_dt: datetime = None,
                                to_dt: datetime = None) -> Sample:
        params = {}
        if include_ids is not None:
            params["includeIds"] = "true" if include_ids else "false"
        if from_dt is not None:
            params["from"] = _format_utc_dt(from_dt)
        if to_dt is not None:
            params["to"] = _format_utc_dt(to_dt)

        data = await self._request("get", LATEST_SAMPLES_URL_TEMPLATE.format(sn=sn), params=params)
        try:
            return Sample.from_payload(data)
        except Exception:
            logger.exception("failed to construct sample from payload: %s", data)
            raise

    async def get_state(self, sn: str) -> DeviceState:
        update = False
        async with self.__states_lock:
            try:
                v = self.__states[sn]
                update = True
            except KeyError:
                v = self.__states[sn] = await DeviceState.get(self, sn)

        if update:
            await v.update()

        return v

    async def __update_serial_numbers_once(self) -> None:
        logger.debug("updating serial numbers")
        sns_now = set(await self.get_serial_numbers())
        sns_before = set(self.__states.keys())

        added_sns = sns_now - sns_before
        for sn in added_sns:
            state = await self.get_state(sn)
            logger.info("found new state: %s", state)
            self.dispatch_async("device_added", state)

        removed_sns = sns_before - sns_now
        if not removed_sns:
            return

        async with self.__states_lock:
            for sn in removed_sns:
                state = self.__states.pop(sn)
                self.dispatch_async("device_removed", state)
                state.dispatch_async("removed")

    async def __update_serial_numbers_loop(self, interval: timedelta) -> None:
        interval_s = interval.total_seconds()
        while True:
            try:
                await self.__update_serial_numbers_once()
            except Exception:
                logger.exception("serial numbers update failed")

            await asyncio.sleep(interval_s)

    async def __update_states_once(self) -> None:
        logger.debug("updating states")
        for state in self.__states.values():
            await state.update()

    async def __update_states_loop(self, interval: timedelta) -> None:
        interval_s = interval.total_seconds()
        while True:
            try:
                await self.__update_states_once()
            except Exception:
                logger.exception("states update failed")

            await asyncio.sleep(interval_s)

    __update_tasks: Tuple[Optional[asyncio.Task], Optional[asyncio.Task]] = (None, None)

    @property
    def _auto_update_running(self) -> bool:
        return all(t is not None and not t.done() for t in self.__update_tasks)

    def start_auto_update(self, update_interval: timedelta, search_interval: timedelta) -> None:
        if self._auto_update_running:
            raise RuntimeError("auto update already running")

        self.__update_tasks = (
            asyncio.create_task(self.__update_serial_numbers_loop(search_interval)),
            asyncio.create_task(self.__update_states_loop(update_interval))
        )
