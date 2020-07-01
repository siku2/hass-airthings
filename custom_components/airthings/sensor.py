import dataclasses
import logging
from typing import Any, Dict, Iterator, List, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_BATTERY,
    PRESSURE_MBAR,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from . import DOMAIN, KEY_API
from .airthings import AirthingsAPI, DeviceState, models

logger = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, _config_entry: ConfigEntry, add_entities
) -> bool:
    api: AirthingsAPI = hass.data[DOMAIN][KEY_API]

    async def on_device_added(device: DeviceState) -> None:
        logger.debug("setting up sensors for device: %s", device.serial_number)
        add_entities(create_sensors(device))

    api.add_listener("device_added", on_device_added)

    # just a little sanity check
    tracked_devices = await api.get_tracked_devices()
    if tracked_devices:
        logger.error(
            "sensor platform setup after API is already tracking devices: %s",
            tracked_devices,
        )

    return True


async def async_unload_entry(
    hass: HomeAssistantType, _config_entry: ConfigEntry
) -> bool:
    api: AirthingsAPI = hass.data[DOMAIN][KEY_API]
    api.remove_listeners("device_added")

    return True


class CommonSensor(Entity):
    _state: DeviceState
    _device_info: Dict[str, Any]

    def __init__(self, state: DeviceState, device_info: Dict[str, Any]) -> None:
        self._state = state
        self._device_info = device_info

        state.add_listener("updated", self._on_updated)
        state.add_listener("removed", self._on_removed)

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def name(self) -> str:
        return self._state.info.room_name

    @property
    def device_info(self) -> Dict[str, Any]:
        return self._device_info

    async def async_added_to_hass(self) -> None:
        await self._on_updated()

    async def _on_updated(self) -> None:
        self.async_schedule_update_ha_state()

    async def _on_removed(self) -> None:
        await self.async_remove()


@dataclasses.dataclass()
class SensorInfo:
    id: str
    name: str
    icon: Optional[str] = None
    unit_of_measurement: Optional[str] = None
    device_class: Optional[str] = None
    mult: float = 1.0


class AirthingsSensor(CommonSensor):
    _sensor: SensorInfo
    __current_sensor: Optional[models.Sensor]

    def __init__(
        self, state: DeviceState, device_info: Dict[str, Any], sensor: SensorInfo
    ) -> None:
        super().__init__(state, device_info)
        self._sensor = sensor
        self.__current_sensor = None

    @property
    def unique_id(self) -> Optional[str]:
        return f"{self._state.info.serial_number}-{self._sensor.id}"

    @property
    def name(self) -> str:
        return f"{super().name} {self._sensor.name}"

    @property
    def state(self) -> Optional[float]:
        sensor = self.__current_sensor
        if sensor is None:
            return None

        return round(self._sensor.mult * sensor.value, 2)

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        sensor = self.__current_sensor
        if sensor is None:
            return None

        return {
            "alert": "yes" if sensor.is_alert else "no",
            "thresholds": sensor.thresholds,
        }

    @property
    def device_class(self) -> Optional[str]:
        return self._sensor.device_class

    @property
    def unit_of_measurement(self) -> Optional[str]:
        return self._sensor.unit_of_measurement

    @property
    def icon(self) -> Optional[str]:
        return self._sensor.icon

    async def _on_updated(self) -> None:
        self.__current_sensor = self._state.get_sensor(self._sensor.id)
        await super()._on_updated()


_BASIC_SENSORS = (
    SensorInfo(
        "humidity",
        "Humidity",
        unit_of_measurement=UNIT_PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SensorInfo(
        "temp",
        "Temperature",
        unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
)
_RADON_SENSORS = (
    SensorInfo(
        "radonShortTermAvg",
        "Radon",
        icon="mdi:radioactive",
        unit_of_measurement="Bq/m3",
    ),
)

_MINI_PLUS_SENSORS = (
    SensorInfo(
        "voc",
        "VOC",
        icon="mdi:air-filter",
        unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
    ),
)

_PLUS_SENSORS = (
    SensorInfo(
        "pressure",
        "Pressure",
        unit_of_measurement=PRESSURE_MBAR,
        device_class=DEVICE_CLASS_PRESSURE,
        mult=1 / 100,
    ),
    SensorInfo(
        "co2",
        "CO2",
        icon="mdi:periodic-table-co2",
        unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
)


def _iter_sensor_infos(model_type: str) -> Iterator[SensorInfo]:
    yield from _BASIC_SENSORS
    if model_type != models.MODEL_TYPE_MINI:
        yield from _RADON_SENSORS

    if model_type in (models.MODEL_TYPE_MINI, models.MODEL_TYPE_PLUS):
        yield from _MINI_PLUS_SENSORS

    if model_type == models.MODEL_TYPE_PLUS:
        yield from _PLUS_SENSORS


class BatterySensor(CommonSensor):
    __battery_precentage: Optional[int]

    def __init__(self, state: DeviceState, device_info: Dict[str, Any]) -> None:
        super().__init__(state, device_info)
        self.__battery_precentage = None

    @property
    def unique_id(self) -> Optional[str]:
        return f"{self._state.info.serial_number}-battery"

    @property
    def name(self) -> str:
        return f"{super().name} Battery Level"

    @property
    def state(self) -> Optional[int]:
        return self.__battery_precentage

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        info = self._state.info
        return {
            "latest_sample": info.latest_sample,
            "signal_quality": info.signal_quality,
        }

    @property
    def device_class(self) -> Optional[str]:
        return DEVICE_CLASS_BATTERY

    @property
    def unit_of_measurement(self) -> Optional[str]:
        return UNIT_PERCENTAGE

    async def _on_updated(self) -> None:
        self.__battery_precentage = self._state.info.battery_percentage
        await super()._on_updated()


def create_sensors(device: DeviceState) -> List[AirthingsSensor]:
    sn = device.serial_number
    device_info = {
        "identifiers": {(DOMAIN, sn)},
        "name": device.info.room_name,
        "manufacturer": "Airthings AS",
        "model": device.info.model_name,
    }
    sensors = [
        AirthingsSensor(device, device_info, sensor)
        for sensor in _iter_sensor_infos(device.info.model_type)
    ]
    sensors.append(BatterySensor(device, device_info))
    return sensors

