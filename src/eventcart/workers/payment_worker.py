"""Payment worker handlers."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from eventcart.modules.events import EventEnvelope, OutboxEvent
from eventcart.modules.idempotency import ConsumerInbox
from eventcart.modules.payments import Payment, PaymentStatus

PAYMENT_CONSUMER_NAME = "payment-worker"


def handle_inventory_reserved(
    session: Session,
    event: EventEnvelope,
) -> OutboxEvent | None:
    inbox = ConsumerInbox(session, consumer_name=PAYMENT_CONSUMER_NAME)
    outbox_event = inbox.process_once(
        event,
        lambda handled_event: _authorize_payment(session, handled_event),
    )
    if outbox_event is not None:
        session.commit()
    return outbox_event


def _authorize_payment(session: Session, event: EventEnvelope) -> OutboxEvent:
    order_id = str(event.payload["order_id"])
    amount_cents = _amount_cents(event.payload)

    if event.payload.get("payment_should_fail") is True:
        payment = Payment(
            order_id=order_id,
            status=PaymentStatus.FAILED,
            amount_cents=amount_cents,
            failure_reason="Simulated payment failure.",
        )
        session.add(payment)
        session.flush()

        outbox_event = _build_result_event(
            source_event=event,
            event_type="PaymentFailed",
            order_id=order_id,
            payload={
                "order_id": order_id,
                "payment_id": payment.id,
                "amount_cents": amount_cents,
                "reason": payment.failure_reason,
                "items": event.payload.get("items", []),
            },
        )
        session.add(outbox_event)
        return outbox_event

    payment = Payment(
        order_id=order_id,
        status=PaymentStatus.AUTHORIZED,
        amount_cents=amount_cents,
        failure_reason=None,
    )
    session.add(payment)
    session.flush()

    outbox_event = _build_result_event(
        source_event=event,
        event_type="PaymentAuthorized",
        order_id=order_id,
        payload={
            "order_id": order_id,
            "payment_id": payment.id,
            "amount_cents": amount_cents,
        },
    )
    session.add(outbox_event)
    return outbox_event


def _amount_cents(payload: dict[str, object]) -> int:
    items = payload.get("items")
    if not isinstance(items, list):
        return 0

    total = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        quantity = item.get("quantity")
        unit_price_cents = item.get("unit_price_cents")
        if isinstance(quantity, int) and isinstance(unit_price_cents, int):
            total += quantity * unit_price_cents
    return total


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
