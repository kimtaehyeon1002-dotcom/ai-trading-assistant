"""research_report: AI Research 4-블록 산출물(감사 영속화)

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-24
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_report",
        sa.Column("report_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.user_id", ondelete="SET NULL"),
        ),
        sa.Column(
            "instrument_id",
            sa.BigInteger(),
            sa.ForeignKey("instrument.instrument_id", ondelete="SET NULL"),
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("query", sa.Text()),
        sa.Column("style", sa.String(16), nullable=False, server_default="swing"),
        sa.Column("depth", sa.String(16), nullable=False, server_default="standard"),
        sa.Column("status", sa.String(16), nullable=False, server_default="completed"),
        sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("markdown", sa.Text(), nullable=False, server_default=""),
        sa.Column("blocks", postgresql.JSONB()),
        sa.Column("citations", postgresql.JSONB()),
        sa.Column("intent", postgresql.JSONB()),
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
    )
    op.create_index("ix_research_report_user_id", "research_report", ["user_id"])
    op.create_index("ix_research_report_instrument_id", "research_report", ["instrument_id"])


def downgrade() -> None:
    op.drop_index("ix_research_report_instrument_id", table_name="research_report")
    op.drop_index("ix_research_report_user_id", table_name="research_report")
    op.drop_table("research_report")
