"""theme/theme_membership/theme_score + morning_report (Phase 3)

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-24
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "theme",
        sa.Column("theme_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("market", sa.String(2), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
        sa.Column("kr_link_slug", sa.String(64)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.UniqueConstraint("slug", name="uq_theme_slug"),
    )
    op.create_index("ix_theme_market", "theme", ["market", "is_active"])

    op.create_table(
        "theme_membership",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "theme_id", sa.BigInteger(), sa.ForeignKey("theme.theme_id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "instrument_id",
            sa.BigInteger(),
            sa.ForeignKey("instrument.instrument_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("weight", sa.Numeric(12, 4), nullable=False, server_default="1"),
        sa.UniqueConstraint("theme_id", "instrument_id", name="uq_theme_membership"),
    )
    op.create_index("ix_theme_membership_theme", "theme_membership", ["theme_id"])

    op.create_table(
        "theme_score",
        sa.Column("theme_score_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "theme_id", sa.BigInteger(), sa.ForeignKey("theme.theme_id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("market", sa.String(2), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timeframe", sa.String(16), nullable=False),
        sa.Column("score", sa.Numeric(6, 2), nullable=False),
        sa.Column("components", postgresql.JSONB()),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("percentile", sa.Numeric(6, 2), nullable=False),
        sa.Column("weights_version", sa.String(16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
    )
    op.create_index("ix_theme_score_theme_asof", "theme_score", ["theme_id", "as_of"])

    op.create_table(
        "morning_report",
        sa.Column("report_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("scope", sa.String(32), nullable=False, server_default="global"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("sections", postgresql.JSONB()),
        sa.Column("markdown", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(16), nullable=False, server_default="completed"),
        sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("model", sa.String(48)),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column(
            "agent_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_run.run_id", ondelete="SET NULL"),
        ),
        sa.Column("disclaimer_version", sa.String(32)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.UniqueConstraint("report_date", "scope", "version", name="uq_morning_report_date_scope_ver"),
    )
    op.create_index("ix_morning_report_date", "morning_report", ["report_date"])


def downgrade() -> None:
    op.drop_index("ix_morning_report_date", table_name="morning_report")
    op.drop_table("morning_report")
    op.drop_index("ix_theme_score_theme_asof", table_name="theme_score")
    op.drop_table("theme_score")
    op.drop_index("ix_theme_membership_theme", table_name="theme_membership")
    op.drop_table("theme_membership")
    op.drop_index("ix_theme_market", table_name="theme")
    op.drop_table("theme")
