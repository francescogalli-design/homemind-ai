"""Sensor platform for HomeMind AI."""

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class HomeMindStatusSensor(CoordinatorEntity, SensorEntity):
    """Sensor for HomeMind AI status."""

    def __init__(self, coordinator, entry_id):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = "HomeMind AI Status"
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_status"
        self._attr_icon = "mdi:brain"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get("status", "unknown")
        return "unknown"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.coordinator.data:
            return {
                "last_update": self.coordinator.data.get("last_update"),
                "api_url": self.coordinator.data.get("api_url"),
            }
        return {}
