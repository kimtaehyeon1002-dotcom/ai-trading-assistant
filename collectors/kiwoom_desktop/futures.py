"""야간선물 시세 — KRX 야간파생시장(2025-06 개설, 18:00~익일 05:00).

2025-06 EUREX 연계 종료 후, 야간장은 **주간과 동일한 KRX 종목**을 연장 시간대에 거래한다.
따라서 별도 '야간' 종목코드는 없다. 최근월(front-month) 코스피200/코스닥150 선물을
야간 시간대에 조회하면 그 값이 곧 야간선물 시세다.

종목코드는 하드코딩하지 않고 로그인 세션의 GetFutureList에서 종목명 패턴으로 최근월을
자동 선택한다(월물이 롤오버되어도 안전). 시세는 opt50001(선물시세) 단일 레코드.
"""
from __future__ import annotations

import re

from collectors.kiwoom_desktop.api import KiwoomAPI, fix_mojibake
from utils.logging import get_logger

log = get_logger("collectors.kiwoom_futures")

TR_CODE = "opt50001"
RQ_NAME = "opt50001_quote"

# 실계좌 검증(2026-07-06): 등락율 = 전일대비/기준가, 기준가 = **전일 정규장 종가**.
# 즉 야간세션 중 등락률은 '전일종가 대비'(거래소 관례)로 당일 주간 변동을 포함하며,
# '밤사이 변동분'이 아니다. 주간 종가는 opt50001에 없어 야간분 분리는 불가 —
# 리포트에는 기준을 명시해 표시한다(morning notes).
_FIELD_CANDIDATES: dict[str, tuple[str, ...]] = {
    "price": ("현재가",),
    "change_pct": ("등락률", "등락율"),
}
_ALL_FIELDS = [f for cands in _FIELD_CANDIDATES.values() for f in cands]

# 종목명 패턴 → 최근월 선택. 코스피200 선물명은 접두어 없이 'F YYYYMM',
# 코스닥150은 '코스닥 F YYYYMM'(코스닥글로벌 등 섹터물 제외).
_FRONT_MONTH_PATTERNS: dict[str, re.Pattern] = {
    "kospi_night": re.compile(r"^F\s+(\d{6})$"),
    "kosdaq_night": re.compile(r"^코스닥\s+F\s+(\d{6})$"),
}


def _num(s: str) -> float | None:
    try:
        return float(str(s).replace(",", "").replace("+", "").strip())
    except (ValueError, TypeError):
        return None


def _list_codes(api: KiwoomAPI) -> list[str]:
    """선물 종목코드 리스트 — 버전별로 함수명이 달라 여러 개 시도."""
    codes: list[str] = []
    for call in ("GetFutureList()", "GetActPriceList()"):
        try:
            raw = api.ocx.dynamicCall(call) or ""
        except Exception:  # noqa: BLE001 - 미지원 함수는 건너뜀
            continue
        codes += [c for c in str(raw).replace(",", ";").split(";") if c.strip()]
    seen: set[str] = set()
    return [c for c in codes if not (c in seen or seen.add(c))]


def _name_of(api: KiwoomAPI, code: str) -> str:
    return fix_mojibake((api.ocx.dynamicCall("GetMasterCodeName(QString)", code) or "").strip())


def _family(name: str) -> str:
    """월물/스프레드 표기를 떼어낸 상품군 이름(진단 덤프용)."""
    return re.split(r"\s*(?:F|SP)\s*\d", name)[0].strip() or name


def discover_front_month(api: KiwoomAPI) -> dict[str, str]:
    """{'kospi_night': code, 'kosdaq_night': code} — 최근월 지수선물 코드.

    패턴 매칭 실패 시 상품군 단위 진단 덤프를 남긴다.
    """
    pairs = [(c, _name_of(api, c)) for c in _list_codes(api)]
    out: dict[str, str] = {}
    for key, pat in _FRONT_MONTH_PATTERNS.items():
        matches = [(m.group(1), c, n) for c, n in pairs if (m := pat.match(n))]
        if matches:
            month, code, name = min(matches)  # 최근월(가장 작은 YYYYMM)
            out[key] = code
            log.info("%s 최근월: %s (%s)", key, code, name)

    if len(out) < len(_FRONT_MONTH_PATTERNS):
        fams: dict[str, str] = {}
        for c, n in pairs:
            fams.setdefault(_family(n), n)
        log.warning("일부 지수선물 미발견(found=%s) — 상품군 %d개 덤프:", list(out), len(fams))
        for fam, sample in sorted(fams.items()):
            log.warning("  [%s] 예: %s", fam, sample)
    return out


def fetch_quote(api: KiwoomAPI, code: str) -> dict | None:
    """opt50001 단일 시세 → {'price': float, 'change_pct': float|None} | None."""
    api.set_input("종목코드", code)
    meta = api.comm_rq(RQ_NAME, TR_CODE, fields=_ALL_FIELDS)
    rows = meta.get("rows", [])
    if not rows:
        return None
    raw = rows[0]
    log.info("선물 시세 raw(필드 검증용) %s: %s", code, raw)
    price = next((_num(raw[f]) for f in _FIELD_CANDIDATES["price"] if raw.get(f)), None)
    chg = next((_num(raw[f]) for f in _FIELD_CANDIDATES["change_pct"] if raw.get(f)), None)
    if price is not None:
        price = abs(price)  # Kiwoom은 하락 시 가격에 '-' 부호를 붙임(등락률은 부호 유지)
    if not price:
        return None
    return {"price": price, "change_pct": chg}


def fetch_night_futures(api: KiwoomAPI) -> dict[str, dict | None]:
    """야간선물(=최근월 지수선물) 일괄 조회. 야간 시간대에 실행해야 야간 시세가 잡힌다."""
    codes = discover_front_month(api)
    return {
        "kospi_night": fetch_quote(api, codes["kospi_night"]) if codes.get("kospi_night") else None,
        "kosdaq_night": fetch_quote(api, codes["kosdaq_night"]) if codes.get("kosdaq_night") else None,
    }
