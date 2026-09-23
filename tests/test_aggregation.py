from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from obi_energy_tracker.aggregation import (
    cumulative,
    hourly_buckets,
    to_series,
)
from obi_energy_tracker.const import Measure
from obi_energy_tracker.models import MeasureRecord

BERLIN = ZoneInfo("Europe/Berlin")

BOUNDARY_24_08: tuple[tuple[str, float], ...] = (
    ("2026-08-23 21:53:47", 4767691.0),
    ("2026-08-23 21:58:50", 4767708.0),
    ("2026-08-23 22:03:55", 4767723.0),
    ("2026-08-23 22:08:58", 4767736.0),
    ("2026-08-24 21:53:11", 4772950.0),
    ("2026-08-24 21:58:14", 4772962.0),
    ("2026-08-24 22:03:17", 4772975.0),
)


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def _records(points: tuple[tuple[str, float], ...]) -> list[MeasureRecord]:
    return [
        MeasureRecord(time=_time(time), value=value, measure=Measure.ENERGY)
        for time, value in points
    ]


def _day_series(
    start_local: datetime,
    count: int,
    per_step: float,
    base: float,
    step: timedelta = timedelta(minutes=5),
) -> list[MeasureRecord]:
    start_utc = start_local.astimezone(UTC)
    return [
        MeasureRecord(
            time=start_utc + step * index,
            value=base + per_step * index,
            measure=Measure.ENERGY,
        )
        for index in range(count)
    ]


class TestHourlyBuckets:
    def test_every_increment_counts(self) -> None:
        records = _records(BOUNDARY_24_08)

        total = sum(bucket.consumption for bucket in hourly_buckets(records))

        assert total == 4772975.0 - 4767691.0

    def test_constant_rate_full_day(self) -> None:
        midnight = datetime(2026, 1, 15, 0, 0, tzinfo=BERLIN)
        records = _day_series(midnight, count=288, per_step=12.0, base=1000.0)

        buckets = hourly_buckets(records)

        assert len(buckets) == 24
        assert buckets[0].consumption == 11 * 12.0
        assert all(bucket.consumption == 144.0 for bucket in buckets[1:])

        total = sum(bucket.consumption for bucket in buckets)
        assert total == 287 * 12.0

    def test_buckets_are_on_the_top_of_the_utc_hour(self) -> None:
        records = _day_series(
            datetime(2026, 1, 15, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
            count=288,
            per_step=12.0,
            base=1000.0,
        )

        assert all(
            bucket.start.minute == 0
            and bucket.start.second == 0
            and bucket.start.microsecond == 0
            for bucket in hourly_buckets(records)
        )

    def test_increment_attributed_to_hour_of_end_reading(self) -> None:
        records = [
            MeasureRecord(
                time=datetime(2026, 1, 15, 10, 58, tzinfo=UTC),
                value=100.0,
                measure=Measure.ENERGY,
            ),
            MeasureRecord(
                time=datetime(2026, 1, 15, 10, 59, tzinfo=UTC),
                value=110.0,
                measure=Measure.ENERGY,
            ),
            MeasureRecord(
                time=datetime(2026, 1, 15, 11, 3, tzinfo=UTC),
                value=150.0,
                measure=Measure.ENERGY,
            ),
        ]

        buckets = {
            bucket.start: bucket.consumption for bucket in hourly_buckets(records)
        }

        assert buckets[datetime(2026, 1, 15, 11, 0, tzinfo=UTC)] == 40.0
        assert buckets[datetime(2026, 1, 15, 10, 0, tzinfo=UTC)] == 10.0

    def test_first_bucket_misses_only_the_increment_before_the_window(self) -> None:
        midnight = datetime(2026, 1, 15, 0, 0, tzinfo=UTC)
        full = _day_series(midnight, count=288, per_step=12.0, base=1000.0)

        window = hourly_buckets(full[24:])

        assert [bucket.consumption for bucket in window[1:]] == [144.0] * (
            len(window) - 2
        ) + [window[-1].consumption]

    def test_meter_is_last_raw_reading_of_bucket(self) -> None:
        midnight = datetime(2026, 1, 15, 0, 0, tzinfo=UTC)
        records = _day_series(midnight, count=24, per_step=10.0, base=500.0)

        buckets = hourly_buckets(records)

        assert buckets[0].meter == 500.0 + 10.0 * 11

    def test_decreasing_reading_ignored(self) -> None:
        midnight = datetime(2026, 1, 15, 0, 0, tzinfo=UTC)
        records = [
            *_day_series(midnight, count=6, per_step=10.0, base=1000.0),
            MeasureRecord(
                time=midnight + timedelta(minutes=30),
                value=5.0,
                measure=Measure.ENERGY,
            ),
        ]

        buckets = hourly_buckets(records)

        assert all(bucket.consumption >= 0 for bucket in buckets)

    def test_two_records_are_enough(self) -> None:
        midnight = datetime(2026, 1, 15, 0, 0, tzinfo=UTC)
        records = _day_series(midnight, count=2, per_step=12.0, base=1000.0)

        assert [bucket.consumption for bucket in hourly_buckets(records)] == [12.0]

    def test_too_few_records(self) -> None:
        assert hourly_buckets([]) == []
        assert (
            hourly_buckets(
                [
                    MeasureRecord(
                        time=_time("2026-01-01 00:00:00"),
                        value=1,
                        measure=Measure.ENERGY,
                    )
                ]
            )
            == []
        )


class TestCumulative:
    def test_monotonic_and_matching_deltas(self) -> None:
        midnight = datetime(2026, 1, 15, 0, 0, tzinfo=UTC)
        records = _day_series(midnight, count=288, per_step=12.0, base=1000.0)

        pairs = cumulative(hourly_buckets(records))
        totals = [total for _, total in pairs]

        assert totals == sorted(totals)
        for (bucket, total), (_, previous) in zip(pairs[1:], pairs):
            assert abs((total - previous) - bucket.consumption) < 1e-9

    def test_total_equals_meter_difference(self) -> None:
        midnight = datetime(2026, 1, 15, 0, 0, tzinfo=UTC)
        records = _day_series(midnight, count=2 * 288, per_step=12.0, base=1000.0)

        pairs = cumulative(hourly_buckets(records))

        assert pairs[-1][1] == records[-1].value - records[0].value

    def test_empty(self) -> None:
        assert cumulative([]) == []


class TestToSeries:
    def test_sorted_and_deduplicated(self) -> None:
        records = [
            MeasureRecord(
                time=_time("2026-01-01 02:00:00"), value=3, measure=Measure.ENERGY
            ),
            MeasureRecord(
                time=_time("2026-01-01 00:00:00"), value=1, measure=Measure.ENERGY
            ),
            MeasureRecord(
                time=_time("2026-01-01 00:00:00"), value=5, measure=Measure.ENERGY
            ),
        ]

        assert [value for _, value in to_series(records)] == [5, 3]

    def test_naive_times_become_utc(self) -> None:
        records = [
            MeasureRecord(
                time=datetime(2026, 1, 1, 0, 0), value=1, measure=Measure.ENERGY
            )
        ]

        assert to_series(records)[0][0].tzinfo is UTC
