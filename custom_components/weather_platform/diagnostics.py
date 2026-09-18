"""Diagnostics support for Weather Platform."""

from __future__ import annotations

from dataclasses import fields
from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_URL

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import WeatherPlatformDataUpdateCoordinator

TO_REDACT = {CONF_URL}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry[WeatherPlatformDataUpdateCoordinator],
) -> dict[str, Any]:
    """Return diagnostics for a Weather Platform config entry."""
    del hass

    coordinator = entry.runtime_data
    data = coordinator.data
    metadata = coordinator.metadata

    conditions = data.current.conditions
    available_measurements = [
        field.name
        for field in fields(conditions)
        if getattr(conditions, field.name) is not None
    ]

    air_quality = data.air_quality
    alerts = data.alerts
    radar = data.radar
    events = data.events
    impacts = data.impacts

    return {
        "config_entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "version": entry.version,
            "minor_version": entry.minor_version,
        },
        "integration": {
            "unit_system": coordinator.unit_system,
            "platform_version": (
                metadata.platform_version if metadata is not None else None
            ),
            "api_version": metadata.api_version if metadata is not None else None,
            "advertised_resources": (
                sorted(metadata.resources) if metadata is not None else []
            ),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "optional_endpoint_status": coordinator.optional_endpoint_status,
            "unavailable_optional_endpoints": list(
                coordinator.unavailable_optional_endpoints
            ),
        },
        "current": {
            "generated_at": data.current.generated_at,
            "condition": data.current.condition,
            "station_observed_at": data.current.station.observed_at,
            "station_age_seconds": data.current.station.age_seconds,
            "station_stale": data.current.station.stale,
            "available_measurements": available_measurements,
        },
        "forecast": {
            "generated_at": data.forecast.generated_at,
            "periods_available": data.forecast.periods_available,
            "hourly_available": data.forecast.hourly_available,
            "daily_period_count": len(data.forecast.daily),
            "hourly_period_count": len(data.forecast.hourly),
        },
        "air_quality": {
            "endpoint_available": air_quality is not None,
            "generated_at": (
                air_quality.generated_at if air_quality is not None else None
            ),
            "provider": air_quality.provider if air_quality is not None else None,
            "model": air_quality.model if air_quality is not None else None,
            "stale": air_quality.stale if air_quality is not None else None,
        },
        "alerts": {
            "endpoint_available": alerts is not None,
            "active_count": alerts.active_count if alerts is not None else None,
            "critical_count": (alerts.critical_count if alerts is not None else None),
            "highest_level": (alerts.highest_level if alerts is not None else None),
        },
        "radar": {
            "endpoint_available": radar is not None,
            "lightning_available": (
                radar.lightning.available if radar is not None else None
            ),
            "recent_lightning_strike_count": (
                radar.lightning.recent_window_strike_count
                if radar is not None
                else None
            ),
            "storm_tracking_available": (
                radar.storm_tracking.available if radar is not None else None
            ),
            "tracked_storm_count": (
                radar.storm_tracking.tracked_object_count if radar is not None else None
            ),
            "approaching_storm_count": (
                sum(storm.approaching_home for storm in radar.storm_tracking.storms)
                if radar is not None and radar.storm_tracking.available
                else None
            ),
        },
        "events": {
            "endpoint_available": events is not None,
            "active_count": events.count if events is not None else None,
            "active_types": (
                sorted({event.event_type for event in events.events})
                if events is not None
                else []
            ),
        },
        "impacts": {
            "endpoint_available": impacts is not None,
            "horizon_hours": (impacts.horizon_hours if impacts is not None else None),
            "radar_hazard_active": (
                impacts.radar_hazard_active if impacts is not None else None
            ),
            "profile_ratings": (
                {profile.key: profile.current_rating for profile in impacts.profiles}
                if impacts is not None
                else {}
            ),
        },
    }
