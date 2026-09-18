"""Async REST client for Weather Platform."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from aiohttp import ClientError, ClientSession

from .const import API_BASE_PATH, API_NAME, API_VERSION, REQUEST_TIMEOUT_SECONDS


class WeatherPlatformApiError(Exception):
    """Base exception for Weather Platform API errors."""


class WeatherPlatformConnectionError(WeatherPlatformApiError):
    """Raised when Weather Platform cannot be reached."""


class WeatherPlatformInvalidResponseError(WeatherPlatformApiError):
    """Raised when Weather Platform returns an unexpected response."""


class WeatherPlatformInvalidUrlError(WeatherPlatformApiError):
    """Raised when a Weather Platform base URL is invalid."""


@dataclass(frozen=True, slots=True)
class WeatherPlatformMetadata:
    """Weather Platform API metadata."""

    name: str
    api_version: str
    platform_version: str
    resources: dict[str, str]


def normalize_base_url(value: str) -> str:
    """Normalize a Weather Platform application base URL."""
    candidate = value.strip()
    parsed = urlsplit(candidate)

    if (
        parsed.scheme.lower() not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise WeatherPlatformInvalidUrlError

    path = parsed.path.rstrip("/").removesuffix(API_BASE_PATH).rstrip("/")

    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc,
            path,
            "",
            "",
        )
    ).rstrip("/")


class WeatherPlatformApiClient:
    """Async client for the Weather Platform REST API."""

    def __init__(self, base_url: str, session: ClientSession) -> None:
        """Initialize the client."""
        self._base_url = normalize_base_url(base_url)
        self._api_base_url = f"{self._base_url}{API_BASE_PATH}"
        self._session = session

    @property
    def base_url(self) -> str:
        """Return the normalized application base URL."""
        return self._base_url

    async def async_get_metadata(self) -> WeatherPlatformMetadata:
        """Fetch and validate Weather Platform API metadata."""
        payload = await self._async_get_json("")

        name = payload.get("name")
        api_version = payload.get("apiVersion")
        platform_version = payload.get("platformVersion")
        resources_value = payload.get("resources")

        if (
            name != API_NAME
            or api_version != API_VERSION
            or not isinstance(platform_version, str)
            or not isinstance(resources_value, dict)
        ):
            raise WeatherPlatformInvalidResponseError

        resources = {
            key: value
            for key, value in resources_value.items()
            if isinstance(key, str) and isinstance(value, str)
        }

        if "current" not in resources or "forecast" not in resources:
            raise WeatherPlatformInvalidResponseError

        return WeatherPlatformMetadata(
            name=name,
            api_version=api_version,
            platform_version=platform_version,
            resources=resources,
        )

    async def _async_get_json(self, resource: str) -> dict[str, Any]:
        """Fetch a JSON object from the Weather Platform API."""
        url = self._api_base_url
        if resource:
            url = f"{url}/{resource.lstrip('/')}"

        try:
            async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
                async with self._session.get(
                    url,
                    headers={"Accept": "application/json"},
                ) as response:
                    response.raise_for_status()
                    payload = await response.json(content_type=None)
        except TimeoutError as err:
            raise WeatherPlatformConnectionError from err
        except ClientError as err:
            raise WeatherPlatformConnectionError from err
        except ValueError as err:
            raise WeatherPlatformInvalidResponseError from err

        if not isinstance(payload, dict):
            raise WeatherPlatformInvalidResponseError

        return payload
