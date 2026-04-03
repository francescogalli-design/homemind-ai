"""HomeMind AI v4.0 — sicurezza camera 100% locale con Ollama, zero costi."""
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
    INTERNET_CHECK_INTERVAL,
    INTERNET_CHECK_TARGETS,
    INTERVAL_AWAY_DAY,
    INTERVAL_AWAY_NIGHT,
    INTERVAL_HOME_DAY,
    INTERVAL_HOME_NIGHT,
    PING_ENTITY,
    SERVICE_ANALYZE_CAMERA,
    SERVICE_ASK_AI,
    SERVICE_CLEAR_ALERTS,
    SERVICE_GENERATE_REPORT,
    SERVICE_VALIDATE_PLATE,
    THREAT_HIGH,
    THREAT_LOW,
    THREAT_MEDIUM,
)
from .ollama_provider import (
    analyze_camera_image_ollama,
    ask_ollama,
    ask_ollama_security,
    check_plate_visible,
    test_ollama,
)
from .notification_engine import NotificationEngine, format_digest_message
from .telegram_bot import TelegramBot

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]


# ── Migrazione config entry v1/v2/v3 → v4 ───────────────────────


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migra config entries da versioni precedenti a v4 (solo Ollama)."""
    if entry.version < 4:
        _LOGGER.info("Migrazione HomeMind AI v%s → v4: rimuovo Gemini, solo Ollama", entry.version)
        new_data = dict(entry.data)
        # Rimuovi campi Gemini/provider
        new_data.pop(CONF_GEMINI_API_KEY, None)
        new_data.pop(CONF_GEMINI_MODEL, None)
        new_data.pop(CONF_AI_PROVIDER, None)
        # Aggiungi default Ollama
        new_data.setdefault(CONF_OLLAMA_HOST, DEFAULT_OLLAMA_HOST)
        new_data.setdefault(CONF_OLLAMA_MODEL, DEFAULT_OLLAMA_MODEL)
        new_data.setdefault(CONF_PERSON_ENTITY, "")
        hass.config_entries.async_update_entry(entry, data=new_data, version=4)
        _LOGGER.info("Migrazione completata a v4")
    return True


# ── Setup / Unload ───────────────────────────────────────────────


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
        if entity_id:
            await coordinator.analyze_single_camera(entity_id, force_notify=True)

    async def handle_generate_report(call: ServiceCall) -> None:
        await coordinator.send_morning_report(force=True)

    async def handle_clear_alerts(call: ServiceCall) -> None:
        coordinator.night_events.clear()
        coordinator.alerts_tonight = 0
        coordinator.last_alert = ""
        coordinator.notifier.force_reset()
        coordinator._notify_sensors()

    async def handle_ask_ai(call: ServiceCall) -> None:
        question = call.data.get("question", "").strip()
        if not question:
            return
        from .ha_context import build_home_context
        context = build_home_context(hass, cameras=await coordinator._get_cameras())
        session = async_get_clientsession(hass)
        answer = await ask_ollama(
            session, coordinator.ollama_host, coordinator.ollama_model,
            question, context,
        )
        coordinator.last_ai_answer = answer[:255]
        coordinator._notify_sensors()
        if coordinator.bot:
            await coordinator.bot.send_message(answer)

    async def handle_validate_plate(call: ServiceCall) -> None:
        """Pre-validazione ALPR: Ollama verifica se c'è targa visibile."""
        entity_id = call.data.get("entity_id", "").strip()
        if not entity_id:
            return
        image_bytes = await coordinator._get_camera_snapshot(entity_id)
        if not image_bytes:
            return
        session = async_get_clientsession(hass)
        visible = await check_plate_visible(
            session, coordinator.ollama_host, coordinator.ollama_model, image_bytes,
        )
        hass.bus.async_fire("homemind_plate_check", {
            "entity_id": entity_id,
            "plate_visible": visible,
        })
        _LOGGER.info("Plate check %s: %s", entity_id, "visibile" if visible else "non visibile")

    hass.services.async_register(
        DOMAIN, SERVICE_ANALYZE_CAMERA, handle_analyze_camera,
        schema=vol.Schema({vol.Required("entity_id"): cv.entity_id}),
    )
    hass.services.async_register(DOMAIN, SERVICE_GENERATE_REPORT, handle_generate_report)
    hass.services.async_register(DOMAIN, SERVICE_CLEAR_ALERTS, handle_clear_alerts)
    hass.services.async_register(
        DOMAIN, SERVICE_ASK_AI, handle_ask_ai,
        schema=vol.Schema({vol.Required("question"): str}),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_VALIDATE_PLATE, handle_validate_plate,
        schema=vol.Schema({vol.Required("entity_id"): cv.entity_id}),
    )

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    coordinator.start()
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator: HomeMindCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
    coordinator.stop()
    for svc in (SERVICE_ANALYZE_CAMERA, SERVICE_GENERATE_REPORT, SERVICE_CLEAR_ALERTS, SERVICE_ASK_AI, SERVICE_VALIDATE_PLATE):
        hass.services.async_remove(DOMAIN, svc)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


# ── Coordinator ──────────────────────────────────────────────────


class HomeMindCoordinator:
    """Coordinatore principale di HomeMind AI v4 — solo Ollama locale."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        cfg = {**entry.data, **entry.options}

        # Configurazione Ollama
        self.ollama_host: str = cfg.get(CONF_OLLAMA_HOST, DEFAULT_OLLAMA_HOST).rstrip("/")
        self.ollama_model: str = cfg.get(CONF_OLLAMA_MODEL, DEFAULT_OLLAMA_MODEL)
        self.telegram_token: str = cfg.get(CONF_TELEGRAM_TOKEN, "")
        self.telegram_chat_id: str = str(cfg.get(CONF_TELEGRAM_CHAT_ID, "")).strip()
        self.configured_cameras: list[str] = cfg.get(CONF_CAMERAS, [])
        self.configured_motion_sensors: list[str] = cfg.get(CONF_MOTION_SENSORS, [])
        self.person_entity: str = cfg.get(CONF_PERSON_ENTITY, "")
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

        # Sicurezza
        self.night_events: list[dict] = []
        self._last_alert_times: dict[str, float] = {}

        # Cross-camera correlation
        self._recent_motion_cams: list[tuple[str, float]] = []
        self._cross_camera_window: int = 120

        # Cache snapshot
        self._last_snapshots: dict[str, bytes] = {}
        self._unsupported_cameras: set[str] = set()

        # Digest eventi minori
        self._pending_events: list[dict] = []
        self._last_digest_ts: float = 0
        self._digest_interval_night: int = 900
        self._digest_interval_day: int = 1800

        # ALPR state
        self.last_plate: str = ""
        self.plates_today: int = 0
        self._plate_manager = None

        # Notification engine
        self.notifier = NotificationEngine()

        # Internet monitor
        self._internet_was_offline: bool = False

        self._sensor_callbacks: list = []
        self.bot: TelegramBot | None = None
        self._monitor_task: asyncio.Task | None = None
        self._internet_task: asyncio.Task | None = None

    # ── Lifecycle ────────────────────────────────────────────

    def start(self) -> None:
        if self.telegram_token and self.telegram_chat_id:
            self.bot = TelegramBot(self)
            self.bot.start()
            self.bot_status = "connected"
        else:
            self.bot_status = "not_configured"

        self._monitor_task = self.hass.loop.create_task(self._startup_sequence())
        self._internet_task = self.hass.loop.create_task(self._internet_monitor_loop())
        _LOGGER.info(
            "HomeMind AI v4: avvio — Ollama @ %s, modello=%s, camere=%d",
            self.ollama_host, self.ollama_model, len(self.configured_cameras),
        )

    def stop(self) -> None:
        if self._plate_manager:
            self._plate_manager.stop()
        if self.bot:
            self.bot.stop()
        for task in (self._monitor_task, self._internet_task):
            if task:
                task.cancel()

    # ── Internet connectivity ────────────────────────────────

    def _check_internet_ping(self) -> bool | None:
        """Check internet via binary_sensor.8_8_8_8 (ping integration)."""
        state = self.hass.states.get(PING_ENTITY)
        if state is None:
            return None
        if state.state in ("unavailable", "unknown"):
            return None
        return state.state == "on"

    async def _internet_monitor_loop(self) -> None:
        """Loop separato per monitoraggio internet con fallback HTTP."""
        while True:
            try:
                # Prima prova il ping entity (gratuito, nessuna chiamata)
                ping_result = self._check_internet_ping()
                if ping_result is not None:
                    online = ping_result
                else:
                    # Fallback: HTTP check
                    session = async_get_clientsession(self.hass)
                    online = False
                    for target in INTERNET_CHECK_TARGETS:
                        try:
                            async with session.get(
                                target, timeout=aiohttp.ClientTimeout(total=8),
                            ) as resp:
                                if resp.status < 500:
                                    online = True
                                    break
                        except Exception:
                            continue

                old_status = self.internet_status
                self.internet_status = "online" if online else "offline"

                if old_status != self.internet_status:
                    self._notify_sensors()

                    if self.internet_status == "offline" and not self._internet_was_offline:
                        self._internet_was_offline = True
                        _LOGGER.warning("HomeMind AI: internet OFFLINE")
                        if not self._is_everyone_home() and self.bot:
                            await self.bot.send_message(
                                "⚠️ *HomeMind AI*\n\n"
                                "🔴 Internet **perso**. "
                                "Il monitoraggio AI locale continua.\n"
                                f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                            )

                    elif self.internet_status == "online" and self._internet_was_offline:
                        self._internet_was_offline = False
                        _LOGGER.info("HomeMind AI: internet ripristinato")
                        if not self._is_everyone_home() and self.bot:
                            await self.bot.send_message(
                                "✅ *HomeMind AI*\n\n"
                                "🟢 Internet **ripristinato**.\n"
                                f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                            )

                await asyncio.sleep(INTERNET_CHECK_INTERVAL)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                _LOGGER.error("Internet monitor: %s", exc)
                await asyncio.sleep(60)

    # ── Startup ──────────────────────────────────────────────

    async def _startup_sequence(self) -> None:
        """Testa Ollama, inizializza ALPR, avvia monitor loop."""
        await asyncio.sleep(3)

        session = async_get_clientsession(self.hass)
        ok, msg = await test_ollama(session, self.ollama_host, self.ollama_model)
        if ok:
            self.api_health = f"Online — Ollama ({self.ollama_model})"
            self.ai_status = "online"
            self.last_error = ""
            _LOGGER.info("HomeMind: Ollama OK — %s", msg)
        else:
            self.api_health = f"Errore Ollama — {msg[:80]}"
            self.ai_status = "error"
            self.last_error = msg
            _LOGGER.error("HomeMind: Ollama non disponibile — %s", msg)

        # ALPR
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

        if self.bot and self.ai_status == "online":
            cams = await self._get_cameras()
            home_status = "Casa" if self._is_everyone_home() else "Fuori"
            await self.bot.send_message(
                f"*HomeMind AI v4* avviato\n\n"
                f"AI  Ollama ({self.ollama_model})\n"
                f"Telecamere  {len(cams) if cams else 'autodetect'}\n"
                f"Notte  {self.night_start}:00 — {self.night_end}:00\n"
                f"Stato  {home_status}\n\n"
                f"Zero costi — 100% locale. Scrivi /help per i comandi."
            )
        elif self.bot:
            await self.bot.send_message(
                f"*HomeMind AI v4* — errore avvio\n\n{self.last_error}\n\n"
                "Verifica che Ollama sia avviato: `ollama serve`"
            )

        await self._monitor_loop()

    # ── Callbacks sensori ────────────────────────────────────

    def register_sensor_callback(self, callback) -> None:
        self._sensor_callbacks.append(callback)

    def _notify_sensors(self) -> None:
        for cb in self._sensor_callbacks:
            try:
                cb()
            except Exception:
                pass

    def _set_error(self, msg: str) -> None:
        self.last_error = msg[:200]
        self.ai_status = "error"
        self._notify_sensors()
        _LOGGER.error("HomeMind: %s", msg)

    # ── Camera discovery ─────────────────────────────────────

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

    # ── Night / presence ─────────────────────────────────────

    def _is_night_window(self) -> bool:
        h = datetime.now().hour
        if self.night_start > self.night_end:
            return h >= self.night_start or h < self.night_end
        return self.night_start <= h < self.night_end

    def _is_everyone_home(self) -> bool:
        """Controlla se qualcuno è a casa. Se person_entity configurato, usa quello.
        Altrimenti controlla tutte le person entities."""
        if self.person_entity:
            state = self.hass.states.get(self.person_entity)
            if state and state.state in ("home", "Home", "casa"):
                return True
            return False

        person_ids = self.hass.states.async_entity_ids("person")
        if not person_ids:
            return False
        for eid in person_ids:
            state = self.hass.states.get(eid)
            if state and state.state in ("home", "Home", "casa"):
                return True
        return False

    def _everyone_away(self) -> bool:
        return not self._is_everyone_home()

    def _get_interval(self, is_home: bool, is_night: bool) -> int:
        if is_home and not is_night:
            return INTERVAL_HOME_DAY
        if is_home and is_night:
            return INTERVAL_HOME_NIGHT
        if not is_home and is_night:
            return INTERVAL_AWAY_NIGHT
        return INTERVAL_AWAY_DAY

    # ── Camera snapshot ──────────────────────────────────────

    async def _get_camera_snapshot(self, entity_id: str) -> bytes | None:
        try:
            from homeassistant.components.camera import async_get_image
            image = await async_get_image(self.hass, entity_id, timeout=10)
            if image and image.content and len(image.content) > 500:
                self._last_snapshots[entity_id] = image.content
                return image.content
            _LOGGER.warning("HomeMind: camera %s ritorna immagine vuota — esclusa", entity_id)
            self._unsupported_cameras.add(entity_id)
            return None
        except Exception as exc:
            err_str = str(exc)
            _LOGGER.warning("HomeMind: snapshot %s fallito: %s", entity_id, err_str)
            if "not found" in err_str.lower() or "404" in err_str:
                self._unsupported_cameras.add(entity_id)
            return None

    # ── Camera analysis ──────────────────────────────────────

    async def analyze_single_camera(
        self, entity_id: str, force_notify: bool = False
    ) -> dict | None:
        if self.ai_status == "error":
            _LOGGER.debug("HomeMind: skip analisi, Ollama in errore")
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
            analysis = await analyze_camera_image_ollama(
                session=session,
                host=self.ollama_host,
                model=self.ollama_model,
                image_bytes=image_bytes,
                camera_name=camera_name,
            )
        except Exception as exc:
            self._set_error(f"Ollama Vision errore su {camera_name}: {exc}")
            return None

        if analysis.get("error"):
            self.last_error = f"{camera_name}: {analysis['error']}"
            self._notify_sensors()
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
                f"Movimento su {len(active_cams)} telecamere in 2 min. "
                + analysis.get("summary", "")
            )
            threat_level = "medium"
            threat_detected = True

        # Valutazione contestuale per MEDIUM/HIGH
        if threat_level in (THREAT_MEDIUM, THREAT_HIGH):
            from .ha_context import build_home_context
            home_ctx = build_home_context(self.hass, cameras=await self._get_cameras())
            scene_desc = analysis.get("description", "") + " " + analysis.get("summary", "")
            sec_eval = await ask_ollama_security(
                session=session,
                host=self.ollama_host,
                model=self.ollama_model,
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

            # Decisione notifica
            if force_notify:
                await self._send_security_alert(entity_id, camera_name, analysis, image_bytes)
            elif threat_level in (THREAT_MEDIUM, THREAT_HIGH):
                decision = self.notifier.evaluate(
                    camera_entity=entity_id,
                    threat_level=threat_level,
                    is_home=self._is_everyone_home(),
                    is_night=self._is_night_window(),
                    analysis=analysis,
                )
                if decision.should_notify:
                    await self._send_security_alert(entity_id, camera_name, analysis, image_bytes)
                else:
                    _LOGGER.debug("Notifica soppressa [%s]: %s", entity_id, decision.reason)

        # Evento HA
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

        _LOGGER.info("HomeMind [%s] rischio=%s | %s", camera_name, threat_level, analysis.get("summary", "")[:80])
        return analysis

    # ── Monitor loop ─────────────────────────────────────────

    async def _monitor_loop(self) -> None:
        """Loop principale con scheduling adattivo basato su presenza."""
        morning_report_sent_date: str = ""

        while True:
            try:
                now = datetime.now()
                now_ts = now.timestamp()
                in_night = self._is_night_window()
                is_home = self._is_everyone_home()

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

                # Pulizia notifiche
                self.notifier.cleanup_stale()

                # Digest aggregato
                digest_events = self.notifier.get_and_clear_digest()
                if digest_events and self.bot:
                    digest_msg = format_digest_message(digest_events)
                    if digest_msg:
                        await self.bot.send_message(digest_msg)

                # Report mattutino (solo se eventi rilevanti)
                today = now.strftime("%Y-%m-%d")
                if now.hour == self.morning_report_hour and morning_report_sent_date != today:
                    morning_report_sent_date = today
                    threats = [e for e in self.night_events if e.get("threat_level") in (THREAT_MEDIUM, THREAT_HIGH)]
                    if threats:
                        await self.send_morning_report()
                    else:
                        _LOGGER.info("Morning report: nessun evento rilevante, skip")
                        self.night_events.clear()
                        self.alerts_tonight = 0

                # Scheduling adattivo
                interval = self._get_interval(is_home, in_night)
                if interval == 0:
                    # Casa + giorno: nessuna analisi, controlla tra 5 min
                    await asyncio.sleep(300)
                    continue

                # Analisi camere — SOLO su motion trigger
                cameras = await self._get_cameras()
                motion_sensors = await self._get_motion_sensors()

                for cam_id in cameras:
                    last_ts = self._last_alert_times.get(cam_id, 0)
                    cooldown = self.notifier._get_cooldown(is_home, in_night)
                    if (now_ts - last_ts) < cooldown:
                        continue

                    cam_slug = cam_id.replace("camera.", "").lower()
                    motion_triggered = self._is_motion_triggered(cam_id, cam_slug, motion_sensors)

                    should_analyze = motion_triggered or (not is_home and in_night)
                    if not should_analyze:
                        continue

                    result = await self.analyze_single_camera(cam_id)
                    if not result:
                        continue

                    has_event = result.get("has_event", False)
                    threat_level = result.get("threat_level", "none")

                    if not has_event:
                        continue

                    if result.get("threat_detected"):
                        self._last_alert_times[cam_id] = now_ts

                    # LOW/eventi minori → accumula nel digest
                    if threat_level not in (THREAT_MEDIUM, THREAT_HIGH):
                        state = self.hass.states.get(cam_id)
                        cam_name = state.attributes.get("friendly_name", cam_id) if state else cam_id
                        self._pending_events.append({
                            "time": now.strftime("%H:%M"),
                            "camera_name": cam_name,
                            "camera": cam_id,
                            "description": result.get("description", ""),
                            "summary": result.get("summary", ""),
                            "threat_level": threat_level,
                        })

                # Digest consolidato
                digest_interval = self._digest_interval_night if in_night else self._digest_interval_day
                if self._pending_events and (now_ts - self._last_digest_ts) >= digest_interval:
                    await self._send_digest()
                    self._last_digest_ts = now_ts

                self.cameras_online = len(cameras)
                self._notify_sensors()

                await asyncio.sleep(interval)

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

    # ── Digest ───────────────────────────────────────────────

    async def _send_digest(self) -> None:
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
        for ev in events[-10:]:
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

    # ── Alert sicurezza ──────────────────────────────────────

    async def _send_security_alert(
        self, entity_id: str, camera_name: str, analysis: dict, image_bytes: bytes | None = None,
    ) -> None:
        if not self.bot:
            return

        level = analysis.get("threat_level", "none")
        everyone_away = self._everyone_away()
        ts = datetime.now().strftime("%H:%M")

        risk_label = "ALTO" if level == "high" else "MEDIO"
        header = f"{'🔴' if level == 'high' else '🟠'} *Allerta · {camera_name}*"
        if everyone_away:
            header += " · Casa vuota"

        body = f"{analysis.get('description', '')}".strip()
        if analysis.get("unusual") and analysis["unusual"].lower() not in ("no", "nessuno", "nessuna"):
            body += f" {analysis['unusual']}".rstrip(".") + "."
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

    # ── Morning report ───────────────────────────────────────

    async def send_morning_report(self, force: bool = False) -> None:
        events = self.night_events
        threats = [e for e in events if e.get("threat_level") in (THREAT_MEDIUM, THREAT_HIGH)]

        if not force and not threats:
            return

        today = datetime.now().strftime("%d/%m/%Y")
        lines = [
            f"*Report Notturno · {today}*",
            "",
            f"Analisi  {len(events)}",
            f"Allerte  {len(threats)}",
            f"Internet  {self.internet_status}",
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
            lines.append("Nessun evento sospetto stanotte.")

        lines.append("\n_HomeMind AI v4 — 100% locale con Ollama_")

        report_text = "\n".join(lines)
        self.last_report = report_text[:255]
        self._notify_sensors()

        if self.bot:
            await self.bot.send_message(report_text)

        if not force:
            self.night_events.clear()
            self.alerts_tonight = 0
