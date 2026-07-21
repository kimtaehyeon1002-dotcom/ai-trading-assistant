"""시장 데이터 수집 — Yahoo(지수/WTI/환율폴백) + Frankfurter/ExchangeRate-API(USD/KRW).

반환은 raw dict(모델 변환은 repositories/). 실패 항목은 None(추정 금지).
실행당 1회만 다운로드(메모이즈).
"""
from __future__ import annotations

from config.markets import EXTENDED_SYMBOLS, MORNING_US_INDICES, WTI_SYMBOL
from utils.logging import get_logger

log = get_logger("collectors.market")

_memo: dict | None = None


def _yahoo(symbol: str) -> tuple[float | None, float | None, float | None]:
    """(가격, 전일대비%, 전일종가) — 실패는 (None, None, None)."""
    try:
        import yfinance as yf

        fi = yf.Ticker(symbol).fast_info
        price = fi.get("last_price") or fi.get("lastPrice")
        prev = fi.get("previous_close") or fi.get("previousClose")
        if price is None:
            return None, None, None
        pct = round((price / prev - 1) * 100, 2) if prev else None
        return float(price), pct, (float(prev) if prev else None)
    except Exception as exc:  # noqa: BLE001
        log.warning("yahoo 실패 %s: %s", symbol, exc)
        return None, None, None


def _entry(price: float, chg: float | None, prev: float | None, source: str) -> dict:
    """raw 항목 조립 — previous_close는 change_abs 산출 재료(repositories/에서 계산)."""
    e = {"price": price, "change_pct": chg, "source": source}
    if prev is not None:
        e["previous_close"] = prev
    return e


def _usdkrw() -> dict | None:
    import requests

    try:  # 1) Frankfurter(ECB)
        r = requests.get("https://api.frankfurter.app/latest",
                         params={"from": "USD", "to": "KRW"}, timeout=10)
        r.raise_for_status()
        return {"price": float(r.json()["rates"]["KRW"]), "change_pct": None,
                "source": "frankfurter(ECB)"}
    except Exception as exc:  # noqa: BLE001
        log.warning("frankfurter 실패: %s", exc)
    try:  # 2) ExchangeRate-API
        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
        r.raise_for_status()
        return {"price": float(r.json()["rates"]["KRW"]), "change_pct": None,
                "source": "exchangerate-api"}
    except Exception as exc:  # noqa: BLE001
        log.warning("exchangerate-api 실패: %s", exc)
    price, chg, prev = _yahoo("USDKRW=X")  # 3) Yahoo
    return _entry(price, chg, prev, "yahoo") if price is not None else None


def collect() -> dict[str, dict | None]:
    """모닝리포트 8지표 + 확장 유니버스(design/20 Phase 3) → raw {price, change_pct, source} | None."""
    global _memo
    if _memo is not None:
        return _memo

    out: dict[str, dict | None] = {"usdkrw": _usdkrw()}
    price, chg, prev = _yahoo(WTI_SYMBOL)
    out["wti"] = _entry(price, chg, prev, "yahoo") if price is not None else None
    for key, symbol, _label in MORNING_US_INDICES:
        price, chg, prev = _yahoo(symbol)
        out[key] = _entry(price, chg, prev, "yahoo") if price is not None else None
    for key, symbol, _label in EXTENDED_SYMBOLS:
        price, chg, prev = _yahoo(symbol)
        out[key] = _entry(price, chg, prev, "yahoo") if price is not None else None

    _memo = out
    return out
