"""Options, device triggers, and setup lifecycle for realtime events."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from homeassistant.core import Event
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.weather_platform import async_remove_entry, async_setup_entry
from custom_components.weather_platform.api import WeatherPlatformMetadata
from custom_components.weather_platform.const import (
    CONF_CALLBACK_URL,
    CONF_INTEGRATION_TOKEN,
    CONF_REALTIME_ENABLED,
    CONF_WEBHOOK_ID,
    DOMAIN,
    EVENT_WEATHER_PLATFORM,
)
from custom_components.weather_platform.device_trigger import (
    TRIGGER_SCHEMA,
    async_attach_trigger,
    async_get_triggers,
)
from custom_components.weather_platform.event import WeatherPlatformWeatherEventEntity
from custom_components.weather_platform.subscription import SubscriptionError

from .test_realtime import BASE_URL, STATION, TOKEN, make_entry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

METADATA = WeatherPlatformMetadata(
    name="Weather Platform API",
    api_version="v1",
    platform_version="1.14.0",
    resources={
        "homeAssistantSubscriptions": (
            "/api/v1/integrations/home-assistant/subscriptions"
        )
    },
)


async def test_enable_options_is_read_only(hass: HomeAssistant) -> None:
    """Validate credentials without claiming a station before reload."""
    entry = MockConfigEntry(domain=DOMAIN, data={"url": BASE_URL})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with (
        patch(
            "custom_components.weather_platform.config_flow.WeatherPlatformApiClient.async_get_metadata",
            AsyncMock(return_value=METADATA),
        ),
        patch(
            "custom_components.weather_platform.config_flow.async_subscription_request",
            AsyncMock(return_value=None),
        ) as manage,
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_REALTIME_ENABLED: True,
                CONF_INTEGRATION_TOKEN: TOKEN,
                CONF_CALLBACK_URL: "http://HA.LOCAL:8123/",
            },
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CALLBACK_URL] == "http://ha.local:8123"
    assert result["data"][CONF_INTEGRATION_TOKEN] == TOKEN
    assert manage.call_args.kwargs == {"method": "GET"}
    assert CONF_WEBHOOK_ID not in entry.data


@pytest.mark.parametrize("failure", [False, True])
async def test_disable_options_deletes_before_saving(
    hass: HomeAssistant, *, failure: bool
) -> None:
    """Failed deactivation keeps realtime enabled and its saved credentials."""
    entry = make_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with patch(
        "custom_components.weather_platform.config_flow.async_subscription_request",
        AsyncMock(),
    ) as manage:
        if failure:
            manage.side_effect = SubscriptionError("cannot_connect")
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_REALTIME_ENABLED: False,
                CONF_CALLBACK_URL: "http://ha.local:8123",
            },
        )
    assert manage.call_args.kwargs == {"method": "DELETE"}
    assert manage.call_args.args[2] == TOKEN
    if failure:
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}
        assert entry.options[CONF_REALTIME_ENABLED] is True
    else:
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.options[CONF_REALTIME_ENABLED] is False


async def test_device_trigger_filters(hass: HomeAssistant) -> None:
    """UI triggers filter by integration device, lifecycle, and weather family."""
    entry = make_entry(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, BASE_URL)},
    )
    triggers = await async_get_triggers(hass, device.id)
    config = next(
        t for t in triggers if t["type"] == "ended" and t["subtype"] == "rain"
    )
    action = AsyncMock()
    unsubscribe = await async_attach_trigger(
        hass,
        TRIGGER_SCHEMA(config),
        action,
        {
            "trigger_data": {"id": "0", "idx": "0", "alias": "Weather"},
            "variables": {},
        },
    )
    for data in [
        {"device_id": "another", "event_type": "rain", "change": "ended"},
        {"device_id": device.id, "event_type": "wind", "change": "ended"},
        {"device_id": device.id, "event_type": "rain", "change": "updated"},
    ]:
        hass.bus.async_fire(EVENT_WEATHER_PLATFORM, data)
    await hass.async_block_till_done()
    action.assert_not_awaited()
    hass.bus.async_fire(
        EVENT_WEATHER_PLATFORM,
        {
            "device_id": device.id,
            "event_type": "rain",
            "change": "ended",
        },
    )
    await hass.async_block_till_done()
    action.assert_awaited_once()
    unsubscribe()
    hass.config_entries.async_update_entry(
        entry, options={CONF_REALTIME_ENABLED: False}
    )
    assert await async_get_triggers(hass, device.id) == []


def test_event_entity_uses_delivery_only_in_realtime() -> None:
    """Polling in realtime mode cannot bypass notification policy or double fire."""
    entry = MagicMock()
    entry.entry_id = "entry1"
    entry.unique_id = BASE_URL
    entry.options = {CONF_REALTIME_ENABLED: True}
    coordinator = MagicMock()
    coordinator.metadata = None
    coordinator.data = SimpleNamespace(events=None)
    entity = WeatherPlatformWeatherEventEntity(entry, coordinator)
    entity.async_write_ha_state = Mock()
    entity._trigger_event = Mock()
    coordinator.data = SimpleNamespace(events=SimpleNamespace(events=[]))
    entity._handle_coordinator_update()
    entity._trigger_event.assert_not_called()
    entity._handle_delivery(
        Event(
            EVENT_WEATHER_PLATFORM,
            {
                "config_entry_id": "other",
                "event_type": "rain",
                "change": "started",
            },
        )
    )
    entity._trigger_event.assert_not_called()
    entity._handle_delivery(
        Event(
            EVENT_WEATHER_PLATFORM,
            {
                "config_entry_id": "entry1",
                "event_type": "rain",
                "change": "started",
            },
        )
    )
    entity._trigger_event.assert_called_once_with(
        "rain",
        {
            "config_entry_id": "entry1",
            "change": "started",
        },
    )


async def test_setup_persists_identity_and_forwards_before_registration(
    hass: HomeAssistant,
) -> None:
    """Existing URL-only entries gain a stable ID without re-adding entities."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"url": BASE_URL},
        options={
            CONF_REALTIME_ENABLED: True,
            CONF_INTEGRATION_TOKEN: TOKEN,
            CONF_CALLBACK_URL: "http://ha.local:8123",
        },
    )
    entry.add_to_hass(hass)
    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.data.current.station.code = STATION
    coordinator.realtime = None
    with (
        patch(
            "custom_components.weather_platform.WeatherPlatformDataUpdateCoordinator",
            return_value=coordinator,
        ),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", AsyncMock()
        ) as forward,
        patch(
            "custom_components.weather_platform.realtime.async_subscription_request",
            AsyncMock(),
        ) as manage,
    ):

        async def check_ready(*args: Any, **kwargs: Any) -> dict:
            del args, kwargs
            forward.assert_awaited_once()
            assert entry.data[CONF_WEBHOOK_ID]
            return {}

        manage.side_effect = check_ready
        assert await async_setup_entry(hass, entry)
        webhook_id = entry.data[CONF_WEBHOOK_ID]
        coordinator.realtime.async_stop()
        forward.reset_mock()
        assert await async_setup_entry(hass, entry)
        assert entry.data[CONF_WEBHOOK_ID] == webhook_id
        coordinator.realtime.async_stop()
        assert manage.await_count == 2
        assert manage.call_args_list[0] == manage.call_args_list[1]


async def test_permanent_removal_deactivates_unloaded_entry(
    hass: HomeAssistant,
) -> None:
    """Removal does not require runtime data or a healthy coordinator."""
    entry = make_entry(hass)
    with patch(
        "custom_components.weather_platform.async_subscription_request", AsyncMock()
    ) as manage:
        await async_remove_entry(hass, entry)
    assert manage.call_args.kwargs == {"method": "DELETE"}
    assert manage.call_args.args[3] == entry.entry_id
