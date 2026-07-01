"""trade_journal_entry — 매매일지(Notion 임포트) (Phase 4)

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-24
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trade_journal_entry",
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(16), nullable=False, server_default="notion"),
        sa.Column("source_row_id", sa.String(128), nullable=False),
        sa.Column("symbol", sa.String(32)),
        sa.Column("position", sa.String(8)),
        sa.Column("pnl", sa.Numeric(20, 6)),
        sa.Column("outcome", sa.String(8), nullable=False, server_default="unknown"),
        sa.Column("traded_on", sa.Date()),
        sa.Column("note", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.UniqueConstraint("user_id", "source", "source_row_id", name="uq_journal_source_row"),
    )
    op.create_index("ix_trade_journal_entry_user_id", "trade_journal_entry", ["user_id"])
    op.create_index("ix_trade_journal_entry_traded_on", "trade_journal_entry", ["traded_on"])


def downgrade() -> None:
    op.drop_index("ix_trade_journal_entry_traded_on", table_name="trade_journal_entry")
    op.drop_index("ix_trade_journal_entry_user_id", table_name="trade_journal_entry")
    op.drop_table("trade_journal_entry")
