"""Main coordinator for HomeMind AI — event-driven security monitoring."""

import logging
from datetime import timedelta, time as dt_time
from pathlib import Path

from homeassistant.components import camera
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .ai_analyzer import OllamaAnalyzer
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
    EVENT_HOMEMIND_ALERT,
    EVENT_HOMEMIND_REPORT,
)
from .telegram_notifier import TelegramNotifier

_LOGGER = logging.getLogger(__name__)

# Minimum seconds between analyses of the same entity (debounce)
DEBOUNCE_SECONDS = 30


class HomeMindCoordinator(DataUpdateCoordinator):
    """
    Coordinates all HomeMind AI logic:
    - Listens to camera/motion sensor state changes
    - During night hours: captures snapshots, analyzes with Ollama
    - Sends immediate Telegram alerts for high-priority events
    - Sends a morning report at a configurable time
    """

    def __init__(self, hass: HomeAssistant, entry) -> None:
        # Merge data and options so settings updated via Options UI take effect
        config = {**entry.data, **(entry.options or {})}

        self._ollama = OllamaAnalyzer(
            config.get(CONF_OLLAMA_URL, DEFAULT_OLLAMA_URL),
            config.get(CONF_OLLAMA_MODEL, DEFAULT_OLLAMA_MODEL),
        )

        telegram_token = config.get(CONF_TELEGRAM_TOKEN, "")
        telegram_chat = config.get(CONF_TELEGRAM_CHAT_ID, "")
        self._telegram = TelegramNotifier(telegram_token, telegram_chat) if telegram_token else None

        self._cameras: list[str] = config.get(CONF_CAMERAS) or []
        self._motion_sensors: list[str] = config.get(CONF_MOTION_SENSORS) or []

        self._night_start = self._parse_time(config.get(CONF_NIGHT_START, DEFAULT_NIGHT_START))
        self._night_end = self._parse_time(config.get(CONF_NIGHT_END, DEFAULT_NIGHT_END))
        self._report_time = self._parse_time(config.get(CONF_REPORT_TIME, DEFAULT_REPORT_TIME))

        # Runtime state
        self._tonight_events: list[dict] = []
        self._last_alert: dict | None = None
        self._last_report: dict | None = None
        self._ollama_online: bool = False
        self._processing: bool = False
        self._last_triggered: dict[str, float] = {}  # entity_id → timestamp

        # HA listener unsubscribe handles
        self._unsub_motion: callable | None = None
        self._unsub_report: callable | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
        )

    # ------------------------------------------------------------------
    # Setup / teardown
    # ------------------------------------------------------------------

    async def async_setup(self) -> None:
        """Register HA listeners for motion events and morning report."""
        entities_to_watch = list(set(self._motion_sensors + self._cameras))
        if entities_to_watch:
            self._unsub_motion = async_track_state_change_event(
                self.hass,
                entities_to_watch,
                self._handle_state_change,
            )
            _LOGGER.debug("HomeMind watching: %s", entities_to_watch)

        # Schedule morning report
        self._unsub_report = async_track_time_change(
            self.hass,
            self._scheduled_morning_report,
            hour=self._report_time.hour,
            minute=self._report_time.minute,
            second=0,
        )

        self._ollama_online = await self._ollama.check_connection()
        _LOGGER.info(
            "HomeMind AI ready — Ollama: %s, cameras: %d, sensors: %d",
            "online" if self._ollama_online else "OFFLINE",
            len(self._cameras),
            len(self._motion_sensors),
        )

    async def async_teardown(self) -> None:
        """Clean up HA listeners."""
        if self._unsub_motion:
            self._unsub_motion()
            self._unsub_motion = None
        if self._unsub_report:
            self._unsub_report()
            self._unsub_report = None

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    @callback
    def _handle_state_change(self, event) -> None:
        """Callback when a watched entity changes state."""
        new_state = event.data.get("new_state")
        if not new_state:
            return

        entity_id: str = event.data.get("entity_id", "")
        state_value: str = new_state.state

        # Determine if this is a trigger
        is_trigger = False
        if "binary_sensor" in entity_id and state_value == "on":
            is_trigger = True
        elif "camera" in entity_id and state_value in ("recording", "motion"):
            is_trigger = True

        if not is_trigger:
            return

        if not self._is_night_time():
            return

        # Debounce: ignore repeated triggers within DEBOUNCE_SECONDS
        now_ts = dt_util.now().timestamp()
        last_ts = self._last_triggered.get(entity_id, 0)
        if now_ts - last_ts < DEBOUNCE_SECONDS:
            return
        self._last_triggered[entity_id] = now_ts

        # Kick off async processing (non-blocking)
        self.hass.async_create_task(self._process_event(entity_id))

    async def _process_event(self, entity_id: str) -> None:
        """Capture snapshot, run AI analysis, notify if important."""
        if self._processing:
            _LOGGER.debug("Already processing an event, skipping %s", entity_id)
            return

        self._processing = True
        try:
            camera_entity = self._resolve_camera(entity_id)
            if not camera_entity:
                _LOGGER.warning("No camera found for entity %s — add cameras in config", entity_id)
                return

            # Capture snapshot
            try:
                img = await camera.async_get_image(self.hass, camera_entity)
                image_bytes = img.content
            except Exception as err:
                _LOGGER.error("Snapshot failed for %s: %s", camera_entity, err)
                return

            # AI analysis (with fallback if Ollama is offline)
            if self._ollama_online:
                analysis = await self._ollama.analyze_image(image_bytes)
            else:
                analysis = None

            if analysis is None:
                # Fallback: treat every night motion as medium importance
                analysis = {
                    "important": True,
                    "description": f"Movimento rilevato ({entity_id})",
                    "priority": "medium",
                    "tags": ["motion"],
                }

            if not analysis.get("important", False):
                _LOGGER.debug("Event not important, skipping: %s", analysis.get("description"))
                return

            event_time = dt_util.now()
            filename = f"{event_time.strftime('%Y%m%d_%H%M%S')}_{entity_id.replace('.', '_')}.jpg"
            snapshot_url = f"/local/homemind_snapshots/{filename}"

            event_record = {
                "time": event_time.strftime("%H:%M"),
                "timestamp": event_time.isoformat(),
                "entity": entity_id,
                "camera": camera_entity,
                "description": analysis["description"],
                "priority": analysis["priority"],
                "tags": analysis["tags"],
                "snapshot_url": snapshot_url,
            }

            # Save snapshot to www/homemind_snapshots/
            await self._save_snapshot(image_bytes, filename)

            self._tonight_events.append(event_record)
            self._last_alert = event_record

            # Immediate Telegram alert for HIGH priority
            if analysis["priority"] == "high" and self._telegram:
                caption = (
                    f"🚨 <b>ALLERTA SICUREZZA — HomeMind AI</b>\n"
                    f"🕐 {event_time.strftime('%H:%M')}\n"
                    f"📷 {camera_entity}\n"
                    f"📝 {analysis['description']}\n"
                    f"🏷 {', '.join(analysis['tags'])}"
                )
                await self._telegram.send_photo(image_bytes, caption)

            # Fire HA bus event (can be used in automations)
            self.hass.bus.async_fire(EVENT_HOMEMIND_ALERT, {
                "entity_id": entity_id,
                "camera": camera_entity,
                "description": analysis["description"],
                "priority": analysis["priority"],
                "tags": analysis["tags"],
                "snapshot_url": snapshot_url,
                "timestamp": event_time.isoformat(),
            })

            self.async_set_updated_data(self._build_state())
            _LOGGER.info("HomeMind alert [%s]: %s", analysis["priority"], analysis["description"])

        finally:
            self._processing = False

    # ------------------------------------------------------------------
    # Morning report
    # ------------------------------------------------------------------

    @callback
    def _scheduled_morning_report(self, now) -> None:
        """Callback at morning report time."""
        self.hass.async_create_task(self._send_morning_report())

    async def _send_morning_report(self) -> None:
        """Generate and deliver the morning report, then reset nightly log."""
        events = list(self._tonight_events)
        self._tonight_events = []

        report_text = await self._ollama.generate_night_report(events)
        report_time = dt_util.now()

        self._last_report = {
            "time": report_time.isoformat(),
            "text": report_text,
            "event_count": len(events),
        }

        if self._telegram:
            message = (
                f"🏠 <b>HomeMind AI — Report Notturno</b>\n"
                f"📅 {report_time.strftime('%d/%m/%Y')} — {len(events)} eventi rilevati\n\n"
                f"{report_text}"
            )
            await self._telegram.send_message(message)

        self.hass.bus.async_fire(EVENT_HOMEMIND_REPORT, {
            "event_count": len(events),
            "report": report_text,
            "timestamp": report_time.isoformat(),
        })

        self.async_set_updated_data(self._build_state())
        _LOGGER.info("Morning report sent (%d events)", len(events))

    # ------------------------------------------------------------------
    # Public service methods
    # ------------------------------------------------------------------

    async def async_trigger_report(self) -> None:
        """Manually trigger the morning report (HA service)."""
        await self._send_morning_report()

    async def async_analyze_camera(self, camera_entity_id: str) -> dict:
        """Manually analyze a camera snapshot (HA service)."""
        try:
            img = await camera.async_get_image(self.hass, camera_entity_id)
            result = await self._ollama.analyze_image(img.content)
            return result or {"error": "No result from Ollama"}
        except Exception as err:
            return {"error": str(err)}

    def clear_alerts(self) -> None:
        """Clear tonight's alert log (HA service)."""
        self._tonight_events = []
        self._last_alert = None
        self.async_set_updated_data(self._build_state())

    # ------------------------------------------------------------------
    # Coordinator update loop (periodic health check)
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict:
        """Periodic refresh: check Ollama connectivity."""
        try:
            self._ollama_online = await self._ollama.check_connection()
        except Exception as err:
            raise UpdateFailed(f"Health check failed: {err}") from err
        return self._build_state()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_state(self) -> dict:
        """Assemble the current state dict exposed to sensors."""
        return {
            "status": "online",
            "ollama_online": self._ollama_online,
            "is_night_mode": self._is_night_time(),
            "alerts_tonight": len(self._tonight_events),
            "last_alert": self._last_alert,
            "last_report": self._last_report,
            "cameras": self._cameras,
            "motion_sensors": self._motion_sensors,
        }

    def _is_night_time(self) -> bool:
        """Return True if current time falls in the configured night window."""
        now = dt_util.now().time().replace(second=0, microsecond=0)
        start = self._night_start
        end = self._night_end
        if start > end:  # crosses midnight (e.g. 22:00 → 06:00)
            return now >= start or now < end
        return start <= now < end

    def _resolve_camera(self, entity_id: str) -> str | None:
        """
        Find the best camera entity for a given trigger entity.
        - If entity_id is already a camera, return it directly.
        - Otherwise try to match by name prefix with registered cameras.
        - Fall back to the first registered camera.
        """
        if entity_id.startswith("camera."):
            return entity_id

        # Try name-based match: binary_sensor.front_yard_motion → camera.front_yard
        name = (
            entity_id
            .replace("binary_sensor.", "")
            .replace("_motion", "")
            .replace("_detect", "")
            .replace("_sensor", "")
        )
        for cam in self._cameras:
            cam_name = cam.replace("camera.", "")
            if name in cam_name or cam_name in name:
                return cam

        return self._cameras[0] if self._cameras else None

    @staticmethod
    def _parse_time(time_str: str) -> dt_time:
        """Parse 'HH:MM' or 'HH:MM:SS' into a time object."""
        parts = time_str.split(":")
        return dt_time(int(parts[0]), int(parts[1]))

    async def _save_snapshot(self, image_bytes: bytes, filename: str) -> None:
        """Save snapshot JPEG to /config/www/homemind_snapshots/."""
        try:
            www_dir = Path(self.hass.config.path("www/homemind_snapshots"))
            www_dir.mkdir(parents=True, exist_ok=True)
            filepath = www_dir / filename
            with open(filepath, "wb") as fh:
                fh.write(image_bytes)
            _LOGGER.debug("Snapshot saved: %s", filepath)
        except Exception as err:
            _LOGGER.error("Could not save snapshot: %s", err)
