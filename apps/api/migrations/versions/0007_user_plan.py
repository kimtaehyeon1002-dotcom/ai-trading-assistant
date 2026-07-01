"""user.plan — 요금제(Phase 7)

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-24
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user", sa.Column("plan", sa.String(16), nullable=False, server_default="free")
    )


def downgrade() -> None:
    op.drop_column("user", "plan")
