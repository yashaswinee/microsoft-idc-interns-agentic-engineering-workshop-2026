"""Unit tests for the weekly reflection service (tracer-bullet: normal mode only)."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

import pytest

from app.models.entry import Entry
from app.services.reflection import build_weekly_reflection


def _entry(
    *,
    when: datetime,
    mood: int,
    energy: int = 6,
    tags: Optional[list[str]] = None,
    note: Optional[str] = None,
) -> Entry:
    return Entry(
        id=str(uuid4()),
        mood=mood,
        energy=energy,
        note=note,
        tags=tags or [],
        timestamp=when,
    )


def _fixed_now() -> datetime:
    # Wednesday, 2026-04-15 12:00 UTC
    return datetime(2026, 4, 15, 12, 0, 0, tzinfo=timezone.utc)


def _week_dates(now: datetime) -> list[datetime]:
    """Return the 7 daily timestamps inside the rolling window ending today."""
    end = now.date()
    return [
        datetime.combine(end - timedelta(days=i), datetime.min.time(), tzinfo=timezone.utc)
        + timedelta(hours=10)
        for i in range(6, -1, -1)
    ]


class TestNormalMode:
    def test_full_week_returns_normal_mode(self):
        now = _fixed_now()
        moods = [3, 3, 4, 4, 4, 3, 4]
        entries = [
            _entry(when=ts, mood=m, tags=["sleep", "exercise"])
            for ts, m in zip(_week_dates(now), moods)
        ]
        result = build_weekly_reflection(entries, now)

        assert result.mode == "normal"
        assert result.entry_count == 7
        assert result.days_with_entries == 7
        assert result.window.start == str(now.date() - timedelta(days=6))
        assert result.window.end == str(now.date())
        assert result.narrative is not None and result.narrative.strip() != ""
        assert result.share_text is not None
        assert result.share_text.rstrip().endswith("— Shared from Pulse")
        assert result.suggestion is None
        # Reflection prompt is now picked from a bucket keyed off mode + trend;
        # full bucket-routing behavior is exercised in TestPromptBuckets below.
        assert result.reflection_prompt is not None
        assert result.reflection_prompt.endswith("?")

    def test_averages_rounded_to_one_decimal(self):
        now = _fixed_now()
        # mood 3,3,4,4,4,3,4 -> avg = 25/7 ≈ 3.571 → 3.6
        # energy all 6 -> avg 6.0
        moods = [3, 3, 4, 4, 4, 3, 4]
        entries = [
            _entry(when=ts, mood=m, energy=6)
            for ts, m in zip(_week_dates(now), moods)
        ]
        result = build_weekly_reflection(entries, now)
        assert result.avg_mood == 3.6
        assert result.avg_energy == 6.0


class TestTrendSlope:
    def _build_daily_moods(self, daily_moods: list[int]) -> tuple[list[Entry], datetime]:
        now = _fixed_now()
        days = _week_dates(now)
        entries = [
            _entry(when=ts, mood=m) for ts, m in zip(days, daily_moods)
        ]
        return entries, now

    def test_improving_slope_labeled_improving(self):
        # Strongly improving: 1,2,2,3,3,4,5 → slope > +0.1
        entries, now = self._build_daily_moods([1, 2, 2, 3, 3, 4, 5])
        result = build_weekly_reflection(entries, now)
        assert result.trend.label == "improving"
        assert result.trend.slope is not None
        assert result.trend.slope > 0.1

    def test_declining_slope_labeled_declining(self):
        entries, now = self._build_daily_moods([5, 4, 4, 3, 3, 2, 1])
        result = build_weekly_reflection(entries, now)
        assert result.trend.label == "declining"
        assert result.trend.slope is not None
        assert result.trend.slope < -0.1

    def test_flat_slope_labeled_flat(self):
        entries, now = self._build_daily_moods([3, 3, 3, 3, 3, 3, 3])
        result = build_weekly_reflection(entries, now)
        assert result.trend.label == "flat"
        assert result.trend.slope is not None
        assert abs(result.trend.slope) <= 0.1


class TestBestWorstDay:
    def test_best_and_worst_day_picked_by_daily_mean(self):
        now = _fixed_now()
        days = _week_dates(now)
        moods = [3, 5, 3, 1, 3, 3, 3]  # day index 1 best (5), day index 3 worst (1)
        entries = [_entry(when=ts, mood=m) for ts, m in zip(days, moods)]
        result = build_weekly_reflection(entries, now)
        assert result.best_day is not None
        assert result.worst_day is not None
        assert result.best_day.date == str(days[1].date())
        assert result.worst_day.date == str(days[3].date())

    def test_ties_resolve_to_most_recent_date(self):
        now = _fixed_now()
        days = _week_dates(now)
        # All days have same mean mood; best/worst should both be the most recent date.
        entries = [_entry(when=ts, mood=4) for ts in days]
        result = build_weekly_reflection(entries, now)
        most_recent = str(days[-1].date())
        assert result.best_day is not None and result.best_day.date == most_recent
        assert result.worst_day is not None and result.worst_day.date == most_recent


class TestTopTags:
    def test_top_tags_alphabetical_tiebreak_and_min2_threshold(self):
        now = _fixed_now()
        days = _week_dates(now)
        # exercise: 3, caffeine: 3, sleep: 3, outdoors: 2, lunch: 1 (excluded by min-2).
        # Top 3 by count then alphabetical tie-break => caffeine, exercise, sleep.
        tags_per_day = [
            ["exercise", "caffeine", "sleep"],
            ["exercise", "caffeine", "sleep"],
            ["exercise", "caffeine", "sleep"],
            ["outdoors"],
            ["outdoors"],
            ["lunch"],
            [],
        ]
        entries = [
            _entry(when=ts, mood=3, tags=t) for ts, t in zip(days, tags_per_day)
        ]
        result = build_weekly_reflection(entries, now)
        assert [t.tag for t in result.top_tags] == ["caffeine", "exercise", "sleep"]
        assert all(t.count >= 2 for t in result.top_tags)

    def test_top_tags_max_three_returned(self):
        now = _fixed_now()
        days = _week_dates(now)
        # 4 tags each at count 3 — only 3 returned (alphabetical first).
        tags_per_day = [
            ["alpha", "beta", "gamma", "delta"],
            ["alpha", "beta", "gamma", "delta"],
            ["alpha", "beta", "gamma", "delta"],
            [], [], [], [],
        ]
        entries = [
            _entry(when=ts, mood=3, tags=t) for ts, t in zip(days, tags_per_day)
        ]
        result = build_weekly_reflection(entries, now)
        assert len(result.top_tags) == 3
        assert [t.tag for t in result.top_tags] == ["alpha", "beta", "delta"]

    def test_tag_below_min2_threshold_excluded(self):
        now = _fixed_now()
        days = _week_dates(now)
        entries = [
            _entry(when=days[0], mood=3, tags=["solo"]),
            _entry(when=days[1], mood=3, tags=["pair"]),
            _entry(when=days[2], mood=3, tags=["pair"]),
            _entry(when=days[3], mood=3, tags=[]),
            _entry(when=days[4], mood=3, tags=[]),
            _entry(when=days[5], mood=3, tags=[]),
            _entry(when=days[6], mood=3, tags=[]),
        ]
        result = build_weekly_reflection(entries, now)
        tag_names = [t.tag for t in result.top_tags]
        assert "solo" not in tag_names
        assert "pair" in tag_names


class TestShareText:
    def test_share_text_has_attribution_footer(self):
        now = _fixed_now()
        entries = [
            _entry(when=ts, mood=4, tags=["sleep"]) for ts in _week_dates(now)
        ]
        result = build_weekly_reflection(entries, now)
        assert result.share_text is not None
        assert result.share_text.rstrip().endswith("— Shared from Pulse")

    def test_share_text_excludes_note_field(self):
        now = _fixed_now()
        secret = "this-private-note-should-not-leak"
        entries = [
            _entry(when=ts, mood=4, tags=["sleep"], note=secret)
            for ts in _week_dates(now)
        ]
        result = build_weekly_reflection(entries, now)
        assert result.share_text is not None
        assert secret not in result.share_text

    def test_share_text_is_plain_text_not_markdown(self):
        now = _fixed_now()
        entries = [_entry(when=ts, mood=4, tags=["sleep"]) for ts in _week_dates(now)]
        result = build_weekly_reflection(entries, now)
        assert result.share_text is not None
        # No Markdown emphasis / headings / links / bullets.
        for token in ("**", "__", "##", "](", "* ", "- ["):
            assert token not in result.share_text, f"share_text contains markdown token {token!r}"

    def test_share_text_omits_reflection_prompt_and_suggestion(self):
        now = _fixed_now()
        entries = [_entry(when=ts, mood=4, tags=["sleep"]) for ts in _week_dates(now)]
        result = build_weekly_reflection(entries, now)
        assert result.share_text is not None
        assert "What would you do differently" not in result.share_text


class TestNarrative:
    def test_narrative_has_no_superlatives(self):
        now = _fixed_now()
        entries = [_entry(when=ts, mood=4, tags=["sleep"]) for ts in _week_dates(now)]
        result = build_weekly_reflection(entries, now)
        assert result.narrative is not None
        lowered = result.narrative.lower()
        for forbidden in ("worst", "lowest", "best week ever", "last week"):
            assert forbidden not in lowered


class TestEmptyMode:
    def test_empty_window_returns_empty_mode(self):
        now = _fixed_now()
        result = build_weekly_reflection([], now)

        assert result.mode == "empty"
        assert result.entry_count == 0
        assert result.days_with_entries == 0
        assert result.avg_mood is None
        assert result.avg_energy is None
        assert result.best_day is None
        assert result.worst_day is None
        assert result.narrative is None
        assert result.suggestion is None
        assert result.share_text is None
        assert result.top_tags == []
        assert result.trend.label == "insufficient_data"
        assert result.trend.slope is None
        # Empty-state prompt is the only non-null narrative-ish field.
        assert result.reflection_prompt is not None
        assert result.reflection_prompt.strip() != ""

    def test_entries_outside_window_treated_as_empty(self):
        now = _fixed_now()
        old = _entry(when=now - timedelta(days=30), mood=4, tags=["sleep"])
        result = build_weekly_reflection([old], now)
        assert result.mode == "empty"
        assert result.entry_count == 0
        assert result.share_text is None


class TestSparseMode:
    def test_one_day_with_entries_is_sparse(self):
        now = _fixed_now()
        days = _week_dates(now)
        entries = [_entry(when=days[3], mood=4, energy=7, tags=["sleep"])]
        result = build_weekly_reflection(entries, now)

        assert result.mode == "sparse"
        assert result.entry_count == 1
        assert result.days_with_entries == 1
        assert result.avg_mood == 4.0
        assert result.avg_energy == 7.0
        assert result.best_day is None
        assert result.worst_day is None
        assert result.trend.label == "insufficient_data"
        assert result.trend.slope is None
        assert result.suggestion is None
        assert result.narrative is not None and result.narrative.strip() != ""
        assert result.reflection_prompt is not None
        # min-2 threshold: a single tag occurrence is excluded.
        assert result.top_tags == []

    def test_two_days_with_entries_is_sparse(self):
        now = _fixed_now()
        days = _week_dates(now)
        entries = [
            _entry(when=days[2], mood=3, energy=5, tags=["sleep"]),
            _entry(when=days[5], mood=4, energy=7, tags=["sleep"]),
        ]
        result = build_weekly_reflection(entries, now)

        assert result.mode == "sparse"
        assert result.entry_count == 2
        assert result.days_with_entries == 2
        assert result.avg_mood == 3.5
        assert result.avg_energy == 6.0
        assert result.best_day is None
        assert result.worst_day is None
        assert result.trend.label == "insufficient_data"
        assert result.trend.slope is None
        # Same tag on both days clears the min-2 threshold.
        assert [t.tag for t in result.top_tags] == ["sleep"]

    def test_sparse_share_text_omits_best_and_worst_day_lines(self):
        now = _fixed_now()
        days = _week_dates(now)
        entries = [
            _entry(when=days[1], mood=3, energy=5),
            _entry(when=days[4], mood=4, energy=7),
        ]
        result = build_weekly_reflection(entries, now)

        assert result.share_text is not None
        assert result.share_text.rstrip().endswith("— Shared from Pulse")
        lowered = result.share_text.lower()
        assert "best day" not in lowered
        assert "toughest day" not in lowered
        # Averages must still appear.
        assert "Avg mood" in result.share_text
        assert "Avg energy" in result.share_text

    def test_sparse_narrative_has_no_negative_labels_or_superlatives(self):
        now = _fixed_now()
        days = _week_dates(now)
        # Try all 7 possible "last day" positions so we exercise every template.
        for i in range(7):
            entries = [_entry(when=days[i], mood=3)]
            result = build_weekly_reflection(entries, now)
            assert result.narrative is not None
            lowered = result.narrative.lower()
            for forbidden in (
                "worst",
                "lowest",
                "rough week",
                "bad week",
                "only logged",
                "only twice",
                "only once",
            ):
                assert forbidden not in lowered, (
                    f"sparse narrative {result.narrative!r} contains forbidden {forbidden!r}"
                )

    def test_sparse_share_text_includes_sparse_narrative(self):
        now = _fixed_now()
        days = _week_dates(now)
        entries = [_entry(when=days[3], mood=4, energy=7)]
        result = build_weekly_reflection(entries, now)
        assert result.share_text is not None
        assert result.narrative is not None
        assert result.narrative in result.share_text


class TestToughMode:
    def test_full_week_avg_mood_2_is_tough(self):
        now = _fixed_now()
        days = _week_dates(now)
        entries = [
            _entry(when=ts, mood=2, energy=4, tags=["outdoors"]) for ts in days
        ]
        result = build_weekly_reflection(entries, now)

        assert result.mode == "tough"
        assert result.suggestion is not None
        assert result.suggestion.strip() != ""

    def test_declining_trend_ending_at_25_is_tough(self):
        now = _fixed_now()
        days = _week_dates(now)
        # Overall avg is comfortably above 2.0 so the trend rule is what
        # triggers tough mode. Two entries on the last day average to 2.5.
        entries = [
            _entry(when=days[0], mood=5),
            _entry(when=days[1], mood=5),
            _entry(when=days[2], mood=4),
            _entry(when=days[3], mood=4),
            _entry(when=days[4], mood=3),
            _entry(when=days[5], mood=3),
            _entry(when=days[6], mood=2),
            _entry(when=days[6], mood=3),
        ]
        result = build_weekly_reflection(entries, now)
        assert result.trend.label == "declining"
        assert result.mode == "tough"
        assert result.avg_mood is not None and result.avg_mood > 2.0

    def test_tough_takes_precedence_over_normal(self):
        # avg_mood == 2.0 with no clear decline should still classify as tough.
        now = _fixed_now()
        days = _week_dates(now)
        entries = [_entry(when=ts, mood=2) for ts in days]
        result = build_weekly_reflection(entries, now)
        assert result.mode == "tough"

    def test_sparse_takes_precedence_over_tough(self):
        # Two days with very low mood would otherwise be tough, but
        # sparse must win because the trend window is too short.
        now = _fixed_now()
        days = _week_dates(now)
        entries = [
            _entry(when=days[2], mood=1),
            _entry(when=days[5], mood=1),
        ]
        result = build_weekly_reflection(entries, now)
        assert result.mode == "sparse"

    def test_empty_takes_precedence_over_tough(self):
        now = _fixed_now()
        result = build_weekly_reflection([], now)
        assert result.mode == "empty"

    def test_tough_payload_still_has_best_and_worst_day(self):
        now = _fixed_now()
        days = _week_dates(now)
        moods = [3, 2, 2, 1, 2, 2, 2]
        entries = [_entry(when=ts, mood=m) for ts, m in zip(days, moods)]
        result = build_weekly_reflection(entries, now)
        assert result.mode == "tough"
        # best/worst remain in the JSON payload — the in-app card still shows them.
        assert result.best_day is not None
        assert result.worst_day is not None

    def test_tough_share_text_omits_best_and_worst_day_lines(self):
        now = _fixed_now()
        days = _week_dates(now)
        moods = [3, 2, 2, 1, 2, 2, 2]
        entries = [_entry(when=ts, mood=m) for ts, m in zip(days, moods)]
        result = build_weekly_reflection(entries, now)
        assert result.mode == "tough"
        assert result.share_text is not None
        lowered = result.share_text.lower()
        assert "best day" not in lowered
        assert "toughest day" not in lowered
        # The rest of the share-text contract from issue 001 still holds.
        assert result.share_text.rstrip().endswith("— Shared from Pulse")
        assert "Avg mood" in result.share_text
        assert "Avg energy" in result.share_text

    def test_tough_narrative_templates_have_no_forbidden_substrings(self):
        from app.services.reflection import _TOUGH_NARRATIVES

        forbidden = ("worst", "lowest", "rough", "bad week")
        for template in _TOUGH_NARRATIVES:
            lowered = template.lower()
            for word in forbidden:
                assert word not in lowered, (
                    f"tough narrative {template!r} contains forbidden {word!r}"
                )

    def test_every_tough_narrative_template_is_safe_in_context(self):
        # Exercise the deterministic picker across every possible "last day"
        # position so every template gets selected at least once.
        now = _fixed_now()
        days = _week_dates(now)
        forbidden = ("worst", "lowest", "rough", "bad week")
        seen: set[str] = set()
        for last_index in range(7):
            entries = []
            for i, ts in enumerate(days):
                if i <= last_index:
                    entries.append(_entry(when=ts, mood=2))
            result = build_weekly_reflection(entries, now)
            if result.mode != "tough":
                continue
            assert result.narrative is not None
            seen.add(result.narrative)
            lowered = result.narrative.lower()
            for word in forbidden:
                assert word not in lowered
        # At least one tough narrative was selected.
        assert len(seen) >= 1

    def test_tough_reflection_prompt_is_gentle(self):
        now = _fixed_now()
        days = _week_dates(now)
        entries = [_entry(when=ts, mood=2) for ts in days]
        result = build_weekly_reflection(entries, now)
        assert result.mode == "tough"
        assert result.reflection_prompt is not None
        # The tough prompt must avoid blame-flavoured phrasings.
        lowered = result.reflection_prompt.lower()
        assert "differently" not in lowered

    def test_select_suggestion_returns_none_for_non_tough_modes(self):
        from app.models.reflection import TagCount
        from app.services.reflection import select_suggestion

        tags = [TagCount(tag="outdoors", count=3)]
        assert select_suggestion([], "normal") is None
        assert select_suggestion([], "sparse") is None
        assert select_suggestion([], "empty") is None
        assert select_suggestion(tags, "normal") is None
        assert select_suggestion(tags, "sparse") is None

    def test_select_suggestion_references_top_tag_in_tough_mode(self):
        from app.models.reflection import TagCount
        from app.services.reflection import select_suggestion

        tags = [TagCount(tag="outdoors", count=3), TagCount(tag="sleep", count=2)]
        sug = select_suggestion(tags, "tough")
        assert sug is not None
        # References the highest-count tag (the top one).
        assert "outdoors" in sug
        # Does not name a non-top tag as the primary suggestion.
        assert sug.count("sleep") == 0 or "outdoors" in sug
        # No generic clinical or crisis-resource language.
        lowered = sug.lower()
        for word in ("therapist", "hotline", "doctor", "crisis"):
            assert word not in lowered

    def test_select_suggestion_falls_back_when_no_tags_qualify(self):
        from app.services.reflection import select_suggestion

        sug = select_suggestion([], "tough")
        assert sug is not None
        # The fallback line invites picking one small thing.
        assert "small" in sug.lower()
        # No generic wellbeing tips: no "drink water", "meditate", etc.
        lowered = sug.lower()
        for word in ("meditate", "drink water", "exercise more"):
            assert word not in lowered

    def test_tough_suggestion_present_in_payload_when_tags_qualify(self):
        now = _fixed_now()
        days = _week_dates(now)
        entries = [
            _entry(when=ts, mood=2, tags=["outdoors"]) for ts in days
        ]
        result = build_weekly_reflection(entries, now)
        assert result.mode == "tough"
        assert result.suggestion is not None
        assert "outdoors" in result.suggestion

    def test_tough_suggestion_fallback_when_no_qualifying_tags(self):
        now = _fixed_now()
        days = _week_dates(now)
        # No tags at all → no qualifying tags → fallback line.
        entries = [_entry(when=ts, mood=2) for ts in days]
        result = build_weekly_reflection(entries, now)
        assert result.mode == "tough"
        assert result.suggestion is not None
        assert "small" in result.suggestion.lower()

    def test_tough_share_text_omits_suggestion(self):
        # Share text never carries the suggestion (issue 001 contract).
        now = _fixed_now()
        days = _week_dates(now)
        entries = [
            _entry(when=ts, mood=2, tags=["outdoors"]) for ts in days
        ]
        result = build_weekly_reflection(entries, now)
        assert result.mode == "tough"
        assert result.share_text is not None
        assert result.suggestion is not None
        assert result.suggestion not in result.share_text


class TestPromptBuckets:
    """Issue 004 — context-aware reflection prompts.

    Five buckets keyed off mode + trend, with deterministic rotation
    inside each bucket by window-start date.
    """

    def test_same_window_start_always_selects_same_prompt(self):
        now = _fixed_now()
        days = _week_dates(now)
        moods = [3, 3, 4, 4, 4, 3, 4]
        entries = [_entry(when=ts, mood=m) for ts, m in zip(days, moods)]
        a = build_weekly_reflection(entries, now)
        b = build_weekly_reflection(entries, now)
        assert a.reflection_prompt == b.reflection_prompt
        assert a.reflection_prompt is not None

    def test_successive_window_starts_rotate_prompts(self):
        # Shift `now` by 0..5 days. Each shift changes the window_start by
        # the same amount, which (mod a bucket size of 3) cycles through
        # distinct prompts.
        seen: set[Optional[str]] = set()
        moods = [3, 3, 3, 3, 3, 3, 3]  # flat → flat bucket every time
        for delta in range(6):
            now = _fixed_now() + timedelta(days=delta)
            days = _week_dates(now)
            entries = [_entry(when=ts, mood=m) for ts, m in zip(days, moods)]
            result = build_weekly_reflection(entries, now)
            seen.add(result.reflection_prompt)
        # At least two distinct prompts must appear across six successive weeks.
        assert len(seen) >= 2

    def test_normal_improving_routes_to_improving_bucket(self):
        from app.services.reflection import _PROMPTS

        now = _fixed_now()
        days = _week_dates(now)
        moods = [1, 2, 2, 3, 3, 4, 5]
        entries = [_entry(when=ts, mood=m) for ts, m in zip(days, moods)]
        result = build_weekly_reflection(entries, now)
        assert result.mode == "normal"
        assert result.trend.label == "improving"
        assert result.reflection_prompt in _PROMPTS["improving"]

    def test_normal_declining_routes_to_declining_bucket(self):
        from app.services.reflection import _PROMPTS

        now = _fixed_now()
        days = _week_dates(now)
        moods = [5, 4, 4, 3, 3, 3, 3]  # declining but ends above tough threshold
        entries = [_entry(when=ts, mood=m) for ts, m in zip(days, moods)]
        result = build_weekly_reflection(entries, now)
        assert result.mode == "normal"
        assert result.trend.label == "declining"
        assert result.reflection_prompt in _PROMPTS["declining"]

    def test_normal_flat_routes_to_flat_bucket(self):
        from app.services.reflection import _PROMPTS

        now = _fixed_now()
        days = _week_dates(now)
        entries = [_entry(when=ts, mood=3) for ts in days]
        result = build_weekly_reflection(entries, now)
        assert result.mode == "normal"
        assert result.trend.label == "flat"
        assert result.reflection_prompt in _PROMPTS["flat"]

    def test_tough_routes_to_tough_bucket(self):
        from app.services.reflection import _PROMPTS

        now = _fixed_now()
        days = _week_dates(now)
        entries = [_entry(when=ts, mood=2) for ts in days]
        result = build_weekly_reflection(entries, now)
        assert result.mode == "tough"
        assert result.reflection_prompt in _PROMPTS["tough"]

    def test_sparse_routes_to_sparse_bucket(self):
        from app.services.reflection import _PROMPTS

        now = _fixed_now()
        days = _week_dates(now)
        entries = [
            _entry(when=days[2], mood=3),
            _entry(when=days[5], mood=3),
        ]
        result = build_weekly_reflection(entries, now)
        assert result.mode == "sparse"
        assert result.reflection_prompt in _PROMPTS["sparse"]

    def test_empty_keeps_dedicated_prompt(self):
        from app.services.reflection import EMPTY_PROMPT

        now = _fixed_now()
        result = build_weekly_reflection([], now)
        assert result.mode == "empty"
        assert result.reflection_prompt == EMPTY_PROMPT

    def test_tough_bucket_contains_no_blame_phrasing(self):
        from app.services.reflection import _PROMPTS

        for prompt in _PROMPTS["tough"]:
            lowered = prompt.lower()
            # "what would you do differently?" is the canonical blame form.
            assert "differently" not in lowered, (
                f"tough prompt {prompt!r} implies blame via 'differently'"
            )

    def test_every_bucket_has_at_least_two_prompts(self):
        from app.services.reflection import _PROMPTS

        for bucket_name, prompts in _PROMPTS.items():
            assert len(prompts) >= 2, (
                f"bucket {bucket_name!r} should have ≥2 prompts to support rotation"
            )
