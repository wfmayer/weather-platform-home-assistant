"""Receive and normalize Weather Platform schema-v1 transition deliveries."""

from __future__ import annotations

from typing import Any

from homeassistant.util import dt as dt_util

MAX_PAYLOAD_BYTES = 262144
MAX_DELIVERY_KEYS = 2048
WEATHER_EVENT_TYPES = [
    "rain",
    "nws_alert",
    "lightning",
    "wind",
    "heavy_rain",
    "heat_stress",
    "frost_freeze",
    "pressure_fall",
    "air_quality",
    "hydrology",
    "radar_storm",
    "station_data_health",
    "provider_data_health",
    "other",
]


class InvalidDeliveryError(ValueError):
    """An unsupported or malformed transition delivery."""


def normalize_delivery(  # noqa: PLR0912 - reject each invalid schema field explicitly
    payload: Any, station_code: str
) -> dict[str, Any]:
    """Validate identity and preserve quantitative details and notification text."""
    if not isinstance(payload, dict):
        raise InvalidDeliveryError
    if (
        type(payload.get("schemaVersion")) is not int
        or payload["schemaVersion"] != 1
        or payload.get("source") != "weather-platform"
    ):
        raise InvalidDeliveryError
    for key in ("station", "transition", "event", "notification"):
        if not isinstance(payload.get(key), dict):
            raise InvalidDeliveryError
    station = payload["station"]
    transition = payload["transition"]
    event = payload["event"]
    notification = payload["notification"]
    if station.get("code") != station_code:
        raise InvalidDeliveryError
    for value in (transition.get("id"), event.get("id")):
        if type(value) is not int or value <= 0:
            raise InvalidDeliveryError
    if payload.get("deliveryKey") != f"weather-event-transition-{transition['id']}":
        raise InvalidDeliveryError
    for value in (
        event.get("type"),
        transition.get("occurredAt"),
        notification.get("title"),
        notification.get("message"),
    ):
        if not isinstance(value, str) or not value.strip():
            raise InvalidDeliveryError
    try:
        occurred_at = dt_util.parse_datetime(transition["occurredAt"])
    except ValueError, OverflowError:
        raise InvalidDeliveryError from None
    if occurred_at is None or occurred_at.tzinfo is None:
        raise InvalidDeliveryError
    if not isinstance(notification.get("terminal"), bool):
        raise InvalidDeliveryError
    if not isinstance(event.get("details", {}), dict):
        raise InvalidDeliveryError
    change = "updated"
    if notification["terminal"]:
        change = "ended"
    elif transition.get("fromLifecycleState") is None:
        change = "started"
    event_type = event["type"].lower()
    return {
        **payload,
        "delivery_key": payload["deliveryKey"],
        "transition_id": transition["id"],
        "event_id": event["id"],
        "station_code": station_code,
        "weather_platform_type": event["type"],
        "event_type": event_type if event_type in WEATHER_EVENT_TYPES else "other",
        "change": change,
        "state": transition.get("toLifecycleState") or event.get("lifecycleState"),
        "phase": transition.get("toPhase") or event.get("phase"),
        "previous_phase": transition.get("fromPhase"),
        "priority": transition.get("notificationPriority")
        or notification.get("priority"),
        "occurred_at": transition["occurredAt"],
        "title": notification["title"],
        "message": notification["message"],
    }
