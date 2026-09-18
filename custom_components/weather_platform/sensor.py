"""Sensor entities for Weather Platform."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    LIGHT_LUX,
    EntityCategory,
    UnitOfIrradiance,
    UnitOfPrecipitationDepth,
    UnitOfTime,
    UnitOfVolumetricFlux,
)
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import API_UNIT_SYSTEM_METRIC, DOMAIN, NAME
from .coordinator import WeatherPlatformDataUpdateCoordinator

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import WeatherPlatformData

type SensorValue = float | int | None


@dataclass(frozen=True, kw_only=True)
class WeatherPlatformSensorEntityDescription(SensorEntityDescription):
    """Describe a Weather Platform sensor entity."""

    value_fn: Callable[[WeatherPlatformData], SensorValue]
    imperial_unit: str | None = None
    metric_unit: str | None = None


SENSOR_DESCRIPTIONS = (
    WeatherPlatformSensorEntityDescription(
        key="rain_rate",
        name="Rain rate",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=UnitOfVolumetricFlux.INCHES_PER_HOUR,
        metric_unit=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        value_fn=lambda data: data.current.conditions.rain_rate,
        suggested_display_precision=2,
    ),
    WeatherPlatformSensorEntityDescription(
        key="daily_rain",
        name="Daily rain",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        imperial_unit=UnitOfPrecipitationDepth.INCHES,
        metric_unit=UnitOfPrecipitationDepth.MILLIMETERS,
        value_fn=lambda data: data.current.conditions.daily_rain,
        suggested_display_precision=2,
    ),
    WeatherPlatformSensorEntityDescription(
        key="event_rain",
        name="Event rain",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL,
        imperial_unit=UnitOfPrecipitationDepth.INCHES,
        metric_unit=UnitOfPrecipitationDepth.MILLIMETERS,
        value_fn=lambda data: data.current.conditions.event_rain,
        suggested_display_precision=2,
    ),
    WeatherPlatformSensorEntityDescription(
        key="solar_radiation",
        name="Solar radiation",
        device_class=SensorDeviceClass.IRRADIANCE,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        metric_unit=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        value_fn=lambda data: data.current.conditions.solar_radiation,
        suggested_display_precision=0,
    ),
    WeatherPlatformSensorEntityDescription(
        key="solar_illuminance",
        name="Solar illuminance",
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_unit=LIGHT_LUX,
        metric_unit=LIGHT_LUX,
        value_fn=lambda data: data.current.conditions.solar_illuminance,
        suggested_display_precision=0,
    ),
    WeatherPlatformSensorEntityDescription(
        key="station_data_age",
        name="Station data age",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        imperial_unit=UnitOfTime.SECONDS,
        metric_unit=UnitOfTime.SECONDS,
        value_fn=lambda data: data.current.station.age_seconds,
        suggested_display_precision=0,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[WeatherPlatformDataUpdateCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add Weather Platform sensor entities."""
    del hass
    async_add_entities(
        [
            WeatherPlatformSensorEntity(
                entry,
                entry.runtime_data,
                description,
            )
            for description in SENSOR_DESCRIPTIONS
        ]
    )


class WeatherPlatformSensorEntity(
    CoordinatorEntity[WeatherPlatformDataUpdateCoordinator],
    SensorEntity,
):
    """Weather Platform sensor backed by coordinator data."""

    entity_description: WeatherPlatformSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry[WeatherPlatformDataUpdateCoordinator],
        coordinator: WeatherPlatformDataUpdateCoordinator,
        description: WeatherPlatformSensorEntityDescription,
    ) -> None:
        """Initialize a Weather Platform sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        identifier = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{identifier}:{description.key}"
        self._attr_native_unit_of_measurement = (
            description.metric_unit
            if coordinator.unit_system == API_UNIT_SYSTEM_METRIC
            else description.imperial_unit
        )

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

    @property
    @override
    def native_value(self) -> SensorValue:
        """Return the current sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
