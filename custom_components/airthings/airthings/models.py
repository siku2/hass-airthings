import dataclasses
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from .types import JSONObj

__all__ = [
    "Sensor",
    "Device",
    "Preferences",
    "Me",
]

logger = logging.getLogger(__name__)


def _parse_utc_dt(date_str: str) -> datetime:
    naive = datetime.fromisoformat(date_str)
    return naive.replace(tzinfo=timezone.utc)


@dataclasses.dataclass()
class Sensor:
    sensor_type: str
    value: float
    provided_unit: str
    preferred_unit: str
    is_alert: bool
    thresholds: List[float]

    @classmethod
    def from_payload(cls, payload: JSONObj):
        return cls(
            sensor_type=payload["type"],
            value=payload["value"],
            provided_unit=payload["providedUnit"],
            preferred_unit=payload["preferredUnit"],
            is_alter=payload["isAlert"],
            thresholds=payload["thresholds"],
        )


MODEL_TYPE_TO_NAME = {
    "wave": "Wave",
    "waveMini": "Wave Mini",
    "wavePlus": "Wave Plus",
    "wave2": "Wave 2nd gen",
}


@dataclasses.dataclass()
class Device:
    serial_number: str
    location_name: str
    location_id: uuid.UUID
    lat: float
    lng: float
    segment_id: uuid.UUID
    room_name: str
    segment_start: datetime
    latest_sample: datetime
    sensors: List[Sensor]
    battery_percentage: int
    rssi: Optional[int]
    model_type: str
    signal_quality: str
    relay_device: str

    @classmethod
    def from_payload(cls, payload: JSONObj):
        return cls(
            serial_number=payload["serialNumber"],
            location_name=payload["locationName"],
            location_id=uuid.UUID(payload["locationId"]),
            lat=payload["lat"],
            lng=payload["lng"],
            segment_id=uuid.UUID(payload["segmentId"]),
            room_name=payload["roomName"],
            segment_start=_parse_utc_dt(payload["segmentStart"]),
            latest_sample=_parse_utc_dt(payload["latestSample"]),
            sensors=[Sensor.from_payload(p) for p in payload["currentSensorValues"]],
            battery_percentage=payload["batteryPercentage"],
            rssi=payload.get("rssi"),
            model_type=payload["type"],
            signal_quality=payload["signalQuality"],
            relay_device=payload["relayDevice"],
        )

    @property
    def model_name(self) -> str:
        try:
            MODEL_TYPE_TO_NAME[self.model_type]
        except KeyError:
            return self.model_type.title()

    def get_sensor(self, sensor_type: str) -> Optional[Sensor]:
        for sensor in self.sensors:
            if sensor.sensor_type == sensor_type:
                return sensor
        return None


@dataclasses.dataclass()
class Preferences:
    date_format: str
    measurement_units: str
    temp_unit: str
    radon_unit: str
    rf_region: str
    pro_user: bool
    user_id: uuid.UUID
    language: str

    @classmethod
    def from_payload(cls, payload: JSONObj):
        return cls(
            date_format=payload["dateFormat"],
            measurement_units=payload["measurementUnits"],
            temp_unit=payload["tempUnit"],
            radon_unit=payload["radonUnit"],
            rf_region=payload["rfRegion"],
            pro_user=payload["proUser"],
            user_id=uuid.UUID(payload["userId"]),
            language=payload["language"],
        )


@dataclasses.dataclass()
class Me:
    name: str
    email: str
    preferences: Preferences
    devices: List[Device]

    @classmethod
    def from_payload(cls, payload: JSONObj):
        return cls(
            name=payload["name"],
            email=payload["email"],
            preferences=Preferences.from_payload(payload["preferences"]),
            devices=Preferences.from_payload(payload["devices"]),
        )

    def get_device(self, sn: str) -> Device:
        for device in self.devices:
            if device.serial_number == sn:
                return device
        raise ValueError
