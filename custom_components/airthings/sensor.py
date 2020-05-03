import dataclasses
import logging
from typing import Any, Dict, Iterator, List, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONCENTRATION_PARTS_PER_BILLION, CONCENTRATION_PARTS_PER_MILLION, DEVICE_CLASS_HUMIDITY, \
    DEVICE_CLASS_PRESSURE, DEVICE_CLASS_TEMPERATURE, PRESSURE_MBAR, TEMP_CELSIUS, UNIT_PERCENTAGE
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from . import DOMAIN, KEY_API
from .airthings import AirthingsAPI, DeviceState, MODEL_MINI_SN, MODEL_PLUS_SN

logger = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistantType, _config_entry: ConfigEntry, add_entities) -> bool:
    api: AirthingsAPI = hass.data[DOMAIN][KEY_API]

    async def on_device_added(device: DeviceState) -> None:
        logger.debug("setting up sensors for device: %s", device)
        add_entities(create_sensors(device))

    api.add_listener("device_added", on_device_added)

    return True


async def async_unload_entry(_hass: HomeAssistantType, _config_entry: ConfigEntry) -> bool:
    # TODO unsubscribe from device_added
    return True


@dataclasses.dataclass()
class SensorInfo:
    id: str
    name: str
    icon: Optional[str] = None
    unit_of_measurement: Optional[str] = None
    device_class: Optional[str] = None
    mult: float = 1.0


class AirthingsSensor(Entity):
    _state: DeviceState
    _sensor: SensorInfo
    _device_info: Dict[str, Any]

    def __init__(self, state: DeviceState, sensor: SensorInfo, device_info: Dict[str, Any]) -> None:
        self._state = state
        self._sensor = sensor
        self._device_info = device_info

        state.add_listener("updated", self.__on_updated)
        state.add_listener("removed", self.__on_removed)

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def unique_id(self) -> Optional[str]:
        return f"{self._state.info.serial_number}-{self._sensor.id}"

    @property
    def name(self) -> str:
        return f"{self._state.info.room} {self._sensor.name}"

    @property
    def state(self) -> Optional[float]:
        try:
            value = self._state.values[self._sensor.id]
        except KeyError:
            return None

        return self._sensor.mult * value.value

    @property
    def device_info(self) -> Dict[str, Any]:
        return self._device_info

    @property
    def device_class(self) -> Optional[str]:
        return self._sensor.device_class

    @property
    def unit_of_measurement(self) -> Optional[str]:
        return self._sensor.unit_of_measurement

    @property
    def icon(self) -> Optional[str]:
        return self._sensor.icon

    async def async_added_to_hass(self) -> None:
        self.async_schedule_update_ha_state()

    async def __on_updated(self) -> None:
        self.async_schedule_update_ha_state()

    async def __on_removed(self) -> None:
        await self.async_remove()


_BASIC_SENSORS = (
    SensorInfo("humidity", "Humidity", unit_of_measurement=UNIT_PERCENTAGE, device_class=DEVICE_CLASS_HUMIDITY),
    SensorInfo("temp", "Temperature", unit_of_measurement=TEMP_CELSIUS, device_class=DEVICE_CLASS_TEMPERATURE),
)
_RADON_SENSORS = (
    SensorInfo("radonShortTermAvg", "Radon", icon="mdi:radioactive", unit_of_measurement="Bq/m3"),
)

_MINI_PLUS_SENSORS = (
    SensorInfo("voc", "VOC", icon="mdi:air-filter", unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION),
)

_PLUS_SENSORS = (
    SensorInfo("pressure", "Pressure", unit_of_measurement=PRESSURE_MBAR, device_class=DEVICE_CLASS_PRESSURE,
               mult=1 / 100),
    SensorInfo("co2", "CO2", icon="mdi:periodic-table-co2", unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION),
)


def _iter_sensor_infos(sn: str) -> Iterator[SensorInfo]:
    sn = sn[:4]

    yield from _BASIC_SENSORS
    if sn != MODEL_MINI_SN:
        yield from _RADON_SENSORS

    if sn in (MODEL_MINI_SN, MODEL_PLUS_SN):
        yield from _MINI_PLUS_SENSORS

    if sn == MODEL_PLUS_SN:
        yield from _PLUS_SENSORS


def create_sensors(device: DeviceState) -> List[AirthingsSensor]:
    sn = device.info.serial_number
    device_info = {
        "identifiers": {(DOMAIN, sn)},
        "name": device.info.room,
        "manufacturer": "Airthings AS",
        "model": device.info.model_name
    }
    return [AirthingsSensor(device, info, device_info) for info in _iter_sensor_infos(sn)]
