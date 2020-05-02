import dataclasses
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, TypeVar

import aiohttp
import yarl

from .auth import AuthManagerABC
from .consts import ME_URL
from .errors import APIError
from .types import JSONAny, JSONObj

T = TypeVar("T")


def mut_map_elements(l: List[T], f: Callable[[T], Any]) -> None:
    for i, el in enumerate(l):
        l[i] = f(el)


def mut_map_keys(d: Dict[str, Any], **kmap: str) -> None:
    for new, old in kmap.items():
        d[new] = d.pop(old)


def mut_map_values(d: Dict[str, T], **vmap: Callable[[T], Any]) -> None:
    for key, f in vmap.items():
        d[key] = f(d[key])


@dataclasses.dataclass()
class DefaultNotifications:
    radon_short_term_avg: List[str]
    radon_long_term_avg: List[str]
    temp: List[str]
    humidity: List[str]
    co2: List[str]
    voc: List[str]
    pressure: List[str]
    light: List[str]
    battery_percentage: List[str]
    orientation: List[str]
    pm3015: List[str]

    @classmethod
    def from_json_obj(cls, obj: JSONObj):
        mut_map_keys(obj,
                     radon_short_term_avg="radonShortTermAvg",
                     radon_long_term_avg="radonLongTermAvg",
                     battery_percentage="batteryPercentage",
                     )
        return cls(**obj)


"""
    {"serialNumber": "2930008125",
     "disabledDefaultNotifications": {
         "radonShortTermAvg": ["high"], "temp": ["high"]},
     "customNotifications": [
         {"id": "63ed1ba8-0ba5-47fe-88ef-c18c914d7de4",
          "userId": "64b5b157-572a-44bc-a61b-b9ee541fa2cc",
          "serialNumber": "2930008125",
          "sensorType": "radonShortTermAvg",
          "thresholdLevel": "high", "value": 300.0,
          "unit": "bq"}]},
    {"serialNumber": "2900135175",
     "disabledDefaultNotifications": {
         "radonShortTermAvg": ["high"],
         "temp": ["low"]},
     "customNotifications": [{
         "id": "69e87dc1-5195-4f62-a704-94522f59b7e3",
         "userId": "64b5b157-572a-44bc-a61b-b9ee541fa2cc",
         "serialNumber": "2900135175",
         "sensorType": "radonShortTermAvg",
         "thresholdLevel": "high",
         "value": 300.0,
         "unit": "bq"}]},
    {"serialNumber": "2930008567",
     "disabledDefaultNotifications": {
         "radonShortTermAvg": ["high"], "temp": ["high"]},
     "customNotifications": [
         {"id": "a0662cd4-9149-422f-b7ff-635a169ba56d",
          "userId": "64b5b157-572a-44bc-a61b-b9ee541fa2cc",
          "serialNumber": "2930008567",
          "sensorType": "radonShortTermAvg",
          "thresholdLevel": "high", "value": 300.0,
          "unit": "bq"}]},
    {"serialNumber": "2930007093",
     "disabledDefaultNotifications": {
         "radonShortTermAvg": ["high"],
         "temp": ["low"]},
     "customNotifications": [{
         "id": "d4ea38bc-8dac-4591-94ed-7601f0e32491",
         "userId": "64b5b157-572a-44bc-a61b-b9ee541fa2cc",
         "serialNumber": "2930007093",
         "sensorType": "radonShortTermAvg",
         "thresholdLevel": "high",
         "value": 300.0,
         "unit": "bq"}]},
    {"serialNumber": "2930028641",
     "disabledDefaultNotifications": {
         "humidity": ["high", "low"],
         "radonShortTermAvg": ["high"],
         "temp": ["high", "low"]}, "customNotifications": [
        {"id": "e16f275b-3b67-4cd9-905a-93ed7f9d43c8",
         "userId": "64b5b157-572a-44bc-a61b-b9ee541fa2cc",
         "serialNumber": "2930028641",
         "sensorType": "radonShortTermAvg",
         "thresholdLevel": "high", "value": 300.0,
         "unit": "bq"}]},
    {"serialNumber": "2900135868",
     "disabledDefaultNotifications": {
         "radonShortTermAvg": ["high"]},
     "customNotifications": [{
         "id": "edfd9c2d-f10e-439a-b3ad-a842412cf3c3",
         "userId": "64b5b157-572a-44bc-a61b-b9ee541fa2cc",
         "serialNumber": "2900135868",
         "sensorType": "radonShortTermAvg",
         "thresholdLevel": "high",
         "value": 300.0,
         "unit": "bq"}]}
"""

"""
{
     "radonShortTermAvg": {"defaultHigh": 100, "defaultLow": 50,
                           "minSelectableValue": 0,
                           "maxSelectableValue": 2000, "unit": "bq"},
     "radonLongTermAvg": {"defaultHigh": 100, "defaultLow": 50,
                          "minSelectableValue": 0,
                          "maxSelectableValue": 2000, "unit": "bq"},
     "temp": {"defaultHigh": 22, "defaultLow": 19,
              "minSelectableValue": -10, "maxSelectableValue": 60,
              "unit": "c"},
     "humidity": {"defaultHigh": 60, "defaultLow": 30,
                  "minSelectableValue": 0, "maxSelectableValue": 100,
                  "unit": "pct"},
     "co2": {"defaultHigh": 800, "defaultLow": 500,
             "minSelectableValue": 350, "maxSelectableValue": 3000,
             "unit": "ppm"},
     "voc": {"defaultHigh": 2000, "defaultLow": 1500,
             "minSelectableValue": 0, "maxSelectableValue": 2000,
             "unit": "ppb"},
     "pressure": {"defaultHigh": 1000, "defaultLow": 1000,
                  "minSelectableValue": 900, "maxSelectableValue": 1100,
                  "unit": "mbar"},
     "light": {"defaultHigh": 100, "defaultLow": 0,
               "minSelectableValue": 0, "maxSelectableValue": 100,
               "unit": "pct"},
     "batteryPercentage": {"defaultHigh": 1000, "defaultLow": 11,
                           "minSelectableValue": 0,
                           "maxSelectableValue": 100, "unit": "pct"},
     "orientation": {"defaultHigh": 180, "defaultLow": 0,
                     "minSelectableValue": 0, "maxSelectableValue": 180,
                     "unit": "deg"}}
"""


@dataclasses.dataclass()
class Notifications:
    settings: List[JSONObj]
    thresholds: JSONObj
    default_notifications: DefaultNotifications

    @classmethod
    def from_json_obj(cls, obj: JSONObj):
        mut_map_keys(obj,
                     default_notifications="defaultNotifications",
                     )
        return cls(**obj)


@dataclasses.dataclass()
class Group:
    id: str
    group_name: str
    genesis: bool
    role: str
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime
    display_subscription: bool

    @classmethod
    def from_json_obj(cls, obj: JSONObj):
        mut_map_keys(obj,
                     group_name="groupName",
                     created_by_user_id="createdByUserId",
                     created_at="createdAt",
                     updated_at="updatedAt",
                     display_subscription="displaySubscription",
                     )
        mut_map_values(obj,
                       created_at=datetime.fromisoformat,
                       updated_at=datetime.fromisoformat,
                       )
        return cls(**obj)


@dataclasses.dataclass()
class Me:
    name: str
    email: str
    date_format: str
    measurement_unit: str
    is_pro_user: bool
    notifications: Notifications
    rf_region: str
    is_demo_user: bool
    groups: List[Group]
    language: str
    intercom_user_hash: str
    user_id: uuid.UUID

    @classmethod
    def from_json_obj(cls, obj: JSONObj):
        mut_map_keys(obj,
                     date_format="dateFormat",
                     measurement_unit="measurementUnit",
                     is_pro_user="isProUser",
                     rf_region="rfRegion",
                     is_demo_user="isDemoUser",
                     intercom_user_hash="intercomUserHash",
                     user_id="userId",
                     )
        mut_map_values(obj,
                       notifications=Notifications.from_json_obj,
                       user_id=uuid.UUID)
        mut_map_elements(obj["groups"], Group.from_json_obj)

        return cls(**obj)


class WebAPI:
    session: aiohttp.ClientSession
    auth_manager: AuthManagerABC

    def __init__(self, session: aiohttp.ClientSession, auth_manager: AuthManagerABC) -> None:
        self.session = session
        self.auth_manager = auth_manager

    async def _request(self, method: str, url: yarl.URL, headers: dict = None, **kwargs) -> JSONAny:
        if headers is None:
            headers = {}

        headers["Authorization"] = await self.auth_manager.get_access_token()

        async with self.session.request(method, url, headers=headers, **kwargs) as resp:
            data = await resp.json()
            if resp.status != 200:
                raise APIError.from_response(resp, data)

        return data

    async def me(self) -> Me:
        data = await self._request("get", ME_URL)
        return Me.from_json_obj(data)
