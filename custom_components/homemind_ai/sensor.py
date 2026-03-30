"""Sensori HomeMind AI per Home Assistant."""
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
        HomeMindSensor(coordinator, "ai_status", "HomeMind AI Status", "mdi:robot"),
        HomeMindSensor(coordinator, "night_mode", "HomeMind Night Mode", "mdi:weather-night"),
        HomeMindSensor(coordinator, "alerts_tonight", "HomeMind Alerts Tonight", "mdi:alert", unit="alerts"),
        HomeMindSensor(coordinator, "last_alert", "HomeMind Last Alert", "mdi:bell-alert"),
        HomeMindSensor(coordinator, "last_report", "HomeMind Last Report", "mdi:file-document"),
        HomeMindSensor(coordinator, "last_ai_answer", "HomeMind Last AI Answer", "mdi:brain"),
    ]

    async_add_entities(entities)


class HomeMindSensor(SensorEntity):
    """Sensore HomeMind AI."""

    def __init__(
        self,
        coordinator,
        sensor_type: str,
        name: str,
        icon: str,
        unit: str | None = None,
    ) -> None:
        self._coordinator = coordinator
        self._sensor_type = sensor_type
        self._attr_name = name
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        self._attr_unique_id = f"homemind_{sensor_type}"
        coordinator.register_sensor_callback(self._handle_coordinator_update)

    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self):
        return getattr(self._coordinator, self._sensor_type, None)
