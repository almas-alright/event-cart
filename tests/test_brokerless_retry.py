from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from eventcart.database import Base
from eventcart.modules.events import (
    EventEnvelope,
    EventProcessingAttempt,
    OutboxEvent,
    OutboxEventStatus,
    OutboxRepository,
)
from eventcart.workers.brokerless_dispatcher import (
    EventHandlerRegistration,
    RetryPolicy,
    dispatch_pending_batch,
)


def test_brokerless_dispatcher_records_attempt_and_schedules_retry() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    def fail_once(_session: Session, _event: EventEnvelope) -> None:
        raise RuntimeError("temporary worker failure")

    with Session(engine) as session:
        event = _add_outbox_event(session)

        dispatched_count = dispatch_pending_batch(
            session,
            handlers={
                "OrderCreated": EventHandlerRegistration(
                    consumer_name="inventory-worker",
                    handler=fail_once,
                )
            },
            retry_policy=RetryPolicy(backoff_seconds=10),
        )

        saved_event = session.get_one(OutboxEvent, event.event_id)
        attempt = session.scalars(select(EventProcessingAttempt)).one()

    assert dispatched_count == 1
    assert saved_event.status == OutboxEventStatus.PENDING
    assert saved_event.failure_count == 1
    assert saved_event.next_attempt_at is not None
    assert "temporary worker failure" in str(saved_event.last_error)
    assert attempt.event_id == event.event_id
    assert attempt.consumer_name == "inventory-worker"
    assert attempt.attempt_number == 1
    assert attempt.error == "temporary worker failure"


def test_outbox_repository_skips_events_until_next_attempt_time() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        event = _add_outbox_event(session)
        repository = OutboxRepository(session)
        repository.mark_retryable_failure(
            event.event_id,
            error="temporary failure",
            next_attempt_at=datetime(2026, 6, 26, 12, 5, tzinfo=UTC),
        )
        session.commit()

        early_events = repository.fetch_pending(
            limit=10,
            now=datetime(2026, 6, 26, 12, 4, tzinfo=UTC),
        )
        ready_events = repository.fetch_pending(
            limit=10,
            now=datetime(2026, 6, 26, 12, 5, tzinfo=UTC),
        )

    assert early_events == []
    assert [ready_event.event_id for ready_event in ready_events] == [event.event_id]


def _add_outbox_event(session: Session) -> OutboxEvent:
    event = OutboxEvent(
        event_type="OrderCreated",
        event_version=1,
        aggregate_type="Order",
        aggregate_id="order-1",
        correlation_id="correlation-1",
        causation_id=None,
        payload={"order_id": "order-1"},
    )
    session.add(event)
    session.commit()
    return event
