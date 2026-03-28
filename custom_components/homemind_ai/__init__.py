"""HomeMind AI — local AI security monitoring for Home Assistant."""

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    SERVICE_ANALYZE_CAMERA,
    SERVICE_CLEAR_ALERTS,
    SERVICE_GENERATE_REPORT,
    SERVICE_WHAT_IS_HAPPENING,
)
from .coordinator import HomeMindCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HomeMind AI from a config entry."""
    coordinator = HomeMindCoordinator(hass, entry)

    try:
        await coordinator.async_setup()
        await coordinator.async_config_entry_first_refresh()
    except Exception as ex:
        _LOGGER.error("HomeMind AI setup failed: %s", ex)
        raise ConfigEntryNotReady(f"Setup error: {ex}") from ex

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # --- Register HA services ---

    async def _handle_generate_report(call: ServiceCall) -> None:
        """Service: generate and send morning report now."""
        for coord in hass.data[DOMAIN].values():
            await coord.async_trigger_report()

    async def _handle_analyze_camera(call: ServiceCall) -> None:
        """Service: analyze a specific camera snapshot on demand."""
        camera_entity = call.data["camera_entity"]
        for coord in hass.data[DOMAIN].values():
            result = await coord.async_analyze_camera(camera_entity)
            _LOGGER.info("Manual analysis of %s: %s", camera_entity, result)

    async def _handle_clear_alerts(call: ServiceCall) -> None:
        """Service: clear tonight's alert queue."""
        for coord in hass.data[DOMAIN].values():
            coord.clear_alerts()

    if not hass.services.has_service(DOMAIN, SERVICE_GENERATE_REPORT):
        hass.services.async_register(
            DOMAIN, SERVICE_GENERATE_REPORT, _handle_generate_report
        )

    if not hass.services.has_service(DOMAIN, SERVICE_ANALYZE_CAMERA):
        hass.services.async_register(
            DOMAIN,
            SERVICE_ANALYZE_CAMERA,
            _handle_analyze_camera,
            schema=vol.Schema({vol.Required("camera_entity"): cv.entity_id}),
        )

    if not hass.services.has_service(DOMAIN, SERVICE_CLEAR_ALERTS):
        hass.services.async_register(
            DOMAIN, SERVICE_CLEAR_ALERTS, _handle_clear_alerts
        )

    async def _handle_what_is_happening(call: ServiceCall) -> None:
        """Service: snapshot all cameras and describe current scene."""
        for coord in hass.data[DOMAIN].values():
            await coord.async_what_is_happening()

    if not hass.services.has_service(DOMAIN, SERVICE_WHAT_IS_HAPPENING):
        hass.services.async_register(
            DOMAIN, SERVICE_WHAT_IS_HAPPENING, _handle_what_is_happening
        )

    # Reload integration when options are updated via UI
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    _LOGGER.info("HomeMind AI integration loaded successfully")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload HomeMind AI config entry."""
    coordinator: HomeMindCoordinator | None = hass.data[DOMAIN].get(entry.entry_id)
    if coordinator:
        await coordinator.async_teardown()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        # Remove services if no more instances
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_GENERATE_REPORT)
            hass.services.async_remove(DOMAIN, SERVICE_ANALYZE_CAMERA)
            hass.services.async_remove(DOMAIN, SERVICE_CLEAR_ALERTS)
            hass.services.async_remove(DOMAIN, SERVICE_WHAT_IS_HAPPENING)

    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update by reloading the entry."""
    await hass.config_entries.async_reload(entry.entry_id)
