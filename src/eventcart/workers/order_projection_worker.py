"""Order projection worker handlers."""

from __future__ import annotations

from sqlalchemy.orm import Session

from eventcart.modules.events import EventEnvelope
from eventcart.modules.idempotency import ConsumerInbox
from eventcart.modules.orders import Order, OrderStatus

ORDER_PROJECTION_CONSUMER_NAME = "order-projection-worker"


def handle_notification_sent(
    session: Session,
    event: EventEnvelope,
) -> Order | None:
    inbox = ConsumerInbox(session, consumer_name=ORDER_PROJECTION_CONSUMER_NAME)
    order = inbox.process_once(
        event,
        lambda handled_event: _mark_order_completed(session, handled_event),
    )
    if order is not None:
        session.commit()
    return order


def handle_inventory_released(
    session: Session,
    event: EventEnvelope,
) -> Order | None:
    inbox = ConsumerInbox(session, consumer_name=ORDER_PROJECTION_CONSUMER_NAME)
    order = inbox.process_once(
        event,
        lambda handled_event: _mark_order_cancelled(session, handled_event),
    )
    if order is not None:
        session.commit()
    return order


def _mark_order_completed(session: Session, event: EventEnvelope) -> Order:
    order_id = str(event.payload["order_id"])
    order = session.get(Order, order_id)
    if order is None:
        raise LookupError(f"Order {order_id!r} was not found.")

    order.status = OrderStatus.COMPLETED
    session.flush()
    return order


def _mark_order_cancelled(session: Session, event: EventEnvelope) -> Order:
    order_id = str(event.payload["order_id"])
    order = session.get(Order, order_id)
    if order is None:
        raise LookupError(f"Order {order_id!r} was not found.")

    order.status = OrderStatus.CANCELLED
    session.flush()
    return order
