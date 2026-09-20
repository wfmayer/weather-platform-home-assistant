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
        WeatherPlatformClimateData,
        WeatherPlatformCurrentData,
        WeatherPlatformEventsData,
        WeatherPlatformForecastData,
        WeatherPlatformHydrologyData,
        WeatherPlatformImpactsData,
        WeatherPlatformMetadata,
        WeatherPlatformMeteorologyData,
        WeatherPlatformRadarData,
        WeatherPlatformTodayData,
    )
    from .realtime import WeatherPlatformRealtime

_LOGGER = logging.getLogger(__name__)

OPTIONAL_RESOURCE_KEYS = {
    "air_quality": "airQuality",
    "alerts": "alerts",
    "radar": "radar",
    "events": "events",
    "impacts": "impacts",
    "today": "today",
    "hydrology": "hydrology",
    "climate": "climate",
    "meteorology": "meteorology",
}
OPTIONAL_ENDPOINTS = tuple(OPTIONAL_RESOURCE_KEYS)


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
    today: WeatherPlatformTodayData | None = None
    hydrology: WeatherPlatformHydrologyData | None = None
    climate: WeatherPlatformClimateData | None = None
    meteorology: WeatherPlatformMeteorologyData | None = None


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
        self.realtime: WeatherPlatformRealtime | None = None
        self.client = client
        self.unit_system = unit_system
        self.metadata: WeatherPlatformMetadata | None = None
        self._optional_endpoint_status: dict[str, bool | None] = dict.fromkeys(
            OPTIONAL_ENDPOINTS
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
            always_update=False,
        )

    @property
    def optional_endpoint_status(self) -> dict[str, bool | None]:
        """Return availability for optional Weather Platform API endpoints."""
        return dict(self._optional_endpoint_status)

    @property
    def unavailable_optional_endpoints(self) -> tuple[str, ...]:
        """Return optional endpoints that failed during the latest refresh."""
        return tuple(
            endpoint
            for endpoint, available in self._optional_endpoint_status.items()
            if available is False
        )

    @property
    def optional_api_degraded(self) -> bool:
        """Return whether any optional Weather Platform API endpoint failed."""
        return bool(self.unavailable_optional_endpoints)

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

        (
            air_quality,
            alerts,
            radar,
            events,
            impacts,
            today,
            hydrology,
            climate,
            meteorology,
        ) = await asyncio.gather(
            self._async_get_air_quality(),
            self._async_get_alerts(),
            self._async_get_radar(),
            self._async_get_active_events(),
            self._async_get_impacts(),
            self._async_get_today(),
            self._async_get_hydrology(),
            self._async_get_climate(),
            self._async_get_meteorology(),
        )

        return WeatherPlatformData(
            current=current,
            forecast=forecast,
            air_quality=air_quality,
            alerts=alerts,
            radar=radar,
            events=events,
            impacts=impacts,
            today=today,
            hydrology=hydrology,
            climate=climate,
            meteorology=meteorology,
        )

    def _resource_advertised(self, endpoint: str) -> bool:
        """Return whether the API index advertises an optional resource."""
        metadata = getattr(self, "metadata", None)
        if metadata is None:
            return True

        resource_key = OPTIONAL_RESOURCE_KEYS[endpoint]
        if resource_key in metadata.resources:
            return True

        self._optional_endpoint_status[endpoint] = None
        return False

    def _set_optional_endpoint_status(
        self,
        endpoint: str,
        *,
        available: bool,
    ) -> None:
        """Record optional endpoint health and log status transitions."""
        previous = self._optional_endpoint_status[endpoint]
        self._optional_endpoint_status[endpoint] = available

        if not available and previous is not False:
            _LOGGER.warning(
                "Weather Platform optional API endpoint %s is unavailable; "
                "core weather data will continue updating",
                endpoint,
            )
        elif available and previous is False:
            _LOGGER.info(
                "Weather Platform optional API endpoint %s recovered",
                endpoint,
            )

    async def _async_get_air_quality(
        self,
    ) -> WeatherPlatformAirQualityData | None:
        """Fetch optional air-quality guidance."""
        if not self._resource_advertised("air_quality"):
            return None
        try:
            result = await self.client.async_get_air_quality()
        except WeatherPlatformApiError:
            self._set_optional_endpoint_status("air_quality", available=False)
            _LOGGER.debug(
                "Weather Platform air-quality guidance is unavailable",
                exc_info=True,
            )
            return None

        self._set_optional_endpoint_status("air_quality", available=True)
        return result

    async def _async_get_alerts(self) -> WeatherPlatformAlertsData | None:
        """Fetch optional active-alert intelligence."""
        if not self._resource_advertised("alerts"):
            return None
        try:
            result = await self.client.async_get_alerts()
        except WeatherPlatformApiError:
            self._set_optional_endpoint_status("alerts", available=False)
            _LOGGER.debug(
                "Weather Platform active-alert intelligence is unavailable",
                exc_info=True,
            )
            return None

        self._set_optional_endpoint_status("alerts", available=True)
        return result

    async def _async_get_radar(self) -> WeatherPlatformRadarData | None:
        """Fetch optional radar intelligence."""
        if not self._resource_advertised("radar"):
            return None
        try:
            result = await self.client.async_get_radar(self.unit_system)
        except WeatherPlatformApiError:
            self._set_optional_endpoint_status("radar", available=False)
            _LOGGER.debug(
                "Weather Platform radar intelligence is unavailable",
                exc_info=True,
            )
            return None

        self._set_optional_endpoint_status("radar", available=True)
        return result

    async def _async_get_active_events(
        self,
    ) -> WeatherPlatformEventsData | None:
        """Fetch optional durable active weather events."""
        if not self._resource_advertised("events"):
            return None
        try:
            result = await self.client.async_get_active_events()
        except WeatherPlatformApiError:
            self._set_optional_endpoint_status("events", available=False)
            _LOGGER.debug(
                "Weather Platform active events are unavailable",
                exc_info=True,
            )
            return None

        self._set_optional_endpoint_status("events", available=True)
        return result

    async def _async_get_impacts(self) -> WeatherPlatformImpactsData | None:
        """Fetch optional weather-impact guidance."""
        if not self._resource_advertised("impacts"):
            return None
        try:
            result = await self.client.async_get_impacts(self.unit_system)
        except WeatherPlatformApiError:
            self._set_optional_endpoint_status("impacts", available=False)
            _LOGGER.debug(
                "Weather Platform impact guidance is unavailable",
                exc_info=True,
            )
            return None

        self._set_optional_endpoint_status("impacts", available=True)
        return result

    async def _async_get_today(self) -> WeatherPlatformTodayData | None:
        """Fetch optional synthesized daily weather story."""
        if not self._resource_advertised("today"):
            return None
        try:
            result = await self.client.async_get_today(self.unit_system)
        except WeatherPlatformApiError:
            self._set_optional_endpoint_status("today", available=False)
            _LOGGER.debug(
                "Weather Platform daily weather story is unavailable",
                exc_info=True,
            )
            return None

        self._set_optional_endpoint_status("today", available=True)
        return result

    async def _async_get_hydrology(self) -> WeatherPlatformHydrologyData | None:
        """Fetch optional hydrology context."""
        if not self._resource_advertised("hydrology"):
            return None
        try:
            result = await self.client.async_get_hydrology(self.unit_system)
        except WeatherPlatformApiError:
            self._set_optional_endpoint_status("hydrology", available=False)
            _LOGGER.debug(
                "Weather Platform hydrology context is unavailable",
                exc_info=True,
            )
            return None

        self._set_optional_endpoint_status("hydrology", available=True)
        return result

    async def _async_get_climate(self) -> WeatherPlatformClimateData | None:
        """Fetch optional climate context."""
        if not self._resource_advertised("climate"):
            return None
        try:
            result = await self.client.async_get_climate(self.unit_system)
        except WeatherPlatformApiError:
            self._set_optional_endpoint_status("climate", available=False)
            _LOGGER.debug(
                "Weather Platform climate context is unavailable",
                exc_info=True,
            )
            return None

        self._set_optional_endpoint_status("climate", available=True)
        return result

    async def _async_get_meteorology(
        self,
    ) -> WeatherPlatformMeteorologyData | None:
        """Fetch optional meteorology intelligence."""
        if not self._resource_advertised("meteorology"):
            return None
        try:
            result = await self.client.async_get_meteorology(self.unit_system)
        except WeatherPlatformApiError:
            self._set_optional_endpoint_status("meteorology", available=False)
            _LOGGER.debug(
                "Weather Platform meteorology intelligence is unavailable",
                exc_info=True,
            )
            return None

        self._set_optional_endpoint_status("meteorology", available=True)
        return result
