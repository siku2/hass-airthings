import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .airthings import AirthingsAPI, LoginDetails
from .const import DOMAIN

logger = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    try:
        api = await AirthingsAPI.login(entry.data[CONF_API_KEY],
                                       LoginDetails(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD]))
    except Exception:
        logger.exception("login failed")
        return False

    states = await api.get_states()
    logger.info("STATES: %s", list(map(str, states)))

    return True


async def async_unload_entry(hass: HomeAssistantType, config_entry: ConfigEntry) -> bool:
    return True
