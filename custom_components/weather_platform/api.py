"""Async REST client for Weather Platform."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date
from typing import Any, cast
from urllib.parse import urlsplit, urlunsplit

from aiohttp import ClientError, ClientSession

from .const import API_BASE_PATH, API_NAME, API_VERSION, REQUEST_TIMEOUT_SECONDS

type JsonObject = dict[str, Any]


class WeatherPlatformApiError(Exception):
    """Base exception for Weather Platform API errors."""


class WeatherPlatformConnectionError(WeatherPlatformApiError):
    """Raised when Weather Platform cannot be reached."""


class WeatherPlatformInvalidResponseError(WeatherPlatformApiError):
    """Raised when Weather Platform returns an unexpected response."""


class WeatherPlatformInvalidUrlError(WeatherPlatformApiError):
    """Raised when a Weather Platform base URL is invalid."""


@dataclass(frozen=True, slots=True)
class WeatherPlatformMetadata:
    """Weather Platform API metadata."""

    name: str
    api_version: str
    platform_version: str
    resources: dict[str, str]


@dataclass(frozen=True, slots=True)
class WeatherPlatformStation:
    """Weather Platform station metadata."""

    code: str
    name: str
    observed_at: str | None
    age_seconds: int | None
    stale: bool
    source: str | None


@dataclass(frozen=True, slots=True)
class WeatherPlatformCurrentConditions:
    """Current conditions reported by Weather Platform."""

    temperature: float | None
    dew_point: float | None
    relative_humidity: float | None
    station_pressure: float | None
    wind_speed: float | None
    wind_gust: float | None
    wind_direction_degrees: int | None
    rain_rate: float | None
    daily_rain: float | None
    event_rain: float | None
    solar_radiation: float | None
    solar_illuminance: float | None
    uv_index: float | None


@dataclass(frozen=True, slots=True)
class WeatherPlatformCurrentData:
    """Current Weather Platform data."""

    generated_at: str
    unit_system: str
    station: WeatherPlatformStation
    condition: str | None
    conditions: WeatherPlatformCurrentConditions


@dataclass(frozen=True, slots=True)
class WeatherPlatformWind:
    """Forecast wind range from Weather Platform."""

    minimum: float | None
    maximum: float | None
    direction: str | None


@dataclass(frozen=True, slots=True)
class WeatherPlatformForecastPeriod:
    """One twice-daily Weather Platform forecast period."""

    name: str
    start_time: str
    end_time: str
    daytime: bool
    temperature: float | None
    precipitation_probability: int | None
    short_forecast: str | None
    detailed_forecast: str | None
    wind: WeatherPlatformWind | None


@dataclass(frozen=True, slots=True)
class WeatherPlatformHourlyForecast:
    """Hourly Weather Platform forecast."""

    valid_at: str
    temperature: float | None
    precipitation_probability: int | None
    short_forecast: str | None
    wind: WeatherPlatformWind | None
    wind_gust: float | None


@dataclass(frozen=True, slots=True)
class WeatherPlatformDailyForecast:
    """Daily Weather Platform forecast."""

    date: date
    display_name: str
    high_temperature: float | None
    low_temperature: float | None
    precipitation_probability: int | None
    short_forecast: str | None


@dataclass(frozen=True, slots=True)
class WeatherPlatformForecastData:
    """Forecast data reported by Weather Platform."""

    generated_at: str
    unit_system: str
    periods_available: bool
    hourly_available: bool
    daily: tuple[WeatherPlatformDailyForecast, ...]
    hourly: tuple[WeatherPlatformHourlyForecast, ...]
    periods: tuple[WeatherPlatformForecastPeriod, ...] = ()


@dataclass(frozen=True, slots=True)
class WeatherPlatformAirQualityPeriod:
    """Air-quality guidance for a point in time."""

    valid_at: str | None
    us_aqi: int | None
    category: str | None
    category_headline: str | None
    health_advice: str | None
    dominant_pollutant: str | None
    dominant_pollutant_aqi: int | None
    pm25: float | None
    pm10: float | None
    ozone: float | None
    pm25_aqi: int | None = None
    pm10_aqi: int | None = None
    ozone_aqi: int | None = None
    nitrogen_dioxide_aqi: int | None = None
    carbon_monoxide_aqi: int | None = None
    sulphur_dioxide_aqi: int | None = None
    nitrogen_dioxide: float | None = None
    carbon_monoxide: float | None = None
    sulphur_dioxide: float | None = None
    aerosol_optical_depth: float | None = None
    dust: float | None = None
    wildfire_pm10: float | None = None
    wildfire_pm10_share_percent: float | None = None
    uv_index: float | None = None


@dataclass(frozen=True, slots=True)
class WeatherPlatformAirQualityData:
    """Air-quality guidance reported by Weather Platform."""

    generated_at: str
    provider: str | None
    model: str | None
    fetched_at: str | None
    stale: bool
    current: WeatherPlatformAirQualityPeriod
    peak_next_24_hours: WeatherPlatformAirQualityPeriod | None
    minimum_next_24_hours: WeatherPlatformAirQualityPeriod | None = None
    hourly: tuple[WeatherPlatformAirQualityPeriod, ...] = ()


@dataclass(frozen=True, slots=True)
class WeatherPlatformAlert:
    """One active Weather Platform alert."""

    event: str | None
    headline: str | None
    severity: str | None
    level: str | None
    critical: bool
    expires_at: str | None
    alert_id: str | None = None
    description: str | None = None
    instruction: str | None = None
    area: str | None = None
    certainty: str | None = None
    urgency: str | None = None
    sender: str | None = None
    sent_at: str | None = None
    effective_at: str | None = None
    onset_at: str | None = None
    status: str | None = None
    message_type: str | None = None


@dataclass(frozen=True, slots=True)
class WeatherPlatformAlertsData:
    """Active alerts reported by Weather Platform."""

    generated_at: str
    active_count: int
    critical_count: int
    highest_level: str | None
    alerts: tuple[WeatherPlatformAlert, ...]


@dataclass(frozen=True, slots=True)
class WeatherPlatformRadarPrecipitation:
    """Radar precipitation at the configured home location."""

    available: bool
    inside_coverage: bool
    stale: bool
    source: str | None
    precipitation_rate: float | None
    two_minute_precipitation: float | None
    reflectivity_dbz: float | None
    intensity: str | None
    precipitation_valid_at: str | None
    reflectivity_valid_at: str | None


@dataclass(frozen=True, slots=True)
class WeatherPlatformRadarNowcast:
    """Short-range radar precipitation nowcast."""

    available: bool
    status: str | None
    radar_valid_at: str | None
    precipitation_now: bool
    arrival_lead_minutes: int | None
    arrival_at: str | None
    departure_lead_minutes: int | None
    departure_at: str | None
    projected_duration_minutes: int | None
    peak_reflectivity_dbz: float | None
    arrival_echo_coverage_percent: float | None
    maximum_evaluated_lead_minutes: int | None
    coverage_limited: bool
    motion_direction: str | None
    motion_speed: float | None
    motion_bearing_degrees: float | None
    motion_coherence_percent: float | None
    motion_consensus_sample_count: int | None
    motion_consensus_inlier_count: int | None


@dataclass(frozen=True, slots=True)
class WeatherPlatformRadarLightning:
    """Lightning intelligence reported by Weather Platform."""

    available: bool
    fetched_at: str | None
    strike_count: int
    recent_window_strike_count: int
    strike_rate_per_minute: float | None
    recent_strike_rate_per_minute: float | None
    nearest_distance: float | None
    distance_shift: float | None
    activity_trend: str | None
    rate_trend: str | None
    radius: float | None = None
    prior_window_strike_count: int | None = None
    prior_strike_rate_per_minute: float | None = None


@dataclass(frozen=True, slots=True)
class WeatherPlatformRadarStorm:
    """Tracked storm object reported by Weather Platform."""

    storm_id: str | None
    intensity: str | None
    lifecycle_stage: str | None
    distance: float | None
    peak_reflectivity_dbz: float | None
    approaching_home: bool
    reflectivity_trend: str | None = None
    area_trend: str | None = None
    speed: float | None = None
    bearing_degrees: float | None = None
    direction: str | None = None
    age_minutes: int | None = None


@dataclass(frozen=True, slots=True)
class WeatherPlatformRadarStormTracking:
    """Storm-tracking intelligence reported by Weather Platform."""

    available: bool
    status: str | None
    valid_at: str | None
    tracked_object_count: int
    storms: tuple[WeatherPlatformRadarStorm, ...]
    detection_threshold_dbz: float | None = None


@dataclass(frozen=True, slots=True)
class WeatherPlatformRadarData:
    """Radar intelligence reported by Weather Platform."""

    generated_at: str
    unit_system: str
    lightning: WeatherPlatformRadarLightning
    storm_tracking: WeatherPlatformRadarStormTracking
    precipitation: WeatherPlatformRadarPrecipitation | None = None
    nowcast: WeatherPlatformRadarNowcast | None = None


@dataclass(frozen=True, slots=True)
class WeatherPlatformEvent:
    """One active Weather Platform weather event."""

    event_type: str
    type_label: str | None
    phase: str | None
    phase_label: str | None
    priority: str
    priority_label: str | None
    trigger_source: str | None
    detected_at: str | None
    event_id: int | None = None
    station_code: str | None = None
    category: str | None = None
    state: str | None = None
    state_label: str | None = None
    last_evidence_at: str | None = None
    resolved_at: str | None = None


@dataclass(frozen=True, slots=True)
class WeatherPlatformEventsData:
    """Active durable weather events reported by Weather Platform."""

    generated_at: str
    count: int
    events: tuple[WeatherPlatformEvent, ...]


@dataclass(frozen=True, slots=True)
class WeatherPlatformImpactWindow:
    """A recommended or concerning Weather Platform time window."""

    started_at: str | None
    ended_at: str | None
    rating: str | None
    label: str | None


@dataclass(frozen=True, slots=True)
class WeatherPlatformImpactProfile:
    """Current Weather Platform impact-profile guidance."""

    key: str
    title: str
    current_rating: str | None
    current_status: str | None
    subtitle: str | None = None
    headline: str | None = None
    detail: str | None = None
    next_change_at: str | None = None
    next_change_label: str | None = None
    best_window: WeatherPlatformImpactWindow | None = None
    concern_window: WeatherPlatformImpactWindow | None = None
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class WeatherPlatformImpactsData:
    """Weather-impact guidance reported by Weather Platform."""

    generated_at: str | None
    unit_system: str
    horizon_hours: int
    headline: str | None
    summary: str | None
    radar_hazard_active: bool
    radar_detail: str | None
    profiles: tuple[WeatherPlatformImpactProfile, ...]


@dataclass(frozen=True, slots=True)
class WeatherPlatformStorySection:
    """One section of the synthesized daily weather story."""

    key: str
    label: str | None
    headline: str | None
    detail: str | None
    meta: str | None
    tone: str | None
    action_label: str | None
    action_path: str | None


@dataclass(frozen=True, slots=True)
class WeatherPlatformStoryWindow:
    """One useful or impactful time window in the daily story."""

    label: str | None
    headline: str | None
    detail: str | None
    started_at: str | None
    ended_at: str | None
    tone: str | None


@dataclass(frozen=True, slots=True)
class WeatherPlatformTodayData:
    """Synthesized Weather Platform daily story."""

    generated_at: str
    observed_at: str | None
    unit_system: str
    headline: str | None
    summary: str | None
    tone: str | None
    sections: tuple[WeatherPlatformStorySection, ...]
    evolution: WeatherPlatformStorySection | None
    best_window: WeatherPlatformStoryWindow | None
    impact_window: WeatherPlatformStoryWindow | None


@dataclass(frozen=True, slots=True)
class WeatherPlatformAntecedentRainfall:
    """Recent rainfall context from Weather Platform."""

    available: bool
    generated_at: str | None
    latest_observation_at: str | None
    last_rain_at: str | None
    level: str | None
    headline: str | None
    detail: str | None
    rainfall_24_hours: float | None
    rainfall_3_days: float | None
    rainfall_7_days: float | None
    rainfall_14_days: float | None
    rainfall_30_days: float | None


@dataclass(frozen=True, slots=True)
class WeatherPlatformHydrologyGauge:
    """One nearby hydrology gauge."""

    monitoring_location_id: str | None
    site_number: str | None
    name: str | None
    site_type: str | None
    distance: float | None
    stage: float | None
    stage_change_6_hours: float | None
    stage_change_24_hours: float | None
    discharge: float | None
    discharge_change_6_hours: float | None
    discharge_change_24_hours: float | None
    observed_at: str | None
    trend: str | None


@dataclass(frozen=True, slots=True)
class WeatherPlatformHydrologyGauges:
    """Nearby hydrology gauge summary."""

    available: bool
    stale: bool
    fetched_at: str | None
    rising_count: int
    gauges: tuple[WeatherPlatformHydrologyGauge, ...]


@dataclass(frozen=True, slots=True)
class WeatherPlatformHydrologyData:
    """Hydrology guidance reported by Weather Platform."""

    generated_at: str
    unit_system: str
    rainfall: WeatherPlatformAntecedentRainfall
    gauges: WeatherPlatformHydrologyGauges


@dataclass(frozen=True, slots=True)
class WeatherPlatformClimateLatestDay:
    """Latest complete climate day."""

    date: str | None
    mean_temperature: float | None
    mean_temperature_anomaly: float | None
    high_temperature_percentile: int | None
    low_temperature_percentile: int | None
    percentile_sample_count: int
    percentile_context: str | None


@dataclass(frozen=True, slots=True)
class WeatherPlatformClimateMonth:
    """Current climate month summary."""

    complete_day_count: int
    rainfall: float | None
    expected_rainfall: float | None
    rainfall_departure: float | None
    heating_degree_days: float | None
    heating_degree_day_departure: float | None
    cooling_degree_days: float | None
    cooling_degree_day_departure: float | None


@dataclass(frozen=True, slots=True)
class WeatherPlatformClimateStreaks:
    """Current and longest climate streaks."""

    current_dry_days: int
    longest_dry_days: int
    current_wet_days: int
    longest_wet_days: int
    current_hot_days: int
    longest_hot_days: int
    current_warm_night_days: int
    longest_warm_night_days: int


@dataclass(frozen=True, slots=True)
class WeatherPlatformClimateRecords:
    """Archive climate records."""

    highest_high_temperature: float | None
    highest_high_date: str | None
    lowest_low_temperature: float | None
    lowest_low_date: str | None
    wettest_day_rainfall: float | None
    wettest_day_date: str | None
    strongest_wind_gust: float | None
    strongest_wind_gust_date: str | None


@dataclass(frozen=True, slots=True)
class WeatherPlatformClimateData:
    """Climate context reported by Weather Platform."""

    generated_at: str
    unit_system: str
    available: bool
    first_observed_at: str | None
    last_observed_at: str | None
    headline: str | None
    summary: str | None
    tone: str | None
    complete_day_count: int
    archive_year_count: int
    latest_day: WeatherPlatformClimateLatestDay
    month: WeatherPlatformClimateMonth
    streaks: WeatherPlatformClimateStreaks
    records: WeatherPlatformClimateRecords


@dataclass(frozen=True, slots=True)
class WeatherPlatformMeteorologyCurrent:
    """Derived current meteorology."""

    observed_at: str | None
    feels_like: float | None
    feels_like_type: str | None
    heat_index: float | None
    wind_chill: float | None
    wet_bulb: float | None
    rain_intensity: str | None
    wind_condition: str | None


@dataclass(frozen=True, slots=True)
class WeatherPlatformMeteorologyMoisture:
    """Derived atmospheric moisture metrics."""

    dew_point_depression: float | None
    dew_point_depression_interpretation: str | None
    wet_bulb_depression: float | None
    wet_bulb_depression_interpretation: str | None
    vapor_pressure_deficit: float | None
    vapor_pressure_deficit_interpretation: str | None
    absolute_humidity: float | None
    mixing_ratio: float | None


@dataclass(frozen=True, slots=True)
class WeatherPlatformMeteorologyPressure:
    """Derived pressure metrics."""

    sea_level_pressure: float | None
    pressure_change_three_hours: float | None
    pressure_change_long_period: float | None
    tendency: str | None


@dataclass(frozen=True, slots=True)
class WeatherPlatformMeteorologyThermodynamics:
    """Derived thermodynamic metrics."""

    estimated_cloud_base_agl: float | None
    estimated_cloud_base_msl: float | None
    cloud_base_interpretation: str | None
    potential_temperature: float | None
    gust_factor: float | None
    gust_factor_interpretation: str | None
    daily_maximum_wind_gust: float | None
    wind_gust_below_daily_maximum: float | None


@dataclass(frozen=True, slots=True)
class WeatherPlatformMeteorologyWbgt:
    """Wet-bulb globe temperature estimate."""

    available: bool
    wet_bulb_globe_temperature: float | None
    natural_wet_bulb_temperature: float | None
    globe_temperature: float | None
    two_meter_wind_speed: float | None
    solar_radiation: float | None
    solar_zenith_degrees: float | None


@dataclass(frozen=True, slots=True)
class WeatherPlatformAtmosphericModel:
    """Atmospheric model metrics."""

    available: bool
    stale: bool
    provider: str | None
    model: str | None
    valid_at: str | None
    cape: float | None
    cin: float | None
    lifted_index: float | None
    precipitable_water: float | None
    freezing_level: float | None
    boundary_layer_height: float | None
    lapse_rate_850_to_500: float | None
    lapse_rate_700_to_500: float | None
    surface_pressure: float | None
    surface_temperature: float | None
    surface_dew_point: float | None
    surface_wind_speed: float | None
    surface_wind_direction_degrees: float | None
    bulk_shear_0_to_1_km: float | None
    bulk_shear_0_to_3_km: float | None
    bulk_shear_0_to_6_km: float | None


@dataclass(frozen=True, slots=True)
class WeatherPlatformSevereSignal:
    """One severe-weather intelligence signal."""

    key: str
    label: str | None
    level: str | None
    value_display: str | None
    detail: str | None


@dataclass(frozen=True, slots=True)
class WeatherPlatformSevereWeather:
    """Severe-weather intelligence."""

    available: bool
    outlook_level: str | None
    composite_score: int | None
    headline: str | None
    summary: str | None
    data_status: str | None
    signals: tuple[WeatherPlatformSevereSignal, ...]


@dataclass(frozen=True, slots=True)
class WeatherPlatformMeteorologyData:
    """Meteorology intelligence reported by Weather Platform."""

    generated_at: str
    unit_system: str
    available: bool
    current: WeatherPlatformMeteorologyCurrent | None
    moisture: WeatherPlatformMeteorologyMoisture | None
    pressure: WeatherPlatformMeteorologyPressure | None
    thermodynamics: WeatherPlatformMeteorologyThermodynamics | None
    wbgt: WeatherPlatformMeteorologyWbgt | None
    atmospheric_model: WeatherPlatformAtmosphericModel | None
    severe_weather: WeatherPlatformSevereWeather | None


def normalize_base_url(value: str) -> str:
    """Normalize a Weather Platform application base URL."""
    candidate = value.strip()
    parsed = urlsplit(candidate)

    if (
        parsed.scheme.lower() not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise WeatherPlatformInvalidUrlError

    path = parsed.path.rstrip("/").removesuffix(API_BASE_PATH).rstrip("/")

    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc,
            path,
            "",
            "",
        )
    ).rstrip("/")


class WeatherPlatformApiClient:
    """Async client for the Weather Platform REST API."""

    def __init__(self, base_url: str, session: ClientSession) -> None:
        """Initialize the client."""
        self._base_url = normalize_base_url(base_url)
        self._api_base_url = f"{self._base_url}{API_BASE_PATH}"
        self._session = session

    @property
    def base_url(self) -> str:
        """Return the normalized application base URL."""
        return self._base_url

    async def async_get_metadata(self) -> WeatherPlatformMetadata:
        """Fetch and validate Weather Platform API metadata."""
        payload = await self._async_get_json("")

        name = payload.get("name")
        api_version = payload.get("apiVersion")
        platform_version = payload.get("platformVersion")
        resources_value = payload.get("resources")

        if (
            name != API_NAME
            or api_version != API_VERSION
            or not isinstance(platform_version, str)
            or not isinstance(resources_value, dict)
        ):
            raise WeatherPlatformInvalidResponseError

        resources = {
            key: value
            for key, value in resources_value.items()
            if isinstance(key, str) and isinstance(value, str)
        }

        if "current" not in resources or "forecast" not in resources:
            raise WeatherPlatformInvalidResponseError

        return WeatherPlatformMetadata(
            name=name,
            api_version=api_version,
            platform_version=platform_version,
            resources=resources,
        )

    async def async_get_current(
        self,
        unit_system: str,
    ) -> WeatherPlatformCurrentData:
        """Fetch current Weather Platform conditions."""
        payload = await self._async_get_json(
            "current",
            params={"units": unit_system},
        )

        response_unit_system = _validate_unit_system(payload, unit_system)
        station_payload = _as_object(payload.get("station"))
        conditions_payload = _as_object(payload.get("conditions"))

        station = WeatherPlatformStation(
            code=_required_str(station_payload, "code"),
            name=_required_str(station_payload, "name"),
            observed_at=_optional_str(station_payload, "observedAt"),
            age_seconds=_optional_int(station_payload, "ageSeconds"),
            stale=_optional_bool(station_payload, "stale") or False,
            source=_optional_str(station_payload, "source"),
        )

        conditions = WeatherPlatformCurrentConditions(
            temperature=_optional_float(conditions_payload, "temperature"),
            dew_point=_optional_float(conditions_payload, "dewPoint"),
            relative_humidity=_optional_float(
                conditions_payload,
                "relativeHumidity",
            ),
            station_pressure=_optional_float(
                conditions_payload,
                "stationPressure",
            ),
            wind_speed=_optional_float(conditions_payload, "windSpeed"),
            wind_gust=_optional_float(conditions_payload, "windGust"),
            wind_direction_degrees=_optional_int(
                conditions_payload,
                "windDirectionDegrees",
            ),
            rain_rate=_optional_float(conditions_payload, "rainRate"),
            daily_rain=_optional_float(conditions_payload, "dailyRain"),
            event_rain=_optional_float(conditions_payload, "eventRain"),
            solar_radiation=_optional_float(
                conditions_payload,
                "solarRadiation",
            ),
            solar_illuminance=_optional_float(
                conditions_payload,
                "solarIlluminance",
            ),
            uv_index=_optional_float(conditions_payload, "uvIndex"),
        )

        return WeatherPlatformCurrentData(
            generated_at=_required_str(payload, "generatedAt"),
            unit_system=response_unit_system,
            station=station,
            condition=_optional_str(payload, "condition"),
            conditions=conditions,
        )

    async def async_get_forecast(
        self,
        unit_system: str,
    ) -> WeatherPlatformForecastData:
        """Fetch Weather Platform forecast data."""
        payload = await self._async_get_json(
            "forecast",
            params={"units": unit_system},
        )

        response_unit_system = _validate_unit_system(payload, unit_system)

        return WeatherPlatformForecastData(
            generated_at=_required_str(payload, "generatedAt"),
            unit_system=response_unit_system,
            periods_available=_required_bool(payload, "periodsAvailable"),
            hourly_available=_required_bool(payload, "hourlyAvailable"),
            daily=tuple(
                _parse_daily_forecast(item) for item in _as_list(payload.get("daily"))
            ),
            hourly=tuple(
                _parse_hourly_forecast(item) for item in _as_list(payload.get("hourly"))
            ),
            periods=tuple(
                _parse_forecast_period(item)
                for item in _as_list(payload.get("periods"))
            ),
        )

    async def async_get_air_quality(self) -> WeatherPlatformAirQualityData:
        """Fetch Weather Platform air-quality guidance."""
        payload = await self._async_get_json("air-quality")
        current_payload = _as_object(payload.get("current"))

        return WeatherPlatformAirQualityData(
            generated_at=_required_str(payload, "generatedAt"),
            provider=_optional_str(payload, "provider"),
            model=_optional_str(payload, "model"),
            fetched_at=_optional_str(payload, "fetchedAt"),
            stale=_required_bool(payload, "stale"),
            current=_parse_air_quality_period(current_payload),
            peak_next_24_hours=_parse_optional_air_quality_period(
                payload.get("peakNext24Hours")
            ),
            minimum_next_24_hours=_parse_optional_air_quality_period(
                payload.get("minimumNext24Hours")
            ),
            hourly=tuple(
                _parse_air_quality_period(_as_object(item))
                for item in _as_list(payload.get("hourly"))
            ),
        )

    async def async_get_alerts(self) -> WeatherPlatformAlertsData:
        """Fetch active Weather Platform alerts."""
        payload = await self._async_get_json("alerts")

        return WeatherPlatformAlertsData(
            generated_at=_required_str(payload, "generatedAt"),
            active_count=_required_int(payload, "activeCount"),
            critical_count=_required_int(payload, "criticalCount"),
            highest_level=_optional_str(payload, "highestLevel"),
            alerts=tuple(
                _parse_alert(item) for item in _as_list(payload.get("alerts"))
            ),
        )

    async def async_get_radar(
        self,
        unit_system: str,
    ) -> WeatherPlatformRadarData:
        """Fetch Weather Platform radar intelligence."""
        payload = await self._async_get_json(
            "radar",
            params={"units": unit_system},
        )
        response_unit_system = _validate_unit_system(payload, unit_system)

        return WeatherPlatformRadarData(
            generated_at=_required_str(payload, "generatedAt"),
            unit_system=response_unit_system,
            precipitation=_parse_radar_precipitation(
                _as_object(payload.get("precipitation"))
            ),
            nowcast=_parse_radar_nowcast(_as_object(payload.get("nowcast"))),
            lightning=_parse_radar_lightning(_as_object(payload.get("lightning"))),
            storm_tracking=_parse_radar_storm_tracking(
                _as_object(payload.get("stormTracking"))
            ),
        )

    async def async_get_active_events(self) -> WeatherPlatformEventsData:
        """Fetch active durable Weather Platform weather events."""
        payload = await self._async_get_json(
            "events",
            params={
                "category": "WEATHER",
                "state": "ACTIVE",
                "limit": "500",
            },
        )

        return WeatherPlatformEventsData(
            generated_at=_required_str(payload, "generatedAt"),
            count=_required_int(payload, "count"),
            events=tuple(
                _parse_event(item) for item in _as_list(payload.get("events"))
            ),
        )

    async def async_get_impacts(
        self,
        unit_system: str,
    ) -> WeatherPlatformImpactsData:
        """Fetch Weather Platform impact guidance."""
        payload = await self._async_get_json(
            "impacts",
            params={"units": unit_system},
        )
        response_unit_system = _validate_unit_system(payload, unit_system)
        radar_payload = _as_object(payload.get("radar"))

        return WeatherPlatformImpactsData(
            generated_at=_optional_str(payload, "generatedAt"),
            unit_system=response_unit_system,
            horizon_hours=_required_int(payload, "horizonHours"),
            headline=_optional_str(payload, "headline"),
            summary=_optional_str(payload, "summary"),
            radar_hazard_active=_required_bool(
                radar_payload,
                "hazardActive",
            ),
            radar_detail=_optional_str(radar_payload, "detail"),
            profiles=tuple(
                _parse_impact_profile(item)
                for item in _as_list(payload.get("profiles"))
            ),
        )

    async def async_get_today(
        self,
        unit_system: str,
    ) -> WeatherPlatformTodayData:
        """Fetch the synthesized Weather Platform daily story."""
        payload = await self._async_get_json(
            "today",
            params={"units": unit_system},
        )
        response_unit_system = _validate_unit_system(payload, unit_system)

        return WeatherPlatformTodayData(
            generated_at=_required_str(payload, "generatedAt"),
            observed_at=_optional_str(payload, "observedAt"),
            unit_system=response_unit_system,
            headline=_optional_str(payload, "headline"),
            summary=_optional_str(payload, "summary"),
            tone=_optional_str(payload, "tone"),
            sections=tuple(
                _parse_story_section(item) for item in _as_list(payload.get("sections"))
            ),
            evolution=_parse_optional_story_section(payload.get("evolution")),
            best_window=_parse_optional_story_window(payload.get("bestWindow")),
            impact_window=_parse_optional_story_window(payload.get("impactWindow")),
        )

    async def async_get_hydrology(
        self,
        unit_system: str,
    ) -> WeatherPlatformHydrologyData:
        """Fetch Weather Platform hydrology context."""
        payload = await self._async_get_json(
            "hydrology",
            params={"units": unit_system},
        )
        response_unit_system = _validate_unit_system(payload, unit_system)

        return WeatherPlatformHydrologyData(
            generated_at=_required_str(payload, "generatedAt"),
            unit_system=response_unit_system,
            rainfall=_parse_antecedent_rainfall(_as_object(payload.get("rainfall"))),
            gauges=_parse_hydrology_gauges(_as_object(payload.get("gauges"))),
        )

    async def async_get_climate(
        self,
        unit_system: str,
    ) -> WeatherPlatformClimateData:
        """Fetch Weather Platform climate context."""
        payload = await self._async_get_json(
            "climate",
            params={"units": unit_system},
        )
        response_unit_system = _validate_unit_system(payload, unit_system)

        return WeatherPlatformClimateData(
            generated_at=_required_str(payload, "generatedAt"),
            unit_system=response_unit_system,
            available=_required_bool(payload, "available"),
            first_observed_at=_optional_str(payload, "firstObservedAt"),
            last_observed_at=_optional_str(payload, "lastObservedAt"),
            headline=_optional_str(payload, "headline"),
            summary=_optional_str(payload, "summary"),
            tone=_optional_str(payload, "tone"),
            complete_day_count=_required_int(payload, "completeDayCount"),
            archive_year_count=_required_int(payload, "archiveYearCount"),
            latest_day=_parse_climate_latest_day(_as_object(payload.get("latestDay"))),
            month=_parse_climate_month(_as_object(payload.get("month"))),
            streaks=_parse_climate_streaks(_as_object(payload.get("streaks"))),
            records=_parse_climate_records(_as_object(payload.get("records"))),
        )

    async def async_get_meteorology(
        self,
        unit_system: str,
    ) -> WeatherPlatformMeteorologyData:
        """Fetch Weather Platform meteorology intelligence."""
        payload = await self._async_get_json(
            "meteorology",
            params={"units": unit_system},
        )
        response_unit_system = _validate_unit_system(payload, unit_system)

        return WeatherPlatformMeteorologyData(
            generated_at=_required_str(payload, "generatedAt"),
            unit_system=response_unit_system,
            available=_required_bool(payload, "available"),
            current=_parse_optional_meteorology_current(payload.get("current")),
            moisture=_parse_optional_meteorology_moisture(payload.get("moisture")),
            pressure=_parse_optional_meteorology_pressure(payload.get("pressure")),
            thermodynamics=_parse_optional_meteorology_thermodynamics(
                payload.get("thermodynamics")
            ),
            wbgt=_parse_optional_meteorology_wbgt(payload.get("wbgt")),
            atmospheric_model=_parse_optional_atmospheric_model(
                payload.get("atmosphericModel")
            ),
            severe_weather=_parse_optional_severe_weather(payload.get("severeWeather")),
        )

    async def _async_get_json(
        self,
        resource: str,
        *,
        params: dict[str, str] | None = None,
    ) -> JsonObject:
        """Fetch a JSON object from the Weather Platform API."""
        url = self._api_base_url
        if resource:
            url = f"{url}/{resource.lstrip('/')}"

        try:
            async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
                async with self._session.get(
                    url,
                    headers={"Accept": "application/json"},
                    params=params,
                ) as response:
                    response.raise_for_status()
                    payload = await response.json(content_type=None)
        except TimeoutError as err:
            raise WeatherPlatformConnectionError from err
        except ClientError as err:
            raise WeatherPlatformConnectionError from err
        except ValueError as err:
            raise WeatherPlatformInvalidResponseError from err

        return _as_object(payload)


def _as_object(value: Any) -> JsonObject:
    """Return a JSON object or raise for an invalid response."""
    if not isinstance(value, dict):
        raise WeatherPlatformInvalidResponseError
    return cast("JsonObject", value)


def _as_list(value: Any) -> list[Any]:
    """Return a JSON array or raise for an invalid response."""
    if not isinstance(value, list):
        raise WeatherPlatformInvalidResponseError
    return value


def _validate_unit_system(payload: JsonObject, expected: str) -> str:
    """Validate and return the response unit system."""
    response = _required_str(payload, "unitSystem")
    if response != expected:
        raise WeatherPlatformInvalidResponseError
    return response


def _required_str(payload: dict[str, Any], key: str) -> str:
    """Return a required string value."""
    value = payload.get(key)
    if not isinstance(value, str):
        raise WeatherPlatformInvalidResponseError
    return value


def _optional_str(payload: dict[str, Any], key: str) -> str | None:
    """Return an optional string value."""
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise WeatherPlatformInvalidResponseError
    return value


def _required_bool(payload: dict[str, Any], key: str) -> bool:
    """Return a required boolean value."""
    value = payload.get(key)
    if not isinstance(value, bool):
        raise WeatherPlatformInvalidResponseError
    return value


def _optional_bool(payload: dict[str, Any], key: str) -> bool | None:
    """Return an optional boolean value."""
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise WeatherPlatformInvalidResponseError
    return value


def _required_int(payload: dict[str, Any], key: str) -> int:
    """Return a required integer value."""
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise WeatherPlatformInvalidResponseError
    return value


def _optional_int(payload: dict[str, Any], key: str) -> int | None:
    """Return an optional integer value."""
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise WeatherPlatformInvalidResponseError
    return value


def _optional_float(payload: dict[str, Any], key: str) -> float | None:
    """Return an optional numeric value as a float."""
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise WeatherPlatformInvalidResponseError
    return float(value)


def _parse_wind(value: Any) -> WeatherPlatformWind | None:
    """Parse an optional Weather Platform wind range."""
    if value is None:
        return None

    payload = _as_object(value)
    return WeatherPlatformWind(
        minimum=_optional_float(payload, "minimum"),
        maximum=_optional_float(payload, "maximum"),
        direction=_optional_str(payload, "direction"),
    )


def _parse_forecast_period(value: Any) -> WeatherPlatformForecastPeriod:
    """Parse a twice-daily Weather Platform forecast period."""
    payload = _as_object(value)
    return WeatherPlatformForecastPeriod(
        name=_required_str(payload, "name"),
        start_time=_required_str(payload, "startTime"),
        end_time=_required_str(payload, "endTime"),
        daytime=_required_bool(payload, "daytime"),
        temperature=_optional_float(payload, "temperature"),
        precipitation_probability=_optional_int(
            payload,
            "precipitationChancePercent",
        ),
        short_forecast=_optional_str(payload, "shortForecast"),
        detailed_forecast=_optional_str(payload, "detailedForecast"),
        wind=_parse_wind(payload.get("wind")),
    )


def _parse_hourly_forecast(value: Any) -> WeatherPlatformHourlyForecast:
    """Parse an hourly Weather Platform forecast item."""
    payload = _as_object(value)
    return WeatherPlatformHourlyForecast(
        valid_at=_required_str(payload, "validAt"),
        temperature=_optional_float(payload, "temperature"),
        precipitation_probability=_optional_int(
            payload,
            "precipitationChancePercent",
        ),
        short_forecast=_optional_str(payload, "shortForecast"),
        wind=_parse_wind(payload.get("wind")),
        wind_gust=_optional_float(payload, "windGust"),
    )


def _parse_daily_forecast(value: Any) -> WeatherPlatformDailyForecast:
    """Parse a daily Weather Platform forecast item."""
    payload = _as_object(value)
    try:
        forecast_date = date.fromisoformat(_required_str(payload, "date"))
    except ValueError as err:
        raise WeatherPlatformInvalidResponseError from err

    return WeatherPlatformDailyForecast(
        date=forecast_date,
        display_name=_required_str(payload, "displayName"),
        high_temperature=_optional_float(payload, "highTemperature"),
        low_temperature=_optional_float(payload, "lowTemperature"),
        precipitation_probability=_optional_int(
            payload,
            "precipitationChancePercent",
        ),
        short_forecast=_optional_str(payload, "shortForecast"),
    )


def _parse_air_quality_period(
    payload: JsonObject,
) -> WeatherPlatformAirQualityPeriod:
    """Parse Weather Platform air-quality guidance."""
    return WeatherPlatformAirQualityPeriod(
        valid_at=_optional_str(payload, "validAt"),
        us_aqi=_optional_int(payload, "usAqi"),
        category=_optional_str(payload, "category"),
        category_headline=_optional_str(payload, "categoryHeadline"),
        health_advice=_optional_str(payload, "healthAdvice"),
        dominant_pollutant=_optional_str(payload, "dominantPollutant"),
        dominant_pollutant_aqi=_optional_int(
            payload,
            "dominantPollutantAqi",
        ),
        pm25=_optional_float(payload, "pm25"),
        pm10=_optional_float(payload, "pm10"),
        ozone=_optional_float(payload, "ozone"),
        pm25_aqi=_optional_int(payload, "pm25Aqi"),
        pm10_aqi=_optional_int(payload, "pm10Aqi"),
        ozone_aqi=_optional_int(payload, "ozoneAqi"),
        nitrogen_dioxide_aqi=_optional_int(payload, "nitrogenDioxideAqi"),
        carbon_monoxide_aqi=_optional_int(payload, "carbonMonoxideAqi"),
        sulphur_dioxide_aqi=_optional_int(payload, "sulphurDioxideAqi"),
        nitrogen_dioxide=_optional_float(payload, "nitrogenDioxide"),
        carbon_monoxide=_optional_float(payload, "carbonMonoxide"),
        sulphur_dioxide=_optional_float(payload, "sulphurDioxide"),
        aerosol_optical_depth=_optional_float(payload, "aerosolOpticalDepth"),
        dust=_optional_float(payload, "dust"),
        wildfire_pm10=_optional_float(payload, "wildfirePm10"),
        wildfire_pm10_share_percent=_optional_float(
            payload,
            "wildfirePm10SharePercent",
        ),
        uv_index=_optional_float(payload, "uvIndex"),
    )


def _parse_optional_air_quality_period(
    value: Any,
) -> WeatherPlatformAirQualityPeriod | None:
    """Parse an optional Weather Platform air-quality period."""
    if value is None:
        return None
    return _parse_air_quality_period(_as_object(value))


def _parse_alert(value: Any) -> WeatherPlatformAlert:
    """Parse an active Weather Platform alert."""
    payload = _as_object(value)
    return WeatherPlatformAlert(
        event=_optional_str(payload, "event"),
        headline=_optional_str(payload, "headline"),
        severity=_optional_str(payload, "severity"),
        level=_optional_str(payload, "level"),
        critical=_required_bool(payload, "critical"),
        expires_at=_optional_str(payload, "expiresAt"),
        alert_id=_optional_str(payload, "id"),
        description=_optional_str(payload, "description"),
        instruction=_optional_str(payload, "instruction"),
        area=_optional_str(payload, "area"),
        certainty=_optional_str(payload, "certainty"),
        urgency=_optional_str(payload, "urgency"),
        sender=_optional_str(payload, "sender"),
        sent_at=_optional_str(payload, "sentAt"),
        effective_at=_optional_str(payload, "effectiveAt"),
        onset_at=_optional_str(payload, "onsetAt"),
        status=_optional_str(payload, "status"),
        message_type=_optional_str(payload, "messageType"),
    )


def _parse_radar_precipitation(
    payload: JsonObject,
) -> WeatherPlatformRadarPrecipitation:
    """Parse Weather Platform radar precipitation."""
    return WeatherPlatformRadarPrecipitation(
        available=_required_bool(payload, "available"),
        inside_coverage=_required_bool(payload, "insideCoverage"),
        stale=_required_bool(payload, "stale"),
        source=_optional_str(payload, "source"),
        precipitation_rate=_optional_float(payload, "precipitationRate"),
        two_minute_precipitation=_optional_float(
            payload,
            "twoMinutePrecipitation",
        ),
        reflectivity_dbz=_optional_float(payload, "reflectivityDbz"),
        intensity=_optional_str(payload, "intensity"),
        precipitation_valid_at=_optional_str(payload, "precipitationValidAt"),
        reflectivity_valid_at=_optional_str(payload, "reflectivityValidAt"),
    )


def _parse_radar_nowcast(payload: JsonObject) -> WeatherPlatformRadarNowcast:
    """Parse Weather Platform radar nowcast."""
    return WeatherPlatformRadarNowcast(
        available=_required_bool(payload, "available"),
        status=_optional_str(payload, "status"),
        radar_valid_at=_optional_str(payload, "radarValidAt"),
        precipitation_now=_required_bool(payload, "precipitationNow"),
        arrival_lead_minutes=_optional_int(payload, "arrivalLeadMinutes"),
        arrival_at=_optional_str(payload, "arrivalAt"),
        departure_lead_minutes=_optional_int(payload, "departureLeadMinutes"),
        departure_at=_optional_str(payload, "departureAt"),
        projected_duration_minutes=_optional_int(
            payload,
            "projectedDurationMinutes",
        ),
        peak_reflectivity_dbz=_optional_float(payload, "peakReflectivityDbz"),
        arrival_echo_coverage_percent=_optional_float(
            payload,
            "arrivalEchoCoveragePercent",
        ),
        maximum_evaluated_lead_minutes=_optional_int(
            payload,
            "maximumEvaluatedLeadMinutes",
        ),
        coverage_limited=_required_bool(payload, "coverageLimited"),
        motion_direction=_optional_str(payload, "motionDirection"),
        motion_speed=_optional_float(payload, "motionSpeed"),
        motion_bearing_degrees=_optional_float(
            payload,
            "motionBearingDegrees",
        ),
        motion_coherence_percent=_optional_float(
            payload,
            "motionCoherencePercent",
        ),
        motion_consensus_sample_count=_optional_int(
            payload,
            "motionConsensusSampleCount",
        ),
        motion_consensus_inlier_count=_optional_int(
            payload,
            "motionConsensusInlierCount",
        ),
    )


def _parse_radar_lightning(
    payload: JsonObject,
) -> WeatherPlatformRadarLightning:
    """Parse Weather Platform lightning intelligence."""
    return WeatherPlatformRadarLightning(
        available=_required_bool(payload, "available"),
        fetched_at=_optional_str(payload, "fetchedAt"),
        strike_count=_required_int(payload, "strikeCount"),
        recent_window_strike_count=_required_int(
            payload,
            "recentWindowStrikeCount",
        ),
        strike_rate_per_minute=_optional_float(
            payload,
            "strikeRatePerMinute",
        ),
        recent_strike_rate_per_minute=_optional_float(
            payload,
            "recentStrikeRatePerMinute",
        ),
        nearest_distance=_optional_float(payload, "nearestDistance"),
        distance_shift=_optional_float(payload, "distanceShift"),
        activity_trend=_optional_str(payload, "activityTrend"),
        rate_trend=_optional_str(payload, "rateTrend"),
        radius=_optional_float(payload, "radius"),
        prior_window_strike_count=_optional_int(
            payload,
            "priorWindowStrikeCount",
        ),
        prior_strike_rate_per_minute=_optional_float(
            payload,
            "priorStrikeRatePerMinute",
        ),
    )


def _parse_radar_storm(value: Any) -> WeatherPlatformRadarStorm:
    """Parse one Weather Platform tracked storm."""
    payload = _as_object(value)
    return WeatherPlatformRadarStorm(
        storm_id=_optional_str(payload, "id"),
        intensity=_optional_str(payload, "intensity"),
        lifecycle_stage=_optional_str(payload, "lifecycleStage"),
        distance=_optional_float(payload, "distance"),
        peak_reflectivity_dbz=_optional_float(
            payload,
            "peakReflectivityDbz",
        ),
        approaching_home=_required_bool(payload, "approachingHome"),
        reflectivity_trend=_optional_str(payload, "reflectivityTrend"),
        area_trend=_optional_str(payload, "areaTrend"),
        speed=_optional_float(payload, "speed"),
        bearing_degrees=_optional_float(payload, "bearingDegrees"),
        direction=_optional_str(payload, "direction"),
        age_minutes=_optional_int(payload, "ageMinutes"),
    )


def _parse_radar_storm_tracking(
    payload: JsonObject,
) -> WeatherPlatformRadarStormTracking:
    """Parse Weather Platform storm-tracking intelligence."""
    return WeatherPlatformRadarStormTracking(
        available=_required_bool(payload, "available"),
        status=_optional_str(payload, "status"),
        valid_at=_optional_str(payload, "validAt"),
        tracked_object_count=_required_int(
            payload,
            "trackedObjectCount",
        ),
        storms=tuple(
            _parse_radar_storm(item) for item in _as_list(payload.get("storms"))
        ),
        detection_threshold_dbz=_optional_float(
            payload,
            "detectionThresholdDbz",
        ),
    )


def _parse_event(value: Any) -> WeatherPlatformEvent:
    """Parse one active Weather Platform weather event."""
    payload = _as_object(value)
    return WeatherPlatformEvent(
        event_type=_required_str(payload, "type"),
        type_label=_optional_str(payload, "typeLabel"),
        phase=_optional_str(payload, "phase"),
        phase_label=_optional_str(payload, "phaseLabel"),
        priority=_required_str(payload, "priority"),
        priority_label=_optional_str(payload, "priorityLabel"),
        trigger_source=_optional_str(payload, "triggerSource"),
        detected_at=_optional_str(payload, "detectedAt"),
        event_id=_optional_int(payload, "id"),
        station_code=_optional_str(payload, "stationCode"),
        category=_optional_str(payload, "category"),
        state=_optional_str(payload, "state"),
        state_label=_optional_str(payload, "stateLabel"),
        last_evidence_at=_optional_str(payload, "lastEvidenceAt"),
        resolved_at=_optional_str(payload, "resolvedAt"),
    )


def _parse_impact_window(value: Any) -> WeatherPlatformImpactWindow | None:
    """Parse an optional Weather Platform impact window."""
    if value is None:
        return None
    payload = _as_object(value)
    return WeatherPlatformImpactWindow(
        started_at=_optional_str(payload, "startedAt"),
        ended_at=_optional_str(payload, "endedAt"),
        rating=_optional_str(payload, "rating"),
        label=_optional_str(payload, "label"),
    )


def _parse_impact_profile(value: Any) -> WeatherPlatformImpactProfile:
    """Parse one Weather Platform impact profile."""
    payload = _as_object(value)
    evidence = tuple(
        item for item in _as_list(payload.get("evidence")) if isinstance(item, str)
    )
    return WeatherPlatformImpactProfile(
        key=_required_str(payload, "key"),
        title=_required_str(payload, "title"),
        current_rating=_optional_str(payload, "currentRating"),
        current_status=_optional_str(payload, "currentStatus"),
        subtitle=_optional_str(payload, "subtitle"),
        headline=_optional_str(payload, "headline"),
        detail=_optional_str(payload, "detail"),
        next_change_at=_optional_str(payload, "nextChangeAt"),
        next_change_label=_optional_str(payload, "nextChangeLabel"),
        best_window=_parse_impact_window(payload.get("bestWindow")),
        concern_window=_parse_impact_window(payload.get("concernWindow")),
        evidence=evidence,
    )


def _parse_story_section(value: Any) -> WeatherPlatformStorySection:
    """Parse one Weather Platform story section."""
    payload = _as_object(value)
    return WeatherPlatformStorySection(
        key=_required_str(payload, "key"),
        label=_optional_str(payload, "label"),
        headline=_optional_str(payload, "headline"),
        detail=_optional_str(payload, "detail"),
        meta=_optional_str(payload, "meta"),
        tone=_optional_str(payload, "tone"),
        action_label=_optional_str(payload, "actionLabel"),
        action_path=_optional_str(payload, "actionPath"),
    )


def _parse_optional_story_section(
    value: Any,
) -> WeatherPlatformStorySection | None:
    """Parse an optional Weather Platform story section."""
    if value is None:
        return None
    return _parse_story_section(value)


def _parse_optional_story_window(
    value: Any,
) -> WeatherPlatformStoryWindow | None:
    """Parse an optional Weather Platform story window."""
    if value is None:
        return None
    payload = _as_object(value)
    return WeatherPlatformStoryWindow(
        label=_optional_str(payload, "label"),
        headline=_optional_str(payload, "headline"),
        detail=_optional_str(payload, "detail"),
        started_at=_optional_str(payload, "startedAt"),
        ended_at=_optional_str(payload, "endedAt"),
        tone=_optional_str(payload, "tone"),
    )


def _parse_antecedent_rainfall(
    payload: JsonObject,
) -> WeatherPlatformAntecedentRainfall:
    """Parse Weather Platform antecedent rainfall."""
    return WeatherPlatformAntecedentRainfall(
        available=_required_bool(payload, "available"),
        generated_at=_optional_str(payload, "generatedAt"),
        latest_observation_at=_optional_str(payload, "latestObservationAt"),
        last_rain_at=_optional_str(payload, "lastRainAt"),
        level=_optional_str(payload, "level"),
        headline=_optional_str(payload, "headline"),
        detail=_optional_str(payload, "detail"),
        rainfall_24_hours=_optional_float(payload, "rainfall24Hours"),
        rainfall_3_days=_optional_float(payload, "rainfall3Days"),
        rainfall_7_days=_optional_float(payload, "rainfall7Days"),
        rainfall_14_days=_optional_float(payload, "rainfall14Days"),
        rainfall_30_days=_optional_float(payload, "rainfall30Days"),
    )


def _parse_hydrology_gauge(value: Any) -> WeatherPlatformHydrologyGauge:
    """Parse one nearby Weather Platform hydrology gauge."""
    payload = _as_object(value)
    return WeatherPlatformHydrologyGauge(
        monitoring_location_id=_optional_str(payload, "monitoringLocationId"),
        site_number=_optional_str(payload, "siteNumber"),
        name=_optional_str(payload, "name"),
        site_type=_optional_str(payload, "siteType"),
        distance=_optional_float(payload, "distance"),
        stage=_optional_float(payload, "stage"),
        stage_change_6_hours=_optional_float(payload, "stageChange6Hours"),
        stage_change_24_hours=_optional_float(payload, "stageChange24Hours"),
        discharge=_optional_float(payload, "discharge"),
        discharge_change_6_hours=_optional_float(
            payload,
            "dischargeChange6Hours",
        ),
        discharge_change_24_hours=_optional_float(
            payload,
            "dischargeChange24Hours",
        ),
        observed_at=_optional_str(payload, "observedAt"),
        trend=_optional_str(payload, "trend"),
    )


def _parse_hydrology_gauges(
    payload: JsonObject,
) -> WeatherPlatformHydrologyGauges:
    """Parse nearby Weather Platform hydrology gauges."""
    return WeatherPlatformHydrologyGauges(
        available=_required_bool(payload, "available"),
        stale=_required_bool(payload, "stale"),
        fetched_at=_optional_str(payload, "fetchedAt"),
        rising_count=_required_int(payload, "risingCount"),
        gauges=tuple(
            _parse_hydrology_gauge(item) for item in _as_list(payload.get("gauges"))
        ),
    )


def _parse_climate_latest_day(
    payload: JsonObject,
) -> WeatherPlatformClimateLatestDay:
    """Parse latest complete Weather Platform climate day."""
    return WeatherPlatformClimateLatestDay(
        date=_optional_str(payload, "date"),
        mean_temperature=_optional_float(payload, "meanTemperature"),
        mean_temperature_anomaly=_optional_float(
            payload,
            "meanTemperatureAnomaly",
        ),
        high_temperature_percentile=_optional_int(
            payload,
            "highTemperaturePercentile",
        ),
        low_temperature_percentile=_optional_int(
            payload,
            "lowTemperaturePercentile",
        ),
        percentile_sample_count=_required_int(
            payload,
            "percentileSampleCount",
        ),
        percentile_context=_optional_str(payload, "percentileContext"),
    )


def _parse_climate_month(payload: JsonObject) -> WeatherPlatformClimateMonth:
    """Parse current Weather Platform climate month."""
    return WeatherPlatformClimateMonth(
        complete_day_count=_required_int(payload, "completeDayCount"),
        rainfall=_optional_float(payload, "rainfall"),
        expected_rainfall=_optional_float(payload, "expectedRainfall"),
        rainfall_departure=_optional_float(payload, "rainfallDeparture"),
        heating_degree_days=_optional_float(payload, "heatingDegreeDays"),
        heating_degree_day_departure=_optional_float(
            payload,
            "heatingDegreeDayDeparture",
        ),
        cooling_degree_days=_optional_float(payload, "coolingDegreeDays"),
        cooling_degree_day_departure=_optional_float(
            payload,
            "coolingDegreeDayDeparture",
        ),
    )


def _parse_climate_streaks(
    payload: JsonObject,
) -> WeatherPlatformClimateStreaks:
    """Parse Weather Platform climate streaks."""
    return WeatherPlatformClimateStreaks(
        current_dry_days=_required_int(payload, "currentDryDays"),
        longest_dry_days=_required_int(payload, "longestDryDays"),
        current_wet_days=_required_int(payload, "currentWetDays"),
        longest_wet_days=_required_int(payload, "longestWetDays"),
        current_hot_days=_required_int(payload, "currentHotDays"),
        longest_hot_days=_required_int(payload, "longestHotDays"),
        current_warm_night_days=_required_int(payload, "currentWarmNightDays"),
        longest_warm_night_days=_required_int(payload, "longestWarmNightDays"),
    )


def _parse_climate_records(
    payload: JsonObject,
) -> WeatherPlatformClimateRecords:
    """Parse Weather Platform archive climate records."""
    return WeatherPlatformClimateRecords(
        highest_high_temperature=_optional_float(
            payload,
            "highestHighTemperature",
        ),
        highest_high_date=_optional_str(payload, "highestHighDate"),
        lowest_low_temperature=_optional_float(payload, "lowestLowTemperature"),
        lowest_low_date=_optional_str(payload, "lowestLowDate"),
        wettest_day_rainfall=_optional_float(payload, "wettestDayRainfall"),
        wettest_day_date=_optional_str(payload, "wettestDayDate"),
        strongest_wind_gust=_optional_float(payload, "strongestWindGust"),
        strongest_wind_gust_date=_optional_str(
            payload,
            "strongestWindGustDate",
        ),
    )


def _parse_optional_meteorology_current(
    value: Any,
) -> WeatherPlatformMeteorologyCurrent | None:
    """Parse optional current meteorology."""
    if value is None:
        return None
    payload = _as_object(value)
    return WeatherPlatformMeteorologyCurrent(
        observed_at=_optional_str(payload, "observedAt"),
        feels_like=_optional_float(payload, "feelsLike"),
        feels_like_type=_optional_str(payload, "feelsLikeType"),
        heat_index=_optional_float(payload, "heatIndex"),
        wind_chill=_optional_float(payload, "windChill"),
        wet_bulb=_optional_float(payload, "wetBulb"),
        rain_intensity=_optional_str(payload, "rainIntensity"),
        wind_condition=_optional_str(payload, "windCondition"),
    )


def _parse_optional_meteorology_moisture(
    value: Any,
) -> WeatherPlatformMeteorologyMoisture | None:
    """Parse optional meteorology moisture metrics."""
    if value is None:
        return None
    payload = _as_object(value)
    return WeatherPlatformMeteorologyMoisture(
        dew_point_depression=_optional_float(payload, "dewPointDepression"),
        dew_point_depression_interpretation=_optional_str(
            payload,
            "dewPointDepressionInterpretation",
        ),
        wet_bulb_depression=_optional_float(payload, "wetBulbDepression"),
        wet_bulb_depression_interpretation=_optional_str(
            payload,
            "wetBulbDepressionInterpretation",
        ),
        vapor_pressure_deficit=_optional_float(
            payload,
            "vaporPressureDeficit",
        ),
        vapor_pressure_deficit_interpretation=_optional_str(
            payload,
            "vaporPressureDeficitInterpretation",
        ),
        absolute_humidity=_optional_float(payload, "absoluteHumidity"),
        mixing_ratio=_optional_float(payload, "mixingRatio"),
    )


def _parse_optional_meteorology_pressure(
    value: Any,
) -> WeatherPlatformMeteorologyPressure | None:
    """Parse optional meteorology pressure metrics."""
    if value is None:
        return None
    payload = _as_object(value)
    return WeatherPlatformMeteorologyPressure(
        sea_level_pressure=_optional_float(payload, "seaLevelPressure"),
        pressure_change_three_hours=_optional_float(
            payload,
            "pressureChangeThreeHours",
        ),
        pressure_change_long_period=_optional_float(
            payload,
            "pressureChangeLongPeriod",
        ),
        tendency=_optional_str(payload, "tendency"),
    )


def _parse_optional_meteorology_thermodynamics(
    value: Any,
) -> WeatherPlatformMeteorologyThermodynamics | None:
    """Parse optional meteorology thermodynamic metrics."""
    if value is None:
        return None
    payload = _as_object(value)
    return WeatherPlatformMeteorologyThermodynamics(
        estimated_cloud_base_agl=_optional_float(
            payload,
            "estimatedCloudBaseAgl",
        ),
        estimated_cloud_base_msl=_optional_float(
            payload,
            "estimatedCloudBaseMsl",
        ),
        cloud_base_interpretation=_optional_str(
            payload,
            "cloudBaseInterpretation",
        ),
        potential_temperature=_optional_float(payload, "potentialTemperature"),
        gust_factor=_optional_float(payload, "gustFactor"),
        gust_factor_interpretation=_optional_str(
            payload,
            "gustFactorInterpretation",
        ),
        daily_maximum_wind_gust=_optional_float(
            payload,
            "dailyMaximumWindGust",
        ),
        wind_gust_below_daily_maximum=_optional_float(
            payload,
            "windGustBelowDailyMaximum",
        ),
    )


def _parse_optional_meteorology_wbgt(
    value: Any,
) -> WeatherPlatformMeteorologyWbgt | None:
    """Parse optional wet-bulb globe temperature metrics."""
    if value is None:
        return None
    payload = _as_object(value)
    return WeatherPlatformMeteorologyWbgt(
        available=_required_bool(payload, "available"),
        wet_bulb_globe_temperature=_optional_float(
            payload,
            "wetBulbGlobeTemperature",
        ),
        natural_wet_bulb_temperature=_optional_float(
            payload,
            "naturalWetBulbTemperature",
        ),
        globe_temperature=_optional_float(payload, "globeTemperature"),
        two_meter_wind_speed=_optional_float(payload, "twoMeterWindSpeed"),
        solar_radiation=_optional_float(payload, "solarRadiation"),
        solar_zenith_degrees=_optional_float(payload, "solarZenithDegrees"),
    )


def _parse_optional_atmospheric_model(
    value: Any,
) -> WeatherPlatformAtmosphericModel | None:
    """Parse optional atmospheric model metrics."""
    if value is None:
        return None
    payload = _as_object(value)
    return WeatherPlatformAtmosphericModel(
        available=_required_bool(payload, "available"),
        stale=_required_bool(payload, "stale"),
        provider=_optional_str(payload, "provider"),
        model=_optional_str(payload, "model"),
        valid_at=_optional_str(payload, "validAt"),
        cape=_optional_float(payload, "capeJoulesPerKilogram"),
        cin=_optional_float(payload, "convectiveInhibitionJoulesPerKilogram"),
        lifted_index=_optional_float(payload, "liftedIndex"),
        precipitable_water=_optional_float(payload, "precipitableWater"),
        freezing_level=_optional_float(payload, "freezingLevel"),
        boundary_layer_height=_optional_float(
            payload,
            "boundaryLayerHeight",
        ),
        lapse_rate_850_to_500=_optional_float(
            payload,
            "lapseRate850To500CPerKilometer",
        ),
        lapse_rate_700_to_500=_optional_float(
            payload,
            "lapseRate700To500CPerKilometer",
        ),
        surface_pressure=_optional_float(payload, "surfacePressure"),
        surface_temperature=_optional_float(payload, "surfaceTemperature"),
        surface_dew_point=_optional_float(payload, "surfaceDewPoint"),
        surface_wind_speed=_optional_float(payload, "surfaceWindSpeed"),
        surface_wind_direction_degrees=_optional_float(
            payload,
            "surfaceWindDirectionDegrees",
        ),
        bulk_shear_0_to_1_km=_optional_float(payload, "bulkShear0To1Km"),
        bulk_shear_0_to_3_km=_optional_float(payload, "bulkShear0To3Km"),
        bulk_shear_0_to_6_km=_optional_float(payload, "bulkShear0To6Km"),
    )


def _parse_severe_signal(value: Any) -> WeatherPlatformSevereSignal:
    """Parse one severe-weather signal."""
    payload = _as_object(value)
    return WeatherPlatformSevereSignal(
        key=_required_str(payload, "key"),
        label=_optional_str(payload, "label"),
        level=_optional_str(payload, "level"),
        value_display=_optional_str(payload, "valueDisplay"),
        detail=_optional_str(payload, "detail"),
    )


def _parse_optional_severe_weather(
    value: Any,
) -> WeatherPlatformSevereWeather | None:
    """Parse optional severe-weather intelligence."""
    if value is None:
        return None
    payload = _as_object(value)
    return WeatherPlatformSevereWeather(
        available=_required_bool(payload, "available"),
        outlook_level=_optional_str(payload, "outlookLevel"),
        composite_score=_optional_int(payload, "compositeScore"),
        headline=_optional_str(payload, "headline"),
        summary=_optional_str(payload, "summary"),
        data_status=_optional_str(payload, "dataStatus"),
        signals=tuple(
            _parse_severe_signal(item) for item in _as_list(payload.get("signals"))
        ),
    )
