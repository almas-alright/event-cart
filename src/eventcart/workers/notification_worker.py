"""Notification worker handlers."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from eventcart.modules.events import EventEnvelope, OutboxEvent
from eventcart.modules.idempotency import ConsumerInbox
from eventcart.modules.notifications import Notification, NotificationStatus

NOTIFICATION_CONSUMER_NAME = "notification-worker"


def handle_invoice_created(
    session: Session,
    event: EventEnvelope,
) -> OutboxEvent | None:
    inbox = ConsumerInbox(session, consumer_name=NOTIFICATION_CONSUMER_NAME)
    outbox_event = inbox.process_once(
        event,
        lambda handled_event: _send_invoice_notification(session, handled_event),
    )
    if outbox_event is not None:
        session.commit()
    return outbox_event


def _send_invoice_notification(session: Session, event: EventEnvelope) -> OutboxEvent:
    order_id = str(event.payload["order_id"])
    invoice_id = str(event.payload["invoice_id"])
    recipient_email = event.payload.get("customer_email")
    if recipient_email is not None and not isinstance(recipient_email, str):
        recipient_email = None

    notification = Notification(
        order_id=order_id,
        notification_type="invoice_created",
        status=NotificationStatus.SENT,
        recipient_email=recipient_email,
        payload={
            "invoice_id": invoice_id,
            "amount_cents": event.payload.get("amount_cents"),
        },
    )
    session.add(notification)
    session.flush()

    outbox_event = _build_result_event(
        source_event=event,
        event_type="NotificationSent",
        order_id=order_id,
        payload={
            "order_id": order_id,
            "invoice_id": invoice_id,
            "notification_id": notification.id,
            "notification_type": notification.notification_type,
        },
    )
    session.add(outbox_event)
    return outbox_event


def _build_result_event(
    *,
    source_event: EventEnvelope,
    event_type: str,
    order_id: str,
    payload: dict[str, Any],
) -> OutboxEvent:
    return OutboxEvent(
        event_type=event_type,
        event_version=1,
        aggregate_type="Order",
        aggregate_id=order_id,
        correlation_id=source_event.correlation_id,
        causation_id=source_event.event_id,
        payload=payload,
    )
