"""TA 프리뷰용 KOSPI 일봉 수집(Yahoo Finance history) — raw만 반환, 계산은 calculators/."""
from __future__ import annotations

from config.markets import TA_KOSPI_SYMBOL
from utils.logging import get_logger

log = get_logger("collectors.ta")


def collect_kospi_daily(period: str = "6mo") -> list[dict] | None:
    """[{'date': 'YYYY-MM-DD', 'close': float}, ...] 오름차순 — 실패 시 None."""
    try:
        import yfinance as yf

        hist = yf.Ticker(TA_KOSPI_SYMBOL).history(period=period)
        if hist is None or hist.empty:
            return None
        closes = hist["Close"].dropna()
        return [{"date": idx.strftime("%Y-%m-%d"), "close": float(v)} for idx, v in closes.items()]
    except Exception as exc:  # noqa: BLE001
        log.warning("KOSPI 일봉 수집 실패: %s", exc)
        return None
