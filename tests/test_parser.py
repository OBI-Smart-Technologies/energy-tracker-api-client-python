from __future__ import annotations

from datetime import UTC, datetime

import pytest

from obi_energy_tracker import ConnectionStrength, connection_strength_from_rssi
from obi_energy_tracker.parser import parse_time


class TestParseTime:
    def test_zulu_suffix(self) -> None:
        assert parse_time("2026-08-26T07:38:05Z") == datetime(
            2026, 8, 26, 7, 38, 5, tzinfo=UTC
        )

    def test_milliseconds(self) -> None:
        assert parse_time("2026-07-20T15:13:10.164Z") == datetime(
            2026, 7, 20, 15, 13, 10, 164000, tzinfo=UTC
        )

    def test_timestream_nanoseconds_and_space(self) -> None:
        assert parse_time("2024-08-19 00:00:00.000000000") == datetime(
            2024, 8, 19, 0, 0, 0
        )

    def test_offset_is_preserved(self) -> None:
        parsed = parse_time("2026-08-26T09:38:05.123456+02:00")

        assert parsed is not None
        assert parsed.astimezone(UTC) == datetime(
            2026, 8, 26, 7, 38, 5, 123456, tzinfo=UTC
        )

    def test_invalid_returns_none(self) -> None:
        assert parse_time("not-a-date") is None

    def test_non_string_returns_none(self) -> None:
        assert parse_time(None) is None
        assert parse_time(12345) is None


class TestConnectionStrengthFromRssi:
    @pytest.mark.parametrize(
        ("rssi", "expected"),
        [
            (-20.0, ConnectionStrength.EXCELLENT),
            (-49.0, ConnectionStrength.EXCELLENT),
            (-50.0, ConnectionStrength.GOOD),
            (-79.0, ConnectionStrength.GOOD),
            (-80.0, ConnectionStrength.FAIR),
            (-94.0, ConnectionStrength.FAIR),
            (-95.0, ConnectionStrength.BAD),
            (-99.0, ConnectionStrength.BAD),
        ],
    )
    def test_thresholds(self, rssi: float, expected: ConnectionStrength) -> None:
        assert connection_strength_from_rssi(rssi) is expected

    def test_without_rssi(self) -> None:
        assert connection_strength_from_rssi(None) is None
