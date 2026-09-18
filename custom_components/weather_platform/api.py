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


@dataclass(frozen=True, slots=True)
class WeatherPlatformAlert:
    """One active Weather Platform alert."""

    event: str | None
    headline: str | None
    severity: str | None
    level: str | None
    critical: bool
    expires_at: str | None


@dataclass(frozen=True, slots=True)
class WeatherPlatformAlertsData:
    """Active alerts reported by Weather Platform."""

    generated_at: str
    active_count: int
    critical_count: int
    highest_level: str | None
    alerts: tuple[WeatherPlatformAlert, ...]


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


@dataclass(frozen=True, slots=True)
class WeatherPlatformRadarStorm:
    """Tracked storm object reported by Weather Platform."""

    storm_id: str | None
    intensity: str | None
    lifecycle_stage: str | None
    distance: float | None
    peak_reflectivity_dbz: float | None
    approaching_home: bool


@dataclass(frozen=True, slots=True)
class WeatherPlatformRadarStormTracking:
    """Storm-tracking intelligence reported by Weather Platform."""

    available: bool
    status: str | None
    valid_at: str | None
    tracked_object_count: int
    storms: tuple[WeatherPlatformRadarStorm, ...]


@dataclass(frozen=True, slots=True)
class WeatherPlatformRadarData:
    """Radar intelligence reported by Weather Platform."""

    generated_at: str
    unit_system: str
    lightning: WeatherPlatformRadarLightning
    storm_tracking: WeatherPlatformRadarStormTracking


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


@dataclass(frozen=True, slots=True)
class WeatherPlatformEventsData:
    """Active durable weather events reported by Weather Platform."""

    generated_at: str
    count: int
    events: tuple[WeatherPlatformEvent, ...]


@dataclass(frozen=True, slots=True)
class WeatherPlatformImpactProfile:
    """Current Weather Platform impact-profile guidance."""

    key: str
    title: str
    current_rating: str | None
    current_status: str | None


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

        response_unit_system = _required_str(payload, "unitSystem")
        if response_unit_system != unit_system:
            raise WeatherPlatformInvalidResponseError

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

        response_unit_system = _required_str(payload, "unitSystem")
        if response_unit_system != unit_system:
            raise WeatherPlatformInvalidResponseError

        daily = tuple(
            _parse_daily_forecast(item) for item in _as_list(payload.get("daily"))
        )
        hourly = tuple(
            _parse_hourly_forecast(item) for item in _as_list(payload.get("hourly"))
        )

        return WeatherPlatformForecastData(
            generated_at=_required_str(payload, "generatedAt"),
            unit_system=response_unit_system,
            periods_available=_required_bool(payload, "periodsAvailable"),
            hourly_available=_required_bool(payload, "hourlyAvailable"),
            daily=daily,
            hourly=hourly,
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

        response_unit_system = _required_str(payload, "unitSystem")
        if response_unit_system != unit_system:
            raise WeatherPlatformInvalidResponseError

        return WeatherPlatformRadarData(
            generated_at=_required_str(payload, "generatedAt"),
            unit_system=response_unit_system,
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

        response_unit_system = _required_str(payload, "unitSystem")
        if response_unit_system != unit_system:
            raise WeatherPlatformInvalidResponseError

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
    )


def _parse_impact_profile(value: Any) -> WeatherPlatformImpactProfile:
    """Parse one Weather Platform impact profile."""
    payload = _as_object(value)
    return WeatherPlatformImpactProfile(
        key=_required_str(payload, "key"),
        title=_required_str(payload, "title"),
        current_rating=_optional_str(payload, "currentRating"),
        current_status=_optional_str(payload, "currentStatus"),
    )
