"""portfolio + holding (Phase 5)

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-24
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portfolio",
        sa.Column("portfolio_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(64), nullable=False, server_default="기본 포트폴리오"),
        sa.Column("base_currency", sa.String(3), nullable=False, server_default="KRW"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
    )
    op.create_index("ix_portfolio_user_id", "portfolio", ["user_id"])

    op.create_table(
        "holding",
        sa.Column("holding_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "portfolio_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("portfolio.portfolio_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "instrument_id",
            sa.BigInteger(),
            sa.ForeignKey("instrument.instrument_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Numeric(28, 8), nullable=False),
        sa.Column("avg_cost", sa.Numeric(20, 6)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.UniqueConstraint("portfolio_id", "instrument_id", name="uq_holding_portfolio_instrument"),
    )
    op.create_index("ix_holding_portfolio_id", "holding", ["portfolio_id"])


def downgrade() -> None:
    op.drop_index("ix_holding_portfolio_id", table_name="holding")
    op.drop_table("holding")
    op.drop_index("ix_portfolio_user_id", table_name="portfolio")
    op.drop_table("portfolio")
