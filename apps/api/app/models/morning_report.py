"""모닝리포트 — 평일 06:30 공용 브리핑(불변 이력). 설계서 §1.3-A, §2.4, §4.

content_hash로 재현/캐시. scope='global'(공용 유니버스 1회 생성) + 사용자별 뷰는 조립 단계.
뉴스 본문 미저장(sections에는 제목+요약+URL만).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MorningReport(Base):
    __tablename__ = "morning_report"
    __table_args__ = (
        UniqueConstraint("report_date", "scope", "version", name="uq_morning_report_date_scope_ver"),
    )

    report_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(32), default="global", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    sections: Mapped[dict | None] = mapped_column(JSONB)  # 구조화 섹션(지수/환율/테마/뉴스/영향)
    markdown: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="completed", nullable=False)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    model: Mapped[str | None] = mapped_column(String(48))
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"), nullable=False)
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_run.run_id", ondelete="SET NULL")
    )
    disclaimer_version: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
