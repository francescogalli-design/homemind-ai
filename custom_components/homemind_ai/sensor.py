"""Sensori HomeMind AI — stato e debug per Home Assistant."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        # Stato operativo
        HomeMindSensor(coordinator, "ai_status",       "HomeMind Status",         "mdi:robot",             None),
        HomeMindSensor(coordinator, "night_mode",      "HomeMind Night Mode",     "mdi:weather-night",     None),
        HomeMindSensor(coordinator, "alerts_tonight",  "HomeMind Alerts Tonight", "mdi:shield-alert",      "alerts"),
        HomeMindSensor(coordinator, "last_alert",      "HomeMind Last Alert",     "mdi:bell-alert",        None),
        HomeMindSensor(coordinator, "last_report",     "HomeMind Last Report",    "mdi:file-document",     None),
        HomeMindSensor(coordinator, "last_ai_answer",  "HomeMind Last Answer",    "mdi:brain",             None),
        # Debug / diagnostica
        HomeMindSensor(coordinator, "api_health",      "HomeMind API Health",     "mdi:api",               None),
        HomeMindSensor(coordinator, "last_error",      "HomeMind Last Error",     "mdi:alert-circle",      None),
        HomeMindSensor(coordinator, "cameras_online",  "HomeMind Cameras Online", "mdi:cctv",              "cameras"),
        HomeMindSensor(coordinator, "bot_status",      "HomeMind Bot Status",     "mdi:send",              None),
        HomeMindSensor(coordinator, "internet_status", "HomeMind Internet",        "mdi:web",               None),
        # ALPR
        HomeMindSensor(coordinator, "last_plate",      "HomeMind Ultima Targa",   "mdi:car",               None),
        HomeMindSensor(coordinator, "plates_today",    "HomeMind Targhe Oggi",    "mdi:counter",           "targhe"),
    ]

    async_add_entities(entities)


class HomeMindSensor(SensorEntity):
    """Sensore HomeMind AI generico."""

    def __init__(
        self,
        coordinator,
        sensor_type: str,
        name: str,
        icon: str,
        unit: str | None,
    ) -> None:
        self._coordinator = coordinator
        self._sensor_type = sensor_type
        self._attr_name = name
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        self._attr_unique_id = f"homemind_{sensor_type}"
        coordinator.register_sensor_callback(self._handle_update)

    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self):
        return getattr(self._coordinator, self._sensor_type, None)
