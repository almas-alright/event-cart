"""Invoice worker handlers."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from eventcart.modules.events import EventEnvelope, OutboxEvent, notify_outbox_event
from eventcart.modules.idempotency import ConsumerInbox
from eventcart.modules.invoices import Invoice, InvoiceStatus

INVOICE_CONSUMER_NAME = "invoice-worker"


def handle_payment_authorized(
    session: Session,
    event: EventEnvelope,
) -> OutboxEvent | None:
    inbox = ConsumerInbox(session, consumer_name=INVOICE_CONSUMER_NAME)
    outbox_event = inbox.process_once(
        event,
        lambda handled_event: _create_invoice(session, handled_event),
    )
    if outbox_event is not None:
        session.commit()
    return outbox_event


def _create_invoice(session: Session, event: EventEnvelope) -> OutboxEvent:
    order_id = str(event.payload["order_id"])
    payment_id = str(event.payload["payment_id"])
    amount_cents = _int_payload_value(event.payload, "amount_cents")

    invoice = Invoice(
        order_id=order_id,
        payment_id=payment_id,
        status=InvoiceStatus.CREATED,
        amount_cents=amount_cents,
    )
    session.add(invoice)
    session.flush()

    outbox_event = _build_result_event(
        source_event=event,
        event_type="InvoiceCreated",
        order_id=order_id,
        payload={
            "order_id": order_id,
            "payment_id": payment_id,
            "invoice_id": invoice.id,
            "amount_cents": amount_cents,
        },
    )
    session.add(outbox_event)
    notify_outbox_event(session, outbox_event)
    return outbox_event


def _int_payload_value(payload: dict[str, object], key: str) -> int:
    value = payload[key]
    if not isinstance(value, int):
        raise TypeError(f"{key} must be an integer.")
    return value


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
