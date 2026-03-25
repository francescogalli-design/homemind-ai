"""Coordinator for HomeMind AI."""

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class HomeMindCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator for HomeMind AI."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        """Initialize."""
        self.api_url = entry.data.get("api_url", "http://localhost:8080")
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )

    async def _async_update_data(self):
        """Update data via API."""
        try:
            return {
                "status": "online",
                "last_update": self.hass.config.time_zone_now().isoformat(),
                "api_url": self.api_url,
            }
        except Exception as exception:
            raise UpdateFailed(f"Error communicating with API: {exception}")
