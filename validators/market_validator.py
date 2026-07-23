"""시장 raw 값 검증 — 가격 수치/유한성, 원값 게시 신선도 문턱. 불합격은 None(생략).

여기서의 신선도 판정은 "값이 너무 낡아 애초에 게시하지 않는다"는 수집단 게이트다.
열람 시점의 FRESH/DELAYED/STALE/CLOSED-SNAPSHOT 배지는 클라이언트 freshness.js가
Envelope의 as_of_iso·session_key로 판정한다(design/21 §6) — 이 모듈의 책임이 아니다.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from config.markets import MAX_ABS_CHANGE_PCT, MAX_ABS_CHANGE_PCT_DEFAULT
from config.settings import NIGHT_FUTURES_MAX_AGE_H, NIGHT_FUTURES_MAX_AGE_WEEKEND_H
from utils.logging import get_logger

log = get_logger("validators.market")


def _max_abs_change(key: str) -> float:
    """심볼별 등락률 sanity 상한(%) — 미등재 심볼은 기본값."""
    return MAX_ABS_CHANGE_PCT.get(key, MAX_ABS_CHANGE_PCT_DEFAULT)


def _spans_weekend(start: datetime, end: datetime) -> bool:
    """구간(KST 날짜 기준)에 토·일이 포함되는가.

    야간선물 값이 20h를 넘겨서도 살아남을 수 있는 유일한 사유가 주말 휴장이다
    (금요일 밤 세션 값 → 월요일 아침 리포트). 호출부가 60h 초과를 먼저 걸러 루프는 ≤3일.
    """
    from utils.dates import to_kst  # 지연 import(config→utils 단방향 의존 유지)

    day, last = to_kst(start).date(), to_kst(end).date()
    while day <= last:
        if day.weekday() >= 5:  # 5=토, 6=일
            return True
        day += timedelta(days=1)
    return False


def _night_max_age_h(as_of: datetime, now: datetime) -> int:
    """야간선물 표시 만료(시간) — 평일 20h, 구간에 주말이 낀 경우만 60h(design/23 P2)."""
    if now - as_of > timedelta(hours=NIGHT_FUTURES_MAX_AGE_WEEKEND_H):
        return NIGHT_FUTURES_MAX_AGE_H  # 어느 규칙으로도 탈락 — 주말 판정 생략(루프 상한 보장)
    return (NIGHT_FUTURES_MAX_AGE_WEEKEND_H if _spans_weekend(as_of, now)
            else NIGHT_FUTURES_MAX_AGE_H)


# 원값 게시 신선도 문턱 — 소스별 규칙 테이블. 값이 이 한도보다 낡으면 표시하지 않는다.
# design/20 Phase 0에서 "_night 전용 → 소스별 파라미터 규칙"으로 일반화했고, design/23에서
# 한도가 시점에 따라 달라지게 되어(평일/주말) 상수 대신 (as_of, now) → 시간 함수로 둔다.
_STALE_DROP_RULES: dict[str, Callable[[datetime, datetime], int]] = {
    "kospi_night": _night_max_age_h,
    "kosdaq_night": _night_max_age_h,
}
_NIGHT_FUTURES_KEYS = frozenset(_STALE_DROP_RULES)


def _valid_price(v) -> bool:
    return isinstance(v, (int, float)) and math.isfinite(v) and v > 0


def _parse_as_of(as_of: str | None) -> datetime | None:
    """ISO 문자열 → aware datetime. 없거나 파싱 실패면 None(= 신선도 판정 불가 → 탈락)."""
    if not as_of:
        return None
    try:
        dt = datetime.fromisoformat(as_of)
    except (ValueError, TypeError):
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def validate(raw: dict[str, dict | None], now: datetime | None = None) -> dict[str, dict | None]:
    """필드별 검증. 가격 비정상 → None. 게시 신선도 규칙이 등재된 소스는 as_of까지 요구.

    now는 테스트에서 시각을 고정하기 위한 주입점이다(주말 규칙이 있어 실행 요일에 결과가
    달라지므로, 기본값 datetime.now로는 결정적 테스트를 쓸 수 없다).
    """
    now = now or datetime.now(timezone.utc)
    out: dict[str, dict | None] = {}
    for key, e in raw.items():
        if not isinstance(e, dict) or not _valid_price(e.get("price")):
            out[key] = None
            continue
        rule = _STALE_DROP_RULES.get(key)
        if rule is not None:
            as_of = _parse_as_of(e.get("as_of"))
            if as_of is None or (now - as_of) > timedelta(hours=rule(as_of, now)):
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
        elif chg is not None and abs(chg) > _max_abs_change(key):
            log.warning("등락률 sanity 상한 초과 %s: %.2f%% (상한 %.1f%%) — 소스 오류로 보고 폐기",
                        key, chg, _max_abs_change(key))
            out[key] = None  # 자릿수 밀림·기준가 오배정 등 소스 오류 차단
            continue
        out[key] = e
    return out
