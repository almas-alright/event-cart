"""PostgreSQL brokerless outbox dispatcher."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from sqlalchemy.orm import Session

from eventcart.database import SessionLocal
from eventcart.modules.events import EventEnvelope, OutboxRepository
from eventcart.workers.inventory_worker import (
    handle_order_created,
    handle_payment_failed,
)
from eventcart.workers.invoice_worker import handle_payment_authorized
from eventcart.workers.notification_worker import handle_invoice_created
from eventcart.workers.order_projection_worker import (
    handle_inventory_released,
    handle_notification_sent,
)
from eventcart.workers.outbox_publisher import envelope_from_outbox_event
from eventcart.workers.payment_worker import handle_inventory_reserved

EventHandler = Callable[[Session, EventEnvelope], object]


class UnsupportedEventTypeError(Exception):
    pass


def default_event_handlers() -> dict[str, EventHandler]:
    return {
        "OrderCreated": handle_order_created,
        "InventoryReserved": handle_inventory_reserved,
        "PaymentAuthorized": handle_payment_authorized,
        "InvoiceCreated": handle_invoice_created,
        "NotificationSent": handle_notification_sent,
        "PaymentFailed": handle_payment_failed,
        "InventoryReleased": handle_inventory_released,
    }


def dispatch_pending_batch(
    session: Session,
    *,
    handlers: Mapping[str, EventHandler] | None = None,
    limit: int = 50,
) -> int:
    repository = OutboxRepository(session)
    events = repository.fetch_pending(limit=limit)
    event_handlers = handlers or default_event_handlers()

    for event in events:
        try:
            handler = event_handlers.get(event.event_type)
            if handler is None:
                raise UnsupportedEventTypeError(
                    f"No brokerless handler registered for {event.event_type!r}."
                )

            handler(session, envelope_from_outbox_event(event))
            repository.mark_published(event.event_id)
        except Exception as error:
            repository.mark_failed(event.event_id, str(error))

        session.commit()

    return len(events)


def run_once(limit: int = 50) -> int:
    with SessionLocal() as session:
        return dispatch_pending_batch(session, limit=limit)


def main() -> None:
    run_once()


if __name__ == "__main__":
    main()
