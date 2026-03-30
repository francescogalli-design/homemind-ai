"""HomeMind AI — sicurezza camera con Gemini Vision per Home Assistant."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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
    SERVICE_ANALYZE_CAMERA,
    SERVICE_GENERATE_REPORT,
    SERVICE_CLEAR_ALERTS,
    THREAT_MEDIUM,
    THREAT_HIGH,
)
from .gemini_vision import analyze_camera_image

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configura HomeMind AI da una config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = HomeMindCoordinator(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Registra servizi HA
    async def handle_analyze_camera(call: ServiceCall) -> None:
        camera_entity = call.data.get("entity_id", "")
        if not camera_entity:
            _LOGGER.warning("analyze_camera: entity_id mancante")
            return
        await coordinator.analyze_single_camera(camera_entity)

    async def handle_generate_report(call: ServiceCall) -> None:
        await coordinator.send_morning_report(force=True)

    async def handle_clear_alerts(call: ServiceCall) -> None:
        coordinator.night_events.clear()
        coordinator.alerts_tonight = 0
        coordinator.last_alert = ""
        _LOGGER.info("HomeMind AI: coda alert svuotata")

    hass.services.async_register(DOMAIN, SERVICE_ANALYZE_CAMERA, handle_analyze_camera)
    hass.services.async_register(DOMAIN, SERVICE_GENERATE_REPORT, handle_generate_report)
    hass.services.async_register(DOMAIN, SERVICE_CLEAR_ALERTS, handle_clear_alerts)

    # Avvia il loop di monitoraggio
    coordinator.start_monitoring()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Rimuove HomeMind AI."""
    coordinator: HomeMindCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
    coordinator.stop_monitoring()

    hass.services.async_remove(DOMAIN, SERVICE_ANALYZE_CAMERA)
    hass.services.async_remove(DOMAIN, SERVICE_GENERATE_REPORT)
    hass.services.async_remove(DOMAIN, SERVICE_CLEAR_ALERTS)

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class HomeMindCoordinator:
    """Coordinatore principale di HomeMind AI."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._task: asyncio.Task | None = None

        # Configurazione
        self.api_key: str = entry.data.get(CONF_GEMINI_API_KEY, "")
        self.gemini_model: str = entry.data.get(CONF_GEMINI_MODEL, DEFAULT_GEMINI_MODEL)
        self.telegram_token: str = entry.data.get(CONF_TELEGRAM_TOKEN, "")
        self.telegram_chat_id: str = entry.data.get(CONF_TELEGRAM_CHAT_ID, "")
        self.configured_cameras: list[str] = entry.data.get(CONF_CAMERAS, [])
        self.night_start: int = entry.data.get(CONF_NIGHT_START, DEFAULT_NIGHT_START)
        self.night_end: int = entry.data.get(CONF_NIGHT_END, DEFAULT_NIGHT_END)
        self.morning_report_hour: int = entry.data.get(CONF_MORNING_REPORT_HOUR, DEFAULT_MORNING_REPORT_HOUR)

        # Stato sensori
        self.ai_status: str = "online"
        self.night_mode: str = "inactive"
        self.alerts_tonight: int = 0
        self.last_alert: str = ""
        self.last_report: str = ""

        # Registro eventi notturni
        self.night_events: list[dict] = []
        self._last_alert_times: dict[str, float] = {}
        self._alert_cooldown: int = 300  # 5 minuti

        # Callback per aggiornamento sensori
        self._sensor_callbacks: list = []

    def register_sensor_callback(self, callback) -> None:
        self._sensor_callbacks.append(callback)

    def _notify_sensors(self) -> None:
        for cb in self._sensor_callbacks:
            cb()

    def start_monitoring(self) -> None:
        """Avvia il loop di monitoraggio in background."""
        self._task = self.hass.loop.create_task(self._monitor_loop())
        _LOGGER.info("HomeMind AI: monitoraggio avviato")

    def stop_monitoring(self) -> None:
        if self._task:
            self._task.cancel()
            _LOGGER.info("HomeMind AI: monitoraggio fermato")

    def _is_night_window(self) -> bool:
        h = datetime.now().hour
        if self.night_start > self.night_end:
            return h >= self.night_start or h < self.night_end
        return self.night_start <= h < self.night_end

    async def _get_cameras(self) -> list[str]:
        """Restituisce le camere da monitorare."""
        if self.configured_cameras:
            return self.configured_cameras
        # Autodetect: tutte le camere in HA
        return [
            eid for eid in self.hass.states.async_entity_ids("camera")
        ]

    async def _get_camera_snapshot(self, entity_id: str) -> bytes | None:
        """Scarica snapshot JPEG dalla camera usando l'API nativa di HA."""
        try:
            from homeassistant.components.camera import async_get_image
            image = await async_get_image(self.hass, entity_id, timeout=10)
            return image.content
        except Exception as exc:
            _LOGGER.error("Errore snapshot %s: %s", entity_id, exc)
            return None

    async def analyze_single_camera(self, entity_id: str) -> dict | None:
        """Analizza una singola camera e invia alert se necessario."""
        image_bytes = await self._get_camera_snapshot(entity_id)
        if not image_bytes:
            return None

        session = async_get_clientsession(self.hass)
        camera_name = entity_id.replace("camera.", "").replace("_", " ").title()

        analysis = await analyze_camera_image(
            session=session,
            api_key=self.api_key,
            image_bytes=image_bytes,
            camera_name=camera_name,
            model=self.gemini_model,
        )

        # Aggiorna ultimo alert
        if analysis.get("threat_detected"):
            self.alerts_tonight += 1
            self.last_alert = f"{camera_name}: {analysis.get('summary', '')}"
            self.night_events.append({
                "time": datetime.now().strftime("%H:%M"),
                "camera": entity_id,
                "threat_level": analysis["threat_level"],
                "summary": analysis.get("summary", ""),
            })
            self._notify_sensors()

            # Invia alert Telegram
            if analysis["threat_level"] in (THREAT_MEDIUM, THREAT_HIGH):
                await self._send_telegram_alert(entity_id, analysis, image_bytes)

        # Spara evento HA per automazioni
        self.hass.bus.async_fire(
            "homemind_ai_alert",
            {
                "entity_id": entity_id,
                "camera": camera_name,
                "priority": "high" if analysis["threat_level"] in (THREAT_MEDIUM, THREAT_HIGH) else "low",
                "threat_level": analysis["threat_level"],
                "description": analysis.get("description", ""),
                "summary": analysis.get("summary", ""),
                "snapshot_url": f"/api/camera_proxy/{entity_id}",
            },
        )

        _LOGGER.info("HomeMind [%s] rischio=%s | %s", entity_id, analysis["threat_level"], analysis.get("summary", "")[:80])
        return analysis

    async def _monitor_loop(self) -> None:
        """Loop principale di monitoraggio camere."""
        morning_report_sent_date: str = ""

        while True:
            try:
                now = datetime.now()
                in_night = self._is_night_window()

                # Aggiorna stato night_mode
                new_mode = "active" if in_night else "inactive"
                if self.night_mode != new_mode:
                    self.night_mode = new_mode
                    self._notify_sensors()

                # Report mattutino
                today = now.strftime("%Y-%m-%d")
                if now.hour == self.morning_report_hour and morning_report_sent_date != today:
                    await self.send_morning_report()
                    morning_report_sent_date = today

                # Analisi camere
                cameras = await self._get_cameras()
                states = self.hass.states

                for cam_id in cameras:
                    now_ts = now.timestamp()
                    last_ts = self._last_alert_times.get(cam_id, 0)
                    if (now_ts - last_ts) < self._alert_cooldown:
                        continue

                    # Controlla sensori movimento abbinati
                    cam_slug = cam_id.replace("camera.", "")
                    motion_triggered = any(
                        cam_slug in eid and states.get(eid) and states.get(eid).state == "on"
                        for eid in self.hass.states.async_entity_ids("binary_sensor")
                        if "motion" in eid or "movimento" in eid
                    )

                    if motion_triggered or in_night:
                        result = await self.analyze_single_camera(cam_id)
                        if result and result.get("threat_detected"):
                            self._last_alert_times[cam_id] = now_ts

                sleep = 120 if in_night else 300
                await asyncio.sleep(sleep)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                _LOGGER.error("HomeMind monitor errore: %s", exc)
                await asyncio.sleep(60)

    async def send_morning_report(self, force: bool = False) -> None:
        """Genera e invia il report mattutino via Telegram."""
        if not self.telegram_token or not self.telegram_chat_id:
            _LOGGER.debug("Telegram non configurato, skip report")
            return

        events = self.night_events
        threats = [e for e in events if e["threat_level"] in (THREAT_MEDIUM, THREAT_HIGH)]

        lines = [
            "🌅 *Report Notturno HomeMind AI*",
            f"_{datetime.now().strftime('%d/%m/%Y')}_\n",
            f"📊 Analisi totali: {len(events)}",
            f"🚨 Allerte sicurezza: {len(threats)}\n",
        ]

        if threats:
            lines.append("⚠️ *Eventi rilevati:*")
            for e in threats[:5]:
                emoji = "🔴" if e["threat_level"] == "high" else "🟠"
                cam = e["camera"].replace("camera.", "").replace("_", " ").title()
                lines.append(f"{emoji} {e['time']} — {cam}: {e['summary']}")
        else:
            lines.append("✅ Nessun evento sospetto rilevato stanotte.")

        lines.append("\n_HomeMind AI con Gemini Vision_")

        report_text = "\n".join(lines)
        self.last_report = report_text
        self._notify_sensors()

        await self._send_telegram_message(report_text)

        if not force:
            self.night_events.clear()
            self.alerts_tonight = 0

    async def _send_telegram_alert(self, entity_id: str, analysis: dict, image_bytes: bytes | None = None) -> None:
        if not self.telegram_token or not self.telegram_chat_id:
            return

        emoji = "🔴" if analysis["threat_level"] == "high" else "🟠"
        cam = entity_id.replace("camera.", "").replace("_", " ").title()
        text = (
            f"🚨 *ALLERTA — {cam}*\n\n"
            f"{emoji} Rischio: *{analysis['threat_level'].upper()}*\n"
            f"🔍 {analysis.get('description', '')}\n"
        )
        if analysis.get("unusual"):
            text += f"⚠️ Insolito: {analysis['unusual']}\n"
        if analysis.get("summary"):
            text += f"\n💬 _{analysis['summary']}_"

        if image_bytes:
            await self._send_telegram_photo(image_bytes, text)
        else:
            await self._send_telegram_message(text)

    async def _send_telegram_message(self, text: str) -> None:
        try:
            session = async_get_clientsession(self.hass)
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            await session.post(url, json={
                "chat_id": self.telegram_chat_id,
                "text": text,
                "parse_mode": "Markdown",
            })
        except Exception as exc:
            _LOGGER.error("Telegram sendMessage errore: %s", exc)

    async def _send_telegram_photo(self, image_bytes: bytes, caption: str) -> None:
        try:
            session = async_get_clientsession(self.hass)
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendPhoto"
            data = aiohttp.FormData()
            data.add_field("chat_id", self.telegram_chat_id)
            data.add_field("caption", caption)
            data.add_field("parse_mode", "Markdown")
            data.add_field("photo", image_bytes, filename="snapshot.jpg", content_type="image/jpeg")
            await session.post(url, data=data)
        except Exception as exc:
            _LOGGER.error("Telegram sendPhoto errore: %s", exc)
