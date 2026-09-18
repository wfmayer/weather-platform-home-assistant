"""Config flow for Weather Platform."""

from __future__ import annotations

import logging
from typing import Any, override

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    WeatherPlatformApiClient,
    WeatherPlatformConnectionError,
    WeatherPlatformInvalidResponseError,
    WeatherPlatformInvalidUrlError,
    normalize_base_url,
)
from .const import DOMAIN, NAME

_LOGGER = logging.getLogger(__name__)


class WeatherPlatformConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Weather Platform."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle setup initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                base_url = normalize_base_url(user_input[CONF_URL])
            except WeatherPlatformInvalidUrlError:
                errors["base"] = "invalid_url"
            else:
                await self.async_set_unique_id(base_url)
                self._abort_if_unique_id_configured()

                client = WeatherPlatformApiClient(
                    base_url=base_url,
                    session=async_get_clientsession(self.hass),
                )

                try:
                    metadata = await client.async_get_metadata()
                except WeatherPlatformConnectionError:
                    errors["base"] = "cannot_connect"
                except WeatherPlatformInvalidResponseError:
                    errors["base"] = "invalid_response"
                except Exception:
                    _LOGGER.exception(
                        "Unexpected error while validating Weather Platform"
                    )
                    errors["base"] = "unknown"
                else:
                    return self.async_create_entry(
                        title=NAME,
                        data={CONF_URL: base_url},
                        description_placeholders={
                            "platform_version": metadata.platform_version
                        },
                    )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_URL,
                    default=(user_input or {}).get(CONF_URL, ""),
                ): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
