"""Config flow per HomeMind AI — wizard di configurazione HA UI."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_GEMINI_API_KEY,
    CONF_GEMINI_MODEL,
    CONF_TELEGRAM_TOKEN,
    CONF_TELEGRAM_CHAT_ID,
    CONF_CAMERAS,
    CONF_NIGHT_START,
    CONF_NIGHT_END,
    CONF_MORNING_REPORT_HOUR,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_NIGHT_START,
    DEFAULT_NIGHT_END,
    DEFAULT_MORNING_REPORT_HOUR,
)


class HomeMindConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Wizard di configurazione HomeMind AI."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Step 1 — Gemini API."""
        errors = {}

        if user_input is not None:
            if not user_input.get(CONF_GEMINI_API_KEY):
                errors[CONF_GEMINI_API_KEY] = "api_key_required"
            else:
                return self.async_create_entry(
                    title="HomeMind AI",
                    data=user_input,
                )

        schema = vol.Schema({
            vol.Required(CONF_GEMINI_API_KEY): str,
            vol.Optional(CONF_GEMINI_MODEL, default=DEFAULT_GEMINI_MODEL): selector.SelectSelector(
                selector.SelectSelectorConfig(options=[
                    "gemini-2.0-flash",
                    "gemini-1.5-flash",
                    "gemini-1.5-pro",
                ])
            ),
            vol.Optional(CONF_TELEGRAM_TOKEN, default=""): str,
            vol.Optional(CONF_TELEGRAM_CHAT_ID, default=""): str,
            vol.Optional(CONF_NIGHT_START, default=DEFAULT_NIGHT_START): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=23)
            ),
            vol.Optional(CONF_NIGHT_END, default=DEFAULT_NIGHT_END): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=23)
            ),
            vol.Optional(CONF_MORNING_REPORT_HOUR, default=DEFAULT_MORNING_REPORT_HOUR): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=23)
            ),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={"docs_url": "https://github.com/francescogalli-design/homemind-ai"},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return HomeMindOptionsFlow(config_entry)


class HomeMindOptionsFlow(config_entries.OptionsFlow):
    """Opzioni modificabili dopo l'installazione."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.data
        schema = vol.Schema({
            vol.Optional(CONF_NIGHT_START, default=current.get(CONF_NIGHT_START, DEFAULT_NIGHT_START)): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=23)
            ),
            vol.Optional(CONF_NIGHT_END, default=current.get(CONF_NIGHT_END, DEFAULT_NIGHT_END)): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=23)
            ),
            vol.Optional(CONF_MORNING_REPORT_HOUR, default=current.get(CONF_MORNING_REPORT_HOUR, DEFAULT_MORNING_REPORT_HOUR)): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=23)
            ),
            vol.Optional(CONF_TELEGRAM_TOKEN, default=current.get(CONF_TELEGRAM_TOKEN, "")): str,
            vol.Optional(CONF_TELEGRAM_CHAT_ID, default=current.get(CONF_TELEGRAM_CHAT_ID, "")): str,
        })

        return self.async_show_form(step_id="init", data_schema=schema)
