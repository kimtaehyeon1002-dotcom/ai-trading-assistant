"""AI Research 산출물 — 4-블록 리포트(감사용 영속화). 설계서 §4.1, §4.3.

뉴스 본문은 저장하지 않는다(citations에는 제목+URL+출처만). 모든 생성은 agent_run에 연결.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ResearchReport(Base):
    __tablename__ = "research_report"

    report_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.user_id", ondelete="SET NULL"), index=True
    )
    instrument_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("instrument.instrument_id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    query: Mapped[str | None] = mapped_column(Text)
    style: Mapped[str] = mapped_column(String(16), default="swing", nullable=False)
    depth: Mapped[str] = mapped_column(String(16), default="standard", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="completed", nullable=False)  # completed|blocked|error
    blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    markdown: Mapped[str] = mapped_column(Text, default="", nullable=False)
    blocks: Mapped[dict | None] = mapped_column(JSONB)  # 4-블록 구조
    citations: Mapped[list | None] = mapped_column(JSONB)  # [{n,title,url,source,published_at}]
    intent: Mapped[dict | None] = mapped_column(JSONB)  # 의도분류 스냅샷
    model: Mapped[str | None] = mapped_column(String(48))
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"), nullable=False)
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_run.run_id", ondelete="SET NULL")
    )
    disclaimer_version: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
