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

import logging
from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Any

from .const import (
    UNKNOWN_VERSION,
    ConnectionStrength,
    DeviceKind,
    Measure,
    OtaStatus,
    OutletState,
)
from .models import Bridge, Device, FirmwareUpdate, MeasureRecord

_LOGGER = logging.getLogger(__name__)

OTA_STATUSES: Mapping[str, OtaStatus] = {
    "NOT_UPDATING": OtaStatus.IDLE,
    "BRIDGE_UPDATE_STARTED": OtaStatus.STARTED,
    "FIRMWARE_DOWNLOAD_STARTED": OtaStatus.DOWNLOADING,
    "BRIDGE_UPDATE_INSTALLING": OtaStatus.INSTALLING,
    "BRIDGE_UPDATE_COMPLETE": OtaStatus.COMPLETE,
    "BRIDGE_UPDATE_FAILED": OtaStatus.FAILED,
}

OUTLET_STATES: Mapping[str, OutletState] = {state.value: state for state in OutletState}

MEASURES: Mapping[str, Measure] = {measure.value: measure for measure in Measure}

DEVICE_LABELS: Mapping[DeviceKind, str] = {
    DeviceKind.SENSOR: "Sensor",
    DeviceKind.OUTLET: "Outlet",
}

DEVICE_KEYS: Mapping[DeviceKind, str] = {
    DeviceKind.SENSOR: "sensors",
    DeviceKind.OUTLET: "outlets",
}


def parse_time(raw: Any) -> datetime | None:
    if not isinstance(raw, str):
        return None
    value = raw.strip()
    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"
    if " " in value and "T" not in value:
        value = value.replace(" ", "T", 1)
    if "." in value:
        head, _, tail = value.partition(".")
        fraction = tail
        offset = ""
        for sign in ("+", "-"):
            if sign in tail:
                fraction, _, rest = tail.partition(sign)
                offset = f"{sign}{rest}"
                break
        value = f"{head}.{fraction[:6]}{offset}"
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        _LOGGER.debug("Could not parse timestamp %r", raw)
        return None


def parse_number(raw: Any) -> float | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def parse_int(raw: Any) -> int | None:
    value = parse_number(raw)
    return None if value is None else int(value)


def parse_enum[EnumT: StrEnum](raw: Any, options: Mapping[str, EnumT]) -> EnumT | None:
    return options.get(raw) if isinstance(raw, str) else None


def connection_strength_from_rssi(rssi: float | None) -> ConnectionStrength | None:
    if rssi is None:
        return None
    if rssi > -50:
        return ConnectionStrength.EXCELLENT
    if rssi > -80:
        return ConnectionStrength.GOOD
    if rssi > -95:
        return ConnectionStrength.FAIR
    return ConnectionStrength.BAD


def _short_id(device_id: str) -> str:
    return device_id.split("-")[0][:6].upper()


def parse_device(raw: dict[str, Any], bridge_id: str, kind: DeviceKind) -> Device:
    device_id = raw["id"]
    return Device(
        id=device_id,
        bridge_id=bridge_id or raw.get("bridgeId") or "",
        kind=kind,
        display_name=raw.get("displayName")
        or raw.get("label")
        or f"OBI {DEVICE_LABELS[kind]} {_short_id(device_id)}",
        firmware_version=raw.get("firmwareVersion") or UNKNOWN_VERSION,
        hardware_version=raw.get("hardwareVersion") or UNKNOWN_VERSION,
        is_online=bool(raw.get("isOnline", False)),
        battery_level=parse_int(raw.get("batteryLevel")),
        state=parse_enum(raw.get("state"), OUTLET_STATES),
    )


def _parse_devices(
    raw: dict[str, Any], bridge_id: str, kind: DeviceKind
) -> list[Device]:
    return [
        parse_device(item, bridge_id, kind)
        for item in raw.get(DEVICE_KEYS[kind]) or []
        if isinstance(item, dict) and item.get("id")
    ]


def parse_bridge(raw: dict[str, Any]) -> Bridge:
    bridge_id = raw["id"]
    return Bridge(
        id=bridge_id,
        display_name=raw.get("displayName")
        or raw.get("label")
        or f"OBI Bridge {_short_id(bridge_id)}",
        firmware_version=raw.get("firmwareVersion") or UNKNOWN_VERSION,
        hardware_version=raw.get("hardwareVersion") or UNKNOWN_VERSION,
        ota_status=parse_enum(raw.get("otaStatus"), OTA_STATUSES),
        ota_progress=parse_int(raw.get("otaProgress")),
        sensors=_parse_devices(raw, bridge_id, DeviceKind.SENSOR),
        outlets=_parse_devices(raw, bridge_id, DeviceKind.OUTLET),
    )


def parse_firmware_update(raw: Any) -> FirmwareUpdate | None:
    if not isinstance(raw, dict):
        return None
    update_id = raw.get("id")
    version = raw.get("semVer")
    if not isinstance(update_id, str) or not isinstance(version, str):
        return None
    change_log = raw.get("changeLog")
    return FirmwareUpdate(
        id=update_id,
        version=version,
        change_log=change_log if isinstance(change_log, str) else None,
    )


def parse_records(raw: Any) -> dict[Measure, list[MeasureRecord]]:
    records: dict[Measure, list[MeasureRecord]] = defaultdict(list)
    items = raw if isinstance(raw, list) else [raw]
    for item in items:
        if not isinstance(item, dict):
            continue
        time = parse_time(item.get("time"))
        value = parse_number(item.get("value"))
        if time is None or value is None:
            continue
        measure = parse_enum(item.get("measure") or Measure.ENERGY, MEASURES)
        if measure is None:
            continue
        records[measure].append(MeasureRecord(time=time, value=value, measure=measure))
    for series in records.values():
        series.sort(key=lambda record: record.time)
    return dict(records)
