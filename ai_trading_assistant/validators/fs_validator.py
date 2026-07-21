"""재무제표 원장 검증 — 결측/비정상 값 제거. 라인 전부 결측이면 None(생략)."""
from __future__ import annotations

import math

_LINES = ("revenue", "operating_income", "net_income", "assets", "liabilities", "equity",
          "operating_cf", "capex", "eps")


def _clean_series(rows) -> list[dict]:
    return [
        r for r in (rows or [])
        if isinstance(r, dict) and isinstance(r.get("year"), str) and r["year"]
        and isinstance(r.get("value"), (int, float)) and math.isfinite(r["value"])
    ]


def validate(raw: dict | None) -> dict | None:
    if not raw:
        return None
    cleaned = {line: sorted(_clean_series(raw.get(line)), key=lambda r: r["year"]) for line in _LINES}
    if not any(cleaned.values()):
        return None
    return cleaned
