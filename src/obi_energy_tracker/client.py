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

import json
import logging
from collections.abc import Iterable
from typing import Any

import aiohttp

from .auth import TokenProvider
from .const import (
    CONTENT_TYPE_BRIDGE,
    CONTENT_TYPE_FIRMWARE_UPDATE,
    CONTENT_TYPE_FIRMWARE_UPDATE_REQUEST,
    CONTENT_TYPE_HISTORICAL,
    CONTENT_TYPE_HISTORICAL_MULTI,
    CONTENT_TYPE_OUTLET,
    DEFAULT_BASE_URL,
    DeviceKind,
    Measure,
    OutletState,
)
from .exceptions import (
    ObiEnergyTrackerAuthError,
    ObiEnergyTrackerDeviceOfflineError,
    ObiEnergyTrackerError,
)
from .models import Bridge, Device, DeviceMeasures, FirmwareUpdate, MeasureRecord
from .parser import parse_bridge, parse_device, parse_firmware_update, parse_records

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)
HISTORY_TIMEOUT = aiohttp.ClientTimeout(total=120)


class ObiEnergyTrackerApi:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        token_provider: TokenProvider,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._session = session
        self._token_provider = token_provider

    async def _headers(
        self, accept: str, content_type: str | None = None
    ) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {await self._token_provider()}",
            "Accept": accept,
        }
        if content_type is not None:
            headers["Content-Type"] = content_type
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        accept: str,
        content_type: str | None = None,
        timeout: aiohttp.ClientTimeout = REQUEST_TIMEOUT,
        **kwargs: Any,
    ) -> Any:
        url = f"{self._base_url}{path}"
        headers = await self._headers(accept, content_type)
        try:
            async with self._session.request(
                method, url, headers=headers, timeout=timeout, **kwargs
            ) as resp:
                if resp.status == 429:
                    retry_after = resp.headers.get("Retry-After", "60")
                    _LOGGER.warning(
                        "Rate limited (429) on %s, retry after %ss", url, retry_after
                    )
                    raise ObiEnergyTrackerError(
                        f"Rate limited, retry after {retry_after}s"
                    )
                if resp.status in (401, 403):
                    raise ObiEnergyTrackerAuthError("Authentication failed")
                if resp.status == 504:
                    raise ObiEnergyTrackerDeviceOfflineError(
                        "Device did not respond, it might be offline"
                    )
                if resp.status == 204:
                    return None
                if resp.status != 200:
                    text = await resp.text()
                    raise ObiEnergyTrackerError(
                        f"API request failed: {resp.status} {text}"
                    )
                body = await resp.read()
                if not body:
                    return None
                return json.loads(body)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ObiEnergyTrackerError(f"Connection error: {err}") from err

    async def async_get_bridges(self) -> list[Bridge]:
        data = await self._request("GET", "/bridges", accept=CONTENT_TYPE_BRIDGE)
        if not isinstance(data, list):
            raise ObiEnergyTrackerError("Unexpected /bridges response")
        return [parse_bridge(item) for item in data if isinstance(item, dict)]

    async def async_set_outlet_state(
        self, outlet_id: str, state: OutletState
    ) -> Device | None:
        data = await self._request(
            "PATCH",
            f"/outlets/{outlet_id}",
            accept=CONTENT_TYPE_OUTLET,
            content_type=CONTENT_TYPE_OUTLET,
            json={"id": outlet_id, "state": state.value},
        )
        if not isinstance(data, dict) or "id" not in data:
            return None
        return parse_device(data, data.get("bridgeId", ""), DeviceKind.OUTLET)

    async def async_get_bridge_firmware_update(
        self, bridge_id: str
    ) -> FirmwareUpdate | None:
        data = await self._request(
            "GET",
            f"/firmware-updates/{bridge_id}",
            accept=CONTENT_TYPE_FIRMWARE_UPDATE,
        )
        return parse_firmware_update(data)

    async def async_trigger_bridge_firmware_update(
        self, bridge_id: str, firmware_id: str
    ) -> None:
        await self._request(
            "POST",
            f"/firmware-updates/{bridge_id}/trigger",
            accept=CONTENT_TYPE_FIRMWARE_UPDATE,
            content_type=CONTENT_TYPE_FIRMWARE_UPDATE_REQUEST,
            json={"firmwareId": firmware_id},
        )

    async def async_get_bridge_measures(
        self,
        bridge_id: str,
        measures: Iterable[Measure],
        duration: str | None = None,
    ) -> DeviceMeasures:
        params: dict[str, Any] = {
            "to": "now",
            "measures": [measure.value for measure in measures],
        }
        if duration is None:
            params["from"] = "start"
        else:
            params["duration"] = duration
        data = await self._request(
            "GET",
            f"/historical-data/{bridge_id}/measures",
            accept=CONTENT_TYPE_HISTORICAL_MULTI,
            timeout=REQUEST_TIMEOUT if duration is not None else HISTORY_TIMEOUT,
            params=params,
        )
        devices = data.get("devices") if isinstance(data, dict) else None
        if not isinstance(devices, dict):
            return {}
        return {
            device_id: parse_records(records) for device_id, records in devices.items()
        }

    async def async_get_meter_readings(
        self,
        bridge_id: str,
        device_id: str,
        measures: Iterable[Measure],
    ) -> dict[Measure, list[MeasureRecord]]:
        data = await self._request(
            "GET",
            f"/historical-data/{bridge_id}/{device_id}/meter",
            accept=CONTENT_TYPE_HISTORICAL,
            timeout=HISTORY_TIMEOUT,
            params={
                "from": "start",
                "to": "now",
                "measures": [measure.value for measure in measures],
            },
        )
        return parse_records(data)
