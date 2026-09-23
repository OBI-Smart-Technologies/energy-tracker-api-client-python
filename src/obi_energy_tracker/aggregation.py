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

from dataclasses import dataclass
from datetime import UTC, datetime

from .models import MeasureRecord


@dataclass(frozen=True)
class HourlyBucket:
    start: datetime
    consumption: float
    meter: float


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def to_series(records: list[MeasureRecord]) -> list[tuple[datetime, float]]:
    by_time = {_as_utc(record.time): record.value for record in records}
    return sorted(by_time.items())


def _hour_start(moment: datetime) -> datetime:
    return moment.replace(minute=0, second=0, microsecond=0)


def hourly_buckets(records: list[MeasureRecord]) -> list[HourlyBucket]:
    series = to_series(records)
    if len(series) < 2:
        return []

    consumption: dict[datetime, float] = {}
    meters: dict[datetime, float] = {}
    previous_value: float | None = None

    for moment, value in series:
        bucket = _hour_start(moment)
        consumption.setdefault(bucket, 0.0)
        meters[bucket] = value

        if previous_value is not None:
            delta = value - previous_value
            if delta > 0:
                consumption[bucket] += delta
        previous_value = value

    return [
        HourlyBucket(start=start, consumption=consumption[start], meter=meters[start])
        for start in sorted(consumption)
    ]


def cumulative(buckets: list[HourlyBucket]) -> list[tuple[HourlyBucket, float]]:
    total = 0.0
    result: list[tuple[HourlyBucket, float]] = []
    for bucket in buckets:
        total += bucket.consumption
        result.append((bucket, total))
    return result
