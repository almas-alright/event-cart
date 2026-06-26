"""create notifications

Revision ID: 20260626_0008
Revises: 20260626_0007
Create Date: 2026-06-26 00:08:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260626_0008"
down_revision: str | None = "20260626_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("notification_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("recipient_email", sa.String(length=320), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_order_id", "notifications", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_notifications_order_id", table_name="notifications")
    op.drop_table("notifications")
