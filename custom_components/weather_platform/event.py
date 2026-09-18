"""Event entities for Weather Platform."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from homeassistant.components.event import EventEntity
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import WeatherPlatformDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .api import WeatherPlatformEvent

WEATHER_EVENT_TYPES = [
    "rain",
    "nws_alert",
    "lightning",
    "wind",
    "heavy_rain",
    "heat_stress",
    "frost_freeze",
    "pressure_fall",
    "air_quality",
    "hydrology",
    "radar_storm",
    "other",
]

type EventKey = int | tuple[str, str | None]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[WeatherPlatformDataUpdateCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the Weather Platform event entity."""
    del hass
    async_add_entities(
        [
            WeatherPlatformWeatherEventEntity(
                entry,
                entry.runtime_data,
            )
        ]
    )


class WeatherPlatformWeatherEventEntity(
    CoordinatorEntity[WeatherPlatformDataUpdateCoordinator],
    EventEntity,
):
    """Expose Weather Platform weather-event lifecycle changes."""

    _attr_event_types = WEATHER_EVENT_TYPES
    _attr_has_entity_name = True
    _attr_name = "Weather events"

    def __init__(
        self,
        entry: ConfigEntry[WeatherPlatformDataUpdateCoordinator],
        coordinator: WeatherPlatformDataUpdateCoordinator,
    ) -> None:
        """Initialize the Weather Platform event entity."""
        super().__init__(coordinator)

        identifier = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{identifier}:weather_events"

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

        events = coordinator.data.events
        self._events_available = events is not None
        self._known_events = (
            {}
            if events is None
            else {_event_key(event): event for event in events.events}
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether Weather Platform weather events are available."""
        return super().available and self.coordinator.data.events is not None

    @override
    def _handle_coordinator_update(self) -> None:
        """Emit new Weather Platform event lifecycle changes."""
        events = self.coordinator.data.events

        if not self.coordinator.last_update_success or events is None:
            self._events_available = False
            super()._handle_coordinator_update()
            return

        current_events = {_event_key(event): event for event in events.events}

        if not self._events_available:
            self._known_events = current_events
            self._events_available = True
            super()._handle_coordinator_update()
            return

        event_emitted = False

        for key, previous in self._known_events.items():
            if key in current_events:
                continue

            self._emit_event(previous, "ended")
            event_emitted = True

        for key, event in current_events.items():
            previous = self._known_events.get(key)

            if previous is None:
                self._emit_event(event, "started")
                event_emitted = True
                continue

            if event.phase != previous.phase or event.priority != previous.priority:
                self._emit_event(event, "updated", previous)
                event_emitted = True

        self._known_events = current_events

        if not event_emitted:
            super()._handle_coordinator_update()

    def _emit_event(
        self,
        event: WeatherPlatformEvent,
        change: str,
        previous: WeatherPlatformEvent | None = None,
    ) -> None:
        """Emit one native Home Assistant event-entity update."""
        raw_event_type = event.event_type.lower()
        event_type = (
            raw_event_type if raw_event_type in WEATHER_EVENT_TYPES else "other"
        )

        attributes = _event_attributes(event, change, previous)
        self._trigger_event(event_type, attributes)
        self.async_write_ha_state()


def _event_key(event: WeatherPlatformEvent) -> EventKey:
    """Return the stable identity for one active Weather Platform event."""
    if event.event_id is not None:
        return event.event_id
    return event.event_type, event.detected_at


def _event_attributes(
    event: WeatherPlatformEvent,
    change: str,
    previous: WeatherPlatformEvent | None,
) -> dict[str, str | int]:
    """Build native Home Assistant event attributes."""
    attributes: dict[str, str | int] = {
        "change": change,
        "weather_platform_type": event.event_type,
        "priority": event.priority,
    }

    optional_attributes: dict[str, str | int | None] = {
        "event_id": event.event_id,
        "station_code": event.station_code,
        "type_label": event.type_label,
        "category": event.category,
        "state": event.state,
        "state_label": event.state_label,
        "phase": event.phase,
        "phase_label": event.phase_label,
        "priority_label": event.priority_label,
        "trigger_source": event.trigger_source,
        "detected_at": event.detected_at,
        "last_evidence_at": event.last_evidence_at,
        "resolved_at": event.resolved_at,
    }
    attributes.update(
        {key: value for key, value in optional_attributes.items() if value is not None}
    )

    if previous is not None:
        if previous.phase != event.phase and previous.phase is not None:
            attributes["previous_phase"] = previous.phase
        if previous.priority != event.priority:
            attributes["previous_priority"] = previous.priority

    return attributes
