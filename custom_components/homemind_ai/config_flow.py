"""Multi-step config flow for HomeMind AI."""

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_CAMERAS,
    CONF_MOTION_SENSORS,
    CONF_NIGHT_END,
    CONF_NIGHT_START,
    CONF_OLLAMA_MODEL,
    CONF_OLLAMA_URL,
    CONF_REPORT_TIME,
    CONF_TELEGRAM_CHAT_ID,
    CONF_TELEGRAM_TOKEN,
    DEFAULT_NIGHT_END,
    DEFAULT_NIGHT_START,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_URL,
    DEFAULT_REPORT_TIME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

OLLAMA_MODELS = ["llava", "llava-phi3", "llava:13b", "moondream", "bakllava"]


class HomeMindConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """
    4-step config flow:
    1. user    — Ollama URL + model
    2. telegram — Telegram bot (optional)
    3. cameras  — camera entities + motion sensors
    4. schedule — night hours + morning report time
    """

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict = {}

    # ------------------------------------------------------------------
    # Step 1: Ollama setup
    # ------------------------------------------------------------------

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_telegram()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_OLLAMA_URL, default=DEFAULT_OLLAMA_URL): str,
                    vol.Required(CONF_OLLAMA_MODEL, default=DEFAULT_OLLAMA_MODEL): selector.selector(
                        {
                            "select": {
                                "options": OLLAMA_MODELS,
                                "custom_value": True,
                                "mode": "dropdown",
                            }
                        }
                    ),
                }
            ),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Step 2: Telegram (optional)
    # ------------------------------------------------------------------

    async def async_step_telegram(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_cameras()

        return self.async_show_form(
            step_id="telegram",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_TELEGRAM_TOKEN, default=""): str,
                    vol.Optional(CONF_TELEGRAM_CHAT_ID, default=""): str,
                }
            ),
        )

    # ------------------------------------------------------------------
    # Step 3: Camera & motion sensor selection
    # ------------------------------------------------------------------

    async def async_step_cameras(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_schedule()

        return self.async_show_form(
            step_id="cameras",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_CAMERAS, default=[]): selector.selector(
                        {"entity": {"domain": "camera", "multiple": True}}
                    ),
                    vol.Optional(CONF_MOTION_SENSORS, default=[]): selector.selector(
                        {
                            "entity": {
                                "domain": "binary_sensor",
                                "device_class": "motion",
                                "multiple": True,
                            }
                        }
                    ),
                }
            ),
        )

    # ------------------------------------------------------------------
    # Step 4: Schedule
    # ------------------------------------------------------------------

    async def async_step_schedule(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title="HomeMind AI", data=self._data)

        return self.async_show_form(
            step_id="schedule",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NIGHT_START, default=DEFAULT_NIGHT_START): selector.selector(
                        {"time": {}}
                    ),
                    vol.Required(CONF_NIGHT_END, default=DEFAULT_NIGHT_END): selector.selector(
                        {"time": {}}
                    ),
                    vol.Required(CONF_REPORT_TIME, default=DEFAULT_REPORT_TIME): selector.selector(
                        {"time": {}}
                    ),
                }
            ),
        )

    # ------------------------------------------------------------------
    # Options flow entry point
    # ------------------------------------------------------------------

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return HomeMindOptionsFlow()


# ---------------------------------------------------------------------------
# Options flow — lets user update all settings after initial setup
# ---------------------------------------------------------------------------

class HomeMindOptionsFlow(config_entries.OptionsFlow):
    """Allow updating HomeMind AI settings from the UI."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Merge data + existing options as defaults
        cfg = {**self.config_entry.data, **(self.config_entry.options or {})}

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_OLLAMA_URL, default=cfg.get(CONF_OLLAMA_URL, DEFAULT_OLLAMA_URL)): str,
                    vol.Required(CONF_OLLAMA_MODEL, default=cfg.get(CONF_OLLAMA_MODEL, DEFAULT_OLLAMA_MODEL)): selector.selector(
                        {"select": {"options": OLLAMA_MODELS, "custom_value": True, "mode": "dropdown"}}
                    ),
                    vol.Optional(CONF_TELEGRAM_TOKEN, default=cfg.get(CONF_TELEGRAM_TOKEN, "")): str,
                    vol.Optional(CONF_TELEGRAM_CHAT_ID, default=cfg.get(CONF_TELEGRAM_CHAT_ID, "")): str,
                    vol.Optional(CONF_CAMERAS, default=cfg.get(CONF_CAMERAS, [])): selector.selector(
                        {"entity": {"domain": "camera", "multiple": True}}
                    ),
                    vol.Optional(CONF_MOTION_SENSORS, default=cfg.get(CONF_MOTION_SENSORS, [])): selector.selector(
                        {"entity": {"domain": "binary_sensor", "device_class": "motion", "multiple": True}}
                    ),
                    vol.Required(CONF_NIGHT_START, default=cfg.get(CONF_NIGHT_START, DEFAULT_NIGHT_START)): selector.selector({"time": {}}),
                    vol.Required(CONF_NIGHT_END, default=cfg.get(CONF_NIGHT_END, DEFAULT_NIGHT_END)): selector.selector({"time": {}}),
                    vol.Required(CONF_REPORT_TIME, default=cfg.get(CONF_REPORT_TIME, DEFAULT_REPORT_TIME)): selector.selector({"time": {}}),
                }
            ),
        )
