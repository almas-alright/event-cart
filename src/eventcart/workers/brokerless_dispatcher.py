"""PostgreSQL brokerless outbox dispatcher."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from eventcart.database import SessionLocal
from eventcart.modules.events import (
    DeadLetterEventRepository,
    EventEnvelope,
    EventProcessingAttemptRepository,
    OutboxRepository,
)
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


@dataclass(frozen=True)
class EventHandlerRegistration:
    consumer_name: str
    handler: EventHandler


@dataclass(frozen=True)
class RetryPolicy:
    backoff_seconds: int = 5
    max_attempts: int = 3

    def delay_for_attempt(self, attempt_number: int) -> timedelta:
        return timedelta(seconds=self.backoff_seconds * attempt_number)


class UnsupportedEventTypeError(Exception):
    pass


def default_event_handlers() -> dict[str, EventHandlerRegistration]:
    return {
        "OrderCreated": EventHandlerRegistration(
            consumer_name="inventory-worker",
            handler=handle_order_created,
        ),
        "InventoryReserved": EventHandlerRegistration(
            consumer_name="payment-worker",
            handler=handle_inventory_reserved,
        ),
        "PaymentAuthorized": EventHandlerRegistration(
            consumer_name="invoice-worker",
            handler=handle_payment_authorized,
        ),
        "InvoiceCreated": EventHandlerRegistration(
            consumer_name="notification-worker",
            handler=handle_invoice_created,
        ),
        "NotificationSent": EventHandlerRegistration(
            consumer_name="order-projection-worker",
            handler=handle_notification_sent,
        ),
        "PaymentFailed": EventHandlerRegistration(
            consumer_name="inventory-compensation-worker",
            handler=handle_payment_failed,
        ),
        "InventoryReleased": EventHandlerRegistration(
            consumer_name="order-projection-worker",
            handler=handle_inventory_released,
        ),
    }


def dispatch_pending_batch(
    session: Session,
    *,
    handlers: Mapping[str, EventHandlerRegistration] | None = None,
    limit: int = 50,
    retry_policy: RetryPolicy | None = None,
) -> int:
    repository = OutboxRepository(session)
    events = repository.fetch_pending(limit=limit)
    attempt_repository = EventProcessingAttemptRepository(session)
    dead_letter_repository = DeadLetterEventRepository(session)
    event_handlers = handlers or default_event_handlers()
    policy = retry_policy or RetryPolicy()

    for event in events:
        try:
            registration = event_handlers.get(event.event_type)
            if registration is None:
                raise UnsupportedEventTypeError(
                    f"No brokerless handler registered for {event.event_type!r}."
                )

            registration.handler(session, envelope_from_outbox_event(event))
            repository.mark_published(event.event_id)
        except Exception as error:
            consumer_name = _consumer_name_for_failure(
                event_type=event.event_type,
                handlers=event_handlers,
            )
            attempt = attempt_repository.record_failure(
                event_id=event.event_id,
                consumer_name=consumer_name,
                error=str(error),
            )
            if attempt.attempt_number >= policy.max_attempts:
                dead_letter_repository.move_to_dead_letter(
                    event=event,
                    consumer_name=consumer_name,
                    attempt_number=attempt.attempt_number,
                    error=str(error),
                )
                repository.mark_failed(event.event_id, str(error))
            else:
                repository.mark_retryable_failure(
                    event.event_id,
                    error=str(error),
                    next_attempt_at=datetime.now(UTC)
                    + policy.delay_for_attempt(attempt.attempt_number),
                )

        session.commit()

    return len(events)


def dispatch_until_idle(
    session: Session,
    *,
    handlers: Mapping[str, EventHandlerRegistration] | None = None,
    limit: int = 50,
    max_batches: int = 100,
    retry_policy: RetryPolicy | None = None,
) -> int:
    dispatched_total = 0
    for _ in range(max_batches):
        dispatched_count = dispatch_pending_batch(
            session,
            handlers=handlers,
            limit=limit,
            retry_policy=retry_policy,
        )
        dispatched_total += dispatched_count
        if dispatched_count == 0:
            return dispatched_total

    raise RuntimeError("Brokerless dispatcher did not become idle.")


def run_once(limit: int = 50) -> int:
    with SessionLocal() as session:
        return dispatch_pending_batch(session, limit=limit)


def _consumer_name_for_failure(
    *,
    event_type: str,
    handlers: Mapping[str, EventHandlerRegistration],
) -> str:
    registration = handlers.get(event_type)
    if registration is None:
        return "brokerless-dispatcher"
    return registration.consumer_name


def main() -> None:
    run_once()


if __name__ == "__main__":
    main()
