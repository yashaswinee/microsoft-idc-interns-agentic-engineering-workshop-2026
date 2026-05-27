"""Pydantic models for the weekly reflection digest."""

from typing import Optional

from pydantic import BaseModel


class ReflectionWindow(BaseModel):
    start: str
    end: str


class TrendInfo(BaseModel):
    label: str
    slope: Optional[float] = None


class DayAverage(BaseModel):
    date: str
    avg_mood: float


class TagCount(BaseModel):
    tag: str
    count: int


class WeeklyReflection(BaseModel):
    window: ReflectionWindow
    entry_count: int
    days_with_entries: int
    mode: str
    avg_mood: Optional[float] = None
    avg_energy: Optional[float] = None
    trend: TrendInfo
    best_day: Optional[DayAverage] = None
    worst_day: Optional[DayAverage] = None
    top_tags: list[TagCount] = []
    narrative: Optional[str] = None
    suggestion: Optional[str] = None
    reflection_prompt: Optional[str] = None
    share_text: Optional[str] = None
