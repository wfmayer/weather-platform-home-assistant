"""Tests for Weather Platform binary sensor entities."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.weather_platform.binary_sensor import (
    WeatherPlatformAtmosphericModelDataStaleBinarySensor,
    WeatherPlatformHydrologyGaugeDataStaleBinarySensor,
    WeatherPlatformRadarCoverageLimitedBinarySensor,
    WeatherPlatformRadarDataStaleBinarySensor,
    WeatherPlatformRadarPrecipitationNowBinarySensor,
)


def _entry() -> MagicMock:
    """Build a lightweight config entry."""
    entry = MagicMock()
    entry.unique_id = "weather-platform-test"
    entry.entry_id = "entry-test"
    return entry


def _coordinator(data: SimpleNamespace) -> MagicMock:
    """Build a lightweight coordinator."""
    coordinator = MagicMock()
    coordinator.metadata = None
    coordinator.client.base_url = "http://weather-platform.local"
    coordinator.data = data
    return coordinator


def test_radar_nowcast_binary_sensors() -> None:
    """Test radar nowcast and radar-health binary sensors."""
    radar = SimpleNamespace(
        precipitation=SimpleNamespace(stale=False),
        nowcast=SimpleNamespace(
            available=True,
            precipitation_now=True,
            coverage_limited=False,
        ),
    )
    coordinator = _coordinator(SimpleNamespace(radar=radar))
    entry = _entry()

    precipitation = WeatherPlatformRadarPrecipitationNowBinarySensor(
        entry,
        coordinator,
    )
    stale = WeatherPlatformRadarDataStaleBinarySensor(entry, coordinator)
    coverage = WeatherPlatformRadarCoverageLimitedBinarySensor(entry, coordinator)

    assert precipitation.is_on is True
    assert stale.is_on is False
    assert coverage.is_on is False


def test_hydrology_and_atmospheric_stale_sensors() -> None:
    """Test hydrology and atmospheric-model stale diagnostics."""
    data = SimpleNamespace(
        hydrology=SimpleNamespace(
            gauges=SimpleNamespace(available=True, stale=True),
        ),
        meteorology=SimpleNamespace(
            atmospheric_model=SimpleNamespace(available=True, stale=False),
        ),
    )
    coordinator = _coordinator(data)
    entry = _entry()

    hydrology = WeatherPlatformHydrologyGaugeDataStaleBinarySensor(
        entry,
        coordinator,
    )
    atmospheric = WeatherPlatformAtmosphericModelDataStaleBinarySensor(
        entry,
        coordinator,
    )

    assert hydrology.is_on is True
    assert atmospheric.is_on is False
