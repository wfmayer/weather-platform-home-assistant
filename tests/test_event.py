"""Tests for Weather Platform event entities."""

from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

from custom_components.weather_platform.api import (
    WeatherPlatformEvent,
    WeatherPlatformEventsData,
)
from custom_components.weather_platform.event import WeatherPlatformWeatherEventEntity

DETECTED_AT = "2026-09-18T21:00:00Z"


def _event(
    event_type: str = "LIGHTNING",
    *,
    phase: str = "ACTIVE",
    priority: str = "NORMAL",
    detected_at: str = DETECTED_AT,
) -> WeatherPlatformEvent:
    """Build a Weather Platform event for lifecycle tests."""
    return WeatherPlatformEvent(
        event_type=event_type,
        type_label=event_type.replace("_", " ").title(),
        phase=phase,
        phase_label=phase.title(),
        priority=priority,
        priority_label=priority.title(),
        trigger_source="test",
        detected_at=detected_at,
    )


def _events(*events: WeatherPlatformEvent) -> WeatherPlatformEventsData:
    """Build an active-event response."""
    return WeatherPlatformEventsData(
        generated_at="2026-09-18T21:01:00Z",
        count=len(events),
        events=events,
    )


def _entity(
    initial_events: WeatherPlatformEventsData | None,
) -> tuple[WeatherPlatformWeatherEventEntity, MagicMock]:
    """Build an event entity and lightweight coordinator."""
    entry = MagicMock()
    entry.unique_id = "weather-platform-test"
    entry.entry_id = "entry-test"

    coordinator = MagicMock()
    coordinator.data = SimpleNamespace(events=initial_events)
    coordinator.metadata = None
    coordinator.client.base_url = "http://weather-platform.local"
    coordinator.last_update_success = True

    entity = WeatherPlatformWeatherEventEntity(entry, coordinator)
    entity.async_write_ha_state = Mock()
    entity._emit_event = Mock()
    return entity, coordinator


def test_new_active_event_emits_started() -> None:
    """Test a newly active event emits a started lifecycle change."""
    entity, coordinator = _entity(_events())
    lightning = _event()
    coordinator.data = SimpleNamespace(events=_events(lightning))

    entity._handle_coordinator_update()

    entity._emit_event.assert_called_once_with(lightning, "started")


def test_event_change_emits_updated() -> None:
    """Test phase or priority changes emit an updated lifecycle change."""
    previous = _event(phase="DEVELOPING", priority="NORMAL")
    entity, coordinator = _entity(_events(previous))
    updated = _event(phase="ACTIVE", priority="HIGH")
    coordinator.data = SimpleNamespace(events=_events(updated))

    entity._handle_coordinator_update()

    entity._emit_event.assert_called_once_with(updated, "updated", previous)


def test_disappearing_active_event_emits_ended() -> None:
    """Test an event missing from a successful active-event poll emits ended."""
    lightning = _event()
    entity, coordinator = _entity(_events(lightning))
    coordinator.data = SimpleNamespace(events=_events())

    entity._handle_coordinator_update()

    entity._emit_event.assert_called_once_with(lightning, "ended")


def test_endpoint_outage_resyncs_without_replay() -> None:
    """Test recovery from an event endpoint outage silently resynchronizes."""
    lightning = _event()
    entity, coordinator = _entity(_events(lightning))

    coordinator.data = SimpleNamespace(events=None)
    entity._handle_coordinator_update()
    entity._emit_event.assert_not_called()

    pressure = _event(
        "PRESSURE_FALL",
        detected_at="2026-09-18T21:05:00Z",
    )
    coordinator.data = SimpleNamespace(events=_events(lightning, pressure))
    entity._handle_coordinator_update()
    entity._emit_event.assert_not_called()

    rain = _event("RAIN", detected_at="2026-09-18T21:10:00Z")
    coordinator.data = SimpleNamespace(events=_events(lightning, pressure, rain))
    entity._handle_coordinator_update()
    entity._emit_event.assert_called_once_with(rain, "started")
