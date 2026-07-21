"""KR/US 랭킹 원장 검증 — 결측/비정상 행 제거, 최소 길이 확인. 불합격은 None(생략)."""
from __future__ import annotations

import math

MIN_ROWS = 30  # TOP30 산출에 필요한 최소 후보 수


def validate(rows: list[dict] | None) -> list[dict] | None:
    if not rows:
        return None
    clean = [
        r for r in rows
        if isinstance(r.get("code"), str) and r["code"]
        and isinstance(r.get("close"), (int, float)) and math.isfinite(r["close"]) and r["close"] > 0
        and isinstance(r.get("amount"), (int, float)) and math.isfinite(r["amount"]) and r["amount"] >= 0
    ]
    if len(clean) < MIN_ROWS:
        return None
    return clean
