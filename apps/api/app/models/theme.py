"""테마 — theme / theme_membership / theme_score. 설계서 §2.7, §4.

theme_score는 시계열 적재(추세·부상 테마 감지). 점수는 '관찰 지표'(매수 신호 아님).
US→KR 매핑은 theme.kr_link_slug(또는 공통 tags)로 연결.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Theme(Base):
    __tablename__ = "theme"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_theme_slug"),
        Index("ix_theme_market", "market", "is_active"),
    )

    theme_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    market: Mapped[str] = mapped_column(String(2), nullable=False)  # KR | US
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    kr_link_slug: Mapped[str | None] = mapped_column(String(64))  # US 테마 → 대응 KR 테마 slug
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ThemeMembership(Base):
    __tablename__ = "theme_membership"
    __table_args__ = (
        UniqueConstraint("theme_id", "instrument_id", name="uq_theme_membership"),
        Index("ix_theme_membership_theme", "theme_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    theme_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("theme.theme_id", ondelete="CASCADE"), nullable=False
    )
    instrument_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("instrument.instrument_id", ondelete="CASCADE"), nullable=False
    )
    weight: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("1"), nullable=False)


class ThemeScore(Base):
    __tablename__ = "theme_score"
    __table_args__ = (Index("ix_theme_score_theme_asof", "theme_id", "as_of"),)

    theme_score_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    theme_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("theme.theme_id", ondelete="CASCADE"), nullable=False
    )
    market: Mapped[str] = mapped_column(String(2), nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)  # intraday|swing|long
    score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    components: Mapped[dict | None] = mapped_column(JSONB)  # {price,volume,attention,news} z + raw
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    percentile: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    weights_version: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
