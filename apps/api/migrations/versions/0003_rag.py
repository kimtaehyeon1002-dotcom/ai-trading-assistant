"""rag_document + rag_chunk (pgvector HNSW) — 최소 RAG(Phase 2.5)

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-24
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from app.core.config import settings

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rag_document",
        sa.Column("doc_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_table", sa.String(32), nullable=False),
        sa.Column("source_pk", sa.String(128), nullable=False),
        sa.Column(
            "instrument_id",
            sa.BigInteger(),
            sa.ForeignKey("instrument.instrument_id", ondelete="SET NULL"),
        ),
        sa.Column("doc_type", sa.String(16), nullable=False),
        sa.Column("title", sa.String(512)),
        sa.Column("url", sa.Text()),
        sa.Column("language", sa.String(8), nullable=False, server_default="ko"),
        sa.Column("market", sa.String(2)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.user_id", ondelete="CASCADE"),
        ),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("license_ok", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.UniqueConstraint("content_hash", name="uq_rag_document_content_hash"),
    )
    op.create_index("ix_rag_document_source", "rag_document", ["source_table", "source_pk"])
    op.create_index("ix_rag_document_instrument_id", "rag_document", ["instrument_id"])
    op.create_index("ix_rag_document_owner_user_id", "rag_document", ["owner_user_id"])

    op.create_table(
        "rag_chunk",
        sa.Column("chunk_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "doc_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("rag_document.doc_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(settings.embed_dim), nullable=False),
        sa.Column("embed_model", sa.String(32), nullable=False),
        sa.Column("content_tsv", postgresql.TSVECTOR()),
        sa.Column(
            "symbols",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
        sa.Column("doc_type", sa.String(16), nullable=False),
        sa.Column("language", sa.String(8), nullable=False, server_default="ko"),
        sa.Column("market", sa.String(2)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("license_ok", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
    )
    op.create_index("ix_rag_chunk_doc", "rag_chunk", ["doc_id"])
    op.create_index("ix_rag_chunk_filter", "rag_chunk", ["doc_type", "language", "market"])
    op.create_index("ix_rag_chunk_owner_user_id", "rag_chunk", ["owner_user_id"])

    # 벡터 ANN(HNSW, cosine) + BM25용 GIN + 심볼 배열 GIN — raw SQL
    op.execute(
        "CREATE INDEX ix_rag_chunk_embedding_hnsw ON rag_chunk "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 200)"
    )
    op.execute("CREATE INDEX ix_rag_chunk_tsv ON rag_chunk USING gin (content_tsv)")
    op.execute("CREATE INDEX ix_rag_chunk_symbols ON rag_chunk USING gin (symbols)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_rag_chunk_symbols")
    op.execute("DROP INDEX IF EXISTS ix_rag_chunk_tsv")
    op.execute("DROP INDEX IF EXISTS ix_rag_chunk_embedding_hnsw")
    op.drop_index("ix_rag_chunk_owner_user_id", table_name="rag_chunk")
    op.drop_index("ix_rag_chunk_filter", table_name="rag_chunk")
    op.drop_index("ix_rag_chunk_doc", table_name="rag_chunk")
    op.drop_table("rag_chunk")
    op.drop_index("ix_rag_document_owner_user_id", table_name="rag_document")
    op.drop_index("ix_rag_document_instrument_id", table_name="rag_document")
    op.drop_index("ix_rag_document_source", table_name="rag_document")
    op.drop_table("rag_document")
