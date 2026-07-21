"""거시지표 관측치 검증 — 결측/비정상 값 제거, 최소 길이 확인. 불합격은 None(생략)."""
from __future__ import annotations

import math

MIN_OBSERVATIONS = 2  # yoy_change에 최소 필요(이상적으로는 13개월+, 부족하면 YoY만 None)


def validate_observations(rows: list[dict] | None) -> list[dict] | None:
    if not rows:
        return None
    clean = [
        r for r in rows
        if isinstance(r.get("value"), (int, float)) and math.isfinite(r["value"])
        and isinstance(r.get("date"), str) and r["date"]
    ]
    if len(clean) < MIN_OBSERVATIONS:
        return None
    return clean


def validate_price(value) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value) and value > 0
