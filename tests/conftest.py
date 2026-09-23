from __future__ import annotations

from collections import deque
from collections.abc import AsyncGenerator, Mapping
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from multidict import CIMultiDictProxy
from yarl import URL

from obi_energy_tracker import ObiEnergyTrackerApi, static_token_provider

TEST_ACCESS_TOKEN = "test-token-abcdefghijklmnop"


@dataclass(frozen=True)
class RecordedRequest:
    method: str
    url: URL
    headers: CIMultiDictProxy[str]
    json: Any

    @property
    def path(self) -> str:
        return self.url.path

    @property
    def query(self) -> dict[str, list[str]]:
        return {key: list(self.url.query.getall(key)) for key in self.url.query}


@dataclass
class _ResponseSpec:
    status: int = 200
    payload: Any = None
    body: str = ""
    content_type: str = "application/json"
    headers: Mapping[str, str] = field(default_factory=dict)


class FakeBackend:
    def __init__(self) -> None:
        self.base_url = ""
        self.requests: list[RecordedRequest] = []
        self._responses: deque[_ResponseSpec] = deque()

    def respond(
        self,
        status: int = 200,
        payload: Any = None,
        body: str = "",
        content_type: str = "application/json",
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self._responses.append(
            _ResponseSpec(
                status=status,
                payload=payload,
                body=body,
                content_type=content_type,
                headers=headers or {},
            )
        )

    async def handle(self, request: web.Request) -> web.StreamResponse:
        self.requests.append(
            RecordedRequest(
                method=request.method,
                url=request.url,
                headers=request.headers,
                json=await request.json() if request.body_exists else None,
            )
        )
        spec = (
            self._responses.popleft() if self._responses else _ResponseSpec(status=200)
        )
        if spec.status == 204:
            return web.Response(status=204, headers=spec.headers)
        if spec.payload is None:
            return web.Response(
                status=spec.status,
                text=spec.body,
                content_type=spec.content_type,
                headers=spec.headers,
            )
        return web.json_response(
            data=spec.payload,
            status=spec.status,
            content_type=spec.content_type,
            headers=spec.headers,
        )


def recording_session() -> MagicMock:
    response = MagicMock()
    response.status = 200
    response.read = AsyncMock(return_value=b"[]")
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.request = MagicMock(return_value=context)
    return session


def failing_session(error: BaseException) -> MagicMock:
    session = MagicMock()
    session.request = MagicMock(side_effect=error)
    return session


def make_sensor_api_response(
    id: str = "sensor-001",
    bridge_id: str = "bridge-001",
    display_name: str | None = "Test Sensor",
    firmware_version: str = "1.0.0",
    hardware_version: str = "2.0.0",
    battery_level: int | None = 85,
    is_online: bool = True,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": id,
        "bridgeId": bridge_id,
        "displayName": display_name,
        "firmwareVersion": firmware_version,
        "hardwareVersion": hardware_version,
        "isOnline": is_online,
    }
    if battery_level is not None:
        result["batteryLevel"] = battery_level
    return result


def make_outlet_api_response(
    id: str = "outlet-001",
    bridge_id: str = "bridge-001",
    display_name: str | None = "Test Outlet",
    firmware_version: str = "12.0.0",
    hardware_version: str = "0.1.0",
    is_online: bool = True,
    state: str = "off",
) -> dict[str, Any]:
    return {
        "id": id,
        "bridgeId": bridge_id,
        "displayName": display_name,
        "firmwareVersion": firmware_version,
        "hardwareVersion": hardware_version,
        "isOnline": is_online,
        "state": state,
    }


def make_bridge_api_response(
    id: str = "bridge-001",
    label: str | None = "Test Bridge",
    firmware_version: str = "1.0.0",
    hardware_version: str = "2.0.0",
    ota_status: str | None = "NOT_UPDATING",
    ota_progress: int | None = None,
    sensors: list[dict[str, Any]] | None = None,
    outlets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": id,
        "label": label,
        "firmwareVersion": firmware_version,
        "hardwareVersion": hardware_version,
        "otaStatus": ota_status,
        "otaProgress": ota_progress,
        "sensors": sensors if sensors is not None else [],
        "outlets": outlets if outlets is not None else [],
    }


def make_firmware_update_api_response(
    id: str = "firmware-001",
    sem_ver: str = "1.1.0",
    change_log: str | None = "- Improved WiFi stability",
    is_beta: bool = False,
) -> dict[str, Any]:
    return {
        "id": id,
        "semVer": sem_ver,
        "changeLog": change_log,
        "isBeta": is_beta,
    }


def make_record_api_response(
    time: str = "2026-01-01T12:00:00Z",
    value: float = 1234.5,
    measure: str = "energy",
) -> dict[str, Any]:
    return {"time": time, "value": value, "measure": measure}


def make_measures_api_response(
    devices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    return {"devices": devices}


@pytest.fixture
async def session() -> AsyncGenerator[aiohttp.ClientSession]:
    async with aiohttp.ClientSession() as client_session:
        yield client_session


@pytest.fixture
async def backend() -> AsyncGenerator[FakeBackend]:
    fake = FakeBackend()
    app = web.Application()
    app.router.add_route("*", "/{path:.*}", fake.handle)
    server = TestServer(app)
    await server.start_server()
    fake.base_url = str(server.make_url("")).rstrip("/")
    yield fake
    await server.close()


@pytest.fixture
async def api(
    session: aiohttp.ClientSession, backend: FakeBackend
) -> ObiEnergyTrackerApi:
    return ObiEnergyTrackerApi(
        session=session,
        token_provider=static_token_provider(TEST_ACCESS_TOKEN),
        base_url=backend.base_url,
    )
