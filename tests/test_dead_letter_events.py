from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from eventcart.database import Base
from eventcart.modules.events import (
    DeadLetterEvent,
    EventEnvelope,
    EventProcessingAttempt,
    OutboxEvent,
    OutboxEventStatus,
)
from eventcart.workers.brokerless_dispatcher import (
    EventHandlerRegistration,
    RetryPolicy,
    dispatch_pending_batch,
)


def test_brokerless_dispatcher_moves_poison_event_to_dead_letter() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    def poison_handler(_session: Session, _event: EventEnvelope) -> None:
        raise RuntimeError("poison event")

    with Session(engine) as session:
        outbox_event = OutboxEvent(
            event_type="OrderCreated",
            event_version=1,
            aggregate_type="Order",
            aggregate_id="order-1",
            correlation_id="correlation-1",
            causation_id=None,
            payload={"order_id": "order-1"},
        )
        session.add(outbox_event)
        session.commit()

        dispatched_count = dispatch_pending_batch(
            session,
            handlers={
                "OrderCreated": EventHandlerRegistration(
                    consumer_name="inventory-worker",
                    handler=poison_handler,
                )
            },
            retry_policy=RetryPolicy(max_attempts=1),
        )

        saved_event = session.get_one(OutboxEvent, outbox_event.event_id)
        attempt = session.scalars(select(EventProcessingAttempt)).one()
        dead_letter_event = session.scalars(select(DeadLetterEvent)).one()

    assert dispatched_count == 1
    assert saved_event.status == OutboxEventStatus.FAILED
    assert saved_event.failure_count == 1
    assert saved_event.next_attempt_at is None
    assert attempt.attempt_number == 1
    assert dead_letter_event.event_id == outbox_event.event_id
    assert dead_letter_event.event_type == "OrderCreated"
    assert dead_letter_event.consumer_name == "inventory-worker"
    assert dead_letter_event.attempt_number == 1
    assert dead_letter_event.error == "poison event"
    assert dead_letter_event.payload == {"order_id": "order-1"}
