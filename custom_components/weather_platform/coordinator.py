"""DataUpdateCoordinator for Weather Platform."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, override

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WeatherPlatformApiClient, WeatherPlatformApiError
from .const import DOMAIN, UPDATE_INTERVAL_SECONDS

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .api import (
        WeatherPlatformCurrentData,
        WeatherPlatformForecastData,
        WeatherPlatformMetadata,
    )

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WeatherPlatformData:
    """Combined Weather Platform coordinator data."""

    current: WeatherPlatformCurrentData
    forecast: WeatherPlatformForecastData


class WeatherPlatformDataUpdateCoordinator(DataUpdateCoordinator[WeatherPlatformData]):
    """Coordinate Weather Platform REST API updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry[WeatherPlatformDataUpdateCoordinator],
        client: WeatherPlatformApiClient,
        unit_system: str,
    ) -> None:
        """Initialize the Weather Platform coordinator."""
        self.client = client
        self.unit_system = unit_system
        self.metadata: WeatherPlatformMetadata | None = None

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
            always_update=False,
        )

    @override
    async def _async_setup(self) -> None:
        """Load Weather Platform metadata once during entry setup."""
        try:
            self.metadata = await self.client.async_get_metadata()
        except WeatherPlatformApiError as err:
            raise UpdateFailed from err

    @override
    async def _async_update_data(self) -> WeatherPlatformData:
        """Fetch current conditions and forecast data."""
        try:
            current, forecast = await asyncio.gather(
                self.client.async_get_current(self.unit_system),
                self.client.async_get_forecast(self.unit_system),
            )
        except WeatherPlatformApiError as err:
            raise UpdateFailed from err

        return WeatherPlatformData(
            current=current,
            forecast=forecast,
        )
