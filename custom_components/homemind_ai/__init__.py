"""
HomeMind AI Assistant - Home Assistant Custom Integration
"""

import asyncio
import logging
from typing import Dict, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, CONF_HA_URL, CONF_HA_TOKEN
from .coordinator import HomeMindCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HomeMind AI from a config entry."""
    _LOGGER.info("Setting up HomeMind AI integration")
    
    try:
        # Create coordinator
        coordinator = HomeMindCoordinator(hass, entry)
        
        # Store coordinator
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
        
        # Setup platforms (sensors, switches, etc.)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        
        # Setup services
        await _async_setup_services(hass, coordinator)
        
        _LOGGER.info("HomeMind AI integration setup completed")
        return True
        
    except Exception as ex:
        _LOGGER.error("Failed to set up HomeMind AI: %s", ex)
        raise ConfigEntryNotReady from ex


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload HomeMind AI config entry."""
    _LOGGER.info("Unloading HomeMind AI integration")
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Remove coordinator
        hass.data[DOMAIN].pop(entry.entry_id)
        
        # Remove services
        _async_remove_services(hass)
        
        _LOGGER.info("HomeMind AI integration unloaded successfully")
    
    return unload_ok


async def _async_setup_services(hass: HomeAssistant, coordinator: HomeMindCoordinator):
    """Set up HomeMind AI services."""
    
    async def async_chat_service(call: Dict[str, Any]) -> Dict[str, Any]:
        """Handle chat service call."""
        message = call.data.get("message", "")
        user_id = call.data.get("user_id", "default")
        
        if not message:
            return {"error": "Message is required"}
        
        try:
            response = await coordinator.process_message(message, user_id)
            return {"response": response}
        except Exception as ex:
            _LOGGER.error("Error in chat service: %s", ex)
            return {"error": str(ex)}
    
    # Register chat service
    hass.services.async_register(DOMAIN, "chat", async_chat_service)
    _LOGGER.info("Registered chat service")


def _async_remove_services(hass: HomeAssistant):
    """Remove HomeMind AI services."""
    hass.services.async_remove(DOMAIN, "chat")
    _LOGGER.info("Removed chat service")
