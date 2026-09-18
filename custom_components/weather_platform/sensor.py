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
    UnitOfTime,
    UnitOfVolumetricFlux,
)
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import API_UNIT_SYSTEM_METRIC, DOMAIN, NAME
from .coordinator import WeatherPlatformDataUpdateCoordinator

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .api import WeatherPlatformImpactProfile
    from .coordinator import WeatherPlatformData

type SensorValue = float | int | str | None

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


def _highest_alert_level(
    data: WeatherPlatformData,
) -> str | None:
    """Return the highest active alert level."""
    if data.alerts is None:
        return None

    if data.alerts.active_count == 0:
        return "None"

    return data.alerts.highest_level


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


SENSOR_DESCRIPTIONS = (
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
    WeatherPlatformSensorEntityDescription(
        key="air_quality_index",
        name="Air quality index",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            None if data.air_quality is None else data.air_quality.current.us_aqi
        ),
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
        key="active_weather_alerts",
        name="Active weather alerts",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: None if data.alerts is None else data.alerts.active_count,
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
    WeatherPlatformSensorEntityDescription(
        key="active_weather_platform_events",
        name="Active Weather Platform events",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: None if data.events is None else data.events.count,
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
    WeatherPlatformSensorEntityDescription(
        key="impact_forecast",
        name="Impact forecast",
        value_fn=lambda data: None if data.impacts is None else data.impacts.headline,
    ),
    WeatherPlatformSensorEntityDescription(
        key="outdoor_activity_impact",
        name="Outdoor activity impact",
        device_class=SensorDeviceClass.ENUM,
        options=IMPACT_RATINGS,
        value_fn=lambda data: _impact_rating(data, "outdoor"),
    ),
    WeatherPlatformSensorEntityDescription(
        key="open_windows_impact",
        name="Open windows impact",
        device_class=SensorDeviceClass.ENUM,
        options=IMPACT_RATINGS,
        value_fn=lambda data: _impact_rating(data, "windows"),
    ),
    WeatherPlatformSensorEntityDescription(
        key="yard_work_impact",
        name="Yard work impact",
        device_class=SensorDeviceClass.ENUM,
        options=IMPACT_RATINGS,
        value_fn=lambda data: _impact_rating(data, "yard"),
    ),
    WeatherPlatformSensorEntityDescription(
        key="drying_conditions_impact",
        name="Drying conditions impact",
        device_class=SensorDeviceClass.ENUM,
        options=IMPACT_RATINGS,
        value_fn=lambda data: _impact_rating(data, "drying"),
    ),
    WeatherPlatformSensorEntityDescription(
        key="frost_risk_impact",
        name="Frost risk impact",
        device_class=SensorDeviceClass.ENUM,
        options=IMPACT_RATINGS,
        value_fn=lambda data: _impact_rating(data, "frost"),
    ),
    WeatherPlatformSensorEntityDescription(
        key="sun_exposure_impact",
        name="Sun exposure impact",
        device_class=SensorDeviceClass.ENUM,
        options=IMPACT_RATINGS,
        value_fn=lambda data: _impact_rating(data, "sun"),
    ),
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
            configuration_url=coordinator.client.base_url,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    @override
    def native_value(self) -> SensorValue:
        """Return the current sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
