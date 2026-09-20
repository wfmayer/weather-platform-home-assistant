"""Weather Platform integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import webhook
from homeassistant.const import CONF_URL, Platform
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.util.unit_system import METRIC_SYSTEM

from .api import WeatherPlatformApiClient
from .const import (
    API_UNIT_SYSTEM_IMPERIAL,
    API_UNIT_SYSTEM_METRIC,
    CONF_INTEGRATION_TOKEN,
    CONF_REALTIME_ENABLED,
    CONF_STATION_CODE,
    CONF_WEBHOOK_ID,
    DOMAIN,
)
from .coordinator import WeatherPlatformDataUpdateCoordinator
from .realtime import WeatherPlatformRealtime, async_remove_stopped_receiver
from .subscription import SubscriptionError, async_subscription_request

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

    if entry.options.get(CONF_REALTIME_ENABLED, False):
        if CONF_WEBHOOK_ID not in entry.data:
            hass.config_entries.async_update_entry(
                entry,
                data={
                    **entry.data,
                    CONF_WEBHOOK_ID: webhook.async_generate_id(),
                    CONF_STATION_CODE: coordinator.data.current.station.code,
                },
            )
        coordinator.realtime = WeatherPlatformRealtime(hass, entry, coordinator)
        try:
            await coordinator.realtime.async_prepare()
        except (OSError, ValueError) as err:
            msg = "Unable to load event delivery receipts"
            raise ConfigEntryNotReady(msg) from err

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    if coordinator.realtime is not None:
        await coordinator.realtime.async_start()
    entry.async_on_unload(entry.add_update_listener(async_options_updated))
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[WeatherPlatformDataUpdateCoordinator],
) -> bool:
    """Unload a Weather Platform config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply event-delivery option changes."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Deactivate a permanent registration, including an unloaded entry."""
    if CONF_WEBHOOK_ID in entry.data and entry.options.get(CONF_INTEGRATION_TOKEN):
        try:
            coordinator = getattr(entry, "runtime_data", None)
            realtime = getattr(coordinator, "realtime", None)
            if realtime is not None:
                await realtime.async_deactivate(entry.options[CONF_INTEGRATION_TOKEN])
            else:
                await async_subscription_request(
                    async_get_clientsession(hass),
                    entry.data[CONF_URL],
                    entry.options[CONF_INTEGRATION_TOKEN],
                    entry.entry_id,
                    method="DELETE",
                )
        except SubscriptionError as err:
            raise HomeAssistantError(
                "Unable to deactivate the Weather Platform subscription; "
                "use its management API to remove this client: " + entry.entry_id
            ) from err
    async_remove_stopped_receiver(hass, entry.entry_id)
    await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.deliveries").async_remove()
