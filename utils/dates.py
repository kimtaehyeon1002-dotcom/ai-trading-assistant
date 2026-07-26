"""날짜/시간 유틸 — KST 기준."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from config.settings import TIMEZONE


def now_kst() -> datetime:
    return datetime.now(TIMEZONE)


def today_str() -> str:
    """YYYY-MM-DD (KST)."""
    return now_kst().strftime("%Y-%m-%d")


def to_kst(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TIMEZONE)


def within_minutes(dt: datetime, minutes: int) -> bool:
    """dt가 현재로부터 minutes 이내(과거)인가(속보 판정용) — 미래 dt(오배치 타임스탬프)는 항상 False."""
    delta = now_kst() - to_kst(dt)
    return timedelta(0) <= delta <= timedelta(minutes=minutes)


def fmt_kst(dt: datetime, pattern: str = "%Y-%m-%d %H:%M") -> str:
    return to_kst(dt).strftime(pattern)
