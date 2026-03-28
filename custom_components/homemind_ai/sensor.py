"""Sensor platform for HomeMind AI."""

import logging

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HomeMindCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HomeMind AI sensors."""
    coordinator: HomeMindCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        HomeMindStatusSensor(coordinator, entry.entry_id),
        HomeMindNightModeSensor(coordinator, entry.entry_id),
        HomeMindAlertsCountSensor(coordinator, entry.entry_id),
        HomeMindLastAlertSensor(coordinator, entry.entry_id),
        HomeMindLastReportSensor(coordinator, entry.entry_id),
        HomeMindCurrentSceneSensor(coordinator, entry.entry_id),
    ])


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class _HomeMindBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for all HomeMind sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HomeMindCoordinator, entry_id: str, key: str) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._key = key
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{key}"

    @property
    def _data(self) -> dict:
        return self.coordinator.data or {}


# ---------------------------------------------------------------------------
# Sensor: Status / Ollama connectivity
# ---------------------------------------------------------------------------

class HomeMindStatusSensor(_HomeMindBaseSensor):
    """Overall integration status."""

    _attr_icon = "mdi:brain"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id, "status")
        self._attr_name = "HomeMind AI Status"

    @property
    def native_value(self) -> str:
        ollama = self._data.get("ollama_online", False)
        return "online" if ollama else "ollama_offline"

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "ollama_online": self._data.get("ollama_online"),
            "cameras": self._data.get("cameras", []),
            "motion_sensors": self._data.get("motion_sensors", []),
        }


# ---------------------------------------------------------------------------
# Sensor: Night mode
# ---------------------------------------------------------------------------

class HomeMindNightModeSensor(_HomeMindBaseSensor):
    """Whether night monitoring is currently active."""

    _attr_icon = "mdi:weather-night"

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id, "night_mode")
        self._attr_name = "HomeMind Night Mode"

    @property
    def native_value(self) -> str:
        return "active" if self._data.get("is_night_mode", False) else "inactive"


# ---------------------------------------------------------------------------
# Sensor: Alerts count tonight
# ---------------------------------------------------------------------------

class HomeMindAlertsCountSensor(_HomeMindBaseSensor):
    """Count of relevant events captured tonight."""

    _attr_icon = "mdi:shield-alert"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "events"

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id, "alerts_count")
        self._attr_name = "HomeMind Alerts Tonight"

    @property
    def native_value(self) -> int:
        return int(self._data.get("alerts_tonight", 0))


# ---------------------------------------------------------------------------
# Sensor: Last alert description
# ---------------------------------------------------------------------------

class HomeMindLastAlertSensor(_HomeMindBaseSensor):
    """Description of the most recent security alert."""

    _attr_icon = "mdi:alert-circle"

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id, "last_alert")
        self._attr_name = "HomeMind Last Alert"

    @property
    def native_value(self) -> str:
        alert = self._data.get("last_alert")
        if alert:
            return alert.get("description", "nessuno")[:255]
        return "nessuno"

    @property
    def extra_state_attributes(self) -> dict:
        alert = self._data.get("last_alert")
        if not alert:
            return {}
        return {
            "time": alert.get("time"),
            "priority": alert.get("priority"),
            "camera": alert.get("camera"),
            "tags": alert.get("tags", []),
            "snapshot_url": alert.get("snapshot_url"),
            "timestamp": alert.get("timestamp"),
        }


# ---------------------------------------------------------------------------
# Sensor: Last morning report
# ---------------------------------------------------------------------------

class HomeMindLastReportSensor(_HomeMindBaseSensor):
    """Summary of the last morning report."""

    _attr_icon = "mdi:file-document-outline"

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id, "last_report")
        self._attr_name = "HomeMind Last Report"

    @property
    def native_value(self) -> str:
        report = self._data.get("last_report")
        if report:
            return f"{report.get('event_count', 0)} eventi — {report.get('time', '')[:10]}"
        return "nessun report"

    @property
    def extra_state_attributes(self) -> dict:
        report = self._data.get("last_report")
        if not report:
            return {}
        return {
            "report_text": report.get("text", "")[:1024],
            "event_count": report.get("event_count", 0),
            "generated_at": report.get("time"),
        }


# ---------------------------------------------------------------------------
# Sensor: Current scene (what_is_happening result)
# ---------------------------------------------------------------------------

class HomeMindCurrentSceneSensor(_HomeMindBaseSensor):
    """Live description of all cameras — updated by the what_is_happening service."""

    _attr_icon = "mdi:eye"

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id, "current_scene")
        self._attr_name = "HomeMind Current Scene"

    @property
    def native_value(self) -> str:
        scene = self._data.get("current_scene")
        if scene:
            # Return first line as state value (max 255 chars)
            first_line = scene.split("\n")[0]
            return first_line[:255]
        return "non interrogato"

    @property
    def extra_state_attributes(self) -> dict:
        scene = self._data.get("current_scene")
        if not scene:
            return {}
        return {"full_description": scene[:2000]}
