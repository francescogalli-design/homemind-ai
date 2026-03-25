"""Config flow for HomeMind AI Assistant."""

import logging
from typing import Dict, Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_URL, CONF_TOKEN

from .const import DOMAIN, CONF_HA_URL, CONF_HA_TOKEN, CONF_TELEGRAM_TOKEN, CONF_TELEGRAM_CHAT_ID

_LOGGER = logging.getLogger(__name__)

class HomeMindConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HomeMind AI Assistant."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._data = {}

    async def async_step_user(
        self, user_input: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """Handle the initial step."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_telegram()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HA_URL): str,
                    vol.Required(CONF_HA_TOKEN): str,
                }
            ),
        )

    async def async_step_telegram(
        self, user_input: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """Handle the Telegram configuration step."""
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title="HomeMind AI Assistant", data=self._data)

        return self.async_show_form(
            step_id="telegram",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_TELEGRAM_TOKEN): str,
                    vol.Optional(CONF_TELEGRAM_CHAT_ID): str,
                }
            ),
        )
