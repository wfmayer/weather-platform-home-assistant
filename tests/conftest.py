"""Shared fixtures for Weather Platform tests."""

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations for the Home Assistant test harness."""
    del enable_custom_integrations


@pytest.fixture
def mock_setup_entry() -> Iterator[AsyncMock]:
    """Prevent config-flow tests from starting the full integration."""
    with patch(
        "custom_components.weather_platform.async_setup_entry",
        new_callable=AsyncMock,
        return_value=True,
    ) as setup_entry:
        yield setup_entry
