"""Diagnostics support for Weather Platform."""

from __future__ import annotations

from dataclasses import fields
from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_URL

from .const import CONF_CALLBACK_URL, CONF_INTEGRATION_TOKEN, CONF_WEBHOOK_ID

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import WeatherPlatformDataUpdateCoordinator

TO_REDACT = {CONF_URL, CONF_INTEGRATION_TOKEN, CONF_CALLBACK_URL, CONF_WEBHOOK_ID}


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
    today = data.today
    hydrology = data.hydrology
    climate = data.climate
    meteorology = data.meteorology

    return {
        "config_entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
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
        "realtime": {
            "status": coordinator.realtime.status
            if coordinator.realtime
            else "disabled",
            "last_error": coordinator.realtime.last_error
            if coordinator.realtime
            else None,
            "last_received": coordinator.realtime.last_received
            if coordinator.realtime
            else None,
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
            "twice_daily_period_count": len(data.forecast.periods),
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
            "hourly_period_count": (
                len(air_quality.hourly) if air_quality is not None else 0
            ),
            "dominant_pollutant": (
                air_quality.current.dominant_pollutant
                if air_quality is not None
                else None
            ),
        },
        "alerts": {
            "endpoint_available": alerts is not None,
            "active_count": alerts.active_count if alerts is not None else None,
            "critical_count": (alerts.critical_count if alerts is not None else None),
            "highest_level": (alerts.highest_level if alerts is not None else None),
        },
        "radar": {
            "endpoint_available": radar is not None,
            "precipitation_available": (
                radar.precipitation.available
                if radar is not None and radar.precipitation is not None
                else None
            ),
            "precipitation_stale": (
                radar.precipitation.stale
                if radar is not None and radar.precipitation is not None
                else None
            ),
            "nowcast_available": (
                radar.nowcast.available
                if radar is not None and radar.nowcast is not None
                else None
            ),
            "precipitation_now": (
                radar.nowcast.precipitation_now
                if radar is not None and radar.nowcast is not None
                else None
            ),
            "nowcast_status": (
                radar.nowcast.status
                if radar is not None and radar.nowcast is not None
                else None
            ),
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
            "active_ids": (
                sorted(
                    event.event_id
                    for event in events.events
                    if event.event_id is not None
                )
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
            "profiles_with_best_window": (
                sorted(
                    profile.key
                    for profile in impacts.profiles
                    if profile.best_window is not None
                )
                if impacts is not None
                else []
            ),
        },
        "today": {
            "endpoint_available": today is not None,
            "generated_at": today.generated_at if today is not None else None,
            "section_count": len(today.sections) if today is not None else 0,
            "has_best_window": (
                today.best_window is not None if today is not None else None
            ),
            "has_impact_window": (
                today.impact_window is not None if today is not None else None
            ),
        },
        "hydrology": {
            "endpoint_available": hydrology is not None,
            "rainfall_available": (
                hydrology.rainfall.available if hydrology is not None else None
            ),
            "rainfall_level": (
                hydrology.rainfall.level if hydrology is not None else None
            ),
            "gauge_data_available": (
                hydrology.gauges.available if hydrology is not None else None
            ),
            "gauge_data_stale": (
                hydrology.gauges.stale if hydrology is not None else None
            ),
            "gauge_count": (
                len(hydrology.gauges.gauges) if hydrology is not None else 0
            ),
            "rising_gauge_count": (
                hydrology.gauges.rising_count if hydrology is not None else None
            ),
        },
        "climate": {
            "endpoint_available": climate is not None,
            "available": climate.available if climate is not None else None,
            "complete_day_count": (
                climate.complete_day_count if climate is not None else None
            ),
            "archive_year_count": (
                climate.archive_year_count if climate is not None else None
            ),
            "latest_complete_date": (
                climate.latest_day.date if climate is not None else None
            ),
        },
        "meteorology": {
            "endpoint_available": meteorology is not None,
            "available": meteorology.available if meteorology is not None else None,
            "wbgt_available": (
                meteorology.wbgt.available
                if meteorology is not None and meteorology.wbgt is not None
                else None
            ),
            "atmospheric_model_available": (
                meteorology.atmospheric_model.available
                if meteorology is not None and meteorology.atmospheric_model is not None
                else None
            ),
            "atmospheric_model_stale": (
                meteorology.atmospheric_model.stale
                if meteorology is not None and meteorology.atmospheric_model is not None
                else None
            ),
            "severe_weather_available": (
                meteorology.severe_weather.available
                if meteorology is not None and meteorology.severe_weather is not None
                else None
            ),
        },
    }
