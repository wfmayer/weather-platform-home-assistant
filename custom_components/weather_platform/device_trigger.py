"""Device automations backed by accepted Weather Platform deliveries."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.helpers import device_registry as dr

from .const import CONF_REALTIME_ENABLED, DOMAIN, EVENT_WEATHER_PLATFORM
from .event_delivery import WEATHER_EVENT_TYPES

if TYPE_CHECKING:
    from homeassistant.core import CALLBACK_TYPE, HomeAssistant
    from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
    from homeassistant.helpers.typing import ConfigType

CONF_SUBTYPE = "subtype"
TRIGGER_TYPES = ("weather_event", "started", "updated", "ended")
TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
        vol.Required(CONF_SUBTYPE): vol.In(["any", *WEATHER_EVENT_TYPES]),
    }
)


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[ConfigType]:
    """List lifecycle and family filters for realtime-enabled devices."""
    device = dr.async_get(hass).async_get(device_id)
    entry = (
        hass.config_entries.async_get_entry(device.config_entry_id)
        if device is not None
        else None
    )
    if (
        entry is None
        or entry.domain != DOMAIN
        or not entry.options.get(CONF_REALTIME_ENABLED, False)
    ):
        return []
    return [
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device_id,
            CONF_TYPE: kind,
            CONF_SUBTYPE: subtype,
        }
        for kind in TRIGGER_TYPES
        for subtype in ["any", *WEATHER_EVENT_TYPES]
    ]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a device-scoped event-bus trigger."""
    data = {"device_id": config[CONF_DEVICE_ID]}
    if config[CONF_TYPE] != "weather_event":
        data["change"] = config[CONF_TYPE]
    if config[CONF_SUBTYPE] != "any":
        data["event_type"] = config[CONF_SUBTYPE]
    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: EVENT_WEATHER_PLATFORM,
            event_trigger.CONF_EVENT_DATA: data,
        }
    )
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )
