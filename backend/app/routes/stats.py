"""Stats routes — daily averages, weekly averages, heatmap data.

Per-day rollups are delegated to `services.aggregators.aggregate_by_day`
so the same kernel is shared with the reflection service.
"""

from collections import defaultdict
from datetime import date as date_t, datetime, timedelta, timezone

from fastapi import APIRouter

from ..services.aggregators import DailyAggregate, aggregate_by_day
from ..storage import list_entries

router = APIRouter()


def _index_by_date(aggregates: list[DailyAggregate]) -> dict[date_t, DailyAggregate]:
    return {a.date: a for a in aggregates}


@router.get("/stats/daily")
def daily_stats():
    """Daily mood & energy averages for the last 14 days."""
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=13)
    entries = list_entries(start_date=str(start))
    by_date = _index_by_date(aggregate_by_day(entries))

    result = []
    for i in range(14):
        day = start + timedelta(days=i)
        agg = by_date.get(day)
        result.append(
            {
                "date": str(day),
                "avg_mood": agg.avg_mood if agg else None,
                "avg_energy": agg.avg_energy if agg else None,
                "count": agg.count if agg else 0,
            }
        )
    return result


@router.get("/stats/weekly")
def weekly_stats():
    """Weekly mood & energy averages for the last 8 weeks.

    Per-day aggregates come from the shared kernel; we then bucket them
    by ISO week-start (Monday) and take a count-weighted mean so the
    week's average matches what raw averaging would produce.
    """
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(weeks=8)
    entries = list_entries(start_date=str(start))

    aggregates = aggregate_by_day(entries)
    by_week: dict[date_t, list[DailyAggregate]] = defaultdict(list)
    for a in aggregates:
        week_start = a.date - timedelta(days=a.date.weekday())
        by_week[week_start].append(a)

    result = []
    for i in range(8):
        anchor = start + timedelta(weeks=i)
        week_start = anchor - timedelta(days=anchor.weekday())
        week_aggs = by_week.get(week_start, [])
        if week_aggs:
            total = sum(a.count for a in week_aggs)
            avg_mood = round(
                sum(a.avg_mood * a.count for a in week_aggs) / total, 1
            )
            avg_energy = round(
                sum(a.avg_energy * a.count for a in week_aggs) / total, 1
            )
            count = total
        else:
            avg_mood = None
            avg_energy = None
            count = 0
        result.append(
            {
                "week_start": str(week_start),
                "avg_mood": avg_mood,
                "avg_energy": avg_energy,
                "count": count,
            }
        )
    return result


@router.get("/stats/heatmap")
def heatmap_data():
    """Calendar heatmap data — average mood per day for the last 90 days."""
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=89)
    entries = list_entries(start_date=str(start))
    by_date = _index_by_date(aggregate_by_day(entries))

    result = []
    for i in range(90):
        day = start + timedelta(days=i)
        agg = by_date.get(day)
        result.append(
            {
                "date": str(day),
                "avg_mood": agg.avg_mood if agg else None,
                "count": agg.count if agg else 0,
            }
        )
    return result
