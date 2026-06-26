from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from eventcart.database import Base
from eventcart.modules.events import (
    EventProcessingAttempt,
    EventProcessingAttemptRepository,
    OutboxEvent,
)


def test_event_processing_attempt_repository_records_numbered_failures() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

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
        session.flush()

        repository = EventProcessingAttemptRepository(session)
        first = repository.record_failure(
            event_id=outbox_event.event_id,
            consumer_name="inventory-worker",
            error="temporary database timeout",
        )
        second = repository.record_failure(
            event_id=outbox_event.event_id,
            consumer_name="inventory-worker",
            error="still timing out",
        )

        attempts = session.scalars(
            select(EventProcessingAttempt).order_by(
                EventProcessingAttempt.attempt_number
            )
        ).all()

    assert first.attempt_number == 1
    assert second.attempt_number == 2
    assert [attempt.error for attempt in attempts] == [
        "temporary database timeout",
        "still timing out",
    ]
    assert attempts[0].event_id == outbox_event.event_id
    assert attempts[0].consumer_name == "inventory-worker"
    assert attempts[0].attempted_at is not None


def test_event_processing_attempts_are_counted_per_consumer() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

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
        session.flush()

        repository = EventProcessingAttemptRepository(session)
        repository.record_failure(
            event_id=outbox_event.event_id,
            consumer_name="inventory-worker",
            error="inventory failed",
        )
        repository.record_failure(
            event_id=outbox_event.event_id,
            consumer_name="audit-worker",
            error="audit failed",
        )

        assert (
            repository.count_failures(
                event_id=outbox_event.event_id,
                consumer_name="inventory-worker",
            )
            == 1
        )
        assert (
            repository.next_attempt_number(
                event_id=outbox_event.event_id,
                consumer_name="inventory-worker",
            )
            == 2
        )
