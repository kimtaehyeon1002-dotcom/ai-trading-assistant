"""매매일지 — trade_journal_entry(완결 거래 1건 = 1행). 설계서 §1.3-C, §4.

Notion '매매 일지' 행을 정규화 적재. source_row_id로 멱등 재임포트(중복 방지).
note는 사용자 본인의 복기 기록(제3자 저작물 아님).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TradeJournalEntry(Base):
    __tablename__ = "trade_journal_entry"
    __table_args__ = (
        UniqueConstraint("user_id", "source", "source_row_id", name="uq_journal_source_row"),
    )

    entry_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(16), default="notion", nullable=False)
    source_row_id: Mapped[str] = mapped_column(String(128), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(32))
    position: Mapped[str | None] = mapped_column(String(8))  # long | short
    pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))  # 수익금(USD)
    outcome: Mapped[str] = mapped_column(String(8), default="unknown", nullable=False)
    traded_on: Mapped[date | None] = mapped_column(Date, index=True)
    note: Mapped[str | None] = mapped_column(Text)  # 매매 복기(사용자 기록)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
