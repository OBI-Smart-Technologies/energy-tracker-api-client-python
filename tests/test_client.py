from __future__ import annotations

import aiohttp
import pytest

from obi_energy_tracker import (
    DEFAULT_BASE_URL,
    Bridge,
    Device,
    FirmwareUpdate,
    Measure,
    ObiEnergyTrackerApi,
    ObiEnergyTrackerAuthError,
    ObiEnergyTrackerDeviceOfflineError,
    ObiEnergyTrackerError,
    OtaStatus,
    OutletState,
    static_token_provider,
)
from obi_energy_tracker.client import HISTORY_TIMEOUT, REQUEST_TIMEOUT
from obi_energy_tracker.const import (
    CONTENT_TYPE_BRIDGE,
    CONTENT_TYPE_FIRMWARE_UPDATE,
    CONTENT_TYPE_FIRMWARE_UPDATE_REQUEST,
    CONTENT_TYPE_HISTORICAL,
    CONTENT_TYPE_HISTORICAL_MULTI,
    CONTENT_TYPE_OUTLET,
)

from .conftest import (
    TEST_ACCESS_TOKEN,
    FakeBackend,
    failing_session,
    make_bridge_api_response,
    make_firmware_update_api_response,
    make_measures_api_response,
    make_outlet_api_response,
    make_record_api_response,
    make_sensor_api_response,
    recording_session,
)


def _offline_api(session: object, token: str = "tok") -> ObiEnergyTrackerApi:
    return ObiEnergyTrackerApi(
        session=session,  # type: ignore[arg-type]
        token_provider=static_token_provider(token),
    )


class TestHeaders:
    async def test_bearer_token_from_provider(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(payload=[])

        await api.async_get_bridges()

        assert (
            backend.requests[0].headers["Authorization"]
            == f"Bearer {TEST_ACCESS_TOKEN}"
        )

    async def test_accept_header(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(payload=[])

        await api.async_get_bridges()

        assert backend.requests[0].headers["Accept"] == CONTENT_TYPE_BRIDGE

    async def test_content_type_only_on_writes(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(payload=[])
        backend.respond(payload=make_outlet_api_response(id="o-1"))

        await api.async_get_bridges()
        await api.async_set_outlet_state("o-1", OutletState.ON)

        assert "Content-Type" not in backend.requests[0].headers
        assert backend.requests[1].headers["Content-Type"] == CONTENT_TYPE_OUTLET

    async def test_token_is_fetched_for_every_request(self) -> None:
        tokens = iter(["first", "second"])

        async def _provider() -> str:
            return next(tokens)

        session = recording_session()
        api = ObiEnergyTrackerApi(session=session, token_provider=_provider)

        await api.async_get_bridges()
        await api.async_get_bridges()

        sent = [call.kwargs["headers"] for call in session.request.call_args_list]
        assert [headers["Authorization"] for headers in sent] == [
            "Bearer first",
            "Bearer second",
        ]

    def test_trailing_slash_stripped_from_base_url(self) -> None:
        api = ObiEnergyTrackerApi(
            session=recording_session(),
            token_provider=static_token_provider(TEST_ACCESS_TOKEN),
            base_url=f"{DEFAULT_BASE_URL}/",
        )

        assert api._base_url == DEFAULT_BASE_URL

    def test_production_host_is_the_default(self) -> None:
        assert _offline_api(recording_session())._base_url == DEFAULT_BASE_URL


class TestRequest:
    @pytest.mark.parametrize("status", [401, 403])
    async def test_unauthorized_raises_auth_error(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend, status: int
    ) -> None:
        backend.respond(status=status)

        with pytest.raises(ObiEnergyTrackerAuthError, match="Authentication failed"):
            await api.async_get_bridges()

    async def test_404_raises_api_error(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(status=404, body="Not Found", content_type="text/plain")

        with pytest.raises(ObiEnergyTrackerError, match="404"):
            await api.async_get_bridges()

    async def test_error_body_is_part_of_the_message(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(status=404, body="Not Found", content_type="text/plain")

        with pytest.raises(ObiEnergyTrackerError, match="Not Found"):
            await api.async_get_bridges()

    async def test_500_raises_api_error(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(
            status=500, body="Internal Server Error", content_type="text/plain"
        )

        with pytest.raises(ObiEnergyTrackerError, match="500"):
            await api.async_get_bridges()

    async def test_429_reports_retry_after(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(status=429, headers={"Retry-After": "30"})

        with pytest.raises(ObiEnergyTrackerError, match="retry after 30s"):
            await api.async_get_bridges()

    async def test_429_without_header_falls_back_to_60s(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(status=429)

        with pytest.raises(ObiEnergyTrackerError, match="retry after 60s"):
            await api.async_get_bridges()

    async def test_504_raises_device_offline_error(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(status=504)

        with pytest.raises(ObiEnergyTrackerDeviceOfflineError):
            await api.async_set_outlet_state("o-1", OutletState.OFF)

    async def test_204_returns_none(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(status=204)

        assert await api.async_set_outlet_state("o-1", OutletState.OFF) is None

    async def test_client_error_becomes_api_error(self) -> None:
        api = _offline_api(failing_session(aiohttp.ClientError("conn refused")))

        with pytest.raises(ObiEnergyTrackerError, match="Connection error"):
            await api.async_get_bridges()

    async def test_timeout_becomes_api_error(self) -> None:
        api = _offline_api(failing_session(TimeoutError()))

        with pytest.raises(ObiEnergyTrackerError, match="Connection error"):
            await api.async_get_bridges()

    async def test_requests_carry_the_default_timeout(self) -> None:
        session = recording_session()

        await _offline_api(session).async_get_bridges()

        assert session.request.call_args.kwargs["timeout"] is REQUEST_TIMEOUT

    async def test_history_requests_get_the_longer_timeout(self) -> None:
        session = recording_session()

        await _offline_api(session).async_get_meter_readings(
            "br-1", "s-1", [Measure.ENERGY]
        )

        assert session.request.call_args.kwargs["timeout"] is HISTORY_TIMEOUT
        assert HISTORY_TIMEOUT.total is not None
        assert REQUEST_TIMEOUT.total is not None
        assert HISTORY_TIMEOUT.total > REQUEST_TIMEOUT.total

    async def test_body_is_parsed_even_with_a_foreign_content_type(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(body="[]", content_type="text/plain")

        assert await api.async_get_bridges() == []


class TestGetBridges:
    async def test_standard_response(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        bridge_data = make_bridge_api_response()
        backend.respond(payload=[bridge_data])

        bridges = await api.async_get_bridges()

        assert len(bridges) == 1
        bridge = bridges[0]
        assert isinstance(bridge, Bridge)
        assert bridge.id == bridge_data["id"]
        assert bridge.firmware_version == bridge_data["firmwareVersion"]
        assert bridge.hardware_version == bridge_data["hardwareVersion"]

    async def test_endpoint(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(payload=[])

        await api.async_get_bridges()

        assert backend.requests[0].method == "GET"
        assert backend.requests[0].path == "/bridges"

    async def test_empty_list(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(payload=[])

        assert await api.async_get_bridges() == []

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("NOT_UPDATING", OtaStatus.IDLE),
            ("BRIDGE_UPDATE_STARTED", OtaStatus.STARTED),
            ("FIRMWARE_DOWNLOAD_STARTED", OtaStatus.DOWNLOADING),
            ("BRIDGE_UPDATE_INSTALLING", OtaStatus.INSTALLING),
            ("BRIDGE_UPDATE_COMPLETE", OtaStatus.COMPLETE),
            ("BRIDGE_UPDATE_FAILED", OtaStatus.FAILED),
            ("SOMETHING_NEW", None),
            (None, None),
        ],
    )
    async def test_ota_status_parsing(
        self,
        api: ObiEnergyTrackerApi,
        backend: FakeBackend,
        raw: str | None,
        expected: OtaStatus | None,
    ) -> None:
        backend.respond(payload=[make_bridge_api_response(ota_status=raw)])

        bridges = await api.async_get_bridges()

        assert bridges[0].ota_status is expected

    async def test_ota_progress_parsing(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(payload=[make_bridge_api_response(ota_progress=72)])

        bridges = await api.async_get_bridges()

        assert bridges[0].ota_progress == 72

    async def test_missing_ota_progress_is_none(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(payload=[make_bridge_api_response(ota_progress=None)])

        bridges = await api.async_get_bridges()

        assert bridges[0].ota_progress is None

    async def test_non_list_response_raises(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(payload={"unexpected": True})

        with pytest.raises(ObiEnergyTrackerError, match="Unexpected /bridges"):
            await api.async_get_bridges()

    async def test_sensors_and_outlets_parsed(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(
            payload=[
                make_bridge_api_response(
                    id="br-1",
                    sensors=[make_sensor_api_response(id="s-1")],
                    outlets=[make_outlet_api_response(id="o-1", state="on")],
                )
            ]
        )

        bridge = (await api.async_get_bridges())[0]

        assert [s.id for s in bridge.sensors] == ["s-1"]
        assert [o.id for o in bridge.outlets] == ["o-1"]
        assert [d.id for d in bridge.devices] == ["s-1", "o-1"]
        assert bridge.outlets[0].is_outlet is True
        assert bridge.outlets[0].state is OutletState.ON

    async def test_multiple_sensors_per_bridge(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(
            payload=[
                make_bridge_api_response(
                    id="br-1",
                    sensors=[
                        make_sensor_api_response(id="s-1"),
                        make_sensor_api_response(id="s-2"),
                        make_sensor_api_response(id="s-3"),
                    ],
                )
            ]
        )

        bridge = (await api.async_get_bridges())[0]

        assert [s.id for s in bridge.sensors] == ["s-1", "s-2", "s-3"]

    async def test_string_sensor_entries_ignored(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        bridge_data = make_bridge_api_response(id="br-1")
        bridge_data["sensors"] = ["s-1", "s-2"]
        backend.respond(payload=[bridge_data])

        assert (await api.async_get_bridges())[0].sensors == []

    async def test_missing_device_lists(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        bridge_data = make_bridge_api_response()
        bridge_data.pop("sensors")
        bridge_data.pop("outlets")
        backend.respond(payload=[bridge_data])

        assert (await api.async_get_bridges())[0].devices == []

    async def test_display_name_precedence(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        bridge_data = make_bridge_api_response(id="abc12345-0000", label="LBL")
        bridge_data["displayName"] = "Wohnung"
        backend.respond(payload=[bridge_data])

        assert (await api.async_get_bridges())[0].display_name == "Wohnung"

    async def test_display_name_falls_back_to_short_id(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(
            payload=[make_bridge_api_response(id="abc12345-0000", label=None)]
        )

        assert (await api.async_get_bridges())[0].display_name == "OBI Bridge ABC123"

    async def test_optional_fields_defaults(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        bridge_data = make_bridge_api_response()
        bridge_data.pop("firmwareVersion")
        bridge_data.pop("hardwareVersion")
        backend.respond(payload=[bridge_data])

        bridge = (await api.async_get_bridges())[0]

        assert bridge.firmware_version == "unknown"
        assert bridge.hardware_version == "unknown"

    async def test_devices_across_multiple_bridges(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(
            payload=[
                make_bridge_api_response(
                    id="b1",
                    sensors=[
                        make_sensor_api_response(id="s1"),
                        make_sensor_api_response(id="s2"),
                    ],
                    outlets=[make_outlet_api_response(id="o1")],
                ),
                make_bridge_api_response(
                    id="b2", sensors=[make_sensor_api_response(id="s3")]
                ),
            ]
        )

        bridges = await api.async_get_bridges()
        devices = [device for bridge in bridges for device in bridge.devices]

        assert [d.id for d in devices] == ["s1", "s2", "o1", "s3"]
        assert [d.bridge_id for d in devices] == ["b1", "b1", "b1", "b2"]


class TestDeviceParsing:
    async def test_sensor_fields(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        sensor_data = make_sensor_api_response(id="s-1", bridge_id="br-1")
        backend.respond(
            payload=[make_bridge_api_response(id="br-1", sensors=[sensor_data])]
        )

        sensors = (await api.async_get_bridges())[0].sensors

        assert len(sensors) == 1
        sensor = sensors[0]
        assert isinstance(sensor, Device)
        assert sensor.id == "s-1"
        assert sensor.bridge_id == "br-1"
        assert sensor.battery_level == sensor_data["batteryLevel"]
        assert sensor.is_online is True
        assert sensor.state is None
        assert sensor.is_outlet is False

    async def test_outlet_fields(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        outlet_data = make_outlet_api_response(id="o-1", bridge_id="br-1", state="on")
        backend.respond(
            payload=[make_bridge_api_response(id="br-1", outlets=[outlet_data])]
        )

        outlets = (await api.async_get_bridges())[0].outlets

        assert len(outlets) == 1
        outlet = outlets[0]
        assert outlet.id == "o-1"
        assert outlet.state is OutletState.ON
        assert outlet.battery_level is None
        assert outlet.is_outlet is True

    async def test_minimal_sensor_defaults(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        bridge_data = make_bridge_api_response(id="br-1")
        bridge_data["sensors"] = [{"id": "abcdef12-0000"}]
        backend.respond(payload=[bridge_data])

        sensor = (await api.async_get_bridges())[0].sensors[0]

        assert sensor.bridge_id == "br-1"
        assert sensor.display_name == "OBI Sensor ABCDEF"
        assert sensor.firmware_version == "unknown"
        assert sensor.hardware_version == "unknown"
        assert sensor.battery_level is None
        assert sensor.is_online is False

    async def test_minimal_outlet_default_name(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        bridge_data = make_bridge_api_response(id="br-1")
        bridge_data["outlets"] = [{"id": "abcdef12-0000"}]
        backend.respond(payload=[bridge_data])

        outlet = (await api.async_get_bridges())[0].outlets[0]

        assert outlet.display_name == "OBI Outlet ABCDEF"

    async def test_unknown_outlet_state_is_dropped(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(
            payload=[
                make_bridge_api_response(
                    id="br-1", outlets=[make_outlet_api_response(state="unknown")]
                )
            ]
        )

        outlet = (await api.async_get_bridges())[0].outlets[0]

        assert outlet.state is None


class TestGetBridgeMeasures:
    async def test_records_grouped_per_device_and_measure(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(
            payload=make_measures_api_response(
                {
                    "s-1": [
                        make_record_api_response(
                            time="2026-01-01T12:00:00Z", value=100, measure="energy"
                        ),
                        make_record_api_response(
                            time="2026-01-01T12:05:00Z", value=110, measure="energy"
                        ),
                        make_record_api_response(
                            time="2026-01-01T12:05:00Z", value=-70, measure="rssi"
                        ),
                        make_record_api_response(
                            time="2026-01-01T12:05:00Z", value=92, measure="battery"
                        ),
                    ],
                    "o-1": [
                        make_record_api_response(
                            time="2026-01-01T12:05:00Z", value=1137, measure="energy"
                        )
                    ],
                }
            )
        )

        measures = await api.async_get_bridge_measures(
            "br-1", [Measure.ENERGY, Measure.RSSI], "PT6H"
        )

        assert set(measures) == {"s-1", "o-1"}
        assert [r.value for r in measures["s-1"][Measure.ENERGY]] == [100, 110]
        assert measures["s-1"][Measure.RSSI][0].value == -70
        assert measures["s-1"][Measure.BATTERY][0].value == 92
        assert measures["o-1"][Measure.ENERGY][-1].value == 1137

    async def test_records_sorted_chronologically(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(
            payload=make_measures_api_response(
                {
                    "s-1": [
                        make_record_api_response(
                            time="2026-01-01T12:10:00Z", value=300
                        ),
                        make_record_api_response(
                            time="2026-01-01T12:00:00Z", value=100
                        ),
                        make_record_api_response(
                            time="2026-01-01T12:05:00Z", value=200
                        ),
                    ]
                }
            )
        )

        measures = await api.async_get_bridge_measures("br-1", [Measure.ENERGY], "PT6H")

        assert [r.value for r in measures["s-1"][Measure.ENERGY]] == [100, 200, 300]

    async def test_missing_devices_key_returns_empty(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(payload={})

        assert (
            await api.async_get_bridge_measures("br-1", [Measure.ENERGY], "PT6H") == {}
        )

    async def test_invalid_records_skipped(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(
            payload=make_measures_api_response(
                {
                    "s-1": [
                        {"time": "not-a-date", "value": 1, "measure": "energy"},
                        {"value": 2, "measure": "energy"},
                        {"time": "2026-01-01T12:00:00Z", "measure": "energy"},
                        make_record_api_response(value=42),
                    ]
                }
            )
        )

        measures = await api.async_get_bridge_measures("br-1", [Measure.ENERGY], "PT6H")

        assert [r.value for r in measures["s-1"][Measure.ENERGY]] == [42]

    async def test_unknown_measures_skipped(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(
            payload=make_measures_api_response(
                {
                    "s-1": [
                        make_record_api_response(value=1, measure="water"),
                        make_record_api_response(value=2, measure="energy"),
                    ]
                }
            )
        )

        measures = await api.async_get_bridge_measures("br-1", [Measure.ENERGY], "PT6H")

        assert list(measures["s-1"]) == [Measure.ENERGY]

    async def test_records_without_measure_default_to_energy(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(
            payload=make_measures_api_response(
                {"s-1": [{"time": "2026-01-01T12:00:00Z", "value": 7}]}
            )
        )

        measures = await api.async_get_bridge_measures("br-1", [Measure.ENERGY], "PT6H")

        assert measures["s-1"][Measure.ENERGY][0].value == 7

    async def test_query_parameters_and_accept_header(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(payload={"devices": {}})

        await api.async_get_bridge_measures(
            "br-1", [Measure.ENERGY, Measure.RSSI], "PT6H"
        )

        request = backend.requests[0]

        assert request.path == "/historical-data/br-1/measures"
        assert request.query["measures"] == ["energy", "rssi"]
        assert request.query["duration"] == ["PT6H"]
        assert request.query["to"] == ["now"]
        assert "from" not in request.query
        assert request.headers["Accept"] == CONTENT_TYPE_HISTORICAL_MULTI

    async def test_without_duration_the_full_history_is_requested(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(payload={"devices": {}})

        await api.async_get_bridge_measures(
            "br-1", [Measure.ENERGY, Measure.NEGATIVE_ENERGY]
        )

        request = backend.requests[0]

        assert request.path == "/historical-data/br-1/measures"
        assert request.query["measures"] == ["energy", "negative_energy"]
        assert request.query["from"] == ["start"]
        assert request.query["to"] == ["now"]
        assert "duration" not in request.query

    async def test_full_history_gets_the_longer_timeout(self) -> None:
        session = recording_session()

        await _offline_api(session).async_get_bridge_measures("br-1", [Measure.ENERGY])

        assert session.request.call_args.kwargs["timeout"] is HISTORY_TIMEOUT

    async def test_windowed_request_keeps_the_default_timeout(self) -> None:
        session = recording_session()

        await _offline_api(session).async_get_bridge_measures(
            "br-1", [Measure.ENERGY], "PT6H"
        )

        assert session.request.call_args.kwargs["timeout"] is REQUEST_TIMEOUT


class TestGetMeterReadings:
    async def test_grouped_by_measure(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(
            payload=[
                make_record_api_response(
                    time="2026-01-01T12:00:00Z", value=1000.0, measure="energy"
                ),
                make_record_api_response(
                    time="2026-01-01T12:00:00Z",
                    value=500.0,
                    measure="negative_energy",
                ),
            ]
        )

        readings = await api.async_get_meter_readings(
            "br-1", "s-1", [Measure.ENERGY, Measure.NEGATIVE_ENERGY]
        )

        assert readings[Measure.ENERGY][0].value == 1000.0
        assert readings[Measure.NEGATIVE_ENERGY][0].value == 500.0

    async def test_energy_only(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(payload=[make_record_api_response(value=42.0)])

        readings = await api.async_get_meter_readings(
            "br-1", "s-1", [Measure.ENERGY, Measure.NEGATIVE_ENERGY]
        )

        assert list(readings) == [Measure.ENERGY]
        assert readings[Measure.ENERGY][0].value == 42.0

    async def test_empty_list(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(payload=[])

        assert await api.async_get_meter_readings("br-1", "s-1", [Measure.ENERGY]) == {}

    async def test_url_query_and_accept_header(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(payload=[])

        await api.async_get_meter_readings(
            "br-abc", "sn-xyz", [Measure.ENERGY, Measure.NEGATIVE_ENERGY]
        )

        request = backend.requests[0]

        assert request.path == "/historical-data/br-abc/sn-xyz/meter"
        assert request.query["from"] == ["start"]
        assert request.query["to"] == ["now"]
        assert request.query["measures"] == ["energy", "negative_energy"]
        assert request.headers["Accept"] == CONTENT_TYPE_HISTORICAL


class TestSetOutletState:
    async def test_patch_payload_and_headers(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(payload=make_outlet_api_response(state="on"))

        await api.async_set_outlet_state("o-1", OutletState.ON)

        request = backend.requests[0]

        assert request.method == "PATCH"
        assert request.path == "/outlets/o-1"
        assert request.json == {"id": "o-1", "state": "on"}
        assert request.headers["Content-Type"] == CONTENT_TYPE_OUTLET
        assert request.headers["Accept"] == CONTENT_TYPE_OUTLET

    async def test_returns_updated_device(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(payload=make_outlet_api_response(id="o-1", state="on"))

        outlet = await api.async_set_outlet_state("o-1", OutletState.ON)

        assert outlet is not None
        assert outlet.id == "o-1"
        assert outlet.state is OutletState.ON
        assert outlet.is_outlet is True

    async def test_unexpected_body_returns_none(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(payload={"ok": True})

        assert await api.async_set_outlet_state("o-1", OutletState.OFF) is None


class TestGetBridgeFirmwareUpdate:
    async def test_available_update_is_parsed(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(
            payload=make_firmware_update_api_response(
                id="fw-1", sem_ver="1.1.0", change_log="- Fixed it"
            )
        )

        update = await api.async_get_bridge_firmware_update("br-1")

        assert update == FirmwareUpdate(
            id="fw-1", version="1.1.0", change_log="- Fixed it"
        )

    async def test_endpoint_and_accept_header(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(payload=make_firmware_update_api_response())

        await api.async_get_bridge_firmware_update("br-1")

        request = backend.requests[0]

        assert request.method == "GET"
        assert request.path == "/firmware-updates/br-1"
        assert request.headers["Accept"] == CONTENT_TYPE_FIRMWARE_UPDATE

    async def test_204_means_no_update(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(status=204)

        assert await api.async_get_bridge_firmware_update("br-1") is None

    async def test_missing_change_log_is_none(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(payload=make_firmware_update_api_response(change_log=None))

        update = await api.async_get_bridge_firmware_update("br-1")

        assert update is not None
        assert update.change_log is None

    @pytest.mark.parametrize(
        "payload",
        [
            {"semVer": "1.1.0"},
            {"id": "fw-1"},
            {"id": 1, "semVer": "1.1.0"},
            {"id": "fw-1", "semVer": 110},
            [],
        ],
    )
    async def test_unusable_payload_returns_none(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend, payload: object
    ) -> None:
        backend.respond(payload=payload)

        assert await api.async_get_bridge_firmware_update("br-1") is None


class TestTriggerBridgeFirmwareUpdate:
    async def test_post_payload_and_headers(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(status=204)

        await api.async_trigger_bridge_firmware_update("br-1", "fw-1")

        request = backend.requests[0]

        assert request.method == "POST"
        assert request.path == "/firmware-updates/br-1/trigger"
        assert request.json == {"firmwareId": "fw-1"}
        assert request.headers["Content-Type"] == CONTENT_TYPE_FIRMWARE_UPDATE_REQUEST

    async def test_empty_200_body_is_accepted(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(status=200, body="")

        await api.async_trigger_bridge_firmware_update("br-1", "fw-1")

        assert [r.path for r in backend.requests] == ["/firmware-updates/br-1/trigger"]

    async def test_unknown_bridge_raises(
        self, api: ObiEnergyTrackerApi, backend: FakeBackend
    ) -> None:
        backend.respond(status=404, body="Not Found", content_type="text/plain")

        with pytest.raises(ObiEnergyTrackerError, match="404"):
            await api.async_trigger_bridge_firmware_update("br-1", "fw-1")
