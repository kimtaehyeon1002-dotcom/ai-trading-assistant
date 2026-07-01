"""포트폴리오 — portfolio / holding. 설계서 §4.

보유 비중·집중도·노출은 코드 계산(analytics.portfolio_metrics). 다통화는 base_currency 환산.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Portfolio(Base):
    __tablename__ = "portfolio"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), default="기본 포트폴리오", nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), default="KRW", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Holding(Base):
    __tablename__ = "holding"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "instrument_id", name="uq_holding_portfolio_instrument"),
    )

    holding_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portfolio.portfolio_id", ondelete="CASCADE"), nullable=False, index=True
    )
    instrument_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("instrument.instrument_id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    avg_cost: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))  # 종목 통화 기준 평단
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
