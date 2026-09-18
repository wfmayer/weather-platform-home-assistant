"""Tests for the Weather Platform REST client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.weather_platform.api import (
    WeatherPlatformApiClient,
    WeatherPlatformInvalidResponseError,
    WeatherPlatformInvalidUrlError,
    normalize_base_url,
)

BASE_URL = "http://weather-platform.local"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (BASE_URL, BASE_URL),
        (f"{BASE_URL}/", BASE_URL),
        (f"{BASE_URL}/api/v1", BASE_URL),
        (f"{BASE_URL}/api/v1/", BASE_URL),
        ("  http://weather-platform.local/  ", BASE_URL),
    ],
)
def test_normalize_base_url(value: str, expected: str) -> None:
    """Test normalization of supported Weather Platform URLs."""
    assert normalize_base_url(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "weather-platform.local",
        "ftp://weather-platform.local",
        "http://user:password@weather-platform.local",
        "http://weather-platform.local?test=true",
        "http://weather-platform.local#fragment",
    ],
)
def test_normalize_base_url_rejects_invalid_urls(value: str) -> None:
    """Test rejection of unsupported Weather Platform URLs."""
    with pytest.raises(WeatherPlatformInvalidUrlError):
        normalize_base_url(value)


async def test_current_conditions_parsing() -> None:
    """Test parsing current conditions, including the native condition field."""
    client = WeatherPlatformApiClient(BASE_URL, MagicMock())
    payload = {
        "generatedAt": "2026-09-18T21:00:00Z",
        "unitSystem": "imperial",
        "station": {
            "code": "TEST123",
            "name": "Test Station",
            "observedAt": "2026-09-18T20:59:00Z",
            "ageSeconds": 60,
            "stale": False,
            "source": "home-assistant",
        },
        "condition": "partlycloudy",
        "conditions": {
            "temperature": 78.4,
            "dewPoint": 61.2,
            "relativeHumidity": 51.0,
            "stationPressure": 29.84,
            "windSpeed": 4.2,
            "windGust": 8.1,
            "windDirectionDegrees": 220,
            "rainRate": 0.0,
            "dailyRain": 0.21,
            "eventRain": 0.21,
            "solarRadiation": 410.0,
            "solarIlluminance": 33800.0,
            "uvIndex": 3.0,
        },
    }

    with patch.object(client, "_async_get_json", new=AsyncMock(return_value=payload)):
        current = await client.async_get_current("imperial")

    assert current.condition == "partlycloudy"
    assert current.station.code == "TEST123"
    assert current.station.stale is False
    assert current.conditions.temperature == 78.4
    assert current.conditions.daily_rain == 0.21
    assert current.conditions.solar_radiation == 410.0


async def test_current_conditions_reject_unit_mismatch() -> None:
    """Test that a response using unexpected units is rejected."""
    client = WeatherPlatformApiClient(BASE_URL, MagicMock())
    payload = {
        "generatedAt": "2026-09-18T21:00:00Z",
        "unitSystem": "metric",
        "station": {},
        "conditions": {},
    }

    with (
        patch.object(client, "_async_get_json", new=AsyncMock(return_value=payload)),
        pytest.raises(WeatherPlatformInvalidResponseError),
    ):
        await client.async_get_current("imperial")
