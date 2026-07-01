"""종목 마스터. 티커는 PK가 아니다 — instrument_id surrogate + UNIQUE(market,ticker). (설계서 §4.1)"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Instrument(Base):
    __tablename__ = "instrument"
    __table_args__ = (
        UniqueConstraint("market", "ticker", name="uq_instrument_market_ticker"),
        CheckConstraint("market in ('KR','US')", name="ck_instrument_market"),
        Index("ix_instrument_active", "market", "is_active"),
    )

    instrument_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    market: Mapped[str] = mapped_column(String(2), nullable=False)  # KR | US
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)  # 005930 | AAPL
    symbol_norm: Mapped[str] = mapped_column(
        String(48), unique=True, index=True, nullable=False
    )  # 005930.KS | AAPL
    exchange: Mapped[str | None] = mapped_column(String(16))  # KRX|KOSDAQ|NASDAQ|NYSE
    name_local: Mapped[str | None] = mapped_column(String(255))
    name_en: Mapped[str | None] = mapped_column(String(255))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)  # KRW | USD (ISO 4217)
    timezone: Mapped[str] = mapped_column(String(40), nullable=False)  # IANA
    asset_type: Mapped[str] = mapped_column(String(16), default="EQUITY", nullable=False)
    isin: Mapped[str | None] = mapped_column(String(12), index=True)
    sector: Mapped[str | None] = mapped_column(String(64))
    industry: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    listed_at: Mapped[date | None] = mapped_column(Date)
    delisted_at: Mapped[date | None] = mapped_column(Date)
    meta: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
