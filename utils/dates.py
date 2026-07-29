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
    """dt가 현재로부터 minutes 이내인가(속보 판정용)."""
    return (now_kst() - to_kst(dt)) <= timedelta(minutes=minutes)


def fmt_kst(dt: datetime, pattern: str = "%Y-%m-%d %H:%M") -> str:
    return to_kst(dt).strftime(pattern)


def spans_weekend(start: datetime, end: datetime) -> bool:
    """구간(KST 날짜 기준)에 토·일이 포함되는가.

    "평일 상한 / 주말 상한"으로 갈라지는 신선도 규칙이 두 곳에 있다 — 야간선물 표시 만료
    (validators/market_validator, design/23 P2)와 루프 센서의 워커 신선도(scripts/health_probe,
    design/26 §3-1). 둘 다 같은 질문을 하므로 여기 한 번만 둔다.

    호출부는 명백히 과도한 구간을 먼저 걸러 루프 길이를 제한해야 한다(일 단위 순회).
    """
    day, last = to_kst(start).date(), to_kst(end).date()
    while day <= last:
        if day.weekday() >= 5:  # 5=토, 6=일
            return True
        day += timedelta(days=1)
    return False
