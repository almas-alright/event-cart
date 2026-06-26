"""create event processing attempts

Revision ID: 20260626_0009
Revises: 20260626_0008
Create Date: 2026-06-26 00:09:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260626_0009"
down_revision: str | None = "20260626_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "event_processing_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("consumer_name", sa.String(length=100), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("error", sa.String(length=500), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["outbox_events.event_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_event_processing_attempts_event_id",
        "event_processing_attempts",
        ["event_id"],
    )
    op.create_index(
        "ix_event_processing_attempts_consumer_name",
        "event_processing_attempts",
        ["consumer_name"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_event_processing_attempts_consumer_name",
        table_name="event_processing_attempts",
    )
    op.drop_index(
        "ix_event_processing_attempts_event_id",
        table_name="event_processing_attempts",
    )
    op.drop_table("event_processing_attempts")
