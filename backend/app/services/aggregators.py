"""Daily aggregation kernel.

Shared by `routes/stats.py` and `services/reflection.py` for grouping
entries by calendar date and computing per-day mean mood and mean energy.
Pure function: no I/O, no clock, no global state.

This is the seam called out in the PRD's "Further Notes" — the same
`defaultdict(list)` → group-by-day → `sum/len` pattern was duplicated
across four callers; this module is the one place that pattern lives now.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from ..models.entry import Entry


@dataclass(frozen=True)
class DailyAggregate:
    """A single day's rollup: averages and entry count for one calendar date."""

    date: date
    avg_mood: float
    avg_energy: float
    count: int


def aggregate_by_day(entries: list[Entry]) -> list[DailyAggregate]:
    """Group entries by calendar date and compute per-day averages.

    Returns one `DailyAggregate` per day that has at least one entry,
    sorted ascending by date. Averages are rounded to one decimal place.

    Days with no entries are not represented in the output — callers that
    need a "dense" series over a date range are responsible for filling
    gaps themselves.
    """
    by_day: dict[date, list[Entry]] = defaultdict(list)
    for entry in entries:
        by_day[entry.timestamp.date()].append(entry)

    aggregates: list[DailyAggregate] = []
    for day, items in by_day.items():
        aggregates.append(
            DailyAggregate(
                date=day,
                avg_mood=round(sum(i.mood for i in items) / len(items), 1),
                avg_energy=round(sum(i.energy for i in items) / len(items), 1),
                count=len(items),
            )
        )
    aggregates.sort(key=lambda a: a.date)
    return aggregates
