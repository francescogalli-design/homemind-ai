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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configura HomeMind AI da config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = HomeMindCoordinator(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # ---- Registra servizi HA ----
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
        _LOGGER.info("HomeMind AI: alert notturni azzerati")

    async def handle_ask_ai(call: ServiceCall) -> None:
        question = call.data.get("question", "").strip()
        if not question:
            return
        from .ha_context import build_home_context
        from .ai_provider import ask_gemini

        context = build_home_context(hass, cameras=await coordinator._get_cameras())
        session = async_get_clientsession(hass)
        answer = await ask_gemini(
            session=session,
            api_key=coordinator.api_key,
            model=coordinator.gemini_model,
            question=question,
            home_context=context,
        )
        coordinator.last_ai_answer = answer
        coordinator._notify_sensors()
        if coordinator.bot:
            await coordinator.bot.send_message(f"🤖 *HomeMind AI:*\n\n{answer}")

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

    # Ricarica il coordinator quando le opzioni cambiano
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    # Avvia tutto
    coordinator.start()
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Ricarica l'integrazione quando le opzioni vengono aggiornate."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Rimuove HomeMind AI."""
    coordinator: HomeMindCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
    coordinator.stop()

    for service in (SERVICE_ANALYZE_CAMERA, SERVICE_GENERATE_REPORT, SERVICE_CLEAR_ALERTS, SERVICE_ASK_AI):
        hass.services.async_remove(DOMAIN, service)

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class HomeMindCoordinator:
    """
    Coordinatore principale di HomeMind AI.

    Gestisce:
    - Loop di monitoraggio sicurezza proattivo
    - Analisi camere con Gemini Vision
    - Bot Telegram per query e comandi
    - Sensori HA con stato in tempo reale
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        # Merge data + options (options hanno priorità)
        cfg = {**entry.data, **entry.options}

        # Configurazione
        self.api_key: str = cfg.get(CONF_GEMINI_API_KEY, "")
        self.gemini_model: str = cfg.get(CONF_GEMINI_MODEL, DEFAULT_GEMINI_MODEL)
        self.telegram_token: str = cfg.get(CONF_TELEGRAM_TOKEN, "")
        self.telegram_chat_id: str = str(cfg.get(CONF_TELEGRAM_CHAT_ID, "")).strip()
        self.configured_cameras: list[str] = cfg.get(CONF_CAMERAS, [])
        self.configured_motion_sensors: list[str] = cfg.get(CONF_MOTION_SENSORS, [])
        self.night_start: int = cfg.get(CONF_NIGHT_START, DEFAULT_NIGHT_START)
        self.night_end: int = cfg.get(CONF_NIGHT_END, DEFAULT_NIGHT_END)
        self.morning_report_hour: int = cfg.get(CONF_MORNING_REPORT_HOUR, DEFAULT_MORNING_REPORT_HOUR)

        # Stato sensori esposti in HA
        self.ai_status: str = "online"
        self.night_mode: str = "inactive"
        self.alerts_tonight: int = 0
        self.last_alert: str = ""
        self.last_report: str = ""
        self.last_ai_answer: str = ""

        # Registro eventi sicurezza
        self.night_events: list[dict] = []
        self._last_alert_times: dict[str, float] = {}
        self._alert_cooldown: int = 300  # 5 minuti per camera

        # Tracciamento cross-camera (sicurezza proattiva avanzata)
        self._recent_motion_cams: list[tuple[str, float]] = []  # (cam_id, timestamp)
        self._cross_camera_window: int = 120  # 2 min finestra correlazione

        # Callbacks sensori
        self._sensor_callbacks: list = []

        # Componenti
        self.bot: TelegramBot | None = None
        self._monitor_task: asyncio.Task | None = None

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        """Avvia bot e loop di monitoraggio."""
        # Bot Telegram
        if self.telegram_token and self.telegram_chat_id:
            self.bot = TelegramBot(self)
            self.bot.start()
        else:
            _LOGGER.info("HomeMind: Telegram non configurato, solo alert in uscita disabilitati")

        # Loop monitoraggio
        self._monitor_task = self.hass.loop.create_task(self._monitor_loop())
        _LOGGER.info(
            "HomeMind AI avviato: camere=%d, modello=%s, bot=%s",
            len(self.configured_cameras),
            self.gemini_model,
            "attivo" if self.bot else "non configurato",
        )

    def stop(self) -> None:
        """Ferma tutto."""
        if self.bot:
            self.bot.stop()
        if self._monitor_task:
            self._monitor_task.cancel()
        _LOGGER.info("HomeMind AI fermato")

    # ------------------------------------------------------------------ #
    # Sensor callbacks
    # ------------------------------------------------------------------ #

    def register_sensor_callback(self, callback) -> None:
        self._sensor_callbacks.append(callback)

    def _notify_sensors(self) -> None:
        for cb in self._sensor_callbacks:
            try:
                cb()
            except Exception as exc:
                _LOGGER.debug("Sensor callback errore: %s", exc)

    # ------------------------------------------------------------------ #
    # Camera discovery
    # ------------------------------------------------------------------ #

    async def _get_cameras(self) -> list[str]:
        """Restituisce camere configurate o autodetect."""
        if self.configured_cameras:
            # Filtra solo quelle che esistono ancora in HA
            return [
                eid for eid in self.configured_cameras
                if self.hass.states.get(eid) is not None
            ]
        # Autodetect: tutte le camera.* presenti
        return self.hass.states.async_entity_ids("camera")

    async def _get_motion_sensors(self) -> list[str]:
        """Restituisce sensori movimento configurati o autodetect."""
        if self.configured_motion_sensors:
            return [
                eid for eid in self.configured_motion_sensors
                if self.hass.states.get(eid) is not None
            ]
        # Autodetect: binary_sensor con device_class motion/occupancy
        sensors = []
        for eid in self.hass.states.async_entity_ids("binary_sensor"):
            state = self.hass.states.get(eid)
            if state:
                dc = state.attributes.get("device_class", "")
                if dc in ("motion", "occupancy"):
                    sensors.append(eid)
        return sensors

    # ------------------------------------------------------------------ #
    # Night window helpers
    # ------------------------------------------------------------------ #

    def _is_night_window(self) -> bool:
        h = datetime.now().hour
        if self.night_start > self.night_end:
            return h >= self.night_start or h < self.night_end
        return self.night_start <= h < self.night_end

    def _everyone_away(self) -> bool:
        """Controlla se tutti sono fuori casa."""
        person_ids = self.hass.states.async_entity_ids("person")
        if not person_ids:
            return False
        for eid in person_ids:
            state = self.hass.states.get(eid)
            if state and state.state in ("home", "Home", "casa"):
                return False
        return True

    # ------------------------------------------------------------------ #
    # Camera snapshot
    # ------------------------------------------------------------------ #

    async def _get_camera_snapshot(self, entity_id: str) -> bytes | None:
        try:
            from homeassistant.components.camera import async_get_image
            image = await async_get_image(self.hass, entity_id, timeout=10)
            return image.content
        except Exception as exc:
            _LOGGER.error("Snapshot errore %s: %s", entity_id, exc)
            return None

    # ------------------------------------------------------------------ #
    # Camera analysis — cuore della sicurezza proattiva
    # ------------------------------------------------------------------ #

    async def analyze_single_camera(self, entity_id: str) -> dict | None:
        """
        Analizza una camera con Gemini Vision e invia alert se necessario.

        Sicurezza proattiva avanzata rispetto a HomeMind:
        - Contesto casa completo (chi è a casa, ora, porte, sensori)
        - Correlazione cross-camera: se 2+ camere attive in 2 min → escalation
        - Valutazione contestuale con ask_gemini_security per MEDIUM/HIGH
        - Alert immediato su Telegram con foto se minaccia confermata
        """
        image_bytes = await self._get_camera_snapshot(entity_id)
        if not image_bytes:
            return None

        session = async_get_clientsession(self.hass)
        state = self.hass.states.get(entity_id)
        camera_name = (
            state.attributes.get("friendly_name")
            or entity_id.replace("camera.", "").replace("_", " ").title()
            if state
            else entity_id
        )

        analysis = await analyze_camera_image(
            session=session,
            api_key=self.api_key,
            image_bytes=image_bytes,
            camera_name=camera_name,
            model=self.gemini_model,
        )

        threat_level = analysis.get("threat_level", "none")
        threat_detected = analysis.get("threat_detected", False)

        # ---- Cross-camera correlation (sicurezza proattiva) ----
        now_ts = datetime.now().timestamp()
        if threat_detected or threat_level != "none":
            self._recent_motion_cams.append((entity_id, now_ts))

        # Pulisci vecchi (fuori finestra)
        self._recent_motion_cams = [
            (cid, ts)
            for cid, ts in self._recent_motion_cams
            if now_ts - ts <= self._cross_camera_window
        ]

        # Se 2+ camere diverse hanno rilevato in finestra → escalation
        active_cams = {cid for cid, _ in self._recent_motion_cams}
        if len(active_cams) >= 2 and threat_level in ("low", "none"):
            _LOGGER.warning(
                "HomeMind: correlazione cross-camera (%s) → escalation a medium",
                ", ".join(active_cams),
            )
            analysis["threat_level"] = "medium"
            analysis["threat_detected"] = True
            analysis["summary"] = (
                f"[ESCALATION] Movimento su {len(active_cams)} telecamere contemporaneamente. "
                + analysis.get("summary", "")
            )
            threat_level = "medium"
            threat_detected = True

        # ---- Valutazione contestuale per MEDIUM/HIGH ----
        if threat_level in (THREAT_MEDIUM, THREAT_HIGH):
            from .ha_context import build_home_context
            from .ai_provider import ask_gemini_security

            home_ctx = build_home_context(self.hass, cameras=await self._get_cameras())
            sec_eval = await ask_gemini_security(
                session=session,
                api_key=self.api_key,
                model=self.gemini_model,
                camera_name=camera_name,
                scene_description=analysis.get("description", "") + " " + analysis.get("summary", ""),
                home_context=home_ctx,
            )
            if sec_eval:
                analysis["security_evaluation"] = sec_eval
                # Se la valutazione dice "normale", abbassa il livello
                if "normale" in sec_eval.lower() and "falso allarme" in sec_eval.lower():
                    _LOGGER.info("HomeMind: valutazione contestuale → normale (falso allarme)")
                    analysis["threat_level"] = "low"
                    threat_level = "low"

        # ---- Aggiorna stato ----
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

            # Alert Telegram con foto per MEDIUM/HIGH
            if threat_level in (THREAT_MEDIUM, THREAT_HIGH):
                await self._send_alert(entity_id, camera_name, analysis, image_bytes)

        elif threat_level == THREAT_LOW:
            # Low threat: solo log, no alert
            _LOGGER.info(
                "HomeMind [%s]: rischio basso — %s",
                camera_name,
                analysis.get("summary", "")[:80],
            )

        # Spara evento HA per automazioni
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
            camera_name,
            threat_level,
            analysis.get("summary", "")[:80],
        )
        return analysis

    # ------------------------------------------------------------------ #
    # Monitor loop — sicurezza proattiva continua
    # ------------------------------------------------------------------ #

    async def _monitor_loop(self) -> None:
        """
        Loop principale di monitoraggio sicurezza.

        Strategia proattiva:
        - Notte: analisi ogni 120s o al trigger movimento
        - Giorno + tutti fuori: analisi ogni 180s
        - Giorno + qualcuno a casa: solo trigger movimento, scan ogni 600s
        - Cooldown 5 min per camera dopo alert
        """
        morning_report_sent_date: str = ""
        # Messaggio di avvio
        if self.bot:
            await asyncio.sleep(5)  # Attendi che il bot sia pronto
            await self.bot.send_message(
                "🏠 *HomeMind AI avviato*\n"
                f"📷 Telecamere: {len(self.configured_cameras) or 'autodetect'}\n"
                f"🌙 Monitoraggio notturno: {self.night_start}:00 → {self.night_end}:00\n"
                "💬 Scrivi /help per i comandi disponibili."
            )

        while True:
            try:
                now = datetime.now()
                now_ts = now.timestamp()
                in_night = self._is_night_window()
                everyone_away = self._everyone_away()

                # Aggiorna night_mode
                new_mode = "active" if in_night else "inactive"
                if self.night_mode != new_mode:
                    self.night_mode = new_mode
                    self._notify_sensors()
                    if self.bot:
                        if in_night:
                            await self.bot.send_message(
                                f"🌙 *Monitoraggio notturno attivo*\n"
                                f"Dalle {now.strftime('%H:%M')} — scansione camere ogni 2 minuti."
                            )
                        else:
                            await self.bot.send_message("🌅 Monitoraggio notturno terminato.")

                # Report mattutino
                today = now.strftime("%Y-%m-%d")
                if now.hour == self.morning_report_hour and morning_report_sent_date != today:
                    await self.send_morning_report()
                    morning_report_sent_date = today

                # Determina camere da analizzare
                cameras = await self._get_cameras()
                motion_sensors = await self._get_motion_sensors()

                for cam_id in cameras:
                    last_ts = self._last_alert_times.get(cam_id, 0)
                    if (now_ts - last_ts) < self._alert_cooldown:
                        continue  # In cooldown

                    # Controlla trigger movimento associato
                    cam_slug = cam_id.replace("camera.", "").lower()
                    motion_triggered = self._is_motion_triggered(cam_id, cam_slug, motion_sensors)

                    # Logica di scansione proattiva
                    should_analyze = (
                        motion_triggered
                        or in_night
                        or everyone_away  # Casa vuota → sempre attento
                    )

                    if should_analyze:
                        result = await self.analyze_single_camera(cam_id)
                        if result and result.get("threat_detected"):
                            self._last_alert_times[cam_id] = now_ts

                # Intervallo sleep adattivo
                if in_night:
                    sleep = 120       # notte: ogni 2 min
                elif everyone_away:
                    sleep = 180       # casa vuota: ogni 3 min
                else:
                    sleep = 600       # tutti a casa di giorno: ogni 10 min

                await asyncio.sleep(sleep)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                _LOGGER.error("HomeMind monitor errore: %s", exc)
                self.ai_status = "error"
                self._notify_sensors()
                await asyncio.sleep(60)

    def _is_motion_triggered(self, cam_id: str, cam_slug: str, motion_sensors: list[str]) -> bool:
        """
        Controlla se c'è movimento associato alla camera.

        Strategia di matching:
        1. Sensori configurati esplicitamente con nome simile alla camera
        2. Qualsiasi sensore movimento attivo (se in modalità notturna o tutti fuori)
        """
        for sensor_id in motion_sensors:
            state = self.hass.states.get(sensor_id)
            if not state or state.state != "on":
                continue
            # Match per slug: camera.ingresso ↔ binary_sensor.ingresso_motion
            sensor_slug = sensor_id.replace("binary_sensor.", "").lower()
            if (
                cam_slug in sensor_slug
                or sensor_slug.startswith(cam_slug)
                or any(part in sensor_slug for part in cam_slug.split("_") if len(part) > 3)
            ):
                return True
        return False

    # ------------------------------------------------------------------ #
    # Alert e notifiche
    # ------------------------------------------------------------------ #

    async def _send_alert(
        self,
        entity_id: str,
        camera_name: str,
        analysis: dict,
        image_bytes: bytes | None = None,
    ) -> None:
        """Invia alert di sicurezza via Telegram."""
        if not self.bot:
            return

        level = analysis.get("threat_level", "none")
        emoji = "🔴" if level == "high" else "🟠"
        everyone_away = self._everyone_away()
        context_note = " ⚠️ *CASA VUOTA*" if everyone_away else ""

        caption = (
            f"🚨 *ALLERTA — {camera_name}*{context_note}\n\n"
            f"{emoji} Rischio: *{level.upper()}*\n"
            f"🔍 {analysis.get('description', '')}\n"
        )
        if analysis.get("unusual"):
            unusual = analysis["unusual"]
            if unusual.lower() not in ("no", "nessuno", "nessuna"):
                caption += f"⚠️ Insolito: {unusual}\n"
        if analysis.get("summary"):
            caption += f"\n💬 _{analysis['summary']}_"
        if analysis.get("security_evaluation"):
            caption += f"\n\n🧠 *Valutazione AI:* {analysis['security_evaluation'][:200]}"

        if image_bytes:
            await self.bot.send_photo(image_bytes, caption)
        else:
            await self.bot.send_message(caption)

    # ------------------------------------------------------------------ #
    # Report mattutino
    # ------------------------------------------------------------------ #

    async def send_morning_report(self, force: bool = False) -> None:
        """Genera e invia il report mattutino sicurezza + stato casa."""
        events = self.night_events
        threats = [e for e in events if e.get("threat_level") in (THREAT_MEDIUM, THREAT_HIGH)]

        lines = [
            "🌅 *Report Notturno HomeMind AI*",
            f"_{datetime.now().strftime('%d/%m/%Y')}_\n",
            f"📊 Analisi totali: {len(events)}",
            f"🚨 Allerte sicurezza: {len(threats)}\n",
        ]

        if threats:
            lines.append("⚠️ *Eventi rilevati stanotte:*")
            for e in threats[:5]:
                level = e.get("threat_level", "")
                icon = "🔴" if level == "high" else "🟠"
                cam = e.get("camera_name") or e.get("camera", "").replace("camera.", "").replace("_", " ").title()
                lines.append(f"{icon} {e['time']} — {cam}: {e.get('summary', '')}")
        else:
            lines.append("✅ Nessun evento sospetto rilevato stanotte.")

        # Aggiungi contesto casa attuale
        from .ha_context import build_home_context
        ctx = build_home_context(self.hass, cameras=await self._get_cameras())
        lines.append("\n" + ctx[:600])  # Max 600 chars di contesto
        lines.append("\n_HomeMind AI con Gemini Vision_")

        report_text = "\n".join(lines)
        self.last_report = report_text
        self._notify_sensors()

        if self.bot:
            await self.bot.send_message(report_text)

        if not force:
            self.night_events.clear()
            self.alerts_tonight = 0
