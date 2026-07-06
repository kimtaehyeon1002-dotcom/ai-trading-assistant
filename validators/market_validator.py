"""시장 raw 값 검증 — 가격 수치/유한성, 야간선물 타임스탬프 신선도. 불합격은 None(생략)."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from config.settings import NIGHT_FUTURES_MAX_AGE_H


def _valid_price(v) -> bool:
    return isinstance(v, (int, float)) and math.isfinite(v) and v > 0


def _fresh(as_of: str | None, max_age_h: int) -> bool:
    if not as_of:
        return False
    try:
        dt = datetime.fromisoformat(as_of)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - dt <= timedelta(hours=max_age_h)
    except ValueError:
        return False


def validate(raw: dict[str, dict | None]) -> dict[str, dict | None]:
    """필드별 검증. 가격 비정상 → None. 야간선물(kiwoom)은 as_of 신선도까지 요구."""
    out: dict[str, dict | None] = {}
    for key, e in raw.items():
        if not isinstance(e, dict) or not _valid_price(e.get("price")):
            out[key] = None
            continue
        if key.endswith("_night") and not _fresh(e.get("as_of"), NIGHT_FUTURES_MAX_AGE_H):
            out[key] = None  # 만료/무타임스탬프 야간선물은 표시하지 않는다
            continue
        if key.endswith("_night"):
            nc = e.get("change_pct")
            if not (isinstance(nc, (int, float)) and math.isfinite(nc) and nc != 0.0):
                out[key] = None  # 등락 0/누락/비정상 = 마감·개장전 스냅샷 → 표시 금지(팩트 우선)
                continue
        chg = e.get("change_pct")
        if chg is not None and not (isinstance(chg, (int, float)) and math.isfinite(chg)):
            e = {**e, "change_pct": None}
        out[key] = e
    return out
