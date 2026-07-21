"""TA 일봉 시계열 검증 — 결측/비정상 종가 제거, 최소 길이 확인. 불합격은 None(생략)."""
from __future__ import annotations

import math

# RSI(14) 산출(15개) + 60일 추세 판정(61개) 중 더 큰 요구치 + 여유
MIN_CLOSES = 61


def validate(rows: list[dict] | None) -> list[dict] | None:
    if not rows:
        return None
    clean = [
        r for r in rows
        if isinstance(r.get("close"), (int, float)) and math.isfinite(r["close"]) and r["close"] > 0
        and isinstance(r.get("date"), str) and r["date"]
    ]
    if len(clean) < MIN_CLOSES:
        return None
    return clean
