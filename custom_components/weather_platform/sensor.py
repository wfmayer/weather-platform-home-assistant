"""Sensor entities for Weather Platform."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    LIGHT_LUX,
    EntityCategory,
    UnitOfDensity,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfRatio,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumetricFlux,
)
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import API_UNIT_SYSTEM_METRIC, DOMAIN, NAME
from .coordinator import WeatherPlatformDataUpdateCoordinator

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .api import (
        WeatherPlatformHydrologyGauge,
        WeatherPlatformImpactProfile,
        WeatherPlatformImpactWindow,
    )
    from .coordinator import WeatherPlatformData

type SensorValue = float | int | str | datetime | None

AIR_QUALITY_CATEGORIES = [
    "Good",
    "Moderate",
    "Unhealthy for Sensitive Groups",
    "Unhealthy",
    "Very Unhealthy",
    "Hazardous",
    "Unavailable",
]

ALERT_LEVELS = [
    "None",
    "INFO",
    "ADVISORY",
    "WATCH",
    "WARNING",
]

LIGHTNING_ACTIVITY_TRENDS = [
    "APPROACHING",
    "STEADY",
    "DEPARTING",
    "UNKNOWN",
]

LIGHTNING_RATE_TRENDS = [
    "INCREASING",
    "STEADY",
    "DECREASING",
    "UNKNOWN",
]

EVENT_PRIORITIES = [
    "None",
    "NORMAL",
    "TIME_SENSITIVE",
    "CRITICAL",
]

IMPACT_RATINGS = [
    "excellent",
    "good",
    "caution",
    "poor",
    "unavailable",
]


@dataclass(frozen=True, kw_only=True)
class WeatherPlatformSensorEntityDescription(SensorEntityDescription):
    """Describe a Weather Platform sensor entity."""

    value_fn: Callable[[WeatherPlatformData], SensorValue]
    imperial_unit: str | None = None
    metric_unit: str | None = None
    attributes_fn: Callable[[WeatherPlatformData], dict[str, object]] | None = None


def _timestamp(value: str | None) -> datetime | None:
    """Parse an API timestamp for a timestamp sensor."""
    if value is None:
        return None
    return dt_util.parse_datetime(value)


def _highest_alert_level(
    data: WeatherPlatformData,
) -> str | None:
    """Return the highest active alert level."""
    if data.alerts is None:
        return None

    if data.alerts.active_count == 0:
        return "None"

    return data.alerts.highest_level


def _alerts_attributes(data: WeatherPlatformData) -> dict[str, object]:
    """Return compact active-alert metadata."""
    if data.alerts is None:
        return {}

    return {
        "alerts": [
            {
                key: value
                for key, value in {
                    "id": alert.alert_id,
                    "event": alert.event,
                    "headline": alert.headline,
                    "area": alert.area,
                    "severity": alert.severity,
                    "certainty": alert.certainty,
                    "urgency": alert.urgency,
                    "level": alert.level,
                    "critical": alert.critical,
                    "onset_at": alert.onset_at,
                    "expires_at": alert.expires_at,
                }.items()
                if value is not None
            }
            for alert in data.alerts.alerts
        ]
    }


def _air_quality_attributes(data: WeatherPlatformData) -> dict[str, object]:
    """Return compact air-quality context."""
    air_quality = data.air_quality
    if air_quality is None:
        return {}

    current = air_quality.current
    attributes: dict[str, object] = {
        "provider": air_quality.provider,
        "model": air_quality.model,
        "category": current.category,
        "category_headline": current.category_headline,
        "dominant_pollutant": current.dominant_pollutant,
        "dominant_pollutant_aqi": current.dominant_pollutant_aqi,
    }
    if air_quality.peak_next_24_hours is not None:
        attributes["peak_next_24_hours"] = air_quality.peak_next_24_hours.us_aqi
    if air_quality.minimum_next_24_hours is not None:
        attributes["minimum_next_24_hours"] = air_quality.minimum_next_24_hours.us_aqi
    return {key: value for key, value in attributes.items() if value is not None}


def _approaching_storm_count(
    data: WeatherPlatformData,
) -> int | None:
    """Return the number of tracked storms approaching home."""
    if data.radar is None or not data.radar.storm_tracking.available:
        return None

    return sum(storm.approaching_home for storm in data.radar.storm_tracking.storms)


def _nearest_storm_distance(
    data: WeatherPlatformData,
) -> float | None:
    """Return the nearest tracked storm distance."""
    if data.radar is None or not data.radar.storm_tracking.available:
        return None

    distances = [
        storm.distance
        for storm in data.radar.storm_tracking.storms
        if storm.distance is not None
    ]
    return min(distances, default=None)


def _strongest_storm_reflectivity(
    data: WeatherPlatformData,
) -> float | None:
    """Return the strongest tracked-storm peak reflectivity."""
    if data.radar is None or not data.radar.storm_tracking.available:
        return None

    reflectivities = [
        storm.peak_reflectivity_dbz
        for storm in data.radar.storm_tracking.storms
        if storm.peak_reflectivity_dbz is not None
    ]
    return max(reflectivities, default=None)


def _tracked_storm_attributes(data: WeatherPlatformData) -> dict[str, object]:
    """Return compact tracked-storm metadata."""
    if data.radar is None or not data.radar.storm_tracking.available:
        return {}

    tracking = data.radar.storm_tracking
    return {
        "status": tracking.status,
        "valid_at": tracking.valid_at,
        "detection_threshold_dbz": tracking.detection_threshold_dbz,
        "storms": [
            {
                key: value
                for key, value in {
                    "id": storm.storm_id,
                    "intensity": storm.intensity,
                    "lifecycle_stage": storm.lifecycle_stage,
                    "distance": storm.distance,
                    "peak_reflectivity_dbz": storm.peak_reflectivity_dbz,
                    "reflectivity_trend": storm.reflectivity_trend,
                    "area_trend": storm.area_trend,
                    "speed": storm.speed,
                    "bearing_degrees": storm.bearing_degrees,
                    "direction": storm.direction,
                    "approaching_home": storm.approaching_home,
                    "age_minutes": storm.age_minutes,
                }.items()
                if value is not None
            }
            for storm in tracking.storms
        ],
    }


def _radar_nowcast_attributes(data: WeatherPlatformData) -> dict[str, object]:
    """Return radar-nowcast context."""
    if data.radar is None or data.radar.nowcast is None:
        return {}

    nowcast = data.radar.nowcast
    return {
        key: value
        for key, value in {
            "status": nowcast.status,
            "radar_valid_at": nowcast.radar_valid_at,
            "arrival_lead_minutes": nowcast.arrival_lead_minutes,
            "departure_lead_minutes": nowcast.departure_lead_minutes,
            "peak_reflectivity_dbz": nowcast.peak_reflectivity_dbz,
            "arrival_echo_coverage_percent": nowcast.arrival_echo_coverage_percent,
            "maximum_evaluated_lead_minutes": nowcast.maximum_evaluated_lead_minutes,
            "coverage_limited": nowcast.coverage_limited,
            "motion_direction": nowcast.motion_direction,
            "motion_speed": nowcast.motion_speed,
            "motion_bearing_degrees": nowcast.motion_bearing_degrees,
            "motion_coherence_percent": nowcast.motion_coherence_percent,
            "motion_consensus_sample_count": nowcast.motion_consensus_sample_count,
            "motion_consensus_inlier_count": nowcast.motion_consensus_inlier_count,
        }.items()
        if value is not None
    }


def _highest_event_priority(
    data: WeatherPlatformData,
) -> str | None:
    """Return the highest active durable weather-event priority."""
    if data.events is None:
        return None

    if not data.events.events:
        return "None"

    for priority in reversed(EVENT_PRIORITIES[1:]):
        if any(event.priority == priority for event in data.events.events):
            return priority

    return "None"


def _latest_active_event(
    data: WeatherPlatformData,
) -> str | None:
    """Return the newest active durable weather-event type."""
    if data.events is None:
        return None

    if not data.events.events:
        return "None"

    event = data.events.events[0]
    return event.type_label or event.event_type


def _latest_active_event_phase(
    data: WeatherPlatformData,
) -> str | None:
    """Return the newest active durable weather-event phase."""
    if data.events is None:
        return None

    if not data.events.events:
        return "None"

    event = data.events.events[0]
    return event.phase_label or event.phase or "None"


def _active_events_attributes(data: WeatherPlatformData) -> dict[str, object]:
    """Return compact active-event metadata."""
    if data.events is None:
        return {}

    return {
        "events": [
            {
                key: value
                for key, value in {
                    "id": event.event_id,
                    "type": event.event_type,
                    "type_label": event.type_label,
                    "state": event.state,
                    "phase": event.phase,
                    "priority": event.priority,
                    "trigger_source": event.trigger_source,
                    "detected_at": event.detected_at,
                    "last_evidence_at": event.last_evidence_at,
                }.items()
                if value is not None
            }
            for event in data.events.events
        ]
    }


def _impact_profile(
    data: WeatherPlatformData,
    key: str,
) -> WeatherPlatformImpactProfile | None:
    """Return an impact profile by key."""
    if data.impacts is None:
        return None

    return next(
        (profile for profile in data.impacts.profiles if profile.key == key),
        None,
    )


def _impact_rating(
    data: WeatherPlatformData,
    key: str,
) -> str | None:
    """Return the current rating for an impact profile."""
    profile = _impact_profile(data, key)
    return None if profile is None else profile.current_rating


def _window_attributes(
    window: WeatherPlatformImpactWindow | None,
) -> dict[str, object] | None:
    """Return serializable impact-window attributes."""
    if window is None:
        return None
    return {
        key: value
        for key, value in {
            "started_at": window.started_at,
            "ended_at": window.ended_at,
            "rating": window.rating,
            "label": window.label,
        }.items()
        if value is not None
    }


def _impact_attributes(
    data: WeatherPlatformData,
    key: str,
) -> dict[str, object]:
    """Return rich context for one impact profile."""
    profile = _impact_profile(data, key)
    if profile is None:
        return {}

    attributes: dict[str, object] = {
        "title": profile.title,
        "subtitle": profile.subtitle,
        "status": profile.current_status,
        "headline": profile.headline,
        "detail": profile.detail,
        "next_change_at": profile.next_change_at,
        "next_change_label": profile.next_change_label,
        "best_window": _window_attributes(profile.best_window),
        "concern_window": _window_attributes(profile.concern_window),
        "evidence": list(profile.evidence),
    }
    return {key: value for key, value in attributes.items() if value is not None}


def _today_attributes(data: WeatherPlatformData) -> dict[str, object]:
    """Return synthesized daily-story details."""
    today = data.today
    if today is None:
        return {}

    attributes: dict[str, object] = {
        "observed_at": today.observed_at,
        "summary": today.summary,
        "tone": today.tone,
        "sections": [
            {
                key: value
                for key, value in {
                    "key": section.key,
                    "label": section.label,
                    "headline": section.headline,
                    "detail": section.detail,
                    "meta": section.meta,
                    "tone": section.tone,
                    "action_label": section.action_label,
                    "action_path": section.action_path,
                }.items()
                if value is not None
            }
            for section in today.sections
        ],
    }
    if today.evolution is not None:
        attributes["evolution"] = {
            key: value
            for key, value in {
                "headline": today.evolution.headline,
                "detail": today.evolution.detail,
                "meta": today.evolution.meta,
                "tone": today.evolution.tone,
            }.items()
            if value is not None
        }
    if today.best_window is not None:
        attributes["best_window"] = {
            key: value
            for key, value in {
                "label": today.best_window.label,
                "headline": today.best_window.headline,
                "detail": today.best_window.detail,
                "started_at": today.best_window.started_at,
                "ended_at": today.best_window.ended_at,
                "tone": today.best_window.tone,
            }.items()
            if value is not None
        }
    if today.impact_window is not None:
        attributes["impact_window"] = {
            key: value
            for key, value in {
                "label": today.impact_window.label,
                "headline": today.impact_window.headline,
                "detail": today.impact_window.detail,
                "started_at": today.impact_window.started_at,
                "ended_at": today.impact_window.ended_at,
                "tone": today.impact_window.tone,
            }.items()
            if value is not None
        }
    return {key: value for key, value in attributes.items() if value is not None}


def _nearest_gauge(
    data: WeatherPlatformData,
) -> WeatherPlatformHydrologyGauge | None:
    """Return the nearest hydrology gauge with a known distance."""
    if data.hydrology is None or not data.hydrology.gauges.available:
        return None

    gauges = [
        gauge for gauge in data.hydrology.gauges.gauges if gauge.distance is not None
    ]
    if not gauges:
        return None
    return min(gauges, key=lambda gauge: gauge.distance or 0.0)


def _nearest_gauge_distance(data: WeatherPlatformData) -> float | None:
    """Return the nearest gauge distance."""
    gauge = _nearest_gauge(data)
    return None if gauge is None else gauge.distance


def _nearest_gauge_stage(data: WeatherPlatformData) -> float | None:
    """Return the nearest gauge stage."""
    gauge = _nearest_gauge(data)
    return None if gauge is None else gauge.stage


def _nearest_gauge_trend(data: WeatherPlatformData) -> str | None:
    """Return the nearest gauge trend."""
    gauge = _nearest_gauge(data)
    return None if gauge is None else gauge.trend


def _nearest_gauge_attributes(data: WeatherPlatformData) -> dict[str, object]:
    """Return metadata for the nearest hydrology gauge."""
    gauge = _nearest_gauge(data)
    if gauge is None:
        return {}

    unit_system = data.hydrology.unit_system if data.hydrology is not None else None
    return {
        key: value
        for key, value in {
            "monitoring_location_id": gauge.monitoring_location_id,
            "site_number": gauge.site_number,
            "name": gauge.name,
            "site_type": gauge.site_type,
            "stage": gauge.stage,
            "stage_change_6_hours": gauge.stage_change_6_hours,
            "stage_change_24_hours": gauge.stage_change_24_hours,
            "discharge": gauge.discharge,
            "discharge_change_6_hours": gauge.discharge_change_6_hours,
            "discharge_change_24_hours": gauge.discharge_change_24_hours,
            "observed_at": gauge.observed_at,
            "trend": gauge.trend,
            "stage_unit": "m" if unit_system == API_UNIT_SYSTEM_METRIC else "ft",
            "discharge_unit": (
                "m3/s" if unit_system == API_UNIT_SYSTEM_METRIC else "ft3/s"
            ),
        }.items()
        if value is not None
    }


def _antecedent_rainfall_attributes(
    data: WeatherPlatformData,
) -> dict[str, object]:
    """Return antecedent-rainfall context."""
    if data.hydrology is None:
        return {}

    rainfall = data.hydrology.rainfall
    return {
        key: value
        for key, value in {
            "headline": rainfall.headline,
            "detail": rainfall.detail,
            "latest_observation_at": rainfall.latest_observation_at,
            "last_rain_at": rainfall.last_rain_at,
        }.items()
        if value is not None
    }


def _climate_attributes(data: WeatherPlatformData) -> dict[str, object]:
    """Return compact climate context."""
    climate = data.climate
    if climate is None:
        return {}

    records = climate.records
    return {
        "summary": climate.summary,
        "tone": climate.tone,
        "complete_day_count": climate.complete_day_count,
        "archive_year_count": climate.archive_year_count,
        "first_observed_at": climate.first_observed_at,
        "last_observed_at": climate.last_observed_at,
        "records": {
            key: value
            for key, value in {
                "highest_high_temperature": records.highest_high_temperature,
                "highest_high_date": records.highest_high_date,
                "lowest_low_temperature": records.lowest_low_temperature,
                "lowest_low_date": records.lowest_low_date,
                "wettest_day_rainfall": records.wettest_day_rainfall,
                "wettest_day_date": records.wettest_day_date,
                "strongest_wind_gust": records.strongest_wind_gust,
                "strongest_wind_gust_date": records.strongest_wind_gust_date,
            }.items()
            if value is not None
        },
    }


def _meteorology_current_attributes(data: WeatherPlatformData) -> dict[str, object]:
    """Return derived current-meteorology context."""
    if data.meteorology is None or data.meteorology.current is None:
        return {}

    current = data.meteorology.current
    return {
        key: value
        for key, value in {
            "observed_at": current.observed_at,
            "feels_like_type": current.feels_like_type,
            "rain_intensity": current.rain_intensity,
            "wind_condition": current.wind_condition,
        }.items()
        if value is not None
    }


def _atmospheric_model_attributes(data: WeatherPlatformData) -> dict[str, object]:
    """Return atmospheric-model source and freshness context."""
    if data.meteorology is None or data.meteorology.atmospheric_model is None:
        return {}

    model = data.meteorology.atmospheric_model
    return {
        key: value
        for key, value in {
            "available": model.available,
            "stale": model.stale,
            "provider": model.provider,
            "model": model.model,
            "valid_at": model.valid_at,
        }.items()
        if value is not None
    }


def _severe_weather_attributes(data: WeatherPlatformData) -> dict[str, object]:
    """Return severe-weather intelligence context."""
    if data.meteorology is None or data.meteorology.severe_weather is None:
        return {}

    severe = data.meteorology.severe_weather
    return {
        "headline": severe.headline,
        "summary": severe.summary,
        "data_status": severe.data_status,
        "signals": [
            {
                key: value
                for key, value in {
                    "key": signal.key,
                    "label": signal.label,
                    "level": signal.level,
                    "value": signal.value_display,
                    "detail": signal.detail,
                }.items()
                if value is not None
            }
            for signal in severe.signals
        ],
    }


BASE_SENSOR_DESCRIPTIONS = (
    WeatherPlatformSensorEntityDescription(
        key="rain_rate",
        name="Rain rate",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=UnitOfVolumetricFlux.INCHES_PER_HOUR,
        metric_unit=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        value_fn=lambda data: data.current.conditions.rain_rate,
        suggested_display_precision=2,
    ),
    WeatherPlatformSensorEntityDescription(
        key="daily_rain",
        name="Daily rain",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        imperial_unit=UnitOfPrecipitationDepth.INCHES,
        metric_unit=UnitOfPrecipitationDepth.MILLIMETERS,
        value_fn=lambda data: data.current.conditions.daily_rain,
        suggested_display_precision=2,
    ),
    WeatherPlatformSensorEntityDescription(
        key="event_rain",
        name="Event rain",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL,
        imperial_unit=UnitOfPrecipitationDepth.INCHES,
        metric_unit=UnitOfPrecipitationDepth.MILLIMETERS,
        value_fn=lambda data: data.current.conditions.event_rain,
        suggested_display_precision=2,
    ),
    WeatherPlatformSensorEntityDescription(
        key="solar_radiation",
        name="Solar radiation",
        device_class=SensorDeviceClass.IRRADIANCE,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        metric_unit=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        value_fn=lambda data: data.current.conditions.solar_radiation,
        suggested_display_precision=0,
    ),
    WeatherPlatformSensorEntityDescription(
        key="solar_illuminance",
        name="Solar illuminance",
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=LIGHT_LUX,
        metric_unit=LIGHT_LUX,
        value_fn=lambda data: data.current.conditions.solar_illuminance,
        suggested_display_precision=0,
    ),
)

AIR_QUALITY_SENSOR_DESCRIPTIONS = (
    WeatherPlatformSensorEntityDescription(
        key="air_quality_index",
        name="Air quality index",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            None if data.air_quality is None else data.air_quality.current.us_aqi
        ),
        attributes_fn=_air_quality_attributes,
        suggested_display_precision=0,
    ),
    WeatherPlatformSensorEntityDescription(
        key="air_quality_category",
        name="Air quality category",
        device_class=SensorDeviceClass.ENUM,
        options=AIR_QUALITY_CATEGORIES,
        value_fn=lambda data: (
            None if data.air_quality is None else data.air_quality.current.category
        ),
    ),
    WeatherPlatformSensorEntityDescription(
        key="air_quality_guidance",
        name="Air quality guidance",
        value_fn=lambda data: (
            None if data.air_quality is None else data.air_quality.current.health_advice
        ),
    ),
    WeatherPlatformSensorEntityDescription(
        key="air_quality_dominant_pollutant",
        name="Air quality dominant pollutant",
        value_fn=lambda data: (
            None
            if data.air_quality is None
            else data.air_quality.current.dominant_pollutant
        ),
    ),
    WeatherPlatformSensorEntityDescription(
        key="pm25",
        name="PM2.5",
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        metric_unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        value_fn=lambda data: (
            None if data.air_quality is None else data.air_quality.current.pm25
        ),
        suggested_display_precision=1,
    ),
    WeatherPlatformSensorEntityDescription(
        key="pm10",
        name="PM10",
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        metric_unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        value_fn=lambda data: (
            None if data.air_quality is None else data.air_quality.current.pm10
        ),
        suggested_display_precision=1,
    ),
    WeatherPlatformSensorEntityDescription(
        key="ozone",
        name="Ozone",
        device_class=SensorDeviceClass.OZONE,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        metric_unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        value_fn=lambda data: (
            None if data.air_quality is None else data.air_quality.current.ozone
        ),
        suggested_display_precision=1,
    ),
    WeatherPlatformSensorEntityDescription(
        key="nitrogen_dioxide",
        name="Nitrogen dioxide",
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        metric_unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        value_fn=lambda data: (
            None
            if data.air_quality is None
            else data.air_quality.current.nitrogen_dioxide
        ),
        suggested_display_precision=1,
    ),
    WeatherPlatformSensorEntityDescription(
        key="carbon_monoxide",
        name="Carbon monoxide",
        device_class=SensorDeviceClass.CO,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        metric_unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        value_fn=lambda data: (
            None
            if data.air_quality is None
            else data.air_quality.current.carbon_monoxide
        ),
        suggested_display_precision=1,
    ),
    WeatherPlatformSensorEntityDescription(
        key="sulphur_dioxide",
        name="Sulphur dioxide",
        device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        metric_unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        value_fn=lambda data: (
            None
            if data.air_quality is None
            else data.air_quality.current.sulphur_dioxide
        ),
        suggested_display_precision=1,
    ),
    WeatherPlatformSensorEntityDescription(
        key="wildfire_pm10",
        name="Wildfire PM10",
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        metric_unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        value_fn=lambda data: (
            None if data.air_quality is None else data.air_quality.current.wildfire_pm10
        ),
        suggested_display_precision=1,
    ),
    WeatherPlatformSensorEntityDescription(
        key="wildfire_pm10_share",
        name="Wildfire PM10 share",
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=UnitOfRatio.PERCENTAGE,
        metric_unit=UnitOfRatio.PERCENTAGE,
        value_fn=lambda data: (
            None
            if data.air_quality is None
            else data.air_quality.current.wildfire_pm10_share_percent
        ),
        suggested_display_precision=1,
    ),
    WeatherPlatformSensorEntityDescription(
        key="peak_air_quality_index_next_24_hours",
        name="Peak air quality index next 24 hours",
        device_class=SensorDeviceClass.AQI,
        value_fn=lambda data: (
            None
            if data.air_quality is None or data.air_quality.peak_next_24_hours is None
            else data.air_quality.peak_next_24_hours.us_aqi
        ),
        suggested_display_precision=0,
    ),
    WeatherPlatformSensorEntityDescription(
        key="minimum_air_quality_index_next_24_hours",
        name="Minimum air quality index next 24 hours",
        device_class=SensorDeviceClass.AQI,
        value_fn=lambda data: (
            None
            if data.air_quality is None
            or data.air_quality.minimum_next_24_hours is None
            else data.air_quality.minimum_next_24_hours.us_aqi
        ),
        suggested_display_precision=0,
    ),
)

ALERT_SENSOR_DESCRIPTIONS = (
    WeatherPlatformSensorEntityDescription(
        key="active_weather_alerts",
        name="Active weather alerts",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: None if data.alerts is None else data.alerts.active_count,
        attributes_fn=_alerts_attributes,
        suggested_display_precision=0,
    ),
    WeatherPlatformSensorEntityDescription(
        key="critical_weather_alerts",
        name="Critical weather alerts",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            None if data.alerts is None else data.alerts.critical_count
        ),
        suggested_display_precision=0,
    ),
    WeatherPlatformSensorEntityDescription(
        key="highest_weather_alert_level",
        name="Highest weather alert level",
        device_class=SensorDeviceClass.ENUM,
        options=ALERT_LEVELS,
        value_fn=_highest_alert_level,
    ),
)

RADAR_SENSOR_DESCRIPTIONS = (
    WeatherPlatformSensorEntityDescription(
        key="radar_precipitation_rate",
        name="Radar precipitation rate",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=UnitOfVolumetricFlux.INCHES_PER_HOUR,
        metric_unit=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        value_fn=lambda data: (
            None
            if data.radar is None
            or data.radar.precipitation is None
            or not data.radar.precipitation.available
            else data.radar.precipitation.precipitation_rate
        ),
        suggested_display_precision=2,
    ),
    WeatherPlatformSensorEntityDescription(
        key="radar_two_minute_precipitation",
        name="Radar precipitation last 2 minutes",
        device_class=SensorDeviceClass.PRECIPITATION,
        imperial_unit=UnitOfPrecipitationDepth.INCHES,
        metric_unit=UnitOfPrecipitationDepth.MILLIMETERS,
        value_fn=lambda data: (
            None
            if data.radar is None
            or data.radar.precipitation is None
            or not data.radar.precipitation.available
            else data.radar.precipitation.two_minute_precipitation
        ),
        suggested_display_precision=3,
    ),
    WeatherPlatformSensorEntityDescription(
        key="radar_reflectivity",
        name="Radar reflectivity",
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit="dBZ",
        metric_unit="dBZ",
        value_fn=lambda data: (
            None
            if data.radar is None
            or data.radar.precipitation is None
            or not data.radar.precipitation.available
            else data.radar.precipitation.reflectivity_dbz
        ),
        suggested_display_precision=1,
    ),
    WeatherPlatformSensorEntityDescription(
        key="radar_precipitation_intensity",
        name="Radar precipitation intensity",
        value_fn=lambda data: (
            None
            if data.radar is None or data.radar.precipitation is None
            else data.radar.precipitation.intensity
        ),
    ),
    WeatherPlatformSensorEntityDescription(
        key="radar_precipitation_arrival",
        name="Radar precipitation arrival",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: (
            None
            if data.radar is None or data.radar.nowcast is None
            else _timestamp(data.radar.nowcast.arrival_at)
        ),
        attributes_fn=_radar_nowcast_attributes,
    ),
    WeatherPlatformSensorEntityDescription(
        key="radar_precipitation_departure",
        name="Radar precipitation departure",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: (
            None
            if data.radar is None or data.radar.nowcast is None
            else _timestamp(data.radar.nowcast.departure_at)
        ),
    ),
    WeatherPlatformSensorEntityDescription(
        key="radar_projected_precipitation_duration",
        name="Radar projected precipitation duration",
        device_class=SensorDeviceClass.DURATION,
        imperial_unit=UnitOfTime.MINUTES,
        metric_unit=UnitOfTime.MINUTES,
        value_fn=lambda data: (
            None
            if data.radar is None or data.radar.nowcast is None
            else data.radar.nowcast.projected_duration_minutes
        ),
        suggested_display_precision=0,
    ),
    WeatherPlatformSensorEntityDescription(
        key="radar_nowcast_status",
        name="Radar nowcast status",
        value_fn=lambda data: (
            None
            if data.radar is None or data.radar.nowcast is None
            else data.radar.nowcast.status
        ),
    ),
    WeatherPlatformSensorEntityDescription(
        key="radar_motion_speed",
        name="Radar motion speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=UnitOfSpeed.MILES_PER_HOUR,
        metric_unit=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda data: (
            None
            if data.radar is None or data.radar.nowcast is None
            else data.radar.nowcast.motion_speed
        ),
        suggested_display_precision=1,
    ),
    WeatherPlatformSensorEntityDescription(
        key="radar_motion_direction",
        name="Radar motion direction",
        value_fn=lambda data: (
            None
            if data.radar is None or data.radar.nowcast is None
            else data.radar.nowcast.motion_direction
        ),
    ),
    WeatherPlatformSensorEntityDescription(
        key="radar_nowcast_peak_reflectivity",
        name="Radar nowcast peak reflectivity",
        imperial_unit="dBZ",
        metric_unit="dBZ",
        value_fn=lambda data: (
            None
            if data.radar is None or data.radar.nowcast is None
            else data.radar.nowcast.peak_reflectivity_dbz
        ),
        suggested_display_precision=1,
    ),
    WeatherPlatformSensorEntityDescription(
        key="recent_lightning_strikes",
        name="Lightning strikes last 2 minutes",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            None
            if data.radar is None or not data.radar.lightning.available
            else data.radar.lightning.recent_window_strike_count
        ),
        suggested_display_precision=0,
    ),
    WeatherPlatformSensorEntityDescription(
        key="lightning_strike_rate",
        name="Lightning strike rate",
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit="strikes/min",
        metric_unit="strikes/min",
        value_fn=lambda data: (
            None
            if data.radar is None or not data.radar.lightning.available
            else data.radar.lightning.recent_strike_rate_per_minute
        ),
        suggested_display_precision=2,
    ),
    WeatherPlatformSensorEntityDescription(
        key="nearest_lightning_distance",
        name="Nearest lightning distance",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=UnitOfLength.MILES,
        metric_unit=UnitOfLength.KILOMETERS,
        value_fn=lambda data: (
            None
            if data.radar is None or not data.radar.lightning.available
            else data.radar.lightning.nearest_distance
        ),
        suggested_display_precision=1,
    ),
    WeatherPlatformSensorEntityDescription(
        key="lightning_activity_trend",
        name="Lightning activity trend",
        device_class=SensorDeviceClass.ENUM,
        options=LIGHTNING_ACTIVITY_TRENDS,
        value_fn=lambda data: (
            None
            if data.radar is None or not data.radar.lightning.available
            else data.radar.lightning.activity_trend
        ),
    ),
    WeatherPlatformSensorEntityDescription(
        key="lightning_rate_trend",
        name="Lightning rate trend",
        device_class=SensorDeviceClass.ENUM,
        options=LIGHTNING_RATE_TRENDS,
        value_fn=lambda data: (
            None
            if data.radar is None or not data.radar.lightning.available
            else data.radar.lightning.rate_trend
        ),
    ),
    WeatherPlatformSensorEntityDescription(
        key="tracked_storms",
        name="Tracked storms",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            None
            if data.radar is None or not data.radar.storm_tracking.available
            else data.radar.storm_tracking.tracked_object_count
        ),
        attributes_fn=_tracked_storm_attributes,
        suggested_display_precision=0,
    ),
    WeatherPlatformSensorEntityDescription(
        key="approaching_tracked_storms",
        name="Approaching tracked storms",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_approaching_storm_count,
        suggested_display_precision=0,
    ),
    WeatherPlatformSensorEntityDescription(
        key="nearest_tracked_storm_distance",
        name="Nearest tracked storm distance",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=UnitOfLength.MILES,
        metric_unit=UnitOfLength.KILOMETERS,
        value_fn=_nearest_storm_distance,
        suggested_display_precision=1,
    ),
    WeatherPlatformSensorEntityDescription(
        key="strongest_tracked_storm_reflectivity",
        name="Strongest tracked storm reflectivity",
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit="dBZ",
        metric_unit="dBZ",
        value_fn=_strongest_storm_reflectivity,
        suggested_display_precision=1,
    ),
)

METEOROLOGY_SENSOR_DESCRIPTIONS = (
    WeatherPlatformSensorEntityDescription(
        key="feels_like",
        name="Feels like",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=UnitOfTemperature.FAHRENHEIT,
        metric_unit=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: (
            None
            if data.meteorology is None or data.meteorology.current is None
            else data.meteorology.current.feels_like
        ),
        attributes_fn=_meteorology_current_attributes,
        suggested_display_precision=1,
    ),
    WeatherPlatformSensorEntityDescription(
        key="heat_index",
        name="Heat index",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=UnitOfTemperature.FAHRENHEIT,
        metric_unit=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: (
            None
            if data.meteorology is None or data.meteorology.current is None
            else data.meteorology.current.heat_index
        ),
        suggested_display_precision=1,
    ),
    WeatherPlatformSensorEntityDescription(
        key="wind_chill",
        name="Wind chill",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=UnitOfTemperature.FAHRENHEIT,
        metric_unit=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: (
            None
            if data.meteorology is None or data.meteorology.current is None
            else data.meteorology.current.wind_chill
        ),
        suggested_display_precision=1,
    ),
    WeatherPlatformSensorEntityDescription(
        key="wet_bulb_temperature",
        name="Wet bulb temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=UnitOfTemperature.FAHRENHEIT,
        metric_unit=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: (
            None
            if data.meteorology is None or data.meteorology.current is None
            else data.meteorology.current.wet_bulb
        ),
        suggested_display_precision=1,
    ),
    WeatherPlatformSensorEntityDescription(
        key="wet_bulb_globe_temperature",
        name="Wet bulb globe temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=UnitOfTemperature.FAHRENHEIT,
        metric_unit=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: (
            None
            if data.meteorology is None
            or data.meteorology.wbgt is None
            or not data.meteorology.wbgt.available
            else data.meteorology.wbgt.wet_bulb_globe_temperature
        ),
        suggested_display_precision=1,
    ),
    WeatherPlatformSensorEntityDescription(
        key="vapor_pressure_deficit",
        name="Vapor pressure deficit",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=UnitOfPressure.KPA,
        metric_unit=UnitOfPressure.KPA,
        value_fn=lambda data: (
            None
            if data.meteorology is None or data.meteorology.moisture is None
            else data.meteorology.moisture.vapor_pressure_deficit
        ),
        suggested_display_precision=2,
    ),
    WeatherPlatformSensorEntityDescription(
        key="absolute_humidity",
        name="Absolute humidity",
        device_class=SensorDeviceClass.ABSOLUTE_HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=UnitOfDensity.GRAMS_PER_CUBIC_METER,
        metric_unit=UnitOfDensity.GRAMS_PER_CUBIC_METER,
        value_fn=lambda data: (
            None
            if data.meteorology is None or data.meteorology.moisture is None
            else data.meteorology.moisture.absolute_humidity
        ),
        suggested_display_precision=1,
    ),
    WeatherPlatformSensorEntityDescription(
        key="mixing_ratio",
        name="Mixing ratio",
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit="g/kg",
        metric_unit="g/kg",
        value_fn=lambda data: (
            None
            if data.meteorology is None or data.meteorology.moisture is None
            else data.meteorology.moisture.mixing_ratio
        ),
        suggested_display_precision=1,
    ),
    WeatherPlatformSensorEntityDescription(
        key="sea_level_pressure",
        name="Sea level pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=UnitOfPressure.INHG,
        metric_unit=UnitOfPressure.HPA,
        value_fn=lambda data: (
            None
            if data.meteorology is None or data.meteorology.pressure is None
            else data.meteorology.pressure.sea_level_pressure
        ),
        suggested_display_precision=2,
    ),
    WeatherPlatformSensorEntityDescription(
        key="pressure_change_3_hours",
        name="Pressure change 3 hours",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=UnitOfPressure.INHG,
        metric_unit=UnitOfPressure.HPA,
        value_fn=lambda data: (
            None
            if data.meteorology is None or data.meteorology.pressure is None
            else data.meteorology.pressure.pressure_change_three_hours
        ),
        suggested_display_precision=2,
    ),
    WeatherPlatformSensorEntityDescription(
        key="pressure_tendency",
        name="Pressure tendency",
        value_fn=lambda data: (
            None
            if data.meteorology is None or data.meteorology.pressure is None
            else data.meteorology.pressure.tendency
        ),
    ),
    WeatherPlatformSensorEntityDescription(
        key="estimated_cloud_base",
        name="Estimated cloud base",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=UnitOfLength.FEET,
        metric_unit=UnitOfLength.METERS,
        value_fn=lambda data: (
            None
            if data.meteorology is None or data.meteorology.thermodynamics is None
            else data.meteorology.thermodynamics.estimated_cloud_base_agl
        ),
        suggested_display_precision=0,
    ),
    WeatherPlatformSensorEntityDescription(
        key="gust_factor",
        name="Gust factor",
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit="ratio",
        metric_unit="ratio",
        value_fn=lambda data: (
            None
            if data.meteorology is None or data.meteorology.thermodynamics is None
            else data.meteorology.thermodynamics.gust_factor
        ),
        suggested_display_precision=2,
    ),
    WeatherPlatformSensorEntityDescription(
        key="cape",
        name="CAPE",
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit="J/kg",
        metric_unit="J/kg",
        value_fn=lambda data: (
            None
            if data.meteorology is None
            or data.meteorology.atmospheric_model is None
            or not data.meteorology.atmospheric_model.available
            else data.meteorology.atmospheric_model.cape
        ),
        attributes_fn=_atmospheric_model_attributes,
        suggested_display_precision=0,
    ),
    WeatherPlatformSensorEntityDescription(
        key="convective_inhibition",
        name="Convective inhibition",
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit="J/kg",
        metric_unit="J/kg",
        value_fn=lambda data: (
            None
            if data.meteorology is None
            or data.meteorology.atmospheric_model is None
            or not data.meteorology.atmospheric_model.available
            else data.meteorology.atmospheric_model.cin
        ),
        suggested_display_precision=0,
    ),
    WeatherPlatformSensorEntityDescription(
        key="lifted_index",
        name="Lifted index",
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit="index",
        metric_unit="index",
        value_fn=lambda data: (
            None
            if data.meteorology is None
            or data.meteorology.atmospheric_model is None
            or not data.meteorology.atmospheric_model.available
            else data.meteorology.atmospheric_model.lifted_index
        ),
        suggested_display_precision=1,
    ),
    WeatherPlatformSensorEntityDescription(
        key="precipitable_water",
        name="Precipitable water",
        device_class=SensorDeviceClass.PRECIPITATION,
        imperial_unit=UnitOfPrecipitationDepth.INCHES,
        metric_unit=UnitOfPrecipitationDepth.MILLIMETERS,
        value_fn=lambda data: (
            None
            if data.meteorology is None
            or data.meteorology.atmospheric_model is None
            or not data.meteorology.atmospheric_model.available
            else data.meteorology.atmospheric_model.precipitable_water
        ),
        suggested_display_precision=2,
    ),
    WeatherPlatformSensorEntityDescription(
        key="freezing_level",
        name="Freezing level",
        device_class=SensorDeviceClass.DISTANCE,
        imperial_unit=UnitOfLength.FEET,
        metric_unit=UnitOfLength.METERS,
        value_fn=lambda data: (
            None
            if data.meteorology is None
            or data.meteorology.atmospheric_model is None
            or not data.meteorology.atmospheric_model.available
            else data.meteorology.atmospheric_model.freezing_level
        ),
        suggested_display_precision=0,
    ),
    WeatherPlatformSensorEntityDescription(
        key="boundary_layer_height",
        name="Boundary layer height",
        device_class=SensorDeviceClass.DISTANCE,
        imperial_unit=UnitOfLength.FEET,
        metric_unit=UnitOfLength.METERS,
        value_fn=lambda data: (
            None
            if data.meteorology is None
            or data.meteorology.atmospheric_model is None
            or not data.meteorology.atmospheric_model.available
            else data.meteorology.atmospheric_model.boundary_layer_height
        ),
        suggested_display_precision=0,
    ),
    WeatherPlatformSensorEntityDescription(
        key="bulk_shear_0_to_6_km",
        name="Bulk shear 0 to 6 km",
        device_class=SensorDeviceClass.WIND_SPEED,
        imperial_unit=UnitOfSpeed.MILES_PER_HOUR,
        metric_unit=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda data: (
            None
            if data.meteorology is None
            or data.meteorology.atmospheric_model is None
            or not data.meteorology.atmospheric_model.available
            else data.meteorology.atmospheric_model.bulk_shear_0_to_6_km
        ),
        suggested_display_precision=1,
    ),
    WeatherPlatformSensorEntityDescription(
        key="severe_weather_outlook",
        name="Severe weather outlook",
        value_fn=lambda data: (
            None
            if data.meteorology is None
            or data.meteorology.severe_weather is None
            or not data.meteorology.severe_weather.available
            else data.meteorology.severe_weather.outlook_level
        ),
        attributes_fn=_severe_weather_attributes,
    ),
    WeatherPlatformSensorEntityDescription(
        key="severe_weather_composite_score",
        name="Severe weather composite score",
        value_fn=lambda data: (
            None
            if data.meteorology is None
            or data.meteorology.severe_weather is None
            or not data.meteorology.severe_weather.available
            else data.meteorology.severe_weather.composite_score
        ),
        suggested_display_precision=0,
    ),
)

HYDROLOGY_SENSOR_DESCRIPTIONS = (
    WeatherPlatformSensorEntityDescription(
        key="antecedent_rainfall_level",
        name="Antecedent rainfall level",
        value_fn=lambda data: (
            None
            if data.hydrology is None or not data.hydrology.rainfall.available
            else data.hydrology.rainfall.level
        ),
        attributes_fn=_antecedent_rainfall_attributes,
    ),
    WeatherPlatformSensorEntityDescription(
        key="rainfall_24_hours",
        name="Rainfall 24 hours",
        device_class=SensorDeviceClass.PRECIPITATION,
        imperial_unit=UnitOfPrecipitationDepth.INCHES,
        metric_unit=UnitOfPrecipitationDepth.MILLIMETERS,
        value_fn=lambda data: (
            None
            if data.hydrology is None or not data.hydrology.rainfall.available
            else data.hydrology.rainfall.rainfall_24_hours
        ),
        suggested_display_precision=2,
    ),
    WeatherPlatformSensorEntityDescription(
        key="rainfall_3_days",
        name="Rainfall 3 days",
        device_class=SensorDeviceClass.PRECIPITATION,
        imperial_unit=UnitOfPrecipitationDepth.INCHES,
        metric_unit=UnitOfPrecipitationDepth.MILLIMETERS,
        value_fn=lambda data: (
            None
            if data.hydrology is None or not data.hydrology.rainfall.available
            else data.hydrology.rainfall.rainfall_3_days
        ),
        suggested_display_precision=2,
    ),
    WeatherPlatformSensorEntityDescription(
        key="rainfall_7_days",
        name="Rainfall 7 days",
        device_class=SensorDeviceClass.PRECIPITATION,
        imperial_unit=UnitOfPrecipitationDepth.INCHES,
        metric_unit=UnitOfPrecipitationDepth.MILLIMETERS,
        value_fn=lambda data: (
            None
            if data.hydrology is None or not data.hydrology.rainfall.available
            else data.hydrology.rainfall.rainfall_7_days
        ),
        suggested_display_precision=2,
    ),
    WeatherPlatformSensorEntityDescription(
        key="rainfall_14_days",
        name="Rainfall 14 days",
        device_class=SensorDeviceClass.PRECIPITATION,
        imperial_unit=UnitOfPrecipitationDepth.INCHES,
        metric_unit=UnitOfPrecipitationDepth.MILLIMETERS,
        value_fn=lambda data: (
            None
            if data.hydrology is None or not data.hydrology.rainfall.available
            else data.hydrology.rainfall.rainfall_14_days
        ),
        suggested_display_precision=2,
    ),
    WeatherPlatformSensorEntityDescription(
        key="rainfall_30_days",
        name="Rainfall 30 days",
        device_class=SensorDeviceClass.PRECIPITATION,
        imperial_unit=UnitOfPrecipitationDepth.INCHES,
        metric_unit=UnitOfPrecipitationDepth.MILLIMETERS,
        value_fn=lambda data: (
            None
            if data.hydrology is None or not data.hydrology.rainfall.available
            else data.hydrology.rainfall.rainfall_30_days
        ),
        suggested_display_precision=2,
    ),
    WeatherPlatformSensorEntityDescription(
        key="rising_hydrology_gauges",
        name="Rising hydrology gauges",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            None
            if data.hydrology is None or not data.hydrology.gauges.available
            else data.hydrology.gauges.rising_count
        ),
        suggested_display_precision=0,
    ),
    WeatherPlatformSensorEntityDescription(
        key="nearest_hydrology_gauge_distance",
        name="Nearest hydrology gauge distance",
        device_class=SensorDeviceClass.DISTANCE,
        imperial_unit=UnitOfLength.MILES,
        metric_unit=UnitOfLength.KILOMETERS,
        value_fn=_nearest_gauge_distance,
        attributes_fn=_nearest_gauge_attributes,
        suggested_display_precision=1,
    ),
    WeatherPlatformSensorEntityDescription(
        key="nearest_hydrology_gauge_stage",
        name="Nearest hydrology gauge stage",
        device_class=SensorDeviceClass.DISTANCE,
        imperial_unit=UnitOfLength.FEET,
        metric_unit=UnitOfLength.METERS,
        value_fn=_nearest_gauge_stage,
        suggested_display_precision=2,
    ),
    WeatherPlatformSensorEntityDescription(
        key="nearest_hydrology_gauge_trend",
        name="Nearest hydrology gauge trend",
        value_fn=_nearest_gauge_trend,
    ),
)

TODAY_SENSOR_DESCRIPTIONS = (
    WeatherPlatformSensorEntityDescription(
        key="today_weather_story",
        name="Today weather story",
        value_fn=lambda data: None if data.today is None else data.today.headline,
        attributes_fn=_today_attributes,
    ),
)

CLIMATE_SENSOR_DESCRIPTIONS = (
    WeatherPlatformSensorEntityDescription(
        key="climate_summary",
        name="Climate summary",
        value_fn=lambda data: None if data.climate is None else data.climate.headline,
        attributes_fn=_climate_attributes,
    ),
    WeatherPlatformSensorEntityDescription(
        key="latest_mean_temperature_anomaly",
        name="Latest mean temperature anomaly",
        device_class=SensorDeviceClass.TEMPERATURE_DELTA,
        imperial_unit=UnitOfTemperature.FAHRENHEIT,
        metric_unit=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: (
            None
            if data.climate is None or not data.climate.available
            else data.climate.latest_day.mean_temperature_anomaly
        ),
        suggested_display_precision=1,
    ),
    WeatherPlatformSensorEntityDescription(
        key="latest_high_temperature_percentile",
        name="Latest high temperature percentile",
        imperial_unit=UnitOfRatio.PERCENTAGE,
        metric_unit=UnitOfRatio.PERCENTAGE,
        value_fn=lambda data: (
            None
            if data.climate is None or not data.climate.available
            else data.climate.latest_day.high_temperature_percentile
        ),
        suggested_display_precision=0,
    ),
    WeatherPlatformSensorEntityDescription(
        key="latest_low_temperature_percentile",
        name="Latest low temperature percentile",
        imperial_unit=UnitOfRatio.PERCENTAGE,
        metric_unit=UnitOfRatio.PERCENTAGE,
        value_fn=lambda data: (
            None
            if data.climate is None or not data.climate.available
            else data.climate.latest_day.low_temperature_percentile
        ),
        suggested_display_precision=0,
    ),
    WeatherPlatformSensorEntityDescription(
        key="month_rainfall_departure",
        name="Month rainfall departure",
        device_class=SensorDeviceClass.PRECIPITATION,
        imperial_unit=UnitOfPrecipitationDepth.INCHES,
        metric_unit=UnitOfPrecipitationDepth.MILLIMETERS,
        value_fn=lambda data: (
            None
            if data.climate is None or not data.climate.available
            else data.climate.month.rainfall_departure
        ),
        suggested_display_precision=2,
    ),
    WeatherPlatformSensorEntityDescription(
        key="month_heating_degree_day_departure",
        name="Month heating degree day departure",
        imperial_unit="F-day",
        metric_unit="C-day",
        value_fn=lambda data: (
            None
            if data.climate is None or not data.climate.available
            else data.climate.month.heating_degree_day_departure
        ),
        suggested_display_precision=1,
    ),
    WeatherPlatformSensorEntityDescription(
        key="month_cooling_degree_day_departure",
        name="Month cooling degree day departure",
        imperial_unit="F-day",
        metric_unit="C-day",
        value_fn=lambda data: (
            None
            if data.climate is None or not data.climate.available
            else data.climate.month.cooling_degree_day_departure
        ),
        suggested_display_precision=1,
    ),
    WeatherPlatformSensorEntityDescription(
        key="current_dry_streak",
        name="Current dry streak",
        device_class=SensorDeviceClass.DURATION,
        imperial_unit=UnitOfTime.DAYS,
        metric_unit=UnitOfTime.DAYS,
        value_fn=lambda data: (
            None
            if data.climate is None or not data.climate.available
            else data.climate.streaks.current_dry_days
        ),
        suggested_display_precision=0,
    ),
    WeatherPlatformSensorEntityDescription(
        key="current_wet_streak",
        name="Current wet streak",
        device_class=SensorDeviceClass.DURATION,
        imperial_unit=UnitOfTime.DAYS,
        metric_unit=UnitOfTime.DAYS,
        value_fn=lambda data: (
            None
            if data.climate is None or not data.climate.available
            else data.climate.streaks.current_wet_days
        ),
        suggested_display_precision=0,
    ),
    WeatherPlatformSensorEntityDescription(
        key="current_hot_streak",
        name="Current hot streak",
        device_class=SensorDeviceClass.DURATION,
        imperial_unit=UnitOfTime.DAYS,
        metric_unit=UnitOfTime.DAYS,
        value_fn=lambda data: (
            None
            if data.climate is None or not data.climate.available
            else data.climate.streaks.current_hot_days
        ),
        suggested_display_precision=0,
    ),
)

EVENT_SENSOR_DESCRIPTIONS = (
    WeatherPlatformSensorEntityDescription(
        key="active_weather_platform_events",
        name="Active Weather Platform events",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: None if data.events is None else data.events.count,
        attributes_fn=_active_events_attributes,
        suggested_display_precision=0,
    ),
    WeatherPlatformSensorEntityDescription(
        key="highest_event_priority",
        name="Highest event priority",
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_PRIORITIES,
        value_fn=_highest_event_priority,
    ),
    WeatherPlatformSensorEntityDescription(
        key="latest_active_event",
        name="Latest active event",
        value_fn=_latest_active_event,
    ),
    WeatherPlatformSensorEntityDescription(
        key="latest_active_event_phase",
        name="Latest active event phase",
        value_fn=_latest_active_event_phase,
    ),
)

IMPACT_SENSOR_DESCRIPTIONS = (
    WeatherPlatformSensorEntityDescription(
        key="impact_forecast",
        name="Impact forecast",
        value_fn=lambda data: None if data.impacts is None else data.impacts.headline,
        attributes_fn=lambda data: (
            {}
            if data.impacts is None
            else {
                "summary": data.impacts.summary,
                "horizon_hours": data.impacts.horizon_hours,
                "radar_hazard_active": data.impacts.radar_hazard_active,
                "radar_detail": data.impacts.radar_detail,
            }
        ),
    ),
    WeatherPlatformSensorEntityDescription(
        key="outdoor_activity_impact",
        name="Outdoor activity impact",
        device_class=SensorDeviceClass.ENUM,
        options=IMPACT_RATINGS,
        value_fn=lambda data: _impact_rating(data, "outdoor"),
        attributes_fn=lambda data: _impact_attributes(data, "outdoor"),
    ),
    WeatherPlatformSensorEntityDescription(
        key="open_windows_impact",
        name="Open windows impact",
        device_class=SensorDeviceClass.ENUM,
        options=IMPACT_RATINGS,
        value_fn=lambda data: _impact_rating(data, "windows"),
        attributes_fn=lambda data: _impact_attributes(data, "windows"),
    ),
    WeatherPlatformSensorEntityDescription(
        key="yard_work_impact",
        name="Yard work impact",
        device_class=SensorDeviceClass.ENUM,
        options=IMPACT_RATINGS,
        value_fn=lambda data: _impact_rating(data, "yard"),
        attributes_fn=lambda data: _impact_attributes(data, "yard"),
    ),
    WeatherPlatformSensorEntityDescription(
        key="drying_conditions_impact",
        name="Drying conditions impact",
        device_class=SensorDeviceClass.ENUM,
        options=IMPACT_RATINGS,
        value_fn=lambda data: _impact_rating(data, "drying"),
        attributes_fn=lambda data: _impact_attributes(data, "drying"),
    ),
    WeatherPlatformSensorEntityDescription(
        key="frost_risk_impact",
        name="Frost risk impact",
        device_class=SensorDeviceClass.ENUM,
        options=IMPACT_RATINGS,
        value_fn=lambda data: _impact_rating(data, "frost"),
        attributes_fn=lambda data: _impact_attributes(data, "frost"),
    ),
    WeatherPlatformSensorEntityDescription(
        key="sun_exposure_impact",
        name="Sun exposure impact",
        device_class=SensorDeviceClass.ENUM,
        options=IMPACT_RATINGS,
        value_fn=lambda data: _impact_rating(data, "sun"),
        attributes_fn=lambda data: _impact_attributes(data, "sun"),
    ),
)

DIAGNOSTIC_SENSOR_DESCRIPTIONS = (
    WeatherPlatformSensorEntityDescription(
        key="station_data_age",
        name="Station data age",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        imperial_unit=UnitOfTime.SECONDS,
        metric_unit=UnitOfTime.SECONDS,
        value_fn=lambda data: data.current.station.age_seconds,
        suggested_display_precision=0,
    ),
)

SENSOR_DESCRIPTIONS = (
    BASE_SENSOR_DESCRIPTIONS
    + AIR_QUALITY_SENSOR_DESCRIPTIONS
    + ALERT_SENSOR_DESCRIPTIONS
    + RADAR_SENSOR_DESCRIPTIONS
    + METEOROLOGY_SENSOR_DESCRIPTIONS
    + HYDROLOGY_SENSOR_DESCRIPTIONS
    + TODAY_SENSOR_DESCRIPTIONS
    + CLIMATE_SENSOR_DESCRIPTIONS
    + EVENT_SENSOR_DESCRIPTIONS
    + IMPACT_SENSOR_DESCRIPTIONS
    + DIAGNOSTIC_SENSOR_DESCRIPTIONS
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[WeatherPlatformDataUpdateCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add Weather Platform sensor entities."""
    del hass
    async_add_entities(
        [
            WeatherPlatformSensorEntity(
                entry,
                entry.runtime_data,
                description,
            )
            for description in SENSOR_DESCRIPTIONS
        ]
    )


class WeatherPlatformSensorEntity(
    CoordinatorEntity[WeatherPlatformDataUpdateCoordinator],
    SensorEntity,
):
    """Weather Platform sensor backed by coordinator data."""

    entity_description: WeatherPlatformSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry[WeatherPlatformDataUpdateCoordinator],
        coordinator: WeatherPlatformDataUpdateCoordinator,
        description: WeatherPlatformSensorEntityDescription,
    ) -> None:
        """Initialize a Weather Platform sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        identifier = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{identifier}:{description.key}"
        self._attr_native_unit_of_measurement = (
            description.metric_unit
            if coordinator.unit_system == API_UNIT_SYSTEM_METRIC
            else description.imperial_unit
        )

        platform_version = (
            coordinator.metadata.platform_version
            if coordinator.metadata is not None
            else None
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            name=NAME,
            manufacturer=NAME,
            model="REST API",
            sw_version=platform_version,
            configuration_url=f"{coordinator.client.base_url}/current",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    @override
    def native_value(self) -> SensorValue:
        """Return the current sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, object] | None:
        """Return additional Weather Platform context."""
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.coordinator.data)
