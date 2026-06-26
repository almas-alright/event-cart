"""Idempotency persistence models."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from eventcart.database import Base


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_body: Mapped[dict[str, object] | None] = mapped_column(JSON)
    status_code: Mapped[int | None] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC) + timedelta(hours=24),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class InboxEvent(Base):
    __tablename__ = "inbox_events"

    consumer_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
