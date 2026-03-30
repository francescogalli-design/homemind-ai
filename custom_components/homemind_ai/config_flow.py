"""Config flow per HomeMind AI — wizard a 2 step con selezione telecamere."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_CAMERAS,
    CONF_GEMINI_API_KEY,
    CONF_GEMINI_MODEL,
    CONF_MORNING_REPORT_HOUR,
    CONF_MOTION_SENSORS,
    CONF_NIGHT_END,
    CONF_NIGHT_START,
    CONF_TELEGRAM_CHAT_ID,
    CONF_TELEGRAM_TOKEN,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_MORNING_REPORT_HOUR,
    DEFAULT_NIGHT_END,
    DEFAULT_NIGHT_START,
    DOMAIN,
    GEMINI_MODELS,
)


# ------------------------------------------------------------------ #
# Step 1 — API e Telegram
# ------------------------------------------------------------------ #

_STEP1_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_GEMINI_API_KEY): str,
        vol.Optional(CONF_GEMINI_MODEL, default=DEFAULT_GEMINI_MODEL): vol.In(GEMINI_MODELS),
        vol.Optional(CONF_TELEGRAM_TOKEN, default=""): str,
        vol.Optional(CONF_TELEGRAM_CHAT_ID, default=""): str,
    }
)

# ------------------------------------------------------------------ #
# Step 2 — Telecamere, sensori e orari
# ------------------------------------------------------------------ #

def _step2_schema(current_cameras: list | None = None, current_sensors: list | None = None) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_CAMERAS, default=current_cameras or []): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="camera", multiple=True)
            ),
            vol.Optional(CONF_MOTION_SENSORS, default=current_sensors or []): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)
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
    """Wizard di configurazione HomeMind AI in 2 step."""

    VERSION = 1

    def __init__(self) -> None:
        self._step1_data: dict = {}

    async def async_step_user(self, user_input=None):
        """Step 1 — Gemini API key e Telegram."""
        errors = {}

        if user_input is not None:
            api_key = user_input.get(CONF_GEMINI_API_KEY, "").strip()
            if not api_key:
                errors[CONF_GEMINI_API_KEY] = "api_key_required"
            else:
                self._step1_data = user_input
                return await self.async_step_cameras()

        return self.async_show_form(
            step_id="user",
            data_schema=_STEP1_SCHEMA,
            errors=errors,
        )

    async def async_step_cameras(self, user_input=None):
        """Step 2 — Selezione telecamere, sensori e orari."""
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
        # In HA 2024.x+ config_entry viene passato automaticamente alla flow
        return HomeMindOptionsFlow()


class HomeMindOptionsFlow(config_entries.OptionsFlow):
    """Opzioni modificabili dopo l'installazione (accesso dal tasto Configura)."""

    # NON definire __init__ con config_entry: in HA 2024.x+ è impostato
    # automaticamente dalla base class tramite self.config_entry.

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Merge data + options attuali (self.config_entry impostato da HA)
        cur = {**self.config_entry.data, **self.config_entry.options}

        schema = vol.Schema(
            {
                vol.Optional(CONF_GEMINI_API_KEY, default=cur.get(CONF_GEMINI_API_KEY, "")): str,
                vol.Optional(CONF_GEMINI_MODEL, default=cur.get(CONF_GEMINI_MODEL, DEFAULT_GEMINI_MODEL)): vol.In(GEMINI_MODELS),
                vol.Optional(CONF_TELEGRAM_TOKEN, default=cur.get(CONF_TELEGRAM_TOKEN, "")): str,
                vol.Optional(CONF_TELEGRAM_CHAT_ID, default=cur.get(CONF_TELEGRAM_CHAT_ID, "")): str,
                vol.Optional(CONF_CAMERAS, default=cur.get(CONF_CAMERAS, [])): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="camera", multiple=True)
                ),
                vol.Optional(CONF_MOTION_SENSORS, default=cur.get(CONF_MOTION_SENSORS, [])): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)
                ),
                vol.Optional(CONF_NIGHT_START, default=cur.get(CONF_NIGHT_START, DEFAULT_NIGHT_START)): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=23)
                ),
                vol.Optional(CONF_NIGHT_END, default=cur.get(CONF_NIGHT_END, DEFAULT_NIGHT_END)): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=23)
                ),
                vol.Optional(CONF_MORNING_REPORT_HOUR, default=cur.get(CONF_MORNING_REPORT_HOUR, DEFAULT_MORNING_REPORT_HOUR)): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=23)
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
