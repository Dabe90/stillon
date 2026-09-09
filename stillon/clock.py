"""Frozen desk clock. Deadlines are computed in Python, never by the model."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta


DEFAULT_DESK_DATE = date(2026, 9, 9)


def desk_date() -> date:
    raw = os.environ.get("STILLON_DESK_DATE", "").strip()
    if not raw:
        return DEFAULT_DESK_DATE
    return date.fromisoformat(raw)


def parse_date(value: str | date) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return date.fromisoformat(str(value)[:10])


def days_until(target: date, today: date | None = None) -> int:
    today = today or desk_date()
    return (target - today).days


def add_days(start: date, n: int) -> date:
    return start + timedelta(days=n)
