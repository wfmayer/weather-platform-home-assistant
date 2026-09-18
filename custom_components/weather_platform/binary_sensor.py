"""Binary sensor entities for Weather Platform."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import WeatherPlatformDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[WeatherPlatformDataUpdateCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add Weather Platform binary sensor entities."""
    del hass
    async_add_entities(
        [
            WeatherPlatformStationDataStaleBinarySensor(
                entry,
                entry.runtime_data,
            ),
            WeatherPlatformAirQualityDataStaleBinarySensor(
                entry,
                entry.runtime_data,
            ),
        ]
    )


class WeatherPlatformDiagnosticBinarySensor(
    CoordinatorEntity[WeatherPlatformDataUpdateCoordinator],
    BinarySensorEntity,
):
    """Base Weather Platform diagnostic binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry[WeatherPlatformDataUpdateCoordinator],
        coordinator: WeatherPlatformDataUpdateCoordinator,
        key: str,
    ) -> None:
        """Initialize a Weather Platform diagnostic binary sensor."""
        super().__init__(coordinator)

        identifier = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{identifier}:{key}"

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
            configuration_url=coordinator.client.base_url,
            entry_type=DeviceEntryType.SERVICE,
        )


class WeatherPlatformStationDataStaleBinarySensor(
    WeatherPlatformDiagnosticBinarySensor
):
    """Indicate whether Weather Platform considers station data stale."""

    _attr_name = "Station data stale"

    def __init__(
        self,
        entry: ConfigEntry[WeatherPlatformDataUpdateCoordinator],
        coordinator: WeatherPlatformDataUpdateCoordinator,
    ) -> None:
        """Initialize the station data stale binary sensor."""
        super().__init__(entry, coordinator, "station_data_stale")

    @property
    @override
    def is_on(self) -> bool:
        """Return whether station data is stale."""
        return self.coordinator.data.current.station.stale


class WeatherPlatformAirQualityDataStaleBinarySensor(
    WeatherPlatformDiagnosticBinarySensor
):
    """Indicate whether Weather Platform air-quality data is stale."""

    _attr_name = "Air quality data stale"

    def __init__(
        self,
        entry: ConfigEntry[WeatherPlatformDataUpdateCoordinator],
        coordinator: WeatherPlatformDataUpdateCoordinator,
    ) -> None:
        """Initialize the air-quality stale binary sensor."""
        super().__init__(entry, coordinator, "air_quality_data_stale")

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether air-quality guidance is stale."""
        if self.coordinator.data.air_quality is None:
            return None
        return self.coordinator.data.air_quality.stale
