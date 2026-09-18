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


async def test_forecast_parses_twice_daily_periods() -> None:
    """Test parsing detailed NWS forecast periods for twice-daily forecasts."""
    client = WeatherPlatformApiClient(BASE_URL, MagicMock())
    payload = {
        "generatedAt": "2026-09-18T21:00:00Z",
        "unitSystem": "imperial",
        "periodsAvailable": True,
        "hourlyAvailable": True,
        "periods": [
            {
                "name": "Tonight",
                "startTime": "2026-09-18T22:00:00-04:00",
                "endTime": "2026-09-19T06:00:00-04:00",
                "daytime": False,
                "temperature": 63,
                "precipitationChancePercent": 40,
                "shortForecast": "Chance Showers",
                "detailedForecast": "A chance of showers overnight.",
                "wind": {"minimum": 3, "maximum": 7, "direction": "SW"},
            }
        ],
        "daily": [],
        "hourly": [],
    }

    with patch.object(client, "_async_get_json", new=AsyncMock(return_value=payload)):
        forecast = await client.async_get_forecast("imperial")

    assert len(forecast.periods) == 1
    assert forecast.periods[0].daytime is False
    assert forecast.periods[0].temperature == 63.0
    assert forecast.periods[0].wind is not None
    assert forecast.periods[0].wind.maximum == 7.0


async def test_air_quality_parses_extended_pollutants() -> None:
    """Test extended air-quality and wildfire fields are retained."""
    client = WeatherPlatformApiClient(BASE_URL, MagicMock())
    period = {
        "validAt": "2026-09-18T21:00:00Z",
        "usAqi": 58,
        "category": "Moderate",
        "dominantPollutant": "pm25",
        "dominantPollutantAqi": 58,
        "pm25": 13.2,
        "pm10": 19.0,
        "ozone": 71.0,
        "nitrogenDioxide": 14.0,
        "carbonMonoxide": 180.0,
        "sulphurDioxide": 3.0,
        "wildfirePm10": 4.5,
        "wildfirePm10SharePercent": 23.7,
    }
    payload = {
        "generatedAt": "2026-09-18T21:00:00Z",
        "provider": "Open-Meteo",
        "model": "cams_global",
        "fetchedAt": "2026-09-18T20:55:00Z",
        "stale": False,
        "current": period,
        "peakNext24Hours": {**period, "usAqi": 72},
        "minimumNext24Hours": {**period, "usAqi": 41},
        "hourly": [period],
    }

    with patch.object(client, "_async_get_json", new=AsyncMock(return_value=payload)):
        air_quality = await client.async_get_air_quality()

    assert air_quality.current.nitrogen_dioxide == 14.0
    assert air_quality.current.wildfire_pm10_share_percent == 23.7
    assert air_quality.peak_next_24_hours is not None
    assert air_quality.peak_next_24_hours.us_aqi == 72
    assert air_quality.minimum_next_24_hours is not None
    assert air_quality.minimum_next_24_hours.us_aqi == 41
    assert len(air_quality.hourly) == 1


async def test_radar_parses_precipitation_and_nowcast() -> None:
    """Test radar precipitation and short-range nowcast parsing."""
    client = WeatherPlatformApiClient(BASE_URL, MagicMock())
    payload = {
        "generatedAt": "2026-09-18T21:00:00Z",
        "unitSystem": "imperial",
        "precipitation": {
            "available": True,
            "insideCoverage": True,
            "stale": False,
            "source": "MRMS",
            "precipitationRate": 0.18,
            "twoMinutePrecipitation": 0.006,
            "reflectivityDbz": 41.2,
            "intensity": "MODERATE",
        },
        "nowcast": {
            "available": True,
            "status": "APPROACHING",
            "radarValidAt": "2026-09-18T20:58:00Z",
            "precipitationNow": False,
            "arrivalLeadMinutes": 14,
            "arrivalAt": "2026-09-18T21:14:00Z",
            "projectedDurationMinutes": 38,
            "peakReflectivityDbz": 47.1,
            "arrivalEchoCoveragePercent": 72.0,
            "maximumEvaluatedLeadMinutes": 60,
            "coverageLimited": False,
            "motionDirection": "ENE",
            "motionSpeed": 22.5,
            "motionBearingDegrees": 68.0,
            "motionCoherencePercent": 83.0,
            "motionConsensusSampleCount": 12,
            "motionConsensusInlierCount": 10,
        },
        "lightning": {
            "available": True,
            "strikeCount": 3,
            "recentWindowStrikeCount": 1,
        },
        "stormTracking": {
            "available": True,
            "trackedObjectCount": 1,
            "storms": [
                {
                    "id": "storm-1",
                    "distance": 11.4,
                    "peakReflectivityDbz": 48.0,
                    "approachingHome": True,
                }
            ],
        },
    }

    with patch.object(client, "_async_get_json", new=AsyncMock(return_value=payload)):
        radar = await client.async_get_radar("imperial")

    assert radar.precipitation is not None
    assert radar.precipitation.reflectivity_dbz == 41.2
    assert radar.nowcast is not None
    assert radar.nowcast.arrival_lead_minutes == 14
    assert radar.nowcast.motion_speed == 22.5
    assert radar.storm_tracking.storms[0].approaching_home is True


async def test_hydrology_parsing() -> None:
    """Test antecedent rainfall and nearby gauge parsing."""
    client = WeatherPlatformApiClient(BASE_URL, MagicMock())
    payload = {
        "generatedAt": "2026-09-18T21:00:00Z",
        "unitSystem": "imperial",
        "rainfall": {
            "available": True,
            "level": "WET",
            "headline": "Wet antecedent conditions",
            "rainfall24Hours": 0.4,
            "rainfall3Days": 1.2,
            "rainfall7Days": 2.1,
            "rainfall14Days": 3.0,
            "rainfall30Days": 5.4,
        },
        "gauges": {
            "available": True,
            "stale": False,
            "fetchedAt": "2026-09-18T20:55:00Z",
            "risingCount": 1,
            "gauges": [
                {
                    "monitoringLocationId": "USGS-1",
                    "siteNumber": "02100000",
                    "name": "Test Creek",
                    "distance": 8.3,
                    "stage": 4.2,
                    "discharge": 132.0,
                    "trend": "RISING",
                }
            ],
        },
    }

    with patch.object(client, "_async_get_json", new=AsyncMock(return_value=payload)):
        hydrology = await client.async_get_hydrology("imperial")

    assert hydrology.rainfall.level == "WET"
    assert hydrology.rainfall.rainfall_7_days == 2.1
    assert hydrology.gauges.rising_count == 1
    assert hydrology.gauges.gauges[0].stage == 4.2


async def test_today_and_climate_parsing() -> None:
    """Test daily story and climate summaries retain automation context."""
    client = WeatherPlatformApiClient(BASE_URL, MagicMock())
    today_payload = {
        "generatedAt": "2026-09-18T21:00:00Z",
        "observedAt": "2026-09-18T20:59:00Z",
        "unitSystem": "imperial",
        "headline": "Warm and mostly quiet",
        "summary": "A dry evening with light wind.",
        "tone": "good",
        "sections": [
            {
                "key": "wind",
                "label": "Wind",
                "headline": "Light breeze",
                "detail": "No wind impacts expected.",
            }
        ],
        "evolution": None,
        "bestWindow": {
            "label": "Best outdoor window",
            "headline": "This evening",
            "startedAt": "2026-09-18T22:00:00Z",
            "endedAt": "2026-09-19T00:00:00Z",
        },
        "impactWindow": None,
    }
    climate_payload = {
        "generatedAt": "2026-09-18T21:00:00Z",
        "unitSystem": "imperial",
        "available": True,
        "firstObservedAt": "2025-09-01T00:00:00Z",
        "lastObservedAt": "2026-09-18T20:59:00Z",
        "headline": "Warmer than the recent baseline",
        "summary": "The latest complete day was above normal.",
        "tone": "warm",
        "completeDayCount": 380,
        "archiveYearCount": 2,
        "latestDay": {
            "date": "2026-09-17",
            "meanTemperature": 75.0,
            "meanTemperatureAnomaly": 3.1,
            "highTemperaturePercentile": 82,
            "lowTemperaturePercentile": 71,
            "percentileSampleCount": 365,
        },
        "month": {
            "completeDayCount": 17,
            "rainfall": 2.4,
            "expectedRainfall": 2.8,
            "rainfallDeparture": -0.4,
            "heatingDegreeDays": 0.0,
            "heatingDegreeDayDeparture": 0.0,
            "coolingDegreeDays": 155.0,
            "coolingDegreeDayDeparture": 12.0,
        },
        "streaks": {
            "currentDryDays": 3,
            "longestDryDays": 10,
            "currentWetDays": 0,
            "longestWetDays": 4,
            "currentHotDays": 2,
            "longestHotDays": 8,
            "currentWarmNightDays": 1,
            "longestWarmNightDays": 5,
        },
        "records": {},
    }

    with patch.object(
        client,
        "_async_get_json",
        new=AsyncMock(side_effect=[today_payload, climate_payload]),
    ):
        today = await client.async_get_today("imperial")
        climate = await client.async_get_climate("imperial")

    assert today.headline == "Warm and mostly quiet"
    assert today.best_window is not None
    assert today.best_window.label == "Best outdoor window"
    assert climate.latest_day.mean_temperature_anomaly == 3.1
    assert climate.month.rainfall_departure == -0.4
    assert climate.streaks.current_dry_days == 3


async def test_meteorology_parsing() -> None:
    """Test derived station, model, and severe-weather meteorology parsing."""
    client = WeatherPlatformApiClient(BASE_URL, MagicMock())
    payload = {
        "generatedAt": "2026-09-18T21:00:00Z",
        "unitSystem": "imperial",
        "available": True,
        "current": {
            "observedAt": "2026-09-18T20:59:00Z",
            "feelsLike": 81.2,
            "heatIndex": 82.0,
            "wetBulb": 67.1,
        },
        "moisture": {
            "vaporPressureDeficit": 1.23,
            "absoluteHumidity": 12.4,
            "mixingRatio": 9.8,
        },
        "pressure": {
            "seaLevelPressure": 30.02,
            "pressureChangeThreeHours": -0.05,
            "tendency": "FALLING",
        },
        "thermodynamics": {
            "estimatedCloudBaseAgl": 4100.0,
            "gustFactor": 1.4,
        },
        "wbgt": {
            "available": True,
            "wetBulbGlobeTemperature": 79.0,
        },
        "atmosphericModel": {
            "available": True,
            "stale": False,
            "provider": "Open-Meteo",
            "model": "HRRR",
            "capeJoulesPerKilogram": 1450.0,
            "convectiveInhibitionJoulesPerKilogram": -28.0,
            "liftedIndex": -2.4,
            "precipitableWater": 1.6,
            "bulkShear0To6Km": 31.0,
        },
        "severeWeather": {
            "available": True,
            "outlookLevel": "MARGINAL",
            "compositeScore": 34,
            "headline": "Limited severe risk",
            "signals": [
                {
                    "key": "cape",
                    "label": "Instability",
                    "level": "ELEVATED",
                    "valueDisplay": "1450 J/kg",
                }
            ],
        },
    }

    with patch.object(client, "_async_get_json", new=AsyncMock(return_value=payload)):
        meteorology = await client.async_get_meteorology("imperial")

    assert meteorology.current is not None
    assert meteorology.current.feels_like == 81.2
    assert meteorology.pressure is not None
    assert meteorology.pressure.tendency == "FALLING"
    assert meteorology.atmospheric_model is not None
    assert meteorology.atmospheric_model.cape == 1450.0
    assert meteorology.severe_weather is not None
    assert meteorology.severe_weather.composite_score == 34
