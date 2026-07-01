"""티커/통화/타임존 정규화 — 소스마다 다른 표기를 단일 symbol_norm으로 통일.

규칙:
  KR: 005930 → 005930.KS (KOSPI) / 005930.KQ (KOSDAQ)  (yfinance 호환 표기 사용)
  US: AAPL   → AAPL
모든 시각은 UTC로 저장/반환.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class InstrumentRef:
    """ORM에 의존하지 않는 경량 종목 참조 (provider 입력용)."""

    instrument_id: int | None
    market: str  # KR | US
    ticker: str  # 005930 | AAPL
    symbol_norm: str  # 005930.KS | AAPL
    currency: str  # KRW | USD


def normalize_symbol(market: str, ticker: str, exchange: str | None = None) -> str:
    market = market.upper()
    if market == "US":
        return ticker.upper()
    if market == "KR":
        if "." in ticker:  # 이미 접미사 포함
            return ticker.upper()
        suffix = ".KQ" if (exchange or "").upper() == "KOSDAQ" else ".KS"
        return f"{ticker}{suffix}"
    return ticker.upper()


def market_for_symbol(symbol_norm: str) -> str:
    return "KR" if symbol_norm.upper().endswith((".KS", ".KQ")) else "US"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
