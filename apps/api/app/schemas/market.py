"""시장 데이터 정규화 스키마 — 무료↔유료 Provider가 공통으로 매핑하는 형태. (설계서 §1, §7.1)

모든 시각은 UTC, 모든 응답에 출처/실시간성 메타(source/is_realtime/data_delay_sec/as_of)를 포함한다.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ProviderMeta(BaseModel):
    source: str  # provider 식별자 (yfinance|fdr|pykrx|rss...)
    is_realtime: bool = False
    data_delay_sec: int | None = None
    as_of: datetime  # 데이터 기준시각(UTC)


class Quote(BaseModel):
    instrument_id: int | None = None
    symbol_norm: str
    market: str
    currency: str
    price: float
    change_pct: float | None = None
    volume: float | None = None
    meta: ProviderMeta


class Candle(BaseModel):
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    adjusted_close: float | None = None


class CandleSeries(BaseModel):
    instrument_id: int | None = None
    symbol_norm: str
    interval: str  # 1m|5m|1h|1d
    candles: list[Candle]
    meta: ProviderMeta


class Financials(BaseModel):
    instrument_id: int | None = None
    symbol_norm: str
    period: str  # 2025Q1 | 2025FY
    period_type: str  # quarterly | annual
    statement_type: str  # income|balance|cashflow|ratios
    currency: str
    unit: str  # KRW | KRW_thousand | USD
    items: dict[str, float | None]
    meta: ProviderMeta


class NewsItem(BaseModel):
    id: str  # dedup 해시
    title: str
    summary: str | None = None  # 자체 요약(본문 미저장)
    url: str
    source_name: str
    language: str  # ko | en
    published_at: datetime
    symbols: list[str] = []
    sentiment: float | None = None
    meta: ProviderMeta


class FxRate(BaseModel):
    base: str
    quote: str
    rate: float
    meta: ProviderMeta
