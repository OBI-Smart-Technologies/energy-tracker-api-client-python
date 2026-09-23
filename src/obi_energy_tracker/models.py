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

from dataclasses import dataclass, field
from datetime import datetime

from .const import (
    UNKNOWN_VERSION,
    DeviceKind,
    Measure,
    OtaStatus,
    OutletState,
)


@dataclass
class Device:
    id: str
    bridge_id: str
    kind: DeviceKind
    display_name: str
    firmware_version: str = UNKNOWN_VERSION
    hardware_version: str = UNKNOWN_VERSION
    is_online: bool = False
    battery_level: int | None = None
    state: OutletState | None = None

    @property
    def is_outlet(self) -> bool:
        return self.kind is DeviceKind.OUTLET


@dataclass
class FirmwareUpdate:
    id: str
    version: str
    change_log: str | None = None


@dataclass
class Bridge:
    id: str
    display_name: str
    firmware_version: str = UNKNOWN_VERSION
    hardware_version: str = UNKNOWN_VERSION
    ota_status: OtaStatus | None = None
    ota_progress: int | None = None
    sensors: list[Device] = field(default_factory=list)
    outlets: list[Device] = field(default_factory=list)

    @property
    def devices(self) -> list[Device]:
        return [*self.sensors, *self.outlets]


@dataclass
class MeasureRecord:
    time: datetime
    value: float
    measure: Measure


type DeviceMeasures = dict[str, dict[Measure, list[MeasureRecord]]]
