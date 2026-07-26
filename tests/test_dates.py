"""utils/dates.py — within_minutes() 미래 타임스탬프 가드."""
from __future__ import annotations

from datetime import timedelta

from utils.dates import now_kst, within_minutes


def test_within_minutes_true_for_recent_past():
    dt = now_kst() - timedelta(minutes=5)
    assert within_minutes(dt, minutes=15) is True


def test_within_minutes_false_for_old_past():
    dt = now_kst() - timedelta(minutes=30)
    assert within_minutes(dt, minutes=15) is False


def test_within_minutes_false_for_future_timestamp():
    # 오배치/타임존 오류로 미래 published가 들어와도 "속보"로 오판하면 안 된다.
    dt = now_kst() + timedelta(minutes=30)
    assert within_minutes(dt, minutes=15) is False
