"""시장 raw 값 검증 — 가격 수치/유한성, 원값 게시 신선도 문턱. 불합격은 None(생략).

여기서의 신선도 판정은 "값이 너무 낡아 애초에 게시하지 않는다"는 수집단 게이트다.
열람 시점의 FRESH/DELAYED/STALE/CLOSED-SNAPSHOT 배지는 클라이언트 freshness.js가
Envelope의 as_of_iso·session_key로 판정한다(design/21 §6) — 이 모듈의 책임이 아니다.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from config.settings import NIGHT_FUTURES_MAX_AGE_H

# 원값 게시 신선도 문턱(시간) — 소스별 테이블. 값 자체가 이보다 낡으면 표시하지 않는다.
# design/20 Phase 0: "_fresh()를 _night 전용에서 소스별 파라미터 규칙으로 일반화".
_STALE_DROP_RULES: dict[str, int] = {
    "kospi_night": NIGHT_FUTURES_MAX_AGE_H,
    "kosdaq_night": NIGHT_FUTURES_MAX_AGE_H,
}
_NIGHT_FUTURES_KEYS = frozenset(_STALE_DROP_RULES)


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
    """필드별 검증. 가격 비정상 → None. 게시 신선도 문턱이 등재된 소스는 as_of까지 요구."""
    out: dict[str, dict | None] = {}
    for key, e in raw.items():
        if not isinstance(e, dict) or not _valid_price(e.get("price")):
            out[key] = None
            continue
        max_age_h = _STALE_DROP_RULES.get(key)
        if max_age_h is not None and not _fresh(e.get("as_of"), max_age_h):
            out[key] = None  # 만료/무타임스탬프 값은 표시하지 않는다
            continue
        if key in _NIGHT_FUTURES_KEYS:
            nc = e.get("change_pct")
            if not (isinstance(nc, (int, float)) and math.isfinite(nc) and nc != 0.0):
                out[key] = None  # 등락 0/누락/비정상 = 마감·개장전 스냅샷 → 표시 금지(팩트 우선)
                continue
        chg = e.get("change_pct")
        if chg is not None and not (isinstance(chg, (int, float)) and math.isfinite(chg)):
            e = {**e, "change_pct": None}
        out[key] = e
    return out
