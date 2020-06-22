import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_API_KEY, CONF_EMAIL, CONF_PASSWORD

from .airthings import AirthingsAPI, LoginDetails
from .const import DOMAIN, ERROR_LOGIN_FAILED

logger = logging.getLogger(__name__)


async def check_login(api_key: str, email: str, password: str) -> bool:
    try:
        await AirthingsAPI.login(api_key, LoginDetails(email, password))
    except Exception:
        logger.exception("login failed")
        return False

    return True


class AirthingsConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input: dict = None) -> dict:
        errors = {}
        if user_input is not None:
            if await check_login(
                user_input[CONF_API_KEY],
                user_input[CONF_EMAIL],
                user_input[CONF_PASSWORD],
            ):
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL], data=user_input,
                )
            else:
                errors["base"] = ERROR_LOGIN_FAILED

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
