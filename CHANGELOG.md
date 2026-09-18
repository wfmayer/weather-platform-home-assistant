# Changelog

All notable changes to the Weather Platform Home Assistant integration are documented here.

## 0.2.0 - 2026-09-18

Expanded the integration to expose the Weather Platform API data that is useful in Home Assistant while intentionally leaving application-oriented and historical API resources out of the polling path.

### Added

- Twice-daily Home Assistant forecasts backed by Weather Platform detailed NWS forecast periods.
- Radar precipitation rate, recent two-minute accumulation, reflectivity, intensity, arrival/departure timing, projected duration, motion, and nowcast status.
- Radar precipitation-now, stale-data, and coverage-limited binary sensors.
- Derived meteorology sensors for feels-like temperature, heat index, wind chill, wet bulb, WBGT, moisture, pressure, cloud base, gust factor, and atmospheric-model/severe-weather intelligence.
- Hydrology sensors for antecedent rainfall, multi-day rainfall totals, nearby USGS gauge context, and rising gauges.
- Hydrology and atmospheric-model stale-data diagnostics.
- Synthesized Today weather-story sensor with Weather Platform sections and useful windows as attributes.
- Climate summary, anomaly, percentile, rainfall-departure, degree-day-departure, and streak sensors.
- Extended air-quality pollutant and wildfire-smoke sensors, plus minimum 24-hour AQI context.
- Richer active-alert attributes.
- Richer Weather Impact attributes including next changes, evidence, and best/concern windows.
- Stable Weather Platform event IDs and additional event context in native Home Assistant event payloads.
- Diagnostics coverage for the expanded API surface.
- Backward-compatible optional-resource discovery using the Weather Platform API index.

### Changed

- Radar parsing now consumes precipitation and nowcast data in addition to lightning and tracked storm objects.
- Optional API health tracking now includes Today, hydrology, climate, and meteorology resources.
- Weather Platform API models retain substantially more useful automation and dashboard context instead of discarding it during parsing.

## 0.1.0 - 2026-09-18

Initial release.

### Added

- UI config flow for a Weather Platform base URL.
- Shared 60-second local-polling coordinator.
- Native Home Assistant weather entity with current conditions.
- Daily and hourly forecasts.
- Rain and solar sensors.
- Air-quality sensors and stale-data diagnostics.
- Active-alert and critical-alert intelligence.
- Lightning and tracked-storm intelligence.
- Weather Platform durable event lifecycle integration.
- Weather-impact guidance sensors.
- Optional API endpoint degradation tracking and recovery logging.
- Downloadable Home Assistant diagnostics with URL redaction.
- Automated Ruff linting, pytest coverage, and GitHub Actions CI.
- HACS metadata, HACS validation, hassfest validation, and local brand assets.
- Automated tagged GitHub releases with a manual-install ZIP package.
