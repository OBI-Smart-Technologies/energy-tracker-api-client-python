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

from enum import StrEnum

DEFAULT_BASE_URL = "https://energy-tracking-backend.prod-eks.dbs.obi.solutions"

UNKNOWN_VERSION = "unknown"

_VND = "application/vnd.obi.companion.energy-tracking"

CONTENT_TYPE_BRIDGE = f"{_VND}.bridge.v2+json"
CONTENT_TYPE_OUTLET = f"{_VND}.outlet.v1+json"
CONTENT_TYPE_HISTORICAL = f"{_VND}.historical-record.v1+json"
CONTENT_TYPE_HISTORICAL_MULTI = f"{_VND}.historical-record.v2+json"
CONTENT_TYPE_FIRMWARE_UPDATE = f"{_VND}.firmware-update.v1+json"
CONTENT_TYPE_FIRMWARE_UPDATE_REQUEST = f"{_VND}.firmware-update-request.v1+json"


class DeviceKind(StrEnum):
    SENSOR = "sensor"
    OUTLET = "outlet"


class OutletState(StrEnum):
    ON = "on"
    OFF = "off"


class Measure(StrEnum):
    ENERGY = "energy"
    NEGATIVE_ENERGY = "negative_energy"
    RSSI = "rssi"
    BATTERY = "battery"


class OtaStatus(StrEnum):
    IDLE = "idle"
    STARTED = "started"
    DOWNLOADING = "downloading"
    INSTALLING = "installing"
    COMPLETE = "complete"
    FAILED = "failed"


class ConnectionStrength(StrEnum):
    BAD = "bad"
    FAIR = "fair"
    GOOD = "good"
    EXCELLENT = "excellent"
