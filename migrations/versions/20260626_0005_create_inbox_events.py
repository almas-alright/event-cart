"""create inbox events

Revision ID: 20260626_0005
Revises: 20260626_0004
Create Date: 2026-06-26 00:05:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260626_0005"
down_revision: str | None = "20260626_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inbox_events",
        sa.Column("consumer_name", sa.String(length=100), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("consumer_name", "event_id"),
    )
    op.create_index("ix_inbox_events_event_id", "inbox_events", ["event_id"])


def downgrade() -> None:
    op.drop_index("ix_inbox_events_event_id", table_name="inbox_events")
    op.drop_table("inbox_events")

