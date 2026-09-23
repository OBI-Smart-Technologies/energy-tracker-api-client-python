from __future__ import annotations

from obi_energy_tracker import (
    ObiEnergyTrackerAuthError,
    ObiEnergyTrackerDeviceOfflineError,
    ObiEnergyTrackerError,
)


class TestExceptionHierarchy:
    def test_auth_error_is_an_api_error(self) -> None:
        assert issubclass(ObiEnergyTrackerAuthError, ObiEnergyTrackerError)
        assert issubclass(ObiEnergyTrackerError, Exception)

    def test_device_offline_error_is_an_api_error(self) -> None:
        assert issubclass(ObiEnergyTrackerDeviceOfflineError, ObiEnergyTrackerError)
