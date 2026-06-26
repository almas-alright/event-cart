"""add outbox next attempt timestamp

Revision ID: 20260626_0010
Revises: 20260626_0009
Create Date: 2026-06-26 00:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260626_0010"
down_revision: str | None = "20260626_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "outbox_events",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_outbox_events_next_attempt_at",
        "outbox_events",
        ["next_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_events_next_attempt_at", table_name="outbox_events")
    op.drop_column("outbox_events", "next_attempt_at")
