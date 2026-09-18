"""Tests for the Weather Platform integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_URL, Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.unit_system import METRIC_SYSTEM

from .api import WeatherPlatformApiClient
from .const import (
    API_UNIT_SYSTEM_IMPERIAL,
    API_UNIT_SYSTEM_METRIC,
)
from .coordinator import WeatherPlatformDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

PLATFORMS = (
    Platform.BINARY_SENSOR,
    Platform.EVENT,
    Platform.SENSOR,
    Platform.WEATHER,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[WeatherPlatformDataUpdateCoordinator],
) -> bool:
    """Set up Weather Platform from a config entry."""
    unit_system = (
        API_UNIT_SYSTEM_METRIC
        if hass.config.units is METRIC_SYSTEM
        else API_UNIT_SYSTEM_IMPERIAL
    )
    client = WeatherPlatformApiClient(
        base_url=entry.data[CONF_URL],
        session=async_get_clientsession(hass),
    )
    coordinator = WeatherPlatformDataUpdateCoordinator(
        hass=hass,
        config_entry=entry,
        client=client,
        unit_system=unit_system,
    )

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[WeatherPlatformDataUpdateCoordinator],
) -> bool:
    """Unload a Weather Platform config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
