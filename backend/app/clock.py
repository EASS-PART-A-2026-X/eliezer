"""The one place that reads the clock, so tests can freeze time."""

from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends

GARDEN_TZ = ZoneInfo("Asia/Jerusalem")  # watering days follow the local calendar


def now() -> datetime:
    return datetime.now(UTC)


NowDep = Annotated[datetime, Depends(now)]


def next_watering_on(last_watered_at: datetime, interval_days: int) -> date:
    return last_watered_at.astimezone(GARDEN_TZ).date() + timedelta(days=interval_days)


def days_until(day: date, current: datetime) -> int:
    """Whole calendar days from today (garden time) to `day`; negative = overdue."""
    return (day - current.astimezone(GARDEN_TZ).date()).days
