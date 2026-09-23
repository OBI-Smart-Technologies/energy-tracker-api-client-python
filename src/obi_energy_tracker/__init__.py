# Copyright 2026 OBI Smart Technologies GmbH
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

from .aggregation import HourlyBucket, cumulative, hourly_buckets, to_series
from .auth import TokenProvider, static_token_provider
from .client import ObiEnergyTrackerApi
from .const import (
    DEFAULT_BASE_URL,
    UNKNOWN_VERSION,
    ConnectionStrength,
    DeviceKind,
    Measure,
    OtaStatus,
    OutletState,
)
from .exceptions import (
    ObiEnergyTrackerAuthError,
    ObiEnergyTrackerDeviceOfflineError,
    ObiEnergyTrackerError,
)
from .models import Bridge, Device, DeviceMeasures, FirmwareUpdate, MeasureRecord
from .parser import connection_strength_from_rssi

__all__ = [
    "DEFAULT_BASE_URL",
    "UNKNOWN_VERSION",
    "Bridge",
    "ConnectionStrength",
    "Device",
    "DeviceKind",
    "DeviceMeasures",
    "FirmwareUpdate",
    "HourlyBucket",
    "Measure",
    "MeasureRecord",
    "ObiEnergyTrackerApi",
    "ObiEnergyTrackerAuthError",
    "ObiEnergyTrackerDeviceOfflineError",
    "ObiEnergyTrackerError",
    "OtaStatus",
    "OutletState",
    "TokenProvider",
    "connection_strength_from_rssi",
    "cumulative",
    "hourly_buckets",
    "static_token_provider",
    "to_series",
]
