"""Config flow per HomeMind AI v4 — solo Ollama, nessuna API key."""
from __future__ import annotations

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ALPR_ENTITIES,
    CONF_CAMERAS,
    CONF_MORNING_REPORT_HOUR,
    CONF_MOTION_SENSORS,
    CONF_NIGHT_END,
    CONF_NIGHT_START,
    CONF_OLLAMA_HOST,
    CONF_OLLAMA_MODEL,
    CONF_PERSON_ENTITY,
    CONF_TELEGRAM_CHAT_ID,
    CONF_TELEGRAM_TOKEN,
    CONF_VEHICLE_SENSORS,
    DEFAULT_MORNING_REPORT_HOUR,
    DEFAULT_NIGHT_END,
    DEFAULT_NIGHT_START,
    DEFAULT_OLLAMA_HOST,
    DEFAULT_OLLAMA_MODEL,
    DOMAIN,
    OLLAMA_MODELS,
)


def _step1_schema(defaults: dict | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Optional(CONF_OLLAMA_HOST, default=d.get(CONF_OLLAMA_HOST, DEFAULT_OLLAMA_HOST)): str,
            vol.Optional(CONF_OLLAMA_MODEL, default=d.get(CONF_OLLAMA_MODEL, DEFAULT_OLLAMA_MODEL)): vol.In(OLLAMA_MODELS),
            vol.Optional(CONF_PERSON_ENTITY, default=d.get(CONF_PERSON_ENTITY, "")): str,
            vol.Optional(CONF_TELEGRAM_TOKEN, default=d.get(CONF_TELEGRAM_TOKEN, "")): str,
            vol.Optional(CONF_TELEGRAM_CHAT_ID, default=d.get(CONF_TELEGRAM_CHAT_ID, "")): str,
        }
    )


def _step2_schema(current_cameras: list | None = None, current_sensors: list | None = None) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_CAMERAS, default=current_cameras or []): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="camera", multiple=True)
            ),
            vol.Optional(CONF_MOTION_SENSORS, default=current_sensors or []): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)
            ),
            vol.Optional(CONF_VEHICLE_SENSORS, default=[]): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)
            ),
            vol.Optional(CONF_ALPR_ENTITIES, default=[]): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="image_processing", multiple=True)
            ),
            vol.Optional(CONF_NIGHT_START, default=DEFAULT_NIGHT_START): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=23)
            ),
            vol.Optional(CONF_NIGHT_END, default=DEFAULT_NIGHT_END): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=23)
            ),
            vol.Optional(CONF_MORNING_REPORT_HOUR, default=DEFAULT_MORNING_REPORT_HOUR): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=23)
            ),
        }
    )


class HomeMindConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Wizard configurazione HomeMind AI v4 — 2 step, solo Ollama."""

    VERSION = 4

    def __init__(self) -> None:
        self._step1_data: dict = {}

    async def async_step_user(self, user_input=None):
        """Step 1 — Ollama, persona, Telegram."""
        errors = {}

        if user_input is not None:
            ollama_host = user_input.get(CONF_OLLAMA_HOST, DEFAULT_OLLAMA_HOST).strip().rstrip("/")
            user_input[CONF_OLLAMA_HOST] = ollama_host

            # Valida connessione Ollama
            try:
                session = async_get_clientsession(self.hass)
                async with session.get(
                    f"{ollama_host}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status != 200:
                        errors["base"] = "ollama_connection_failed"
            except Exception:
                errors["base"] = "ollama_connection_failed"

            if not errors:
                self._step1_data = user_input
                return await self.async_step_cameras()

        return self.async_show_form(
            step_id="user",
            data_schema=_step1_schema(),
            errors=errors,
        )

    async def async_step_cameras(self, user_input=None):
        """Step 2 — Telecamere, sensori, ALPR, orari."""
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            full_data = {**self._step1_data, **user_input}
            return self.async_create_entry(title="HomeMind AI", data=full_data)

        return self.async_show_form(
            step_id="cameras",
            data_schema=_step2_schema(),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return HomeMindOptionsFlow()


class HomeMindOptionsFlow(config_entries.OptionsFlow):
    """Opzioni modificabili dopo l'installazione."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            if CONF_OLLAMA_HOST in user_input:
                user_input[CONF_OLLAMA_HOST] = user_input[CONF_OLLAMA_HOST].strip().rstrip("/")
            return self.async_create_entry(title="", data=user_input)

        cur = {**self.config_entry.data, **self.config_entry.options}

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_OLLAMA_HOST,
                    default=cur.get(CONF_OLLAMA_HOST, DEFAULT_OLLAMA_HOST),
                ): str,
                vol.Optional(
                    CONF_OLLAMA_MODEL,
                    default=cur.get(CONF_OLLAMA_MODEL, DEFAULT_OLLAMA_MODEL),
                ): vol.In(OLLAMA_MODELS),
                vol.Optional(
                    CONF_PERSON_ENTITY,
                    default=cur.get(CONF_PERSON_ENTITY, ""),
                ): str,
                vol.Optional(
                    CONF_TELEGRAM_TOKEN,
                    default=cur.get(CONF_TELEGRAM_TOKEN, ""),
                ): str,
                vol.Optional(
                    CONF_TELEGRAM_CHAT_ID,
                    default=cur.get(CONF_TELEGRAM_CHAT_ID, ""),
                ): str,
                vol.Optional(
                    CONF_CAMERAS,
                    default=cur.get(CONF_CAMERAS, []),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="camera", multiple=True)
                ),
                vol.Optional(
                    CONF_MOTION_SENSORS,
                    default=cur.get(CONF_MOTION_SENSORS, []),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)
                ),
                vol.Optional(
                    CONF_VEHICLE_SENSORS,
                    default=cur.get(CONF_VEHICLE_SENSORS, []),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)
                ),
                vol.Optional(
                    CONF_ALPR_ENTITIES,
                    default=cur.get(CONF_ALPR_ENTITIES, []),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="image_processing", multiple=True)
                ),
                vol.Optional(
                    CONF_NIGHT_START,
                    default=cur.get(CONF_NIGHT_START, DEFAULT_NIGHT_START),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
                vol.Optional(
                    CONF_NIGHT_END,
                    default=cur.get(CONF_NIGHT_END, DEFAULT_NIGHT_END),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
                vol.Optional(
                    CONF_MORNING_REPORT_HOUR,
                    default=cur.get(CONF_MORNING_REPORT_HOUR, DEFAULT_MORNING_REPORT_HOUR),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
