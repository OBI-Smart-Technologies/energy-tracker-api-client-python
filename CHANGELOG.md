# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

1.0.0 is not published yet; releasing renames this heading to `## 1.0.0 - YYYY-MM-DD`.

First public release. Extracted from the OBI ENERGY TRACKER Home Assistant integration,
where this code ran as an in-tree module.

### Added

- `ObiEnergyTrackerApi` — async REST client for the OBI ENERGY TRACKER cloud with one
  method per endpoint: `async_get_bridges`, `async_get_bridge_measures`,
  `async_get_meter_readings`, `async_set_outlet_state`,
  `async_get_bridge_firmware_update`, `async_trigger_bridge_firmware_update`.
  `async_get_bridge_measures` covers both windows: with a `duration` the recent values of
  every device, without one their complete history in a single request.
- `Bridge`, `Device`, `MeasureRecord` and `FirmwareUpdate` payload models, plus the
  `DeviceKind`, `OutletState`, `Measure`, `OtaStatus` and `ConnectionStrength` enums.
- `ObiEnergyTrackerError` with the `ObiEnergyTrackerAuthError` and
  `ObiEnergyTrackerDeviceOfflineError` subclasses.
- `TokenProvider` and `static_token_provider` — authentication is awaited before every
  request, so the caller keeps ownership of the OAuth2 session.
- `connection_strength_from_rssi` — the backend's own RSSI thresholds.
- `hourly_buckets` and `cumulative` — hourly and cumulative consumption.
