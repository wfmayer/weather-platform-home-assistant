"""Integration-owned webhook lifecycle and durable retry deduplication."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from aiohttp import web
from homeassistant.components import webhook
from homeassistant.core import CoreState, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store

from .const import (
    CONF_CALLBACK_URL,
    CONF_INTEGRATION_TOKEN,
    CONF_STATION_CODE,
    CONF_WEBHOOK_ID,
    DOMAIN,
    EVENT_WEATHER_PLATFORM,
    NAME,
)
from .event_delivery import (
    MAX_DELIVERY_KEYS,
    MAX_PAYLOAD_BYTES,
    InvalidDeliveryError,
    normalize_delivery,
)
from .subscription import SubscriptionError, async_subscription_request

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import CALLBACK_TYPE, HomeAssistant

    from .coordinator import WeatherPlatformDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
DATA_STOPPED_RECEIVERS = f"{DOMAIN}_stopped_receivers"


async def _async_receiver_unavailable(
    hass: HomeAssistant, webhook_id: str, request: web.Request
) -> web.Response:
    """Request retry while the entry is unloaded instead of HA's default 200."""
    del hass, webhook_id, request
    return web.Response(status=503)


@callback
def async_remove_stopped_receiver(hass: HomeAssistant, entry_id: str) -> None:
    """Clear only a retry placeholder owned by this config entry."""
    if webhook_id := hass.data.get(DATA_STOPPED_RECEIVERS, {}).pop(entry_id, None):
        webhook.async_unregister(hass, webhook_id)


class WeatherPlatformRealtime:
    """Own the receiver and subscription for one platform config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: WeatherPlatformDataUpdateCoordinator,
    ) -> None:
        """Initialize one entry-scoped receiver."""
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self.status = "starting"
        self.last_error: str | None = None
        self.last_received: str | None = None
        self._store = Store[dict[str, Any]](
            hass, 1, f"{DOMAIN}.{entry.entry_id}.deliveries"
        )
        self._keys: list[str] = []
        self._lock = asyncio.Lock()
        self._subscription_lock = asyncio.Lock()
        self._cancel_retry: CALLBACK_TYPE | None = None
        self._refresh_task: asyncio.Task | None = None
        self._registered = False
        self._stopped = False

    async def async_prepare(self) -> None:
        """Load accepted delivery keys before exposing the receiver."""
        saved = await self._store.async_load()
        if saved is not None:
            if (
                not isinstance(saved, dict)
                or not isinstance(saved.get("delivery_keys"), list)
                or not all(isinstance(key, str) for key in saved["delivery_keys"])
            ):
                error = "Invalid Weather Platform delivery receipt store"
                raise ValueError(error)
            self._keys = saved["delivery_keys"][-MAX_DELIVERY_KEYS:]

    async def async_start(self) -> None:
        """Expose the receiver before claiming the platform subscription."""
        async_remove_stopped_receiver(self.hass, self.entry.entry_id)
        webhook.async_register(
            self.hass,
            DOMAIN,
            NAME,
            self.entry.data[CONF_WEBHOOK_ID],
            self.async_handle_webhook,
            allowed_methods=["POST"],
            local_only=False,
        )
        self._registered = True
        self.entry.async_on_unload(self.async_stop)
        self._cancel_retry = async_track_time_interval(
            self.hass, self._async_retry, timedelta(seconds=60)
        )
        await self.async_register_subscription()

    async def async_register_subscription(self) -> None:
        """Idempotently claim delivery; leave ordinary polling usable on failure."""
        async with self._subscription_lock:
            if self._stopped:
                return
            await self._async_register_subscription()

    async def _async_register_subscription(self) -> None:
        """Register while holding the mutation lock."""
        try:
            await async_subscription_request(
                async_get_clientsession(self.hass),
                self.coordinator.client.base_url,
                self.entry.options[CONF_INTEGRATION_TOKEN],
                self.entry.entry_id,
                station=self.entry.data[CONF_STATION_CODE],
                webhook_url=(
                    self.entry.options[CONF_CALLBACK_URL]
                    + webhook.async_generate_path(self.entry.data[CONF_WEBHOOK_ID])
                ),
            )
        except SubscriptionError as err:
            if self.last_error != err.code:
                _LOGGER.warning(
                    "Weather Platform realtime registration failed: %s", err.code
                )
            self.status = "registration_failed"
            self.last_error = err.code
        else:
            self.status = "registered"
            self.last_error = None

    async def async_deactivate(self, token: str) -> None:
        """Serialize DELETE after an in-flight registration and stop retries."""
        async with self._subscription_lock:
            await async_subscription_request(
                async_get_clientsession(self.hass),
                self.coordinator.client.base_url,
                token,
                self.entry.entry_id,
                method="DELETE",
            )
            self.async_stop()

    async def _async_retry(self, now: datetime) -> None:
        """Retry failed registration without replaying or replacing its identity."""
        del now
        if not self._stopped and self.status != "registered":
            await self.async_register_subscription()

    @callback
    def async_stop(self) -> None:
        """Remove only the local receiver on unload; preserve platform retries."""
        self._stopped = True
        if self._registered:
            webhook.async_unregister(self.hass, self.entry.data[CONF_WEBHOOK_ID])
            self._registered = False
            webhook_id = self.entry.data[CONF_WEBHOOK_ID]
            webhook.async_register(
                self.hass,
                DOMAIN,
                NAME,
                webhook_id,
                _async_receiver_unavailable,
                allowed_methods=["POST"],
                local_only=False,
            )
            self.hass.data.setdefault(DATA_STOPPED_RECEIVERS, {})[
                self.entry.entry_id
            ] = webhook_id
        if self._cancel_retry is not None:
            self._cancel_retry()
            self._cancel_retry = None
        if self._refresh_task is not None:
            self._refresh_task.cancel()
        self.status = "stopped"

    async def async_handle_webhook(
        self, hass: HomeAssistant, webhook_id: str, request: web.Request
    ) -> web.Response:
        """Prevent HA from turning an unexpected processing error into HTTP 200."""
        try:
            return await self._async_handle_webhook(hass, webhook_id, request)
        except Exception:  # noqa: BLE001 - webhook boundary must return retry status
            _LOGGER.error(  # noqa: TRY400 - redact receiver and payload details
                "Unable to process Weather Platform delivery; requesting retry"
            )
            return web.Response(status=503)

    async def _async_handle_webhook(  # noqa: PLR0911, PLR0912 - explicit HTTP outcomes
        self, hass: HomeAssistant, webhook_id: str, request: web.Request
    ) -> web.Response:
        """Accept a validated transition once and acknowledge only after persistence."""
        del hass, webhook_id
        if self._stopped or self.hass.state is not CoreState.running:
            return web.Response(status=503)
        if request.method != "POST":
            return web.Response(status=405)
        if request.content_type != "application/json":
            return web.Response(status=415)
        try:
            body = bytearray()
            async for chunk in request.content.iter_chunked(8192):
                body.extend(chunk)
                if len(body) > MAX_PAYLOAD_BYTES:
                    return web.Response(status=413)
            data = normalize_delivery(
                json.loads(body), self.entry.data[CONF_STATION_CODE]
            )
        except ValueError, UnicodeError, InvalidDeliveryError, RecursionError:
            return web.Response(status=400)
        except ConnectionError, TimeoutError:
            return web.Response(status=503)

        async with self._lock:
            if self._stopped:
                return web.Response(status=503)
            key = data["delivery_key"]
            if key in self._keys:
                return web.Response(status=204)
            keys = [*self._keys, key][-MAX_DELIVERY_KEYS:]
            try:
                await self._store.async_save({"delivery_keys": keys})
                # Store logs some disk errors instead of raising. Read back the
                # invalidated store before acknowledging or emitting a delivery.
                if await self._store.async_load() != {"delivery_keys": keys}:
                    return web.Response(status=503)
            except OSError, ValueError:
                _LOGGER.error(  # noqa: TRY400 - avoid sensitive exception text
                    "Unable to persist Weather Platform delivery receipt"
                )
                return web.Response(status=503)
            self._keys = keys
            self.last_received = data["occurred_at"]
            data["config_entry_id"] = self.entry.entry_id
            device = dr.async_get(self.hass).async_get_device_by_identifier(
                (DOMAIN, self.entry.unique_id or self.entry.entry_id),
                self.entry.entry_id,
            )
            if device is not None:
                data["device_id"] = device.id
            data["event_url"] = (
                f"{self.coordinator.client.base_url}/notifications?eventId={data['event_id']}"
            )
            data["event_api_url"] = (
                f"{self.coordinator.client.base_url}/api/v1/events/{data['event_id']}"
            )
            self.hass.bus.async_fire(EVENT_WEATHER_PLATFORM, data)
            # A webhook must not wait for all REST resources before acknowledging.
            if self._refresh_task is None or self._refresh_task.done():
                self._refresh_task = self.entry.async_create_background_task(
                    self.hass,
                    self.coordinator.async_request_refresh(),
                    "Weather Platform event refresh",
                )
        return web.Response(status=204)
