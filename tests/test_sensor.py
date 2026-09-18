"""Tests for Weather Platform sensor descriptions."""

from custom_components.weather_platform.sensor import SENSOR_DESCRIPTIONS


def test_sensor_description_keys_are_unique() -> None:
    """Test every Weather Platform sensor has a stable unique key."""
    keys = [description.key for description in SENSOR_DESCRIPTIONS]
    assert len(keys) == len(set(keys))


def test_expanded_api_sensor_groups_are_exposed() -> None:
    """Test the expanded API surface has representative Home Assistant sensors."""
    keys = {description.key for description in SENSOR_DESCRIPTIONS}

    assert {
        "radar_precipitation_rate",
        "radar_two_minute_precipitation",
        "wet_bulb_globe_temperature",
        "cape",
        "rainfall_7_days",
        "today_weather_story",
        "climate_summary",
        "wildfire_pm10",
    } <= keys
