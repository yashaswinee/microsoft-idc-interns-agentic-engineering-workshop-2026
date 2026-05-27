"""Unit tests for the daily aggregation kernel."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from app.models.entry import Entry
from app.services.aggregators import DailyAggregate, aggregate_by_day


def _entry(
    *,
    when: datetime,
    mood: int,
    energy: int = 6,
    tags: Optional[list[str]] = None,
) -> Entry:
    return Entry(
        id=str(uuid4()),
        mood=mood,
        energy=energy,
        note=None,
        tags=tags or [],
        timestamp=when,
    )


def _midday(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, 12, 0, 0, tzinfo=timezone.utc)


class TestAggregateByDay:
    def test_empty_input_returns_empty_list(self):
        assert aggregate_by_day([]) == []

    def test_single_day_single_entry(self):
        when = _midday(2026, 4, 15)
        entries = [_entry(when=when, mood=4, energy=8)]
        result = aggregate_by_day(entries)
        assert len(result) == 1
        agg = result[0]
        assert isinstance(agg, DailyAggregate)
        assert agg.date == when.date()
        assert agg.avg_mood == 4.0
        assert agg.avg_energy == 8.0
        assert agg.count == 1

    def test_single_day_multiple_entries_average_correctly(self):
        when = _midday(2026, 4, 15)
        entries = [
            _entry(when=when, mood=2, energy=4),
            _entry(when=when + timedelta(hours=1), mood=4, energy=8),
        ]
        result = aggregate_by_day(entries)
        assert len(result) == 1
        agg = result[0]
        assert agg.avg_mood == 3.0
        assert agg.avg_energy == 6.0
        assert agg.count == 2

    def test_multi_day_input_returns_one_aggregate_per_day(self):
        d0 = _midday(2026, 4, 13)
        d1 = _midday(2026, 4, 14)
        d2 = _midday(2026, 4, 15)
        entries = [
            _entry(when=d0, mood=3, energy=5),
            _entry(when=d1, mood=4, energy=6),
            _entry(when=d1 + timedelta(hours=2), mood=2, energy=4),
            _entry(when=d2, mood=5, energy=7),
        ]
        result = aggregate_by_day(entries)
        assert len(result) == 3

    def test_results_sorted_ascending_by_date(self):
        d_early = _midday(2026, 4, 10)
        d_mid = _midday(2026, 4, 12)
        d_late = _midday(2026, 4, 15)
        # Insert out of chronological order.
        entries = [
            _entry(when=d_late, mood=4),
            _entry(when=d_early, mood=3),
            _entry(when=d_mid, mood=5),
        ]
        result = aggregate_by_day(entries)
        dates = [a.date for a in result]
        assert dates == [d_early.date(), d_mid.date(), d_late.date()]

    def test_averages_rounded_to_one_decimal(self):
        when = _midday(2026, 4, 15)
        # mood: 3 + 4 + 4 = 11, /3 = 3.6666… → 3.7
        # energy: 5 + 6 + 6 = 17, /3 = 5.6666… → 5.7
        entries = [
            _entry(when=when, mood=3, energy=5),
            _entry(when=when + timedelta(hours=1), mood=4, energy=6),
            _entry(when=when + timedelta(hours=2), mood=4, energy=6),
        ]
        result = aggregate_by_day(entries)
        assert len(result) == 1
        agg = result[0]
        assert agg.avg_mood == 3.7
        assert agg.avg_energy == 5.7

    def test_entries_with_same_calendar_date_grouped_across_times_of_day(self):
        # Three entries at 00:30, 12:00, 23:30 on the same date collapse
        # into one aggregate.
        d = _midday(2026, 4, 15).date()
        early = datetime(d.year, d.month, d.day, 0, 30, tzinfo=timezone.utc)
        noon = datetime(d.year, d.month, d.day, 12, 0, tzinfo=timezone.utc)
        late = datetime(d.year, d.month, d.day, 23, 30, tzinfo=timezone.utc)
        entries = [
            _entry(when=early, mood=2),
            _entry(when=noon, mood=4),
            _entry(when=late, mood=3),
        ]
        result = aggregate_by_day(entries)
        assert len(result) == 1
        assert result[0].count == 3
        assert result[0].date == d
