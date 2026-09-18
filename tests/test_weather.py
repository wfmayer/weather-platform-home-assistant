"""Tests for the Weather Platform weather entity."""

from datetime import date
from unittest.mock import MagicMock

import pytest
from homeassistant.components.weather import (
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_IS_DAYTIME,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_NATIVE_WIND_GUST_SPEED,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_WIND_BEARING,
)

from custom_components.weather_platform.api import (
    WeatherPlatformCurrentConditions,
    WeatherPlatformCurrentData,
    WeatherPlatformDailyForecast,
    WeatherPlatformForecastData,
    WeatherPlatformForecastPeriod,
    WeatherPlatformHourlyForecast,
    WeatherPlatformStation,
    WeatherPlatformWind,
)
from custom_components.weather_platform.weather import (
    WeatherPlatformWeatherEntity,
    _forecast_condition,
)


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("Sunny", ATTR_CONDITION_SUNNY),
        ("Partly Cloudy", ATTR_CONDITION_PARTLYCLOUDY),
        ("Cloudy", ATTR_CONDITION_CLOUDY),
        ("Light Rain", ATTR_CONDITION_RAINY),
        ("Heavy Rain", ATTR_CONDITION_POURING),
        ("Thunderstorms with Rain", ATTR_CONDITION_LIGHTNING_RAINY),
        ("Snow", ATTR_CONDITION_SNOWY),
        ("Fog", ATTR_CONDITION_FOG),
        ("Windy", ATTR_CONDITION_WINDY),
        (None, None),
    ],
)
def test_forecast_condition_mapping(
    description: str | None,
    expected: str | None,
) -> None:
    """Test forecast text maps to native Home Assistant conditions."""
    assert _forecast_condition(description) == expected


def test_weather_entity_exposes_current_conditions_and_forecasts() -> None:
    """Test weather entity values are backed by coordinator data."""
    current = WeatherPlatformCurrentData(
        generated_at="2026-09-18T21:00:00Z",
        unit_system="imperial",
        station=WeatherPlatformStation(
            code="TEST123",
            name="Test Station",
            observed_at="2026-09-18T20:59:00Z",
            age_seconds=60,
            stale=False,
            source="test",
        ),
        condition="partlycloudy",
        conditions=WeatherPlatformCurrentConditions(
            temperature=78.4,
            dew_point=61.2,
            relative_humidity=51.0,
            station_pressure=29.84,
            wind_speed=4.2,
            wind_gust=8.1,
            wind_direction_degrees=220,
            rain_rate=0.0,
            daily_rain=0.21,
            event_rain=0.21,
            solar_radiation=410.0,
            solar_illuminance=33800.0,
            uv_index=3.0,
        ),
    )
    forecast = WeatherPlatformForecastData(
        generated_at="2026-09-18T21:00:00Z",
        unit_system="imperial",
        periods_available=True,
        hourly_available=True,
        daily=(
            WeatherPlatformDailyForecast(
                date=date(2026, 9, 19),
                display_name="Saturday",
                high_temperature=82.0,
                low_temperature=63.0,
                precipitation_probability=30,
                short_forecast="Partly Cloudy",
            ),
        ),
        hourly=(
            WeatherPlatformHourlyForecast(
                valid_at="2026-09-18T22:00:00Z",
                temperature=77.0,
                precipitation_probability=20,
                short_forecast="Light Rain",
                wind=WeatherPlatformWind(
                    minimum=3.0,
                    maximum=7.0,
                    direction="SW",
                ),
                wind_gust=12.0,
            ),
        ),
        periods=(
            WeatherPlatformForecastPeriod(
                name="Tonight",
                start_time="2026-09-18T22:00:00-04:00",
                end_time="2026-09-19T06:00:00-04:00",
                daytime=False,
                temperature=63.0,
                precipitation_probability=40,
                short_forecast="Chance Showers",
                detailed_forecast="A chance of showers overnight.",
                wind=WeatherPlatformWind(
                    minimum=3.0,
                    maximum=7.0,
                    direction="SW",
                ),
            ),
        ),
    )

    entry = MagicMock()
    entry.unique_id = "weather-platform-test"
    entry.entry_id = "entry-test"

    coordinator = MagicMock()
    coordinator.unit_system = "imperial"
    coordinator.metadata = None
    coordinator.client.base_url = "http://weather-platform.local"
    coordinator.data.current = current
    coordinator.data.forecast = forecast

    entity = WeatherPlatformWeatherEntity(entry, coordinator)

    assert entity.condition == "partlycloudy"
    assert entity.native_temperature == 78.4
    assert entity.native_dew_point == 61.2
    assert entity.humidity == 51.0
    assert entity.native_pressure == 29.84
    assert entity.native_wind_speed == 4.2
    assert entity.native_wind_gust_speed == 8.1
    assert entity.wind_bearing == 220
    assert entity.uv_index == 3.0

    daily = entity._async_forecast_daily()
    hourly = entity._async_forecast_hourly()
    twice_daily = entity._async_forecast_twice_daily()

    assert len(daily) == 1
    assert daily[0][ATTR_FORECAST_CONDITION] == ATTR_CONDITION_PARTLYCLOUDY
    assert daily[0][ATTR_FORECAST_NATIVE_TEMP] == 82.0
    assert daily[0][ATTR_FORECAST_NATIVE_TEMP_LOW] == 63.0
    assert daily[0][ATTR_FORECAST_PRECIPITATION_PROBABILITY] == 30

    assert len(hourly) == 1
    assert hourly[0][ATTR_FORECAST_CONDITION] == ATTR_CONDITION_RAINY
    assert hourly[0][ATTR_FORECAST_NATIVE_TEMP] == 77.0
    assert hourly[0][ATTR_FORECAST_NATIVE_WIND_SPEED] == 7.0
    assert hourly[0][ATTR_FORECAST_WIND_BEARING] == "SW"
    assert hourly[0][ATTR_FORECAST_NATIVE_WIND_GUST_SPEED] == 12.0

    assert len(twice_daily) == 1
    assert twice_daily[0][ATTR_FORECAST_IS_DAYTIME] is False
    assert twice_daily[0][ATTR_FORECAST_CONDITION] == ATTR_CONDITION_RAINY
    assert twice_daily[0][ATTR_FORECAST_NATIVE_TEMP] == 63.0
    assert twice_daily[0][ATTR_FORECAST_PRECIPITATION_PROBABILITY] == 40
    assert twice_daily[0][ATTR_FORECAST_NATIVE_WIND_SPEED] == 7.0
