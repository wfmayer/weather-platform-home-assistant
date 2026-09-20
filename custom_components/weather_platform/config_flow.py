"""Config flow for Weather Platform."""

from __future__ import annotations

import logging
from typing import Any, override

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_URL
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    WeatherPlatformApiClient,
    WeatherPlatformConnectionError,
    WeatherPlatformInvalidResponseError,
    WeatherPlatformInvalidUrlError,
    normalize_base_url,
)
from .const import (
    CONF_CALLBACK_URL,
    CONF_INTEGRATION_TOKEN,
    CONF_REALTIME_ENABLED,
    CONF_WEBHOOK_ID,
    DOMAIN,
    NAME,
)
from .subscription import (
    SubscriptionError,
    async_subscription_request,
    normalize_callback_origin,
)

_LOGGER = logging.getLogger(__name__)
MIN_TOKEN_LENGTH = 32


class WeatherPlatformConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Weather Platform."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> WeatherPlatformOptionsFlow:
        """Configure realtime delivery on existing and newly added entries."""
        del config_entry
        return WeatherPlatformOptionsFlow()

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


class WeatherPlatformOptionsFlow(OptionsFlow):
    """Configure and explicitly deactivate managed event delivery."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the registration token and platform-reachable HA origin."""
        errors: dict[str, str] = {}
        current = self.config_entry.options
        if user_input is not None:
            enabled = user_input[CONF_REALTIME_ENABLED]
            token = user_input.get(CONF_INTEGRATION_TOKEN, "").strip() or current.get(
                CONF_INTEGRATION_TOKEN, ""
            )
            origin = user_input.get(CONF_CALLBACK_URL, "").strip()
            try:
                if enabled:
                    if len(token) < MIN_TOKEN_LENGTH:
                        msg = "invalid_auth"
                        raise SubscriptionError(msg)  # noqa: TRY301 - shared form error handler
                    origin = normalize_callback_origin(origin)
                    client = WeatherPlatformApiClient(
                        self.config_entry.data[CONF_URL],
                        async_get_clientsession(self.hass),
                    )
                    metadata = await client.async_get_metadata()
                    if "homeAssistantSubscriptions" not in metadata.resources:
                        msg = "unsupported_realtime"
                        raise SubscriptionError(msg)  # noqa: TRY301 - shared form error handler
                    # Read-only validation: saving the form never claims a station
                    # before the real receiver and event entities are loaded.
                    await async_subscription_request(
                        async_get_clientsession(self.hass),
                        client.base_url,
                        token,
                        self.config_entry.entry_id,
                        method="GET",
                    )
                elif CONF_WEBHOOK_ID in self.config_entry.data:
                    coordinator = getattr(self.config_entry, "runtime_data", None)
                    realtime = getattr(coordinator, "realtime", None)
                    if realtime is not None:
                        await realtime.async_deactivate(token)
                    else:
                        await async_subscription_request(
                            async_get_clientsession(self.hass),
                            self.config_entry.data[CONF_URL],
                            token,
                            self.config_entry.entry_id,
                            method="DELETE",
                        )
            except SubscriptionError as err:
                errors["base"] = err.code
            except WeatherPlatformConnectionError:
                errors["base"] = "cannot_connect"
            except WeatherPlatformInvalidResponseError:
                errors["base"] = "invalid_response"
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_REALTIME_ENABLED: enabled,
                        CONF_INTEGRATION_TOKEN: token,
                        CONF_CALLBACK_URL: origin,
                    },
                )
        values = user_input if user_input is not None else current
        return self.async_show_form(
            step_id="init",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_REALTIME_ENABLED,
                        default=values.get(CONF_REALTIME_ENABLED, False),
                    ): bool,
                    vol.Optional(CONF_INTEGRATION_TOKEN): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                    vol.Optional(
                        CONF_CALLBACK_URL,
                        default=values.get(CONF_CALLBACK_URL, ""),
                    ): str,
                }
            ),
        )
