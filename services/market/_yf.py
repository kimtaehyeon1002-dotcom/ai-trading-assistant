"""yfinance 단일 시세 조회 헬퍼 — 실패는 (None, None)으로 정규화(폴백 가능)."""
from __future__ import annotations

from core.logging import get_logger

log = get_logger("market.yf")


def fast_quote(symbol: str) -> tuple[float | None, float | None]:
    """(현재가, 전일대비%) — 네트워크/라이브러리 실패 시 (None, None)."""
    try:
        import yfinance as yf

        fi = yf.Ticker(symbol).fast_info
        price = fi.get("last_price") or fi.get("lastPrice")
        prev = fi.get("previous_close") or fi.get("previousClose")
        if price is None:
            return None, None
        change_pct = round((price / prev - 1) * 100, 2) if prev else None
        return float(price), change_pct
    except Exception as exc:  # noqa: BLE001 - 수집 실패는 빈 값으로
        log.warning("fast_quote 실패 %s: %s", symbol, exc)
        return None, None
