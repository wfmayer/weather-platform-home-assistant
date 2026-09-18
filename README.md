# Weather Platform Home Assistant

Native Home Assistant custom integration for Weather Platform.

Weather Platform is the authoritative backend. This integration consumes its REST API over the local network and exposes Weather Platform data through native Home Assistant entities.

## Initial architecture

The first implementation milestone will add:

- UI config flow for the Weather Platform base URL
- Async REST API client
- DataUpdateCoordinator for shared polling and cached data
- Native Weather entity
- Sensors and Weather Platform intelligence in later passes

## Local development

This repository includes a VS Code dev container that runs an isolated Home Assistant development instance.

1. Open the repository in VS Code through WSL.
2. Choose `Dev Containers: Reopen in Container`.
3. Wait for the container setup to finish.
4. In the container terminal, run:

```bash
scripts/develop
```

5. Open Home Assistant at `http://localhost:8123` and complete the one-time onboarding flow.

The local Home Assistant runtime files under `config/` are ignored by Git except for `config/configuration.yaml`.

## Integration domain

```text
weather_platform
```
