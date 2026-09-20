"""Authenticated management of integration-owned event subscriptions."""

from __future__ import annotations

import asyncio
from http import HTTPStatus
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from aiohttp import ClientError

from .const import REQUEST_TIMEOUT_SECONDS

if TYPE_CHECKING:
    from aiohttp import ClientSession

SUBSCRIPTIONS_PATH = "/api/v1/integrations/home-assistant/subscriptions"


class SubscriptionError(Exception):
    """A safe, credential-free subscription failure."""

    def __init__(self, code: str) -> None:
        """Keep only a locally controlled error code."""
        super().__init__(code)
        self.code = code


def normalize_callback_origin(value: str) -> str:
    """Require an HA origin without credentials, path, query, or fragment."""
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError as err:
        msg = "invalid_callback_url"
        raise SubscriptionError(msg) from err
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or any(char.isspace() for char in value.strip())
    ):
        msg = "invalid_callback_url"
        raise SubscriptionError(msg)
    host = parsed.hostname
    if ":" in host:
        host = f"[{host}]"
    return f"{parsed.scheme}://{host}" + (f":{port}" if port is not None else "")


async def async_subscription_request(  # noqa: PLR0913 - explicit request context
    session: ClientSession,
    base_url: str,
    token: str,
    client_id: str,
    *,
    method: str = "PUT",
    station: str | None = None,
    webhook_url: str | None = None,
) -> dict[str, Any] | None:
    """Manage a subscription without redirects or sensitive exception text."""
    body = {"station": station, "webhookUrl": webhook_url} if method == "PUT" else None
    try:
        async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
            async with session.request(
                method,
                f"{base_url}{SUBSCRIPTIONS_PATH}/{client_id}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
                json=body,
                allow_redirects=False,
            ) as response:
                if response.status == HTTPStatus.UNAUTHORIZED:
                    msg = "invalid_auth"
                    raise SubscriptionError(msg)
                if response.status == HTTPStatus.CONFLICT:
                    msg = "subscription_conflict"
                    raise SubscriptionError(msg)
                if response.status == HTTPStatus.BAD_REQUEST:
                    msg = "invalid_subscription"
                    raise SubscriptionError(msg)
                if method == "DELETE" and response.status == HTTPStatus.NO_CONTENT:
                    return None
                if method == "GET" and response.status == HTTPStatus.NOT_FOUND:
                    return None
                if response.status != HTTPStatus.OK:
                    msg = "registration_unavailable"
                    raise SubscriptionError(msg)
                payload = await response.json()
    except ClientError, TimeoutError, ValueError:
        msg = "cannot_connect"
        raise SubscriptionError(msg) from None
    if not isinstance(payload, dict):
        msg = "invalid_response"
        raise SubscriptionError(msg)
    if method == "PUT" and (
        payload.get("clientId") != client_id
        or payload.get("station") != station
        or payload.get("active") is not True
        or type(payload.get("payloadSchemaVersion")) is not int
        or payload["payloadSchemaVersion"] != 1
    ):
        msg = "invalid_response"
        raise SubscriptionError(msg)
    return payload
