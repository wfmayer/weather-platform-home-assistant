# Weather Platform Home Assistant

![Weather Platform icon](custom_components/weather_platform/brand/icon.png)

Native Home Assistant custom integration for Weather Platform.

Weather Platform remains the authoritative weather backend. This integration
polls its REST API and exposes the resulting data through native Home Assistant
weather, sensor, binary sensor, and event entities.

## Status

The integration is actively developed and currently targets Home Assistant
2026.9.x. Development and CI are tested against Home Assistant 2026.9.2.

Current capabilities include:

- UI-based configuration through Home Assistant
- Local polling through the Weather Platform REST API
- Native Home Assistant weather entity
- Current observed conditions
- Hourly and daily forecasts
- Rain and solar measurements
- Air-quality guidance
- Weather alert intelligence
- Lightning and tracked-storm intelligence
- Durable Weather Platform event lifecycle updates
- Weather-impact guidance
- Diagnostic entities and downloadable Home Assistant diagnostics
- Graceful degradation when optional Weather Platform API resources are
  temporarily unavailable

## Requirements

You need a reachable Weather Platform instance with the v1 REST API enabled.
Home Assistant must be able to connect to the Weather Platform application base
URL directly.

For example:

```text
http://192.168.1.50:8080
```

Enter the application base URL only. Do not append `/api/v1`; the integration
adds the API path itself.

## Installation

### HACS

The repository is HACS-ready, but HACS requires repositories to be public.
While this repository remains private, use the manual installation method
below.

When the repository is public:

1. Open HACS in Home Assistant.
2. Open the HACS menu and choose **Custom repositories**.
3. Add `https://github.com/wfmayer/weather-platform-home-assistant`.
4. Select **Integration** as the repository type.
5. Install **Weather Platform**.
6. Restart Home Assistant if requested.
7. Open **Settings > Devices & services** and add **Weather Platform**.

Published GitHub releases are exposed to HACS as selectable versions. The
integration declares Home Assistant 2026.9.2 as its minimum supported version
in `hacs.json`.

### Manual installation from a release

Each tagged release publishes `weather-platform-home-assistant.zip`. The archive
contains the `custom_components/weather_platform` path, so it can be extracted
directly into the Home Assistant configuration directory.

1. Download the ZIP from the GitHub release.
2. Extract it into the Home Assistant configuration directory.
3. Confirm that `custom_components/weather_platform/manifest.json` exists.
4. Restart Home Assistant.
5. Open **Settings > Devices & services**.
6. Choose **Add Integration**.
7. Search for **Weather Platform**.
8. Enter the base URL of the Weather Platform instance.

The config flow validates that the server identifies itself as the supported
Weather Platform v1 API before creating the entry.

### Manual installation from source

For development builds, copy `custom_components/weather_platform` from the
repository into the Home Assistant `custom_components` directory and restart
Home Assistant.

## How it works

The integration uses one shared `DataUpdateCoordinator` with a 60-second update
interval.

Current conditions and forecast data are required. If either required request
fails, Home Assistant marks coordinator-backed entities unavailable until the
next successful refresh.

The following resources are optional and are allowed to fail independently:

- Air quality
- Alerts
- Radar intelligence
- Durable weather events
- Weather-impact guidance

An optional-resource failure does not stop current conditions or forecasts from
updating. The diagnostic **Optional API data unavailable** binary sensor reports
partial API degradation and identifies the unavailable resources.

## Units

When the config entry is loaded, the integration requests Weather Platform data
using the Home Assistant system unit configuration:

- Imperial Home Assistant systems request Weather Platform imperial values.
- Metric Home Assistant systems request Weather Platform metric values.

Home Assistant native unit metadata is also applied to the exposed entities.
Reload the integration after changing the Home Assistant system unit setting so
the coordinator is recreated with the new Weather Platform API unit system.

## Weather entity

The native weather entity exposes observed Weather Platform conditions,
including available values for:

- Condition
- Temperature
- Dew point
- Relative humidity
- Station pressure
- Wind speed
- Wind gust
- Wind bearing
- UV index

It also provides Home Assistant daily and hourly forecasts. Current condition
values come directly from Weather Platform. Forecast text is mapped to Home
Assistant weather-condition values for forecast presentation.

The Weather Platform weather entity can be selected anywhere Home Assistant
accepts a weather entity, including dashboards and weather-based automations.

## Sensors

Weather Platform exposes additional data as native Home Assistant sensors.
Availability depends on which Weather Platform resources currently contain
data.

### Observation and station data

- Rain rate
- Daily rain
- Event rain
- Solar radiation
- Solar illuminance
- Station data age

### Air quality

- Air quality index
- Air quality category
- Air quality guidance
- PM2.5
- PM10
- Ozone
- Peak air quality index for the next 24 hours

### Alerts

- Active weather alerts
- Critical weather alerts
- Highest weather alert level

### Lightning and storm tracking

- Lightning strikes in the recent window
- Lightning strike rate
- Nearest lightning distance
- Lightning activity trend
- Lightning rate trend
- Tracked storms
- Approaching tracked storms
- Nearest tracked storm distance
- Strongest tracked storm reflectivity

### Weather Platform events

- Active Weather Platform events
- Highest event priority
- Latest active event
- Latest active event phase

### Weather impacts

- Impact forecast
- Outdoor activity impact
- Open windows impact
- Yard work impact
- Drying conditions impact
- Frost risk impact
- Sun exposure impact

## Binary sensors

The integration currently exposes:

- **Station data stale** - Weather Platform considers the current station
  observation stale.
- **Air quality data stale** - the current air-quality data is stale.
- **Optional API data unavailable** - one or more optional Weather Platform API
  resources failed during the latest coordinator refresh.
- **Critical weather alert** - at least one critical alert is active.
- **Tracked storm approaching home** - Weather Platform storm tracking reports
  at least one object approaching the configured home location.

## Native weather events

Weather Platform durable weather events are exposed through the native
**Weather events** event entity.

Known Weather Platform weather-event types are emitted as Home Assistant event
types, including rain, NWS alerts, lightning, wind, heavy rain, heat stress,
frost or freeze, pressure fall, air quality, hydrology, and radar storm events.
Unknown future Weather Platform weather-event types fall back to `other`.

Each event includes lifecycle context in its attributes. The `change` attribute
is one of:

- `started`
- `updated`
- `ended`

Updates can also include Weather Platform phase, priority, labels, trigger
source, detection time, and previous phase or priority when applicable.

Events that were already active when Home Assistant starts are used to seed the
integration state and are not replayed as new events. If the optional events
endpoint temporarily becomes unavailable, the integration resynchronizes when
it returns instead of generating synthetic lifecycle changes for the outage.

## Diagnostics and resilience

Home Assistant diagnostics are supported for the config entry. The diagnostics
payload includes API/platform version information, endpoint health, data
freshness, resource availability, forecast counts, radar status, event types,
and impact-profile state.

The configured Weather Platform URL is redacted from the downloadable
diagnostics payload.

For quick health checks, inspect the diagnostic entities:

- Station data stale
- Air quality data stale
- Optional API data unavailable
- Station data age

## Local development

The repository includes a VS Code dev container with Python 3.14 and a local
Home Assistant development environment.

1. Open the repository in VS Code.
2. Reopen it in the dev container.
3. Wait for `scripts/setup` to finish installing dependencies.
4. Start Home Assistant:

```bash
scripts/develop
```

5. Open Home Assistant at `http://localhost:8123` and complete onboarding if
   needed.

The local Home Assistant runtime under `config/` is ignored by Git except for
tracked development configuration files.

## Quality checks

Run the same checks used by CI before pushing changes:

```bash
scripts/lint
scripts/test
```

`scripts/lint` runs Ruff linting and formatting checks. `scripts/test` runs the
pytest Home Assistant custom-component test suite.

GitHub Actions runs both commands automatically for pushes to `main` and pull
requests targeting `main`.

A separate validation workflow runs both hassfest and the HACS repository
validator.

## Releases

The integration version is defined in
`custom_components/weather_platform/manifest.json`.

To publish a release:

1. Update the manifest version and changelog.
2. Commit and push the release changes.
3. Create a matching `v`-prefixed tag.
4. Push the tag.

For example, for manifest version `0.1.0`:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The release workflow verifies that the tag matches the manifest version, runs
lint and tests, creates the manual-install ZIP, and publishes the GitHub release
with generated release notes.

## Repository layout

```text
custom_components/weather_platform/  Home Assistant integration
custom_components/weather_platform/brand/  Local Home Assistant brand assets
scripts/                             Development, lint, and test helpers
tests/                               Automated integration tests
.github/workflows/ci.yml             GitHub Actions quality checks
.github/workflows/validate.yml       HACS and hassfest validation
.github/workflows/release.yml        Tagged release publishing
hacs.json                            HACS repository metadata
CHANGELOG.md                         Release history
```

## Integration domain

```text
weather_platform
```
