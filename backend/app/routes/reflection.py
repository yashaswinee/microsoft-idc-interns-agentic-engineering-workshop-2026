"""Weekly reflection digest route."""

from datetime import datetime, timezone

from fastapi import APIRouter

from ..models.reflection import WeeklyReflection
from ..services.reflection import build_weekly_reflection
from ..storage import list_entries

router = APIRouter()


@router.get("/reflection/weekly", response_model=WeeklyReflection)
def weekly_reflection() -> WeeklyReflection:
    """Build the weekly reflection digest for the rolling 7-day window."""
    now = datetime.now(timezone.utc)
    entries = list_entries()
    return build_weekly_reflection(entries, now)
