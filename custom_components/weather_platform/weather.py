"""Weather entity for Weather Platform."""

from __future__ import annotations

from datetime import datetime, time
from typing import TYPE_CHECKING, override

from homeassistant.components.weather import (
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    ATTR_CONDITION_WINDY_VARIANT,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_IS_DAYTIME,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_NATIVE_WIND_GUST_SPEED,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_WIND_BEARING,
    Forecast,
    SingleCoordinatorWeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.const import (
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.util import dt as dt_util

from .const import (
    API_UNIT_SYSTEM_METRIC,
    DOMAIN,
    NAME,
)
from .coordinator import WeatherPlatformDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

PARALLEL_UPDATES = 0

_RAIN_TERMS = ("rain", "shower", "drizzle")
_PARTLY_CLOUDY_TERMS = (
    "partly cloudy",
    "partly sunny",
    "mostly clear",
    "mostly sunny",
)
_WIND_TERMS = ("windy", "breezy")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[WeatherPlatformDataUpdateCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the Weather Platform weather entity."""
    del hass
    async_add_entities([WeatherPlatformWeatherEntity(entry, entry.runtime_data)])


class WeatherPlatformWeatherEntity(
    SingleCoordinatorWeatherEntity[WeatherPlatformDataUpdateCoordinator]
):
    """Native Home Assistant weather entity backed by Weather Platform."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY
        | WeatherEntityFeature.FORECAST_HOURLY
        | WeatherEntityFeature.FORECAST_TWICE_DAILY
    )

    def __init__(
        self,
        entry: ConfigEntry[WeatherPlatformDataUpdateCoordinator],
        coordinator: WeatherPlatformDataUpdateCoordinator,
    ) -> None:
        """Initialize the Weather Platform weather entity."""
        super().__init__(coordinator)

        identifier = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{identifier}:weather"

        is_metric = coordinator.unit_system == API_UNIT_SYSTEM_METRIC
        self._attr_native_temperature_unit = (
            UnitOfTemperature.CELSIUS if is_metric else UnitOfTemperature.FAHRENHEIT
        )
        self._attr_native_pressure_unit = (
            UnitOfPressure.HPA if is_metric else UnitOfPressure.INHG
        )
        self._attr_native_wind_speed_unit = (
            UnitOfSpeed.KILOMETERS_PER_HOUR if is_metric else UnitOfSpeed.MILES_PER_HOUR
        )
        self._attr_native_precipitation_unit = (
            UnitOfPrecipitationDepth.MILLIMETERS
            if is_metric
            else UnitOfPrecipitationDepth.INCHES
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
    def condition(self) -> str | None:
        """Return the current weather condition."""
        return self.coordinator.data.current.condition

    @property
    @override
    def native_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.coordinator.data.current.conditions.temperature

    @property
    @override
    def native_dew_point(self) -> float | None:
        """Return the current dew point."""
        return self.coordinator.data.current.conditions.dew_point

    @property
    @override
    def humidity(self) -> float | None:
        """Return the current relative humidity."""
        return self.coordinator.data.current.conditions.relative_humidity

    @property
    @override
    def native_pressure(self) -> float | None:
        """Return the current station pressure."""
        return self.coordinator.data.current.conditions.station_pressure

    @property
    @override
    def native_wind_speed(self) -> float | None:
        """Return the current wind speed."""
        return self.coordinator.data.current.conditions.wind_speed

    @property
    @override
    def native_wind_gust_speed(self) -> float | None:
        """Return the current wind gust."""
        return self.coordinator.data.current.conditions.wind_gust

    @property
    @override
    def wind_bearing(self) -> int | None:
        """Return the current wind bearing."""
        return self.coordinator.data.current.conditions.wind_direction_degrees

    @property
    @override
    def uv_index(self) -> float | None:
        """Return the current UV index."""
        return self.coordinator.data.current.conditions.uv_index

    @callback
    @override
    def _async_forecast_daily(self) -> list[Forecast]:
        """Return the daily forecast in native units."""
        forecasts: list[Forecast] = []

        for item in self.coordinator.data.forecast.daily:
            forecast_datetime = datetime.combine(
                item.date,
                time.min,
                tzinfo=dt_util.UTC,
            )
            forecast = Forecast(
                datetime=forecast_datetime.isoformat(),
            )

            condition = _forecast_condition(item.short_forecast)
            if condition is not None:
                forecast[ATTR_FORECAST_CONDITION] = condition
            if item.high_temperature is not None:
                forecast[ATTR_FORECAST_NATIVE_TEMP] = item.high_temperature
            if item.low_temperature is not None:
                forecast[ATTR_FORECAST_NATIVE_TEMP_LOW] = item.low_temperature
            if item.precipitation_probability is not None:
                forecast[ATTR_FORECAST_PRECIPITATION_PROBABILITY] = (
                    item.precipitation_probability
                )

            forecasts.append(forecast)

        return forecasts

    @callback
    @override
    def _async_forecast_hourly(self) -> list[Forecast]:
        """Return the hourly forecast in native units."""
        forecasts: list[Forecast] = []

        for item in self.coordinator.data.forecast.hourly:
            forecast = Forecast(datetime=item.valid_at)

            condition = _forecast_condition(item.short_forecast)
            if condition is not None:
                forecast[ATTR_FORECAST_CONDITION] = condition
            if item.temperature is not None:
                forecast[ATTR_FORECAST_NATIVE_TEMP] = item.temperature
            if item.precipitation_probability is not None:
                forecast[ATTR_FORECAST_PRECIPITATION_PROBABILITY] = (
                    item.precipitation_probability
                )
            if item.wind is not None:
                wind_speed = (
                    item.wind.maximum
                    if item.wind.maximum is not None
                    else item.wind.minimum
                )
                if wind_speed is not None:
                    forecast[ATTR_FORECAST_NATIVE_WIND_SPEED] = wind_speed
                if item.wind.direction is not None:
                    forecast[ATTR_FORECAST_WIND_BEARING] = item.wind.direction
            if item.wind_gust is not None:
                forecast[ATTR_FORECAST_NATIVE_WIND_GUST_SPEED] = item.wind_gust

            forecasts.append(forecast)

        return forecasts

    @callback
    @override
    def _async_forecast_twice_daily(self) -> list[Forecast]:
        """Return NWS day and night forecast periods in native units."""
        forecasts: list[Forecast] = []

        for item in self.coordinator.data.forecast.periods:
            forecast = Forecast(datetime=item.start_time)

            condition = _forecast_condition(item.short_forecast)
            if condition is not None:
                forecast[ATTR_FORECAST_CONDITION] = condition
            forecast[ATTR_FORECAST_IS_DAYTIME] = item.daytime
            if item.temperature is not None:
                forecast[ATTR_FORECAST_NATIVE_TEMP] = item.temperature
            if item.precipitation_probability is not None:
                forecast[ATTR_FORECAST_PRECIPITATION_PROBABILITY] = (
                    item.precipitation_probability
                )
            if item.wind is not None:
                wind_speed = (
                    item.wind.maximum
                    if item.wind.maximum is not None
                    else item.wind.minimum
                )
                if wind_speed is not None:
                    forecast[ATTR_FORECAST_NATIVE_WIND_SPEED] = wind_speed
                if item.wind.direction is not None:
                    forecast[ATTR_FORECAST_WIND_BEARING] = item.wind.direction

            forecasts.append(forecast)

        return forecasts


def _forecast_condition(description: str | None) -> str | None:
    """Map a forecast description to an HA condition."""
    if description is None:
        return None

    normalized = description.casefold()
    has_rain = any(term in normalized for term in _RAIN_TERMS)
    has_wind = any(term in normalized for term in _WIND_TERMS)

    condition: str | None = None

    if "thunder" in normalized:
        condition = (
            ATTR_CONDITION_LIGHTNING_RAINY if has_rain else ATTR_CONDITION_LIGHTNING
        )
    elif "hail" in normalized:
        condition = ATTR_CONDITION_HAIL
    elif (
        "sleet" in normalized
        or "wintry mix" in normalized
        or ("snow" in normalized and has_rain)
    ):
        condition = ATTR_CONDITION_SNOWY_RAINY
    elif "snow" in normalized:
        condition = ATTR_CONDITION_SNOWY
    elif "fog" in normalized or "mist" in normalized:
        condition = ATTR_CONDITION_FOG
    elif has_rain:
        condition = (
            ATTR_CONDITION_POURING if "heavy" in normalized else ATTR_CONDITION_RAINY
        )
    elif any(term in normalized for term in _PARTLY_CLOUDY_TERMS):
        condition = ATTR_CONDITION_PARTLYCLOUDY
    elif has_wind:
        condition = (
            ATTR_CONDITION_WINDY_VARIANT
            if "cloud" in normalized or "overcast" in normalized
            else ATTR_CONDITION_WINDY
        )
    elif "cloud" in normalized or "overcast" in normalized:
        condition = ATTR_CONDITION_CLOUDY
    elif "sunny" in normalized or "clear" in normalized or "fair" in normalized:
        condition = ATTR_CONDITION_SUNNY

    return condition
