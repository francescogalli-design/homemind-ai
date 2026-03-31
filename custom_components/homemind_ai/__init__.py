"""HomeMind AI — assistente AI proattivo per Home Assistant con Gemini Vision."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    AI_PROVIDER_GEMINI,
    AI_PROVIDER_HA_GEMINI,
    AI_PROVIDER_OLLAMA,
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
    GEMINI_FALLBACK_ORDER,
    PING_ENTITY,
    SERVICE_ANALYZE_CAMERA,
    SERVICE_ASK_AI,
    SERVICE_CLEAR_ALERTS,
    SERVICE_GENERATE_REPORT,
    THREAT_HIGH,
    THREAT_LOW,
    THREAT_MEDIUM,
)
from .gemini_vision import analyze_camera_image
from .telegram_bot import TelegramBot

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]

_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configura HomeMind AI da config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = HomeMindCoordinator(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    import voluptuous as vol
    from homeassistant.helpers import config_validation as cv

    async def handle_analyze_camera(call: ServiceCall) -> None:
        entity_id = call.data.get("entity_id", "").strip()
        if not entity_id:
            _LOGGER.warning("analyze_camera: entity_id mancante")
            return
        await coordinator.analyze_single_camera(entity_id)

    async def handle_generate_report(call: ServiceCall) -> None:
        await coordinator.send_morning_report(force=True)

    async def handle_clear_alerts(call: ServiceCall) -> None:
        coordinator.night_events.clear()
        coordinator.alerts_tonight = 0
        coordinator.last_alert = ""
        coordinator._notify_sensors()

    async def handle_ask_ai(call: ServiceCall) -> None:
        question = call.data.get("question", "").strip()
        if not question:
            return
        from .ha_context import build_home_context
        context = build_home_context(hass, cameras=await coordinator._get_cameras())
        session = async_get_clientsession(hass)

        if coordinator.ai_provider == AI_PROVIDER_HA_GEMINI:
            from .ha_gemini_provider import ask_ha_gemini
            answer = await ask_ha_gemini(hass, question, context)
        elif coordinator.ai_provider == AI_PROVIDER_OLLAMA:
            from .ollama_provider import ask_ollama
            answer = await ask_ollama(session, coordinator.ollama_host, coordinator._active_model, question, context)
        else:
            from .ai_provider import ask_gemini
            answer = await ask_gemini(
                session=session,
                api_key=coordinator.api_key,
                model=coordinator._active_model,
                question=question,
                home_context=context,
            )

        coordinator.last_ai_answer = answer[:255]
        coordinator._notify_sensors()
        if coordinator.bot:
            await coordinator.bot.send_message(answer)

    hass.services.async_register(
        DOMAIN,
        SERVICE_ANALYZE_CAMERA,
        handle_analyze_camera,
        schema=vol.Schema({vol.Required("entity_id"): cv.entity_id}),
    )
    hass.services.async_register(DOMAIN, SERVICE_GENERATE_REPORT, handle_generate_report)
    hass.services.async_register(DOMAIN, SERVICE_CLEAR_ALERTS, handle_clear_alerts)
    hass.services.async_register(
        DOMAIN,
        SERVICE_ASK_AI,
        handle_ask_ai,
        schema=vol.Schema({vol.Required("question"): str}),
    )

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    coordinator.start()
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator: HomeMindCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
    coordinator.stop()
    for service in (SERVICE_ANALYZE_CAMERA, SERVICE_GENERATE_REPORT, SERVICE_CLEAR_ALERTS, SERVICE_ASK_AI):
        hass.services.async_remove(DOMAIN, service)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class HomeMindCoordinator:
    """Coordinatore principale di HomeMind AI."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        cfg = {**entry.data, **entry.options}

        # Configurazione provider AI
        self.ai_provider: str = cfg.get(CONF_AI_PROVIDER, DEFAULT_AI_PROVIDER)
        self.api_key: str = cfg.get(CONF_GEMINI_API_KEY, "").strip()
        self.gemini_model: str = cfg.get(CONF_GEMINI_MODEL, DEFAULT_GEMINI_MODEL)
        self.ollama_host: str = cfg.get(CONF_OLLAMA_HOST, DEFAULT_OLLAMA_HOST).rstrip("/")
        self.ollama_model: str = cfg.get(CONF_OLLAMA_MODEL, DEFAULT_OLLAMA_MODEL)
        self.telegram_token: str = cfg.get(CONF_TELEGRAM_TOKEN, "")
        self.telegram_chat_id: str = str(cfg.get(CONF_TELEGRAM_CHAT_ID, "")).strip()
        self.configured_cameras: list[str] = cfg.get(CONF_CAMERAS, [])
        self.configured_motion_sensors: list[str] = cfg.get(CONF_MOTION_SENSORS, [])
        self.night_start: int = cfg.get(CONF_NIGHT_START, DEFAULT_NIGHT_START)
        self.night_end: int = cfg.get(CONF_NIGHT_END, DEFAULT_NIGHT_END)
        self.morning_report_hour: int = cfg.get(CONF_MORNING_REPORT_HOUR, DEFAULT_MORNING_REPORT_HOUR)

        # ALPR config
        self.alpr_entities: list[str] = cfg.get(CONF_ALPR_ENTITIES, [])
        self.vehicle_sensors: list[str] = cfg.get(CONF_VEHICLE_SENSORS, [])

        # Stato sensori
        self.ai_status: str = "starting"
        self.night_mode: str = "inactive"
        self.alerts_tonight: int = 0
        self.last_alert: str = ""
        self.last_report: str = ""
        self.last_ai_answer: str = ""

        # Debug sensori
        self.api_health: str = "testing"
        self.last_error: str = ""
        self.cameras_online: int = 0
        self.bot_status: str = "not_configured"
        self.internet_status: str = "unknown"

        # Modello effettivamente in uso (può essere fallback temporaneo)
        # gemini_model = scelta utente dal config (non cambia mai)
        # _active_model = quello realmente usato nelle chiamate API
        self._active_model: str = self.gemini_model

        # Sicurezza
        self.night_events: list[dict] = []
        self._last_alert_times: dict[str, float] = {}
        self._alert_cooldown: int = 300

        # Cross-camera correlation
        self._recent_motion_cams: list[tuple[str, float]] = []
        self._cross_camera_window: int = 120

        # Cache snapshot per invio foto bot
        self._last_snapshots: dict[str, bytes] = {}

        # Set camere non supportate (es. slideshow virtuali)
        self._unsupported_cameras: set[str] = set()

        # Digest: raccogli eventi, invio periodico consolidato
        self._pending_events: list[dict] = []
        self._last_digest_ts: float = 0
        self._digest_interval_night: int = 900   # 15 min
        self._digest_interval_day: int = 1800    # 30 min

        # ALPR state
        self.last_plate: str = ""
        self.plates_today: int = 0
        self._plate_manager = None  # type: PlateRecognitionManager | None

        self._sensor_callbacks: list = []
        self.bot: TelegramBot | None = None
        self._monitor_task: asyncio.Task | None = None

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        if self.telegram_token and self.telegram_chat_id:
            self.bot = TelegramBot(self)
            self.bot.start()
            self.bot_status = "connected"
        else:
            self.bot_status = "not_configured"

        self._monitor_task = self.hass.loop.create_task(self._startup_sequence())
        _LOGGER.info(
            "HomeMind AI: avvio — camere=%d, provider=%s, bot=%s",
            len(self.configured_cameras),
            self.ai_provider,
            self.bot_status,
        )

    def stop(self) -> None:
        if self._plate_manager:
            self._plate_manager.stop()
        if self.bot:
            self.bot.stop()
        if self._monitor_task:
            self._monitor_task.cancel()

    # ------------------------------------------------------------------ #
    # Startup: test API → avvia monitoraggio
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    # Internet connectivity
    # ------------------------------------------------------------------ #

    def _check_internet(self) -> bool | None:
        """
        Verifica connessione internet tramite binary_sensor.8_8_8_8 (ping Google DNS).
        Returns True=online, False=offline, None=entità non presente.
        """
        state = self.hass.states.get(PING_ENTITY)
        if state is None:
            return None  # Integrazione ping non configurata
        if state.state in ("unavailable", "unknown"):
            return None
        return state.state == "on"

    # ------------------------------------------------------------------ #
    # Startup sequence
    # ------------------------------------------------------------------ #

    async def _startup_sequence(self) -> None:
        """Testa API, inizializza ALPR, poi avvia il loop principale."""
        await asyncio.sleep(3)  # Attendi che HA sia pronto

        await self._init_model()

        # Inizializza ALPR se configurato
        if self.alpr_entities and self.vehicle_sensors:
            from .plate_recognition import PlateRecognitionManager
            self._plate_manager = PlateRecognitionManager(self)
            try:
                await self._plate_manager.async_init()
                self.plates_today = await self._plate_manager.get_detection_count_today()
                _LOGGER.info("HomeMind ALPR: attivo con %d entità", len(self.alpr_entities))
            except Exception as exc:
                _LOGGER.error("HomeMind ALPR: errore init — %s", exc)
                self._plate_manager = None

        self._notify_sensors()

        if self.bot:
            if self.ai_status == "online":
                cams = await self._get_cameras()
                provider_label = {
                    AI_PROVIDER_HA_GEMINI: "Google Gemini (integrazione HA)",
                    AI_PROVIDER_OLLAMA: f"Ollama — {self._active_model}",
                    AI_PROVIDER_GEMINI: self._active_model
                        + (f" _(fallback da {self.gemini_model})_" if self._active_model != self.gemini_model else ""),
                }.get(self.ai_provider, self._active_model)
                await self.bot.send_message(
                    f"*HomeMind AI* avviato\n\n"
                    f"AI  {provider_label}\n"
                    f"Telecamere  {len(cams) if cams else 'autodetect'}\n"
                    f"Notte  {self.night_start}:00 — {self.night_end}:00\n\n"
                    f"Scrivi /help per i comandi."
                )
            elif self.ai_status in ("error", "offline"):
                await self.bot.send_message(
                    f"*HomeMind AI* — avvio con errore\n\n"
                    f"{self.last_error}\n\n"
                    + ("Controlla la connessione internet di HA." if self.ai_status == "offline"
                       else "Verifica la Gemini API key in Impostazioni → Integrazioni → HomeMind AI → Configura.")
                )

        await self._monitor_loop()

    # ------------------------------------------------------------------ #
    # Gemini model validation (rispetta la scelta utente)
    # ------------------------------------------------------------------ #

    async def _test_gemini_model(self, model: str) -> tuple[bool, str]:
        """Richiesta minimale a Gemini per testare un modello. Returns (ok, message)."""
        session = async_get_clientsession(self.hass)
        url = _GEMINI_URL.format(model=model)
        payload = {
            "contents": [{"parts": [{"text": "Test."}]}],
            "generationConfig": {"maxOutputTokens": 5},
        }
        try:
            async with session.post(
                f"{url}?key={self.api_key}",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 200:
                    return True, f"Online — {model}"
                body = await resp.text()
                if resp.status == 404:
                    return False, f"Modello '{model}' non trovato (404) — potrebbe non essere disponibile con la tua API key"
                if resp.status == 400:
                    import json as _json
                    try:
                        err = _json.loads(body).get("error", {}).get("message", body[:100])
                    except Exception:
                        err = body[:100]
                    return False, f"Richiesta non valida: {err}"
                if resp.status == 401:
                    return False, "API key non valida (401) — verifica la chiave in Impostazioni"
                if resp.status == 403:
                    return False, "API key non autorizzata (403) — verifica i permessi su aistudio.google.com"
                if resp.status == 429:
                    return False, f"Limite richieste raggiunto (429) per {model}"
                return False, f"Errore HTTP {resp.status}"
        except asyncio.TimeoutError:
            return False, "Timeout — Gemini non raggiungibile"
        except Exception as exc:
            return False, f"Connessione fallita: {exc}"

    async def _init_model(self) -> None:
        """
        Valida il provider AI configurato.

        Provider supportati:
        - ha_gemini : usa l'integrazione HA google_generative_ai_conversation (consigliato)
        - gemini    : chiamate REST dirette (richiede API key AI Studio)
        - ollama    : Ollama locale (nessuna API key)
        """
        # ----------------------------------------------------------------
        # Provider: HA Gemini integration (usa l'integrazione già in HA)
        # ----------------------------------------------------------------
        if self.ai_provider == AI_PROVIDER_HA_GEMINI:
            from .ha_gemini_provider import test_ha_gemini
            ok, msg = await test_ha_gemini(self.hass)
            if ok:
                self._active_model = "ha_gemini"
                self.api_health = f"Online — Google Gemini (integrazione HA)"
                self.ai_status = "online"
                self.last_error = ""
                self.internet_status = "online"
                _LOGGER.info("HomeMind: provider HA Gemini OK — %s", msg)
            else:
                self._active_model = "ha_gemini"
                self.api_health = f"Errore — {msg[:80]}"
                self.ai_status = "error"
                self.last_error = msg
                _LOGGER.error("HomeMind: HA Gemini non disponibile — %s", msg)
            return

        # ----------------------------------------------------------------
        # Provider: Ollama locale
        # ----------------------------------------------------------------
        if self.ai_provider == AI_PROVIDER_OLLAMA:
            from .ollama_provider import test_ollama
            session = async_get_clientsession(self.hass)
            ok, msg = await test_ollama(session, self.ollama_host, self.ollama_model)
            if ok:
                self._active_model = self.ollama_model
                self.api_health = f"Online — Ollama ({self.ollama_model})"
                self.ai_status = "online"
                self.last_error = ""
                _LOGGER.info("HomeMind: Ollama OK — %s", msg)
            else:
                self._active_model = self.ollama_model
                self.api_health = f"Errore Ollama — {msg[:80]}"
                self.ai_status = "error"
                self.last_error = msg
                _LOGGER.error("HomeMind: Ollama non disponibile — %s", msg)
            return

        # ----------------------------------------------------------------
        # Provider: Gemini REST diretto
        # ----------------------------------------------------------------
        # Step 1: Check internet
        internet = self._check_internet()
        if internet is False:
            self.internet_status = "offline"
            self.api_health = "Nessuna connessione internet"
            self.ai_status = "offline"
            self.last_error = f"HA non ha accesso a internet ({PING_ENTITY} offline)"
            _LOGGER.error("HomeMind: %s", self.last_error)
            return
        self.internet_status = "online" if internet is True else "unknown"

        # Step 2: Testa il modello scelto dall'utente
        ok, msg = await self._test_gemini_model(self.gemini_model)
        if ok:
            self._active_model = self.gemini_model
            self.api_health = f"Online — {self.gemini_model}"
            self.ai_status = "online"
            self.last_error = ""
            _LOGGER.info("HomeMind: Gemini REST OK con modello '%s'", self.gemini_model)
            return

        # Step 3: Fallback temporaneo
        _LOGGER.warning("HomeMind: modello '%s' non disponibile — %s", self.gemini_model, msg)
        self.last_error = f"Modello '{self.gemini_model}': {msg}"

        fallbacks = [m for m in GEMINI_FALLBACK_ORDER if m != self.gemini_model]
        fallback_errors: list[str] = [f"{self.gemini_model}: {msg}"]

        for fallback in fallbacks:
            ok2, msg2 = await self._test_gemini_model(fallback)
            fallback_errors.append(f"{fallback}: {msg2}")
            if ok2:
                self._active_model = fallback
                self.api_health = f"Fallback — {fallback} (selezionato: {self.gemini_model})"
                self.ai_status = "online"
                self.last_error = (
                    f"Il modello '{self.gemini_model}' non è disponibile. "
                    f"Uso temporaneamente '{fallback}'. Motivo: {msg}"
                )
                _LOGGER.warning("HomeMind: fallback a '%s'", fallback)
                if self.bot:
                    self.hass.loop.create_task(
                        self.bot.send_message(
                            f"*Avviso modello AI*\n\n"
                            f"Il modello `{self.gemini_model}` non è disponibile.\n"
                            f"Uso temporaneamente `{fallback}`.\n\n"
                            f"Motivo: {msg}\n\n"
                            f"Cambia provider in Impostazioni → HomeMind AI → Configura."
                        )
                    )
                return

        # Tutti i modelli falliti
        self._active_model = self.gemini_model
        self.api_health = "Errore — nessun modello disponibile"
        self.ai_status = "error"
        detail = " | ".join(fallback_errors[:3])
        self.last_error = (
            f"Nessun modello Gemini disponibile. "
            f"Prova a usare il provider 'ha_gemini' se hai l'integrazione HA attiva. "
            f"Dettaglio: {detail}"
        )
        _LOGGER.error("HomeMind: nessun modello Gemini disponibile. %s", " | ".join(fallback_errors))

    # ------------------------------------------------------------------ #
    # Callbacks sensori
    # ------------------------------------------------------------------ #

    def register_sensor_callback(self, callback) -> None:
        self._sensor_callbacks.append(callback)

    def _notify_sensors(self) -> None:
        for cb in self._sensor_callbacks:
            try:
                cb()
            except Exception as exc:
                _LOGGER.debug("Sensor callback errore: %s", exc)

    def _set_error(self, msg: str) -> None:
        """Aggiorna last_error e notifica i sensori."""
        self.last_error = msg[:200]
        self.ai_status = "error"
        self._notify_sensors()
        _LOGGER.error("HomeMind: %s", msg)

    # ------------------------------------------------------------------ #
    # Camera discovery
    # ------------------------------------------------------------------ #

    async def _get_cameras(self) -> list[str]:
        if self.configured_cameras:
            return [
                eid for eid in self.configured_cameras
                if self.hass.states.get(eid) is not None
                and eid not in self._unsupported_cameras
            ]
        return [
            eid for eid in self.hass.states.async_entity_ids("camera")
            if eid not in self._unsupported_cameras
        ]

    async def _get_all_cameras_raw(self) -> list[str]:
        """Tutte le camere incluse quelle non supportate (per debug)."""
        if self.configured_cameras:
            return [eid for eid in self.configured_cameras if self.hass.states.get(eid)]
        return list(self.hass.states.async_entity_ids("camera"))

    async def _get_motion_sensors(self) -> list[str]:
        if self.configured_motion_sensors:
            return [eid for eid in self.configured_motion_sensors if self.hass.states.get(eid)]
        sensors = []
        for eid in self.hass.states.async_entity_ids("binary_sensor"):
            state = self.hass.states.get(eid)
            if state and state.attributes.get("device_class") in ("motion", "occupancy"):
                sensors.append(eid)
        return sensors

    # ------------------------------------------------------------------ #
    # Night / presence helpers
    # ------------------------------------------------------------------ #

    def _is_night_window(self) -> bool:
        h = datetime.now().hour
        if self.night_start > self.night_end:
            return h >= self.night_start or h < self.night_end
        return self.night_start <= h < self.night_end

    def _everyone_away(self) -> bool:
        person_ids = self.hass.states.async_entity_ids("person")
        if not person_ids:
            return False
        for eid in person_ids:
            state = self.hass.states.get(eid)
            if state and state.state in ("home", "Home", "casa"):
                return False
        return True

    # ------------------------------------------------------------------ #
    # Camera snapshot (con cache + rilevamento camere non supportate)
    # ------------------------------------------------------------------ #

    async def _get_camera_snapshot(self, entity_id: str) -> bytes | None:
        """
        Scarica snapshot dalla camera usando l'API nativa HA.

        - Salva in cache _last_snapshots per invio foto bot.
        - Marca come non supportata se ritorna errore persistente.
        """
        try:
            from homeassistant.components.camera import async_get_image
            image = await async_get_image(self.hass, entity_id, timeout=10)
            if image and image.content and len(image.content) > 500:
                self._last_snapshots[entity_id] = image.content
                return image.content
            # Immagine vuota o troppo piccola → camera non supportata
            _LOGGER.warning(
                "HomeMind: camera %s ritorna immagine vuota/non valida — probabilmente una camera virtuale. "
                "Esclusa dal monitoraggio AI.",
                entity_id,
            )
            self._unsupported_cameras.add(entity_id)
            return None
        except Exception as exc:
            err_str = str(exc)
            _LOGGER.warning("HomeMind: snapshot %s fallito: %s", entity_id, err_str)
            # Non marcare come non supportata per errori temporanei di rete
            if "not found" in err_str.lower() or "404" in err_str:
                _LOGGER.warning(
                    "HomeMind: camera %s restituisce 404 — camera virtuale o offline. "
                    "Esclusa dal monitoraggio.",
                    entity_id,
                )
                self._unsupported_cameras.add(entity_id)
            return None

    # ------------------------------------------------------------------ #
    # Camera analysis
    # ------------------------------------------------------------------ #

    async def analyze_single_camera(self, entity_id: str) -> dict | None:
        """
        Analizza una camera con Gemini Vision.

        - Snapshot cached in _last_snapshots per invio bot
        - Cross-camera correlation
        - Valutazione contestuale per MEDIUM/HIGH
        - Alert Telegram con foto
        """
        if self.ai_status == "error":
            _LOGGER.debug("HomeMind: skip analisi, API in errore")
            return None

        image_bytes = await self._get_camera_snapshot(entity_id)
        if not image_bytes:
            return None

        session = async_get_clientsession(self.hass)
        state = self.hass.states.get(entity_id)
        camera_name = (
            state.attributes.get("friendly_name")
            or entity_id.replace("camera.", "").replace("_", " ").title()
            if state else entity_id
        )

        try:
            if self.ai_provider == AI_PROVIDER_HA_GEMINI:
                from .ha_gemini_provider import analyze_camera_image_ha_gemini
                analysis = await analyze_camera_image_ha_gemini(
                    hass=self.hass,
                    image_bytes=image_bytes,
                    camera_name=camera_name,
                )
            elif self.ai_provider == AI_PROVIDER_OLLAMA:
                from .ollama_provider import analyze_camera_image_ollama
                analysis = await analyze_camera_image_ollama(
                    session=session,
                    host=self.ollama_host,
                    model=self._active_model,
                    image_bytes=image_bytes,
                    camera_name=camera_name,
                )
            else:
                # Gemini REST diretto
                analysis = await analyze_camera_image(
                    session=session,
                    api_key=self.api_key,
                    image_bytes=image_bytes,
                    camera_name=camera_name,
                    model=self._active_model,
                )
        except Exception as exc:
            self._set_error(f"AI Vision errore su {camera_name}: {exc}")
            return None

        # Gestione errori API dall'analisi
        if analysis.get("error"):
            err = analysis["error"]
            self.last_error = f"{camera_name}: {err}"
            self._notify_sensors()
            _LOGGER.warning("HomeMind: analisi %s — %s", camera_name, err)
            return analysis

        threat_level = analysis.get("threat_level", "none")
        threat_detected = analysis.get("threat_detected", False)

        # Cross-camera correlation
        now_ts = datetime.now().timestamp()
        if threat_detected or threat_level != "none":
            self._recent_motion_cams.append((entity_id, now_ts))

        self._recent_motion_cams = [
            (cid, ts) for cid, ts in self._recent_motion_cams
            if now_ts - ts <= self._cross_camera_window
        ]

        active_cams = {cid for cid, _ in self._recent_motion_cams}
        if len(active_cams) >= 2 and threat_level in ("low", "none"):
            analysis["threat_level"] = "medium"
            analysis["threat_detected"] = True
            analysis["summary"] = (
                f"Movimento rilevato su {len(active_cams)} telecamere in 2 minuti. "
                + analysis.get("summary", "")
            )
            threat_level = "medium"
            threat_detected = True
            _LOGGER.warning("HomeMind: correlazione cross-camera → escalation medium")

        # Valutazione contestuale AI per MEDIUM/HIGH
        if threat_level in (THREAT_MEDIUM, THREAT_HIGH):
            from .ha_context import build_home_context
            home_ctx = build_home_context(self.hass, cameras=await self._get_cameras())
            scene_desc = analysis.get("description", "") + " " + analysis.get("summary", "")
            if self.ai_provider == AI_PROVIDER_HA_GEMINI:
                from .ha_gemini_provider import ask_ha_gemini_security
                sec_eval = await ask_ha_gemini_security(
                    hass=self.hass,
                    camera_name=camera_name,
                    scene_description=scene_desc,
                    home_context=home_ctx,
                )
            elif self.ai_provider == AI_PROVIDER_OLLAMA:
                from .ollama_provider import ask_ollama_security
                sec_eval = await ask_ollama_security(
                    session=session,
                    host=self.ollama_host,
                    model=self._active_model,
                    camera_name=camera_name,
                    scene_description=scene_desc,
                    home_context=home_ctx,
                )
            else:
                from .ai_provider import ask_gemini_security
                sec_eval = await ask_gemini_security(
                    session=session,
                    api_key=self.api_key,
                    model=self._active_model,
                    camera_name=camera_name,
                    scene_description=scene_desc,
                    home_context=home_ctx,
                )
            if sec_eval:
                analysis["security_evaluation"] = sec_eval
                if "normale" in sec_eval.lower() and "falso allarme" in sec_eval.lower():
                    analysis["threat_level"] = "low"
                    threat_level = "low"
                    threat_detected = False

        # Aggiorna stato
        if threat_detected:
            self.alerts_tonight += 1
            self.last_alert = f"{camera_name}: {analysis.get('summary', '')}"
            self.night_events.append({
                "time": datetime.now().strftime("%H:%M"),
                "camera": entity_id,
                "camera_name": camera_name,
                "threat_level": threat_level,
                "summary": analysis.get("summary", ""),
                "description": analysis.get("description", ""),
            })
            self._notify_sensors()

            if threat_level in (THREAT_MEDIUM, THREAT_HIGH):
                await self._send_security_alert(entity_id, camera_name, analysis, image_bytes)

        # Evento HA per automazioni
        self.hass.bus.async_fire(
            "homemind_ai_alert",
            {
                "entity_id": entity_id,
                "camera": camera_name,
                "priority": "high" if threat_level in (THREAT_MEDIUM, THREAT_HIGH) else "low",
                "threat_level": threat_level,
                "description": analysis.get("description", ""),
                "summary": analysis.get("summary", ""),
                "snapshot_url": f"/api/camera_proxy/{entity_id}",
                "everyone_away": self._everyone_away(),
            },
        )

        _LOGGER.info(
            "HomeMind [%s] rischio=%s | %s",
            camera_name, threat_level, analysis.get("summary", "")[:80],
        )
        return analysis

    # ------------------------------------------------------------------ #
    # Monitor loop
    # ------------------------------------------------------------------ #

    async def _monitor_loop(self) -> None:
        """Loop principale: analisi motion-triggered, digest consolidato, report."""
        morning_report_sent_date: str = ""

        while True:
            try:
                now = datetime.now()
                now_ts = now.timestamp()
                in_night = self._is_night_window()
                everyone_away = self._everyone_away()

                # Night mode toggle
                new_mode = "active" if in_night else "inactive"
                if self.night_mode != new_mode:
                    self.night_mode = new_mode
                    self._notify_sensors()
                    if self.bot and in_night:
                        await self.bot.send_message(
                            "*Monitoraggio notturno attivo*\n"
                            f"Dalle {now.strftime('%H:%M')} — analisi basata su movimento."
                        )

                # Report mattutino
                today = now.strftime("%Y-%m-%d")
                if now.hour == self.morning_report_hour and morning_report_sent_date != today:
                    await self.send_morning_report()
                    morning_report_sent_date = today

                # Analisi camere — SOLO su motion trigger
                cameras = await self._get_cameras()
                motion_sensors = await self._get_motion_sensors()

                for cam_id in cameras:
                    last_ts = self._last_alert_times.get(cam_id, 0)
                    if (now_ts - last_ts) < self._alert_cooldown:
                        continue

                    cam_slug = cam_id.replace("camera.", "").lower()
                    motion_triggered = self._is_motion_triggered(cam_id, cam_slug, motion_sensors)

                    # Analizza SOLO se c'è movimento (o casa vuota + notte)
                    should_analyze = motion_triggered or (everyone_away and in_night)
                    if not should_analyze:
                        continue

                    result = await self.analyze_single_camera(cam_id)
                    if not result:
                        continue

                    has_event = result.get("has_event", False)
                    threat_level = result.get("threat_level", "none")

                    # NESSUN EVENTO → skip, non mandare nulla
                    if not has_event:
                        continue

                    if result.get("threat_detected"):
                        self._last_alert_times[cam_id] = now_ts

                    # MEDIUM/HIGH → alert immediato con foto
                    if threat_level in (THREAT_MEDIUM, THREAT_HIGH):
                        await self._send_security_alert(
                            cam_id,
                            result.get("camera_name", cam_id),
                            result,
                            self._last_snapshots.get(cam_id),
                        )
                    else:
                        # LOW/eventi minori → accumula nel digest
                        state = self.hass.states.get(cam_id)
                        cam_name = (
                            state.attributes.get("friendly_name", cam_id)
                            if state else cam_id
                        )
                        self._pending_events.append({
                            "time": now.strftime("%H:%M"),
                            "camera_name": cam_name,
                            "camera": cam_id,
                            "description": result.get("description", ""),
                            "summary": result.get("summary", ""),
                            "threat_level": threat_level,
                        })

                # Invia digest consolidato se ci sono eventi pendenti
                digest_interval = (
                    self._digest_interval_night if in_night
                    else self._digest_interval_day
                )
                if (
                    self._pending_events
                    and (now_ts - self._last_digest_ts) >= digest_interval
                ):
                    await self._send_digest()
                    self._last_digest_ts = now_ts

                # Aggiorna cameras_online
                self.cameras_online = len(cameras)
                self._notify_sensors()

                # Intervallo: 60s notte, 90s casa vuota, 300s normali
                sleep = 60 if in_night else (90 if everyone_away else 300)
                await asyncio.sleep(sleep)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._set_error(f"Monitor loop: {exc}")
                await asyncio.sleep(60)

    def _is_motion_triggered(self, cam_id: str, cam_slug: str, motion_sensors: list[str]) -> bool:
        for sensor_id in motion_sensors:
            state = self.hass.states.get(sensor_id)
            if not state or state.state != "on":
                continue
            sensor_slug = sensor_id.replace("binary_sensor.", "").lower()
            if (
                cam_slug in sensor_slug
                or sensor_slug.startswith(cam_slug)
                or any(part in sensor_slug for part in cam_slug.split("_") if len(part) > 3)
            ):
                return True
        return False

    # ------------------------------------------------------------------ #
    # Digest consolidato — un messaggio con tutti gli eventi minori
    # ------------------------------------------------------------------ #

    async def _send_digest(self) -> None:
        """Invia un messaggio consolidato con tutti gli eventi pendenti."""
        if not self._pending_events or not self.bot:
            self._pending_events.clear()
            return

        events = self._pending_events.copy()
        self._pending_events.clear()
        now = datetime.now().strftime("%H:%M")
        everyone_away = self._everyone_away()

        lines = [
            f"*Riepilogo eventi · {now}*"
            + (" · Casa vuota" if everyone_away else ""),
            "",
        ]

        for ev in events[-10:]:  # Max 10 eventi per digest
            risk = ev.get("threat_level", "none").upper()
            icon = "🟡" if risk == "LOW" else "⚪"
            cam = ev.get("camera_name", "")
            desc = ev.get("description", "")
            nota = ev.get("summary", "")
            lines.append(
                f"{icon} *{cam}* · {ev.get('time', '')}\n"
                f"   {desc}"
                + (f"\n   _{nota}_" if nota and nota != desc else "")
            )
            lines.append("")

        lines.append(f"Telecamere: {self.cameras_online} attive")

        await self.bot.send_message("\n".join(lines))

    # ------------------------------------------------------------------ #
    # Alert sicurezza (Apple-minimal)
    # ------------------------------------------------------------------ #

    async def _send_security_alert(
        self,
        entity_id: str,
        camera_name: str,
        analysis: dict,
        image_bytes: bytes | None = None,
    ) -> None:
        if not self.bot:
            return

        level = analysis.get("threat_level", "none")
        everyone_away = self._everyone_away()
        ts = datetime.now().strftime("%H:%M")

        # Header minimale
        risk_label = "ALTO" if level == "high" else "MEDIO"
        header = f"{'🔴' if level == 'high' else '🟠'} *Allerta · {camera_name}*"
        if everyone_away:
            header += " · Casa vuota"

        body = f"{analysis.get('description', '')}".strip()
        if analysis.get("unusual") and analysis["unusual"].lower() not in ("no", "nessuno", "nessuna"):
            body += f" {analysis['unusual']}".rstrip(".")
            body += "."
        summary = analysis.get("summary", "")

        caption = f"{header}\n{ts} · Rischio {risk_label}"
        if body:
            caption += f"\n\n{body}"
        if summary and summary not in body:
            caption += f"\n\n{summary}"
        if analysis.get("security_evaluation"):
            caption += f"\n\n_{analysis['security_evaluation'][:150]}_"

        if image_bytes:
            await self.bot.send_photo(image_bytes, caption[:1024])
        else:
            await self.bot.send_message(caption)

    # ------------------------------------------------------------------ #
    # Report mattutino (Apple-minimal)
    # ------------------------------------------------------------------ #

    async def send_morning_report(self, force: bool = False) -> None:
        events = self.night_events
        threats = [e for e in events if e.get("threat_level") in (THREAT_MEDIUM, THREAT_HIGH)]
        today = datetime.now().strftime("%d/%m/%Y")

        lines = [
            f"*Report Notturno · {today}*",
            "",
            f"Analisi  {len(events)}",
            f"Allerte  {len(threats)}",
            "",
        ]

        if threats:
            lines.append("*Eventi rilevati:*")
            for e in threats[:5]:
                level = e.get("threat_level", "")
                icon = "🔴" if level == "high" else "🟠"
                cam = e.get("camera_name") or e.get("camera", "").replace("camera.", "").replace("_", " ").title()
                lines.append(f"{icon} {e['time']} · {cam}: {e.get('summary', '')}")
        else:
            lines.append("Nessun evento sospetto rilevato stanotte.")

        report_text = "\n".join(lines)
        self.last_report = report_text[:255]
        self._notify_sensors()

        if self.bot:
            await self.bot.send_message(report_text)

        if not force:
            self.night_events.clear()
            self.alerts_tonight = 0
