"""DataUpdateCoordinator for Weather Platform."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, override

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import WeatherPlatformApiClient, WeatherPlatformApiError
from .const import DOMAIN, UPDATE_INTERVAL_SECONDS

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .api import (
        WeatherPlatformAirQualityData,
        WeatherPlatformAlertsData,
        WeatherPlatformCurrentData,
        WeatherPlatformEventsData,
        WeatherPlatformForecastData,
        WeatherPlatformImpactsData,
        WeatherPlatformMetadata,
        WeatherPlatformRadarData,
    )

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WeatherPlatformData:
    """Combined Weather Platform coordinator data."""

    current: WeatherPlatformCurrentData
    forecast: WeatherPlatformForecastData
    air_quality: WeatherPlatformAirQualityData | None
    alerts: WeatherPlatformAlertsData | None
    radar: WeatherPlatformRadarData | None
    events: WeatherPlatformEventsData | None
    impacts: WeatherPlatformImpactsData | None


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
        """Fetch Weather Platform coordinator data."""
        try:
            current, forecast = await asyncio.gather(
                self.client.async_get_current(self.unit_system),
                self.client.async_get_forecast(self.unit_system),
            )
        except WeatherPlatformApiError as err:
            raise UpdateFailed from err

        air_quality, alerts, radar, events, impacts = await asyncio.gather(
            self._async_get_air_quality(),
            self._async_get_alerts(),
            self._async_get_radar(),
            self._async_get_active_events(),
            self._async_get_impacts(),
        )

        return WeatherPlatformData(
            current=current,
            forecast=forecast,
            air_quality=air_quality,
            alerts=alerts,
            radar=radar,
            events=events,
            impacts=impacts,
        )

    async def _async_get_air_quality(
        self,
    ) -> WeatherPlatformAirQualityData | None:
        """Fetch optional air-quality guidance."""
        try:
            return await self.client.async_get_air_quality()
        except WeatherPlatformApiError:
            _LOGGER.debug(
                "Weather Platform air-quality guidance is unavailable",
                exc_info=True,
            )
            return None

    async def _async_get_alerts(self) -> WeatherPlatformAlertsData | None:
        """Fetch optional active-alert intelligence."""
        try:
            return await self.client.async_get_alerts()
        except WeatherPlatformApiError:
            _LOGGER.debug(
                "Weather Platform active-alert intelligence is unavailable",
                exc_info=True,
            )
            return None

    async def _async_get_radar(self) -> WeatherPlatformRadarData | None:
        """Fetch optional radar intelligence."""
        try:
            return await self.client.async_get_radar(self.unit_system)
        except WeatherPlatformApiError:
            _LOGGER.debug(
                "Weather Platform radar intelligence is unavailable",
                exc_info=True,
            )
            return None

    async def _async_get_active_events(
        self,
    ) -> WeatherPlatformEventsData | None:
        """Fetch optional durable active weather events."""
        try:
            return await self.client.async_get_active_events()
        except WeatherPlatformApiError:
            _LOGGER.debug(
                "Weather Platform active events are unavailable",
                exc_info=True,
            )
            return None

    async def _async_get_impacts(self) -> WeatherPlatformImpactsData | None:
        """Fetch optional weather-impact guidance."""
        try:
            return await self.client.async_get_impacts(self.unit_system)
        except WeatherPlatformApiError:
            _LOGGER.debug(
                "Weather Platform impact guidance is unavailable",
                exc_info=True,
            )
            return None
