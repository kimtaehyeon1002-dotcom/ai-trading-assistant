"""야간선물 시세 조회 — KRX 야간파생시장(2025-06 개설, 18:00~익일 05:00).

종목코드를 하드코딩하지 않는다: 로그인 세션에서 GetFutureList/GetActPriceList 계열로
전체 선물 코드를 받아 종목명에 '야간'이 포함된 것을 찾는다(디스커버리). 못 찾으면
전체 리스트를 로그로 남겨 다음 세션에서 코드를 확정할 수 있게 한다.
시세는 opt50001(선물시세정보) — 단일 레코드, 필드명은 후보 폴백(orders.py 패턴).
"""
from __future__ import annotations

from collectors.kiwoom_desktop.api import KiwoomAPI
from utils.logging import get_logger

log = get_logger("collectors.kiwoom_futures")

TR_CODE = "opt50001"
RQ_NAME = "opt50001_night"

# 표준 키 → 시세 응답에서 시도할 후보 필드명
_FIELD_CANDIDATES: dict[str, tuple[str, ...]] = {
    "price": ("현재가",),
    "change_pct": ("등락률", "등락율"),
}
_ALL_FIELDS = [f for cands in _FIELD_CANDIDATES.values() for f in cands]

# 야간 종목 판별용 (종목명 기준)
_NIGHT_KEYWORD = "야간"
_KOSPI_HINTS = ("코스피", "KOSPI", "K200", "코스피200")
_KOSDAQ_HINTS = ("코스닥", "KOSDAQ", "KQ150", "코스닥150")


def _num(s: str) -> float | None:
    try:
        return float(str(s).replace(",", "").replace("+", "").strip())
    except (ValueError, TypeError):
        return None


def _list_codes(api: KiwoomAPI) -> list[str]:
    """선물 종목코드 리스트 — 여러 API 함수를 시도(버전별 상이)."""
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
    return (api.ocx.dynamicCall("GetMasterCodeName(QString)", code) or "").strip()


def discover_night_codes(api: KiwoomAPI) -> dict[str, str]:
    """{'kospi_night': code, 'kosdaq_night': code} — 종목명에 '야간' 포함된 첫 종목(최근월).

    못 찾으면 빈 dict + 전체 (코드, 종목명) 로그를 남긴다(코드 확정용 진단).
    """
    pairs = [(c, _name_of(api, c)) for c in _list_codes(api)]
    night = [(c, n) for c, n in pairs if _NIGHT_KEYWORD in n]
    out: dict[str, str] = {}
    for code, name in night:
        if "kospi_night" not in out and any(h in name for h in _KOSPI_HINTS):
            out["kospi_night"] = code
        elif "kosdaq_night" not in out and any(h in name for h in _KOSDAQ_HINTS):
            out["kosdaq_night"] = code
    if not out:
        log.warning("야간 종목 미발견 — 전체 %d종목 덤프(코드 확정용):", len(pairs))
        for c, n in pairs[:80]:
            log.warning("  %s = %s", c, n)
    else:
        log.info("야간 종목 발견: %s", {k: f"{v}({_name_of(api, v)})" for k, v in out.items()})
    return out


def fetch_quote(api: KiwoomAPI, code: str) -> dict | None:
    """opt50001 단일 시세 → {'price': float, 'change_pct': float|None} | None."""
    api.set_input("종목코드", code)
    meta = api.comm_rq(RQ_NAME, TR_CODE, fields=_ALL_FIELDS)
    rows = meta.get("rows", [])
    if not rows:
        return None
    raw = rows[0]
    log.info("야간선물 raw(필드 검증용) %s: %s", code, raw)
    price = next((_num(raw[f]) for f in _FIELD_CANDIDATES["price"] if raw.get(f)), None)
    chg = next((_num(raw[f]) for f in _FIELD_CANDIDATES["change_pct"] if raw.get(f)), None)
    if price is not None:
        price = abs(price)  # Kiwoom은 하락 시 가격에 '-' 부호를 붙임(등락률은 부호 유지)
    if not price:
        return None
    return {"price": price, "change_pct": chg}


def fetch_night_futures(api: KiwoomAPI) -> dict[str, dict | None]:
    """야간선물 일괄 조회 — {'kospi_night': {...}|None, 'kosdaq_night': {...}|None}."""
    codes = discover_night_codes(api)
    return {key: (fetch_quote(api, code) if code else None) for key, code in
            {"kospi_night": codes.get("kospi_night"), "kosdaq_night": codes.get("kosdaq_night")}.items()}
