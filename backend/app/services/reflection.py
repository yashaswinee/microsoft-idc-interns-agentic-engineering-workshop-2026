"""Weekly reflection digest service.

Pure functions only — no I/O, no global state. The route layer is responsible
for fetching entries and supplying `now`; this module turns them into a
`WeeklyReflection` payload.

Supports `normal`, `sparse`, `empty`, and `tough` modes with context-aware
reflection prompts bucketed by mode and trend. Daily aggregation is delegated
to `services.aggregators` so the same kernel is shared with the stats routes.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

from ..models.entry import Entry
from ..models.reflection import (
    DayAverage,
    ReflectionWindow,
    TagCount,
    TrendInfo,
    WeeklyReflection,
)
from .aggregators import DailyAggregate, aggregate_by_day

WINDOW_DAYS = 7
TREND_FLAT_BAND = 0.1
MIN_DAYS_FOR_TREND = 3
TOP_TAGS_MAX = 3
TOP_TAGS_MIN_COUNT = 2

# Tough-mode classification thresholds. The avg-mood rule fires on its own;
# the trend rule fires only when the last day in the window is also low,
# so a brief bad day doesn't drag a recovering week into tough mode.
TOUGH_AVG_MOOD_MAX = 2.0
TOUGH_LAST_DAY_MOOD_MAX = 2.5

EMPTY_PROMPT = (
    "No entries in the past 7 days. Start with how you're feeling right now."
)
SHARE_FOOTER = "— Shared from Pulse"

# Context-aware reflection prompts. Five buckets keyed off the digest's
# `mode` and `trend`. Within a bucket, selection rotates by the window
# start date so the same week always yields the same prompt and successive
# weeks vary.
#
# The `tough` bucket deliberately avoids any phrasing that implies blame
# ("what would you do differently?"); gentlest phrasings only. The `empty`
# mode keeps its own dedicated empty-state line above and is not bucketed.
_PROMPTS: dict[str, list[str]] = {
    "improving": [
        "What helped this week that you want to carry forward?",
        "Which moment stood out as the high point — and why?",
        "What habit gave you the most lift this week?",
    ],
    "declining": [
        "What felt the heaviest this week, and what made it heavier?",
        "If you could rewind one moment, which would it be?",
        "Is there one small thing you can shift before next week begins?",
    ],
    "flat": [
        "What would you do differently next week?",
        "Was there a moment that surprised you in either direction?",
        "What's something new you'd like to try in the days ahead?",
    ],
    "tough": [
        "What's one small thing that helped, even a little?",
        "Who or what felt steadying this week?",
        "If next week were one degree gentler, what would that look like?",
    ],
    "sparse": [
        "What stood out about the moments you did capture?",
        "What would make it easier to log how you're feeling?",
        "If today were a fresh start, what would you want to notice?",
    ],
}

# Tag-free fallback for the tough-mode suggestion. Deliberately concrete and
# user-driven — no generic wellbeing tips, no clinical or crisis-resource
# language.
TOUGH_SUGGESTION_FALLBACK = (
    "Pick one small thing — sleep, a walk, a message to someone — and try "
    "it once."
)

# Hand-written narrative templates, indexed by "shape". Tracer-bullet uses
# a single shape per trend label; richer shape classification (recovered,
# dipped, volatile) is planned for follow-up issues.
_NARRATIVES: dict[str, list[str]] = {
    "improving": [
        "Your mood trended upward across the week — something is working.",
        "The line moved in a good direction this stretch; keep noticing what helped.",
        "A gentle climb in mood this week. Worth pausing on what shifted.",
    ],
    "declining": [
        "Mood drifted down across the week. Easy to miss in the moment — now it's visible.",
        "The slope tipped downward this stretch. A small reset might be worth a try.",
        "Energy and mood eased lower this week; consider what felt heaviest.",
    ],
    "flat": [
        "Things held steady this week — a quiet kind of consistency.",
        "Mood stayed level across the week. Steady isn't nothing.",
        "A flat line this stretch — neither up nor down, just present.",
    ],
}

# Sparse-mode narratives: gentle, no superlatives, no negative labels about
# how often the user logged. Picked deterministically via the last day in
# the window so the same week always yields the same sentence.
_SPARSE_NARRATIVES: list[str] = [
    "A quiet week in the log — even a few entries help paint a picture.",
    "Just a handful of moments captured this stretch. Each one counts.",
    "A light week of entries; the pattern starts wherever you pick it up.",
]

# Tough-mode narratives: softened voice, forward-looking. None contain the
# strings "worst", "lowest", "rough", or "bad week" (asserted by tests), and
# none make cross-week comparisons. Each ends on a steadying note.
_TOUGH_NARRATIVES: list[str] = [
    "It's been a heavier stretch — small steps still count from here.",
    "A weighty week in the log. Even noticing it is a kind of progress.",
    "Mood eased downward this stretch; gentle next steps are enough.",
]


def _window_bounds(now: datetime) -> tuple[date, date]:
    end = now.date()
    start = end - timedelta(days=WINDOW_DAYS - 1)
    return start, end


def _filter_to_window(entries: list[Entry], now: datetime) -> list[Entry]:
    start, end = _window_bounds(now)
    return [e for e in entries if start <= e.timestamp.date() <= end]


def _least_squares_slope(
    daily: list[DailyAggregate], start: date
) -> Optional[float]:
    """Slope of daily-mean mood over the day index (0..6) for days with entries."""
    if len(daily) < MIN_DAYS_FOR_TREND:
        return None
    xs = [(a.date - start).days for a in daily]
    ys = [a.avg_mood for a in daily]
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _trend(daily: list[DailyAggregate], start: date) -> TrendInfo:
    slope = _least_squares_slope(daily, start)
    if slope is None:
        return TrendInfo(label="insufficient_data", slope=None)
    if slope > TREND_FLAT_BAND:
        label = "improving"
    elif slope < -TREND_FLAT_BAND:
        label = "declining"
    else:
        label = "flat"
    return TrendInfo(label=label, slope=round(slope, 4))


def _best_day(daily: list[DailyAggregate]) -> Optional[DayAverage]:
    if not daily:
        return None
    # Tie-break to most recent date: iterate in chronological order so later
    # days replace earlier ties when mood is equal.
    chosen = daily[0]
    for a in daily[1:]:
        if a.avg_mood >= chosen.avg_mood:
            chosen = a
    return DayAverage(date=str(chosen.date), avg_mood=round(chosen.avg_mood, 1))


def _worst_day(daily: list[DailyAggregate]) -> Optional[DayAverage]:
    if not daily:
        return None
    chosen = daily[0]
    for a in daily[1:]:
        if a.avg_mood <= chosen.avg_mood:
            chosen = a
    return DayAverage(date=str(chosen.date), avg_mood=round(chosen.avg_mood, 1))


def _top_tags(entries: list[Entry]) -> list[TagCount]:
    counts: dict[str, int] = defaultdict(int)
    for e in entries:
        for tag in e.tags:
            counts[tag] += 1
    qualifying = [
        (tag, count) for tag, count in counts.items() if count >= TOP_TAGS_MIN_COUNT
    ]
    qualifying.sort(key=lambda pair: (-pair[1], pair[0]))
    return [TagCount(tag=t, count=c) for t, c in qualifying[:TOP_TAGS_MAX]]


def _classify_shape(trend: TrendInfo) -> str:
    if trend.label in _NARRATIVES:
        return trend.label
    return "flat"


def _select_narrative(
    daily: list[DailyAggregate], trend: TrendInfo, mode: str
) -> Optional[str]:
    if mode == "empty":
        return None
    if mode == "sparse":
        templates = _SPARSE_NARRATIVES
    elif mode == "tough":
        templates = _TOUGH_NARRATIVES
    else:
        templates = _NARRATIVES[_classify_shape(trend)]
    # Deterministic pick keyed off the last day in the window so the same
    # week always yields the same narrative.
    if daily:
        index = daily[-1].date.toordinal() % len(templates)
    else:
        index = 0
    return templates[index]


def _prompt_bucket_for(mode: str, trend: TrendInfo) -> str:
    """Route a (mode, trend) to one of the five prompt bucket keys.

    `empty` mode is handled separately by the caller and never reaches this
    function.
    """
    if mode == "tough":
        return "tough"
    if mode == "sparse":
        return "sparse"
    if trend.label == "improving":
        return "improving"
    if trend.label == "declining":
        return "declining"
    # Both `flat` and `insufficient_data` (e.g. normal mode with thin data
    # right at the 3-day boundary) collapse into the flat bucket.
    return "flat"


def _select_prompt(
    mode: str, trend: TrendInfo, window_start: date
) -> Optional[str]:
    """Pick a reflection prompt from the bucket implied by mode + trend.

    Selection within a bucket is deterministic given `window_start` so the
    same calendar week always yields the same prompt; successive weeks
    rotate.
    """
    if mode == "empty":
        return EMPTY_PROMPT
    bucket = _PROMPTS[_prompt_bucket_for(mode, trend)]
    return bucket[window_start.toordinal() % len(bucket)]


def select_suggestion(top_tags: list[TagCount], mode: str) -> Optional[str]:
    """Return the tough-mode suggestion line, or None for other modes.

    Tag-grounded when a top tag exists; otherwise a concrete, user-driven
    fallback. No generic wellbeing tips, no clinical or crisis-resource
    content.
    """
    if mode != "tough":
        return None
    if top_tags:
        primary = top_tags[0].tag
        return (
            f"You logged {primary} often this stretch — one more this week, "
            f"if you can?"
        )
    return TOUGH_SUGGESTION_FALLBACK


def _trend_label_to_words(label: str) -> str:
    return {
        "improving": "trending up",
        "declining": "trending down",
        "flat": "holding steady",
        "insufficient_data": "not enough data yet",
    }.get(label, label)


def _format_share_text(
    *,
    window: ReflectionWindow,
    avg_mood: Optional[float],
    avg_energy: Optional[float],
    trend: TrendInfo,
    top_tags: list[TagCount],
    narrative: str,
    best_day: Optional[DayAverage],
    worst_day: Optional[DayAverage],
) -> str:
    lines = [f"Pulse — week of {window.start} to {window.end}"]
    if avg_mood is not None and avg_energy is not None:
        lines.append(f"Avg mood {avg_mood}/5 · Avg energy {avg_energy}/10")
    lines.append(f"Trend: {_trend_label_to_words(trend.label)}")
    if best_day is not None:
        lines.append(f"Best day: {best_day.date}")
    if worst_day is not None:
        lines.append(f"Toughest day: {worst_day.date}")
    if top_tags:
        lines.append("Top tags: " + ", ".join(t.tag for t in top_tags))
    lines.append(narrative)
    lines.append(SHARE_FOOTER)
    return "\n".join(lines)


def _classify_mode(
    daily: list[DailyAggregate],
    entry_count: int,
    avg_mood: Optional[float],
    trend: TrendInfo,
) -> str:
    if entry_count == 0:
        return "empty"
    if len(daily) < MIN_DAYS_FOR_TREND:
        return "sparse"
    if avg_mood is not None and avg_mood <= TOUGH_AVG_MOOD_MAX:
        return "tough"
    if (
        trend.label == "declining"
        and daily
        and daily[-1].avg_mood <= TOUGH_LAST_DAY_MOOD_MAX
    ):
        return "tough"
    return "normal"


def build_weekly_reflection(
    entries: list[Entry], now: datetime
) -> WeeklyReflection:
    """Build the weekly reflection digest from a list of entries.

    Pure function: no clock access, no I/O. Caller provides `now`.
    """
    start_date, end_date = _window_bounds(now)
    in_window = _filter_to_window(entries, now)
    daily = aggregate_by_day(in_window)

    window = ReflectionWindow(start=str(start_date), end=str(end_date))
    entry_count = len(in_window)
    days_with_entries = len(daily)

    if entry_count == 0:
        return WeeklyReflection(
            window=window,
            entry_count=0,
            days_with_entries=0,
            mode="empty",
            avg_mood=None,
            avg_energy=None,
            trend=TrendInfo(label="insufficient_data", slope=None),
            best_day=None,
            worst_day=None,
            top_tags=[],
            narrative=None,
            suggestion=None,
            reflection_prompt=_select_prompt("empty"),
            share_text=None,
        )

    avg_mood: Optional[float] = round(
        sum(e.mood for e in in_window) / entry_count, 1
    )
    avg_energy: Optional[float] = round(
        sum(e.energy for e in in_window) / entry_count, 1
    )

    trend = _trend(daily, start_date)
    top_tags = _top_tags(in_window)
    mode = _classify_mode(daily, entry_count, avg_mood, trend)
    narrative = _select_narrative(daily, trend, mode)
    suggestion = select_suggestion(top_tags, mode)
    reflection_prompt = _select_prompt(mode, trend, start_date)

    # Sparse mode suppresses best/worst day in both payload and share text.
    # Tough mode keeps them in the payload (the in-app card still shows them)
    # but suppresses them in share text so recipients don't see which day
    # was lowest.
    raw_best = _best_day(daily)
    raw_worst = _worst_day(daily)
    if mode == "sparse":
        payload_best: Optional[DayAverage] = None
        payload_worst: Optional[DayAverage] = None
        share_best: Optional[DayAverage] = None
        share_worst: Optional[DayAverage] = None
    elif mode == "tough":
        payload_best = raw_best
        payload_worst = raw_worst
        share_best = None
        share_worst = None
    else:
        payload_best = raw_best
        payload_worst = raw_worst
        share_best = raw_best
        share_worst = raw_worst

    share_text = _format_share_text(
        window=window,
        avg_mood=avg_mood,
        avg_energy=avg_energy,
        trend=trend,
        top_tags=top_tags,
        narrative=narrative or "",
        best_day=share_best,
        worst_day=share_worst,
    )

    return WeeklyReflection(
        window=window,
        entry_count=entry_count,
        days_with_entries=days_with_entries,
        mode=mode,
        avg_mood=avg_mood,
        avg_energy=avg_energy,
        trend=trend,
        best_day=payload_best,
        worst_day=payload_worst,
        top_tags=top_tags,
        narrative=narrative,
        suggestion=suggestion,
        reflection_prompt=reflection_prompt,
        share_text=share_text,
    )
