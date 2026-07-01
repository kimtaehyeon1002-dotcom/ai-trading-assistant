"""데이터 소스 레지스트리 — 무료↔유료 폴백을 데이터로 관리. (설계서 §4.1)"""
from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DataProviderSource(Base):
    __tablename__ = "data_provider_source"
    __table_args__ = (UniqueConstraint("name", "domain", name="uq_provider_name_domain"),)

    provider_source_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(String(32), nullable=False)  # yfinance|pykrx|fdr|kis|rss...
    tier: Mapped[str] = mapped_column(String(8), nullable=False)  # free | paid
    domain: Mapped[str] = mapped_column(String(16), nullable=False)  # price|fundamental|news|fx|filing|report
    markets: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    is_realtime: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rate_limit: Mapped[dict | None] = mapped_column(JSONB)  # {"per_min": 60}
    terms_note: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)  # 낮을수록 우선
