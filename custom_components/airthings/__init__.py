import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .airthings import AirthingsAPI, LoginDetails
from .const import DOMAIN, KEY_API, PLATFORMS

logger = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistantType, _config: ConfigType) -> bool:
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    try:
        api = await AirthingsAPI.login(
            entry.data[CONF_API_KEY],
            LoginDetails(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD]),
        )
    except Exception:
        logger.exception("login failed")
        return False

    hass.data[DOMAIN][KEY_API] = api

    for platform in PLATFORMS:
        hass.async_add_job(
            hass.config_entries.async_forward_entry_setup, entry, platform
        )

    logger.info("starting auto update")
    api.start_auto_update(timedelta(minutes=10))

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    for platform in PLATFORMS:
        await hass.config_entries.async_forward_entry_unload(entry, platform)

    return True
