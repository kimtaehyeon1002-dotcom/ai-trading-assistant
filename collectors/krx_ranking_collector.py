"""KRX 전종목 스냅샷 수집 — FinanceDataReader(design/21 §225 "마감 EOD 스냅샷으로 축소").

공식 API가 아니고 장중 20분 신선도를 보장하지 않으므로 마감 스냅샷 용도로 쓴다(design/20
Phase 7 리스크·롤백). 한 번의 호출로 전종목(코스피·코스닥·코넥스) Close/Volume/Amount/Marcap을
모두 받아오므로 별도의 종목별 호출이 필요 없다 — 이 점이 미국(개별 종목 재조회 필요)과 다르다.
실패 시 None(추정 금지). 실행당 1회만 다운로드(메모이즈).
"""
from __future__ import annotations

import math

from utils.logging import get_logger

log = get_logger("collectors.krx_ranking")

_memo: list[dict] | None = None
_memo_done = False


def _num(v, cast=float):
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        return cast(v)
    except (TypeError, ValueError):
        return None


def collect() -> list[dict] | None:
    """[{code, name, market, close, change_pct, volume, amount, marcap}] | None(수집 실패)."""
    global _memo, _memo_done
    if _memo_done:
        return _memo

    _memo_done = True
    try:
        import FinanceDataReader as fdr

        df = fdr.StockListing("KRX")
    except Exception as exc:  # noqa: BLE001
        log.warning("KRX 랭킹 수집 실패: %s", exc)
        _memo = None
        return None

    rows: list[dict] = []
    for r in df.to_dict("records"):
        code, close, amount = r.get("Code"), _num(r.get("Close")), _num(r.get("Amount"))
        if not code or close is None or amount is None:
            continue
        rows.append({
            "code": str(code),
            "name": str(r.get("Name") or code),
            "market": str(r.get("Market") or ""),
            "close": close,
            "change_pct": _num(r.get("ChagesRatio")),
            "volume": _num(r.get("Volume"), cast=int),
            "amount": amount,
            "marcap": _num(r.get("Marcap")),
        })
    _memo = rows or None
    return _memo
