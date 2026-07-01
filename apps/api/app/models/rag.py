"""RAG 저장 — rag_document(원천 추적) + rag_chunk(검색 단위). 설계서 §4.2, §5.2.

- 임베딩 모델/차원 고정: voyage-3.5 1024D(embed_model 컬럼으로 추적, A/B 시 별도 인덱스).
- 저작권 안전: 뉴스는 본문 미저장 — content에는 제목 + 자체요약만 적재(license_ok 플래그).
- 권한 필터(owner_user_id/is_public/license_ok)와 메타 필터(doc_type/market/published_at/symbols)를
  rag_chunk에 비정규화해 단일 쿼리로 필터링.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.models.base import Base


class RagDocument(Base):
    __tablename__ = "rag_document"
    __table_args__ = (
        Index("ix_rag_document_source", "source_table", "source_pk"),
    )

    doc_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_table: Mapped[str] = mapped_column(String(32), nullable=False)  # news_article|user_note|filing...
    source_pk: Mapped[str] = mapped_column(String(128), nullable=False)
    instrument_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("instrument.instrument_id", ondelete="SET NULL"), index=True
    )
    doc_type: Mapped[str] = mapped_column(String(16), nullable=False)  # news|filing|report|note
    title: Mapped[str | None] = mapped_column(String(512))
    url: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(8), default="ko", nullable=False)
    market: Mapped[str | None] = mapped_column(String(2))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)  # dedup
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.user_id", ondelete="CASCADE"), index=True
    )
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    license_ok: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RagChunk(Base):
    __tablename__ = "rag_chunk"
    __table_args__ = (
        Index("ix_rag_chunk_doc", "doc_id"),
        Index("ix_rag_chunk_filter", "doc_type", "language", "market"),
        # HNSW(embedding) / GIN(content_tsv) / GIN(symbols)는 마이그레이션에서 raw SQL로 생성.
    )

    chunk_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    doc_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rag_document.doc_id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # 뉴스 본문 미포함(제목+요약)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embed_dim), nullable=False)
    embed_model: Mapped[str] = mapped_column(String(32), nullable=False)
    content_tsv: Mapped[str | None] = mapped_column(TSVECTOR)  # 향후 BM25(Phase 6)
    symbols: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    # 권한/메타 필터(비정규화)
    doc_type: Mapped[str] = mapped_column(String(16), nullable=False)
    language: Mapped[str] = mapped_column(String(8), default="ko", nullable=False)
    market: Mapped[str | None] = mapped_column(String(2))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    license_ok: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
