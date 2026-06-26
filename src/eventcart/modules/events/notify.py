"""PostgreSQL outbox notification helpers."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from eventcart.modules.events.models import OutboxEvent

OUTBOX_NOTIFY_CHANNEL = "eventcart_outbox"


def notify_outbox_event(session: Session, event: OutboxEvent) -> bool:
    session.flush()
    if session.get_bind().dialect.name != "postgresql":
        return False

    session.execute(
        text("select pg_notify(:channel, :payload)"),
        {"channel": OUTBOX_NOTIFY_CHANNEL, "payload": event.event_id},
    )
    return True


def outbox_listen_sql() -> str:
    return f"LISTEN {OUTBOX_NOTIFY_CHANNEL}"
