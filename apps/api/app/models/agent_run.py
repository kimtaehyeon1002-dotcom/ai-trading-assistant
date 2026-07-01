"""LLM 실행 로그 — model/tokens/cache/cost/latency. 비용 대시보드·라우팅 검증의 백본. (설계서 §4.2)"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AgentRun(Base):
    __tablename__ = "agent_run"
    __table_args__ = (
        Index("ix_agent_run_task_started", "task_type", "started_at"),
        Index("ix_agent_run_model", "model"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.user_id", ondelete="SET NULL"), index=True
    )
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)  # research|morning_report|classify|...
    model: Mapped[str] = mapped_column(String(48), nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_batch: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="ok", nullable=False)  # ok|error|blocked
    error: Mapped[str | None] = mapped_column(Text)
    trace: Mapped[dict | None] = mapped_column(JSONB)  # tool-use 단계 참조(본문 비저장)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
