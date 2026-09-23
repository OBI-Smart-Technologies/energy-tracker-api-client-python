# obi-energy-tracker

[![PyPI version](https://img.shields.io/pypi/v/obi-energy-tracker.svg)](https://pypi.org/project/obi-energy-tracker/)
[![Python versions](https://img.shields.io/pypi/pyversions/obi-energy-tracker.svg)](https://pypi.org/project/obi-energy-tracker/)
[![CI](https://github.com/OBI-Smart-Technologies/energy-tracker-api-client-python/actions/workflows/ci.yml/badge.svg)](https://github.com/OBI-Smart-Technologies/energy-tracker-api-client-python/actions/workflows/ci.yml)

Async Python client for the **OBI ENERGY TRACKER** cloud API — the electricity meter
sensor, the smart outlet and the bridge that connects them.

The library is the API layer behind the OBI ENERGY TRACKER Home Assistant integration,
but it has no Home Assistant dependency and can be used on its own.

## What it does

| Capability | Function |
|---|---|
| List the account topology | `async_get_bridges()` — bridges with their sensors and outlets |
| Read recent measurements | `async_get_bridge_measures()` — energy, feed-in, RSSI, battery per device |
| Read the full history of every device | `async_get_bridge_measures()` without `duration` |
| Read the full meter history of one device | `async_get_meter_readings()` — every reading the cloud has kept |
| Switch an outlet | `async_set_outlet_state()` |
| Check bridge firmware | `async_get_bridge_firmware_update()` |
| Start a bridge firmware update | `async_trigger_bridge_firmware_update()` |
| Reproduce the OBI app's hourly/daily figures | `hourly_buckets()`, `cumulative()` |

Everything is `async`, typed (`py.typed`) and built on a caller-supplied
`aiohttp.ClientSession`, so the library never owns a session and never blocks the event
loop.

## Installation

```bash
pip install obi-energy-tracker
```

## Usage

The API is protected by OAuth2 (Keycloak). The library does not implement the
authorization flow: it takes a `TokenProvider`, an awaitable that returns a valid access
token, and calls it before *every* request. That way token refreshing stays with whoever
owns the OAuth session.

```python
import asyncio

import aiohttp
from obi_energy_tracker import (
    Measure,
    ObiEnergyTrackerApi,
    OutletState,
    static_token_provider,
)


async def main() -> None:
    async with aiohttp.ClientSession() as session:
        api = ObiEnergyTrackerApi(
            session=session,
            token_provider=static_token_provider("<access-token>"),
        )

        for bridge in await api.async_get_bridges():
            print(bridge.display_name, bridge.firmware_version)

            measures = await api.async_get_bridge_measures(
                bridge.id,
                measures=[Measure.ENERGY, Measure.BATTERY],
                duration="PT6H",
            )
            for device in bridge.devices:
                readings = measures.get(device.id, {})
                energy = readings.get(Measure.ENERGY)
                if energy:
                    print(f"  {device.display_name}: {energy[-1].value} Wh")

            for outlet in bridge.outlets:
                await api.async_set_outlet_state(outlet.id, OutletState.ON)


asyncio.run(main())
```

For a long-lived session, pass your own provider instead of `static_token_provider`:

```python
async def token_provider() -> str:
    await oauth_session.ensure_valid()
    return oauth_session.access_token

api = ObiEnergyTrackerApi(session=session, token_provider=token_provider)
```

### Hourly and daily consumption

Called without a `duration`, `async_get_bridge_measures()` returns the raw meter readings
of every device of a bridge (cumulative watt-hours, one every 300 seconds) in a single
request. `aggregation` turns them into the hourly buckets the OBI app shows:

```python
from zoneinfo import ZoneInfo

from obi_energy_tracker import Measure, cumulative, hourly_buckets

history = await api.async_get_bridge_measures(bridge.id, [Measure.ENERGY])
for device in bridge.devices:
    readings = history.get(device.id, {}).get(Measure.ENERGY, [])
    for bucket, total in cumulative(
        hourly_buckets(readings, ZoneInfo("Europe/Berlin"))
    ):
        print(device.display_name, bucket.start, bucket.consumption, total)
```

`async_get_meter_readings()` does the same for a single device. Prefer it when a device
may have no `dataVisibleSince` in the cloud: the multi-device route drops such a device's
readings, while the per-device route returns them.

Two properties of that arithmetic are deliberate, because it reproduces the **app**, not
the physical meter:

- Day boundaries come from the time zone you pass in. Pass the zone the meter lives in;
  with UTC the daily figures will not match the app.
- The first increment of each local day is skipped, exactly as the app does, so
  cumulative totals grow roughly 0.5 % slower than the meter's own reading.

### Errors

All failures raise `ObiEnergyTrackerError` or one of its subclasses, so a single
`except ObiEnergyTrackerError` is enough to catch everything the library raises:

| Exception | Raised when |
|---|---|
| `ObiEnergyTrackerAuthError` | HTTP 401/403 — the token was rejected |
| `ObiEnergyTrackerDeviceOfflineError` | HTTP 504 on an outlet write — the bridge could not reach the outlet |
| `ObiEnergyTrackerError` | everything else: connection errors, timeouts, rate limiting (429), unexpected payloads |

Unknown enum values (a new `otaStatus`, `state` or `measure`) parse
to `None` or are dropped rather than escaping as raw strings, so a backend addition cannot
break a consumer.

### Timeouts

Every request carries an explicit total timeout: 30 s for normal calls and 120 s for the
two that fetch a whole history — `async_get_meter_readings()` and
`async_get_bridge_measures()` without a `duration`. Do not rely on the session's timeout —
a shared session may have a far coarser one.

## Development

```bash
python3.14 -m venv .venv
.venv/bin/pip install -e ".[dev]"

.venv/bin/python -m pytest
.venv/bin/ruff check src tests
.venv/bin/ruff format src tests
.venv/bin/mypy
```

## Contributing

Bug reports, feature requests and pull requests are welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md) for the checks that have to pass, the versioning rules
and how a release is cut. Participation is subject to the
[Code of Conduct](CODE_OF_CONDUCT.md). For security reports see [SECURITY.md](SECURITY.md);
please do not open a public issue for those.

The Home Assistant integration is the primary consumer and pins this package exactly, so a
change to the public surface is always a coordinated change in both repositories.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

Licensed under the [Apache License, Version 2.0](LICENSE).

Copyright 2026 OBI Smart Technologies GmbH.
