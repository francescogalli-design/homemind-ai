"""Config flow per HomeMind AI — wizard a 2 step con selezione provider AI."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    AI_PROVIDER_GEMINI,
    AI_PROVIDER_HA_GEMINI,
    AI_PROVIDER_OLLAMA,
    AI_PROVIDERS,
    CONF_AI_PROVIDER,
    CONF_ALPR_ENTITIES,
    CONF_CAMERAS,
    CONF_GEMINI_API_KEY,
    CONF_GEMINI_MODEL,
    CONF_MORNING_REPORT_HOUR,
    CONF_MOTION_SENSORS,
    CONF_NIGHT_END,
    CONF_NIGHT_START,
    CONF_OLLAMA_HOST,
    CONF_OLLAMA_MODEL,
    CONF_TELEGRAM_CHAT_ID,
    CONF_TELEGRAM_TOKEN,
    CONF_VEHICLE_SENSORS,
    DEFAULT_AI_PROVIDER,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_MORNING_REPORT_HOUR,
    DEFAULT_NIGHT_END,
    DEFAULT_NIGHT_START,
    DEFAULT_OLLAMA_HOST,
    DEFAULT_OLLAMA_MODEL,
    DOMAIN,
    GEMINI_MODELS,
)


def _step1_schema(defaults: dict | None = None) -> vol.Schema:
    d = defaults or {}
    provider = d.get(CONF_AI_PROVIDER, DEFAULT_AI_PROVIDER)
    return vol.Schema(
        {
            # ---- Provider AI ----
            vol.Optional(CONF_AI_PROVIDER, default=provider): vol.In(AI_PROVIDERS),

            # ---- Gemini (usato solo se provider=gemini) ----
            vol.Optional(CONF_GEMINI_API_KEY, default=d.get(CONF_GEMINI_API_KEY, "")): str,
            vol.Optional(CONF_GEMINI_MODEL, default=d.get(CONF_GEMINI_MODEL, DEFAULT_GEMINI_MODEL)): vol.In(GEMINI_MODELS),

            # ---- Ollama (usato solo se provider=ollama) ----
            vol.Optional(CONF_OLLAMA_HOST, default=d.get(CONF_OLLAMA_HOST, DEFAULT_OLLAMA_HOST)): str,
            vol.Optional(CONF_OLLAMA_MODEL, default=d.get(CONF_OLLAMA_MODEL, DEFAULT_OLLAMA_MODEL)): str,

            # ---- Telegram (sempre opzionale) ----
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
            # ALPR — riconoscimento targhe
            vol.Optional(CONF_VEHICLE_SENSORS, default=[]): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)
            ),
            vol.Optional(CONF_ALPR_ENTITIES, default=[]): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="image_processing", multiple=True)
            ),
            # Orari
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
        """Step 1 — Provider AI, credenziali e Telegram."""
        errors = {}

        if user_input is not None:
            provider = user_input.get(CONF_AI_PROVIDER, DEFAULT_AI_PROVIDER)
            api_key = user_input.get(CONF_GEMINI_API_KEY, "").strip()
            ollama_host = user_input.get(CONF_OLLAMA_HOST, "").strip()

            if provider == AI_PROVIDER_GEMINI and not api_key:
                errors[CONF_GEMINI_API_KEY] = "api_key_required"
            elif provider == AI_PROVIDER_OLLAMA and not ollama_host:
                errors[CONF_OLLAMA_HOST] = "ollama_host_required"
            # ha_gemini non richiede API key (usa integrazione HA esistente)
            else:
                # Salva la chiave pulita (no spazi/newline)
                user_input[CONF_GEMINI_API_KEY] = api_key
                user_input[CONF_OLLAMA_HOST] = ollama_host.rstrip("/")
                self._step1_data = user_input
                return await self.async_step_cameras()

        return self.async_show_form(
            step_id="user",
            data_schema=_step1_schema(),
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
        return HomeMindOptionsFlow()


class HomeMindOptionsFlow(config_entries.OptionsFlow):
    """Opzioni modificabili dopo l'installazione (accesso dal tasto Configura).

    IMPORTANTE: non definire __init__ con config_entry.
    In HA 2024.x+ self.config_entry è impostato automaticamente dalla base class.
    """

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            # Pulizia spazi API key e host
            if CONF_GEMINI_API_KEY in user_input:
                user_input[CONF_GEMINI_API_KEY] = user_input[CONF_GEMINI_API_KEY].strip()
            if CONF_OLLAMA_HOST in user_input:
                user_input[CONF_OLLAMA_HOST] = user_input[CONF_OLLAMA_HOST].strip().rstrip("/")
            return self.async_create_entry(title="", data=user_input)

        # self.config_entry è impostato automaticamente da HA
        cur = {**self.config_entry.data, **self.config_entry.options}

        schema = vol.Schema(
            {
                # ---- Provider AI ----
                vol.Optional(
                    CONF_AI_PROVIDER,
                    default=cur.get(CONF_AI_PROVIDER, DEFAULT_AI_PROVIDER),
                ): vol.In(AI_PROVIDERS),

                # ---- Gemini ----
                vol.Optional(
                    CONF_GEMINI_API_KEY,
                    default=cur.get(CONF_GEMINI_API_KEY, ""),
                ): str,
                vol.Optional(
                    CONF_GEMINI_MODEL,
                    default=cur.get(CONF_GEMINI_MODEL, DEFAULT_GEMINI_MODEL),
                ): vol.In(GEMINI_MODELS),

                # ---- Ollama ----
                vol.Optional(
                    CONF_OLLAMA_HOST,
                    default=cur.get(CONF_OLLAMA_HOST, DEFAULT_OLLAMA_HOST),
                ): str,
                vol.Optional(
                    CONF_OLLAMA_MODEL,
                    default=cur.get(CONF_OLLAMA_MODEL, DEFAULT_OLLAMA_MODEL),
                ): str,

                # ---- Telegram ----
                vol.Optional(
                    CONF_TELEGRAM_TOKEN,
                    default=cur.get(CONF_TELEGRAM_TOKEN, ""),
                ): str,
                vol.Optional(
                    CONF_TELEGRAM_CHAT_ID,
                    default=cur.get(CONF_TELEGRAM_CHAT_ID, ""),
                ): str,

                # ---- Telecamere ----
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

                # ---- ALPR (targhe) ----
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

                # ---- Orari ----
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
