"""create invoices

Revision ID: 20260626_0007
Revises: 20260626_0006
Create Date: 2026-06-26 00:07:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260626_0007"
down_revision: str | None = "20260626_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invoices",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("payment_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoices_order_id", "invoices", ["order_id"])
    op.create_index("ix_invoices_payment_id", "invoices", ["payment_id"])


def downgrade() -> None:
    op.drop_index("ix_invoices_payment_id", table_name="invoices")
    op.drop_index("ix_invoices_order_id", table_name="invoices")
    op.drop_table("invoices")
