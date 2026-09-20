"""Constants for the Weather Platform integration."""

DOMAIN = "weather_platform"
NAME = "Weather Platform"

API_BASE_PATH = "/api/v1"
API_NAME = "Weather Platform API"
API_VERSION = "v1"
API_UNIT_SYSTEM_IMPERIAL = "imperial"
API_UNIT_SYSTEM_METRIC = "metric"

REQUEST_TIMEOUT_SECONDS = 10
UPDATE_INTERVAL_SECONDS = 60

CONF_REALTIME_ENABLED = "realtime_enabled"
CONF_INTEGRATION_TOKEN = "integration_token"  # noqa: S105 - configuration key
CONF_CALLBACK_URL = "callback_url"
CONF_WEBHOOK_ID = "webhook_id"
CONF_STATION_CODE = "station_code"
EVENT_WEATHER_PLATFORM = "weather_platform_event"
