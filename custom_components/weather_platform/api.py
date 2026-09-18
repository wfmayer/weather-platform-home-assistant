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

    async def async_get_current(self, unit_system: str) -> WeatherPlatformCurrentData:
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
            relative_humidity=_optional_float(conditions_payload, "relativeHumidity"),
            station_pressure=_optional_float(conditions_payload, "stationPressure"),
            wind_speed=_optional_float(conditions_payload, "windSpeed"),
            wind_gust=_optional_float(conditions_payload, "windGust"),
            wind_direction_degrees=_optional_int(
                conditions_payload, "windDirectionDegrees"
            ),
            rain_rate=_optional_float(conditions_payload, "rainRate"),
            daily_rain=_optional_float(conditions_payload, "dailyRain"),
            event_rain=_optional_float(conditions_payload, "eventRain"),
            solar_radiation=_optional_float(conditions_payload, "solarRadiation"),
            solar_illuminance=_optional_float(conditions_payload, "solarIlluminance"),
            uv_index=_optional_float(conditions_payload, "uvIndex"),
        )

        return WeatherPlatformCurrentData(
            generated_at=_required_str(payload, "generatedAt"),
            unit_system=response_unit_system,
            station=station,
            condition=_optional_str(payload, "condition"),
            conditions=conditions,
        )

    async def async_get_forecast(self, unit_system: str) -> WeatherPlatformForecastData:
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
        precipitation_probability=_optional_int(payload, "precipitationChancePercent"),
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
        precipitation_probability=_optional_int(payload, "precipitationChancePercent"),
        short_forecast=_optional_str(payload, "shortForecast"),
    )
