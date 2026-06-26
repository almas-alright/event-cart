"""add dead letter replay fields

Revision ID: 20260626_0012
Revises: 20260626_0011
Create Date: 2026-06-26 00:12:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260626_0012"
down_revision: str | None = "20260626_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "dead_letter_events",
        sa.Column("event_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "dead_letter_events",
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
    )
    op.add_column(
        "dead_letter_events",
        sa.Column("causation_id", sa.String(length=36), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("dead_letter_events", "causation_id")
    op.drop_column("dead_letter_events", "correlation_id")
    op.drop_column("dead_letter_events", "event_version")
