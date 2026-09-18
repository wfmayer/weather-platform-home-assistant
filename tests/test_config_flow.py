"""Tests for the Weather Platform config flow."""

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.const import CONF_URL
from homeassistant.data_entry_flow import FlowResultType

from custom_components.weather_platform.api import (
    WeatherPlatformConnectionError,
    WeatherPlatformMetadata,
)
from custom_components.weather_platform.const import DOMAIN, NAME

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

BASE_URL = "http://weather-platform.local"
METADATA = WeatherPlatformMetadata(
    name="Weather Platform API",
    api_version="v1",
    platform_version="v1.13.0",
    resources={
        "current": "/api/v1/current",
        "forecast": "/api/v1/forecast",
    },
)


async def test_user_flow_creates_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test a successful user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "custom_components.weather_platform.config_flow."
        "WeatherPlatformApiClient.async_get_metadata",
        new=AsyncMock(return_value=METADATA),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: f"{BASE_URL}/api/v1/"},
        )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == {CONF_URL: BASE_URL}
    mock_setup_entry.assert_awaited_once()


async def test_user_flow_rejects_invalid_url(hass: HomeAssistant) -> None:
    """Test an invalid URL remains on the form with a validation error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "weather-platform.local"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_url"}


async def test_user_flow_handles_connection_error(hass: HomeAssistant) -> None:
    """Test an unreachable Weather Platform instance reports cannot connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    with patch(
        "custom_components.weather_platform.config_flow."
        "WeatherPlatformApiClient.async_get_metadata",
        new=AsyncMock(side_effect=WeatherPlatformConnectionError),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: BASE_URL},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
