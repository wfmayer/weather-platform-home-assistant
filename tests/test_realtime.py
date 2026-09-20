"""Tests for the platform/HA registration and webhook contract."""

from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.core import CoreState
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.weather_platform.const import (
    CONF_CALLBACK_URL,
    CONF_INTEGRATION_TOKEN,
    CONF_REALTIME_ENABLED,
    CONF_STATION_CODE,
    CONF_WEBHOOK_ID,
    DOMAIN,
    EVENT_WEATHER_PLATFORM,
)
from custom_components.weather_platform.event_delivery import (
    MAX_PAYLOAD_BYTES,
    InvalidDeliveryError,
    normalize_delivery,
)
from custom_components.weather_platform.realtime import WeatherPlatformRealtime
from custom_components.weather_platform.subscription import (
    SUBSCRIPTIONS_PATH,
    SubscriptionError,
    async_subscription_request,
    normalize_callback_origin,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.test_util.aiohttp import (
        AiohttpClientMocker,
    )

BASE_URL = "http://platform.local/weather-platform"
TOKEN = "test-registration-key-0000000000000000"  # noqa: S105 - test-only value
STATION = "TEST123"


@pytest.fixture
def delivery() -> dict[str, Any]:
    """Build the exact schema-v1 envelope produced by the Java sender."""
    return {
        "schemaVersion": 1,
        "source": "weather-platform",
        "deliveryKey": "weather-event-transition-81",
        "station": {"code": STATION, "location": "Test station"},
        "transition": {
            "id": 81,
            "fromLifecycleState": None,
            "toLifecycleState": "ACTIVE",
            "fromPhase": None,
            "toPhase": "NEARBY",
            "notificationPriority": "HIGH",
            "occurredAt": "2026-09-19T20:01:00Z",
        },
        "event": {
            "id": 42,
            "type": "LIGHTNING",
            "lifecycleState": "ACTIVE",
            "phase": "NEARBY",
            "notificationPriority": "NORMAL",
            "details": {"nearestDistanceMiles": 4.5},
            "apiPath": "/api/v1/events/42",
            "uiPath": "/notifications?eventId=42",
        },
        "notification": {
            "title": "Lightning nearby",
            "message": "Lightning is 4.5 miles away.",
            "priority": "HIGH",
            "terminal": False,
            "tag": "weather-event-42",
            "group": "weather-platform",
        },
    }


def make_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a persisted integration entry with stable receiver identity."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=BASE_URL,
        data={"url": BASE_URL, CONF_STATION_CODE: STATION, CONF_WEBHOOK_ID: "a" * 64},
        options={
            CONF_REALTIME_ENABLED: True,
            CONF_INTEGRATION_TOKEN: TOKEN,
            CONF_CALLBACK_URL: "http://ha.local:8123",
        },
    )
    entry.add_to_hass(hass)
    return entry


def make_manager(
    hass: HomeAssistant, entry: MockConfigEntry
) -> WeatherPlatformRealtime:
    """Build a receiver without starting outbound registration."""
    coordinator = SimpleNamespace(
        client=SimpleNamespace(base_url=BASE_URL), async_request_refresh=AsyncMock()
    )
    return WeatherPlatformRealtime(hass, entry, coordinator)


def request(payload: Any, *, raw: bytes | None = None) -> SimpleNamespace:
    """Create a streaming webhook request."""
    body = raw if raw is not None else json.dumps(payload).encode()

    async def chunks(size: int) -> AsyncIterator[bytes]:
        for offset in range(0, len(body), size):
            yield body[offset : offset + size]

    return SimpleNamespace(
        method="POST",
        content_type="application/json",
        content=SimpleNamespace(iter_chunked=chunks),
    )


async def send(manager: WeatherPlatformRealtime, payload: Any) -> int:
    """Send one schema-v1 delivery through the actual receiver."""
    response = await manager.async_handle_webhook(
        manager.hass, "a" * 64, request(payload)
    )
    return response.status


@pytest.mark.parametrize(
    ("previous", "terminal", "change"),
    [
        (None, False, "started"),
        ("ACTIVE", False, "updated"),
        ("ACTIVE", True, "ended"),
    ],
)
def test_normalized_lifecycle(
    delivery: dict[str, Any], previous: str | None, *, terminal: bool, change: str
) -> None:
    """Use transition lifecycle and priority, preserving family details."""
    delivery["transition"]["fromLifecycleState"] = previous
    delivery["notification"]["terminal"] = terminal
    result = normalize_delivery(delivery, STATION)
    assert result["change"] == change
    assert result["priority"] == "HIGH"
    assert result["event"]["details"]["nearestDistanceMiles"] == 4.5


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schemaVersion", True),
        ("schemaVersion", 2),
        ("source", "other"),
        ("deliveryKey", "wrong"),
        ("event", []),
        ("notification", None),
    ],
)
def test_reject_invalid_envelope(
    delivery: dict[str, Any], field: str, value: Any
) -> None:
    """Malformed envelopes never reach the event bus."""
    delivery[field] = value
    with pytest.raises(InvalidDeliveryError):
        normalize_delivery(delivery, STATION)


@pytest.mark.parametrize("section", ["event", "transition"])
def test_reject_boolean_ids(delivery: dict[str, Any], section: str) -> None:
    """JSON booleans must not pass integer identity checks."""
    delivery[section]["id"] = True
    with pytest.raises(InvalidDeliveryError):
        normalize_delivery(delivery, STATION)


async def test_delivery_deduplicates_concurrently_and_after_restart(
    hass: HomeAssistant, hass_storage: dict, delivery: dict[str, Any]
) -> None:
    """Lost responses and HA restarts do not emit a delivery twice."""
    hass.set_state(CoreState.running)
    entry = make_entry(hass)
    manager = make_manager(hass, entry)
    await manager.async_prepare()
    received = []
    hass.bus.async_listen(EVENT_WEATHER_PLATFORM, received.append)
    assert await asyncio.gather(send(manager, delivery), send(manager, delivery)) == [
        204,
        204,
    ]
    await hass.async_block_till_done()
    assert len(received) == 1
    assert received[0].data["event_url"] == f"{BASE_URL}/notifications?eventId=42"
    assert received[0].data["config_entry_id"] == entry.entry_id
    manager.coordinator.async_request_refresh.assert_awaited_once()
    assert hass_storage[f"{DOMAIN}.{entry.entry_id}.deliveries"]["data"][
        "delivery_keys"
    ]

    restarted = make_manager(hass, entry)
    await restarted.async_prepare()
    assert await send(restarted, delivery) == 204
    await hass.async_block_till_done()
    assert len(received) == 1

    # A lower transition ID can legitimately arrive after a newer retry.
    older = deepcopy(delivery)
    older["transition"]["id"] = 80
    older["deliveryKey"] = "weather-event-transition-80"
    assert await send(restarted, older) == 204
    await hass.async_block_till_done()
    assert len(received) == 2


async def test_storage_failure_is_retryable_without_emitting(
    hass: HomeAssistant, delivery: dict[str, Any]
) -> None:
    """A failed or silently unsuccessful disk write is not acknowledged."""
    hass.set_state(CoreState.running)
    manager = make_manager(hass, make_entry(hass))
    listener = Mock()
    hass.bus.async_listen(EVENT_WEATHER_PLATFORM, listener)
    with patch.object(manager._store, "async_save", AsyncMock(side_effect=OSError)):
        assert await send(manager, delivery) == 503
    with patch.object(manager._store, "async_save", AsyncMock()):
        assert await send(manager, delivery) == 503
    await hass.async_block_till_done()
    listener.assert_not_called()
    assert manager._keys == []
    assert await send(manager, delivery) == 204


async def test_invalid_http_and_station(
    hass: HomeAssistant, delivery: dict[str, Any]
) -> None:
    """Validate content type, size, JSON, station, startup, and shutdown."""
    manager = make_manager(hass, make_entry(hass))
    hass.set_state(CoreState.starting)
    assert await send(manager, delivery) == 503
    hass.set_state(CoreState.running)
    assert await send(manager, []) == 400
    delivery["station"]["code"] = "OTHER"
    assert await send(manager, delivery) == 400
    for raw, expected in [(b"{", 400), (b"x" * (MAX_PAYLOAD_BYTES + 1), 413)]:
        result = await manager.async_handle_webhook(hass, "", request(None, raw=raw))
        assert result.status == expected
    req = request(delivery)
    req.content_type = "text/plain"
    assert (await manager.async_handle_webhook(hass, "", req)).status == 415
    req.method = "GET"
    assert (await manager.async_handle_webhook(hass, "", req)).status == 405
    manager.async_stop()
    assert await send(manager, delivery) == 503


async def test_registration_lifecycle(hass: HomeAssistant) -> None:
    """Receiver precedes PUT; reload removes only the local webhook."""
    manager = make_manager(hass, make_entry(hass))
    await manager.async_prepare()
    with (
        patch(
            "custom_components.weather_platform.realtime.webhook.async_register"
        ) as register,
        patch(
            "custom_components.weather_platform.realtime.webhook.async_unregister"
        ) as unregister,
        patch(
            "custom_components.weather_platform.realtime.async_subscription_request",
            AsyncMock(),
        ) as put,
    ):

        async def registered_first(*args: Any, **kwargs: Any) -> dict:
            del args
            register.assert_called_once()
            assert (
                kwargs["webhook_url"] == f"http://ha.local:8123/api/webhook/{'a' * 64}"
            )
            return {}

        put.side_effect = registered_first
        await manager.async_start()
        assert manager.status == "registered"
        assert put.call_args.args[3] == manager.entry.entry_id
        manager.async_stop()
        unregister.assert_called_once()
        assert register.call_count == 2
        put.assert_awaited_once()


async def test_registration_recovers(hass: HomeAssistant) -> None:
    """Registration failure does not prevent polling or change receiver identity."""
    manager = make_manager(hass, make_entry(hass))
    with patch(
        "custom_components.weather_platform.realtime.async_subscription_request",
        AsyncMock(),
    ) as put:
        put.side_effect = SubscriptionError("cannot_connect")
        await manager.async_register_subscription()
        assert manager.status == "registration_failed"
        put.side_effect = None
        await manager._async_retry(None)
        assert manager.status == "registered"
        assert manager.last_error is None
        assert put.await_count == 2
        assert put.call_args_list[0] == put.call_args_list[1]


async def test_subscription_preserves_context_and_auth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Management calls target the application context and authenticate."""
    url = f"{BASE_URL}{SUBSCRIPTIONS_PATH}/client-1"
    aioclient_mock.put(
        url,
        json={
            "clientId": "client-1",
            "station": STATION,
            "active": True,
            "payloadSchemaVersion": 1,
        },
    )
    result = await async_subscription_request(
        async_get_clientsession(hass),
        BASE_URL,
        TOKEN,
        "client-1",
        station=STATION,
        webhook_url="http://ha.local:8123/api/webhook/secret",
    )
    assert result["active"] is True
    sent = aioclient_mock.mock_calls[0]
    assert sent[3]["Authorization"] == f"Bearer {TOKEN}"
    assert sent[2]["station"] == STATION


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (401, "invalid_auth"),
        (409, "subscription_conflict"),
        (400, "invalid_subscription"),
        (503, "registration_unavailable"),
        (302, "registration_unavailable"),
    ],
)
async def test_management_errors_are_safe(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    status: int,
    code: str,
) -> None:
    """Never log response text or follow a redirect carrying credentials."""
    aioclient_mock.put(
        f"{BASE_URL}{SUBSCRIPTIONS_PATH}/client",
        status=status,
        text=TOKEN,
        headers={"Location": "http://other.local/"},
    )
    with pytest.raises(SubscriptionError, match=code):
        await async_subscription_request(
            async_get_clientsession(hass), BASE_URL, TOKEN, "client"
        )
    assert aioclient_mock.call_count == 1


@pytest.mark.parametrize(
    "origin",
    [
        "https://user:pass@ha.local",
        "http://ha.local/path",
        "http://ha.local?x=1",
        "http://ha.local/#x",
        "ftp://ha.local",
        "http://ha.local:bad",
        "http://ha local",
    ],
)
def test_invalid_callback_origin(origin: str) -> None:
    """Disallow origins the platform contract cannot accept."""
    with pytest.raises(SubscriptionError):
        normalize_callback_origin(origin)


def test_callback_normalization() -> None:
    """Keep explicit ports and IPv6 address brackets."""
    assert (
        normalize_callback_origin(" HTTP://HA.LOCAL:8123/ ") == "http://ha.local:8123"
    )
    assert normalize_callback_origin("http://[::1]:8123") == "http://[::1]:8123"


async def test_webhook_router_requests_retry_during_reload(
    hass: HomeAssistant, delivery: dict[str, Any]
) -> None:
    """Exercise HA's actual router, including the temporary unloaded receiver."""
    from homeassistant.components import webhook  # noqa: PLC0415 - focused router test

    hass.set_state(CoreState.running)
    entry = make_entry(hass)
    manager = make_manager(hass, entry)
    await manager.async_prepare()
    req = request(delivery)
    req.remote = "127.0.0.1"
    with patch(
        "custom_components.weather_platform.realtime.async_subscription_request",
        AsyncMock(),
    ):
        await manager.async_start()
        response = await webhook.async_handle_webhook(
            hass, entry.data[CONF_WEBHOOK_ID], req
        )
        assert response.status == 204
        manager.async_stop()
        response = await webhook.async_handle_webhook(
            hass, entry.data[CONF_WEBHOOK_ID], req
        )
        assert response.status == 503
        restarted = make_manager(hass, entry)
        await restarted.async_prepare()
        await restarted.async_start()
        req = request(delivery)
        req.remote = "127.0.0.1"
        response = await webhook.async_handle_webhook(
            hass, entry.data[CONF_WEBHOOK_ID], req
        )
        assert response.status == 204
        restarted.async_stop()


async def test_unexpected_processing_failure_requests_retry(
    hass: HomeAssistant, delivery: dict[str, Any]
) -> None:
    """Unexpected processing failures must not reach HA's implicit-200 handler."""
    manager = make_manager(hass, make_entry(hass))
    with patch.object(
        manager, "_async_handle_webhook", AsyncMock(side_effect=RuntimeError)
    ):
        assert await send(manager, delivery) == 503


async def test_deactivate_waits_for_registration(hass: HomeAssistant) -> None:
    """An in-flight PUT must finish before DELETE, with no later retry claim."""
    manager = make_manager(hass, make_entry(hass))
    entered = asyncio.Event()
    release = asyncio.Event()
    methods = []

    async def manage(*args: Any, **kwargs: Any) -> None:
        del args
        method = kwargs.get("method", "PUT")
        methods.append(method)
        if method == "PUT":
            entered.set()
            await release.wait()

    with patch(
        "custom_components.weather_platform.realtime.async_subscription_request",
        side_effect=manage,
    ):
        registering = asyncio.create_task(manager.async_register_subscription())
        await entered.wait()
        deleting = asyncio.create_task(manager.async_deactivate(TOKEN))
        release.set()
        await asyncio.gather(registering, deleting)
        await manager.async_register_subscription()
    assert methods == ["PUT", "DELETE"]
    assert manager.status == "stopped"
