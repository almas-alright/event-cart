"""create dead letter events

Revision ID: 20260626_0011
Revises: 20260626_0010
Create Date: 2026-06-26 00:11:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260626_0011"
down_revision: str | None = "20260626_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dead_letter_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", sa.String(length=36), nullable=False),
        sa.Column("consumer_name", sa.String(length=100), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("error", sa.String(length=500), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("replayed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dead_letter_events_event_id",
        "dead_letter_events",
        ["event_id"],
    )
    op.create_index(
        "ix_dead_letter_events_consumer_name",
        "dead_letter_events",
        ["consumer_name"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dead_letter_events_consumer_name",
        table_name="dead_letter_events",
    )
    op.drop_index("ix_dead_letter_events_event_id", table_name="dead_letter_events")
    op.drop_table("dead_letter_events")
