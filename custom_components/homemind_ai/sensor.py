"""Sensor platform for HomeMind AI Assistant."""

import logging
from typing import Dict, Any

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class HomeMindStatusSensor(SensorEntity, CoordinatorEntity):
    """Sensor for HomeMind AI status."""

    def __init__(self, hass: HomeAssistant, coordinator, entry_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.hass = hass
        self._entry_id = entry_id
        self._attr_name = "HomeMind AI Status"
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_status"
        self._attr_icon = "mdi:brain"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get("status", "unknown")
        return "unknown"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        if self.coordinator.data:
            return {
                "last_update": self.coordinator.data.get("last_update"),
                "ai_providers": self.coordinator.data.get("ai_providers", []),
                "active_conversations": self.coordinator.data.get("active_conversations", 0),
                "proactive_notifications": self.coordinator.data.get("proactive_notifications", False),
                "api_url": self.coordinator.data.get("api_url"),
            }
        return {}


class HomeMindConversationSensor(SensorEntity, CoordinatorEntity):
    """Sensor for active conversations."""

    def __init__(self, hass: HomeAssistant, coordinator, entry_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.hass = hass
        self._entry_id = entry_id
        self._attr_name = "HomeMind AI Active Conversations"
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_conversations"
        self._attr_icon = "mdi:forum"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_native_unit_of_measurement = "conversations"

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get("active_conversations", 0)
        return 0
