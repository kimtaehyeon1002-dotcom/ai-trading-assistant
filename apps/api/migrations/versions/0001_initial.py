"""initial: pgvector + core tables (Phase 0/1)

Revision ID: 0001
Revises:
Create Date: 2026-06-21
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # RAG(Phase 6) 대비 벡터 확장 미리 활성화
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "user",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(120)),
        sa.Column("role", sa.String(16), nullable=False, server_default="OWNER"),
        sa.Column(
            "investment_styles",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
        sa.Column("locale", sa.String(8), nullable=False, server_default="ko"),
        sa.Column("timezone", sa.String(40), nullable=False, server_default="Asia/Seoul"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
    )
    op.create_index("ix_user_email", "user", ["email"], unique=True)

    op.create_table(
        "auth_credential",
        sa.Column("credential_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_subject", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255)),
        sa.Column("secret_enc", sa.LargeBinary()),
        sa.Column("token_expires_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("provider", "provider_subject", name="uq_auth_provider_subject"),
    )
    op.create_index("ix_auth_credential_user_id", "auth_credential", ["user_id"])

    op.create_table(
        "instrument",
        sa.Column("instrument_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("market", sa.String(2), nullable=False),
        sa.Column("ticker", sa.String(32), nullable=False),
        sa.Column("symbol_norm", sa.String(48), nullable=False),
        sa.Column("exchange", sa.String(16)),
        sa.Column("name_local", sa.String(255)),
        sa.Column("name_en", sa.String(255)),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("timezone", sa.String(40), nullable=False),
        sa.Column("asset_type", sa.String(16), nullable=False, server_default="EQUITY"),
        sa.Column("isin", sa.String(12)),
        sa.Column("sector", sa.String(64)),
        sa.Column("industry", sa.String(64)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("listed_at", sa.Date()),
        sa.Column("delisted_at", sa.Date()),
        sa.Column("metadata", postgresql.JSONB()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.UniqueConstraint("market", "ticker", name="uq_instrument_market_ticker"),
        sa.CheckConstraint("market in ('KR','US')", name="ck_instrument_market"),
    )
    op.create_index("ix_instrument_symbol_norm", "instrument", ["symbol_norm"], unique=True)
    op.create_index("ix_instrument_isin", "instrument", ["isin"])
    op.create_index("ix_instrument_active", "instrument", ["market", "is_active"])

    op.create_table(
        "data_provider_source",
        sa.Column("provider_source_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(32), nullable=False),
        sa.Column("tier", sa.String(8), nullable=False),
        sa.Column("domain", sa.String(16), nullable=False),
        sa.Column(
            "markets",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
        sa.Column("is_realtime", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("rate_limit", postgresql.JSONB()),
        sa.Column("terms_note", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.UniqueConstraint("name", "domain", name="uq_provider_name_domain"),
    )

    op.create_table(
        "agent_run",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.user_id", ondelete="SET NULL"),
        ),
        sa.Column("task_type", sa.String(32), nullable=False),
        sa.Column("model", sa.String(48), nullable=False),
        sa.Column("prompt_version", sa.String(32)),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_batch", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(16), nullable=False, server_default="ok"),
        sa.Column("error", sa.Text()),
        sa.Column("trace", postgresql.JSONB()),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_agent_run_task_started", "agent_run", ["task_type", "started_at"])
    op.create_index("ix_agent_run_model", "agent_run", ["model"])
    op.create_index("ix_agent_run_user_id", "agent_run", ["user_id"])


def downgrade() -> None:
    op.drop_table("agent_run")
    op.drop_table("data_provider_source")
    op.drop_index("ix_instrument_active", table_name="instrument")
    op.drop_index("ix_instrument_isin", table_name="instrument")
    op.drop_index("ix_instrument_symbol_norm", table_name="instrument")
    op.drop_table("instrument")
    op.drop_index("ix_auth_credential_user_id", table_name="auth_credential")
    op.drop_table("auth_credential")
    op.drop_index("ix_user_email", table_name="user")
    op.drop_table("user")
