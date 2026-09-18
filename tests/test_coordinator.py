"""Tests for the Weather Platform data coordinator."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, sentinel

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.weather_platform.api import WeatherPlatformConnectionError
from custom_components.weather_platform.coordinator import (
    OPTIONAL_ENDPOINTS,
    WeatherPlatformDataUpdateCoordinator,
)

UNIT_SYSTEM = "imperial"


def _client() -> MagicMock:
    """Build a client with successful responses for every endpoint."""
    client = MagicMock()
    client.async_get_current = AsyncMock(return_value=sentinel.current)
    client.async_get_forecast = AsyncMock(return_value=sentinel.forecast)
    client.async_get_air_quality = AsyncMock(return_value=sentinel.air_quality)
    client.async_get_alerts = AsyncMock(return_value=sentinel.alerts)
    client.async_get_radar = AsyncMock(return_value=sentinel.radar)
    client.async_get_active_events = AsyncMock(return_value=sentinel.events)
    client.async_get_impacts = AsyncMock(return_value=sentinel.impacts)
    client.async_get_today = AsyncMock(return_value=sentinel.today)
    client.async_get_hydrology = AsyncMock(return_value=sentinel.hydrology)
    client.async_get_climate = AsyncMock(return_value=sentinel.climate)
    client.async_get_meteorology = AsyncMock(return_value=sentinel.meteorology)
    return client


def _coordinator(client: MagicMock) -> WeatherPlatformDataUpdateCoordinator:
    """Build a coordinator without starting Home Assistant scheduling."""
    coordinator = object.__new__(WeatherPlatformDataUpdateCoordinator)
    coordinator.client = client
    coordinator.unit_system = UNIT_SYSTEM
    coordinator._optional_endpoint_status = dict.fromkeys(OPTIONAL_ENDPOINTS)
    return coordinator


async def test_optional_endpoint_failure_keeps_core_data_available() -> None:
    """Test an optional endpoint failure does not fail the whole refresh."""
    client = _client()
    client.async_get_air_quality.side_effect = WeatherPlatformConnectionError
    coordinator = _coordinator(client)

    data = await coordinator._async_update_data()

    assert data.current is sentinel.current
    assert data.forecast is sentinel.forecast
    assert data.air_quality is None
    assert data.alerts is sentinel.alerts
    assert data.today is sentinel.today
    assert data.hydrology is sentinel.hydrology
    assert data.climate is sentinel.climate
    assert data.meteorology is sentinel.meteorology
    assert coordinator.optional_api_degraded is True
    assert coordinator.unavailable_optional_endpoints == ("air_quality",)
    assert coordinator.optional_endpoint_status["air_quality"] is False
    assert coordinator.optional_endpoint_status["alerts"] is True


async def test_core_endpoint_failure_fails_refresh() -> None:
    """Test a required current-conditions failure fails the coordinator refresh."""
    client = _client()
    client.async_get_current.side_effect = WeatherPlatformConnectionError
    coordinator = _coordinator(client)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_optional_endpoint_recovery_clears_degraded_status() -> None:
    """Test an optional endpoint can recover on a later refresh."""
    client = _client()
    client.async_get_radar.side_effect = WeatherPlatformConnectionError
    coordinator = _coordinator(client)

    assert await coordinator._async_get_radar() is None
    assert coordinator.optional_endpoint_status["radar"] is False
    assert coordinator.optional_api_degraded is True

    client.async_get_radar.side_effect = None
    client.async_get_radar.return_value = sentinel.radar

    assert await coordinator._async_get_radar() is sentinel.radar
    assert coordinator.optional_endpoint_status["radar"] is True
    assert coordinator.optional_api_degraded is False


async def test_new_optional_endpoint_failure_isolated() -> None:
    """Test a new intelligence endpoint can fail without affecting core data."""
    client = _client()
    client.async_get_meteorology.side_effect = WeatherPlatformConnectionError
    coordinator = _coordinator(client)

    data = await coordinator._async_update_data()

    assert data.current is sentinel.current
    assert data.forecast is sentinel.forecast
    assert data.meteorology is None
    assert coordinator.unavailable_optional_endpoints == ("meteorology",)


async def test_unadvertised_optional_resource_is_skipped_without_degradation() -> None:
    """Test backward compatibility with API versions lacking a new resource."""
    client = _client()
    coordinator = _coordinator(client)
    coordinator.metadata = SimpleNamespace(
        resources={
            "current": "/api/v1/current",
            "forecast": "/api/v1/forecast",
            "alerts": "/api/v1/alerts",
        }
    )

    assert await coordinator._async_get_meteorology() is None
    client.async_get_meteorology.assert_not_awaited()
    assert coordinator.optional_endpoint_status["meteorology"] is None
    assert coordinator.optional_api_degraded is False
