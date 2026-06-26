import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from eventcart.database import Base
from eventcart.modules.events import (
    DeadLetterEvent,
    DeadLetterEventRepository,
    OutboxEvent,
    OutboxEventStatus,
)


def test_dead_letter_repository_replays_event_once() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        dead_letter_event = DeadLetterEvent(
            event_id="failed-event-1",
            event_type="OrderCreated",
            event_version=1,
            aggregate_type="Order",
            aggregate_id="order-1",
            correlation_id="correlation-1",
            causation_id=None,
            consumer_name="inventory-worker",
            attempt_number=3,
            error="poison event",
            payload={"order_id": "order-1"},
        )
        session.add(dead_letter_event)
        session.commit()

        replay_event = DeadLetterEventRepository(session).replay(dead_letter_event.id)
        session.commit()

        saved_dead_letter = session.get_one(DeadLetterEvent, dead_letter_event.id)
        outbox_events = session.scalars(select(OutboxEvent)).all()

    assert replay_event.event_id != "failed-event-1"
    assert replay_event.event_type == "OrderCreated"
    assert replay_event.event_version == 1
    assert replay_event.aggregate_id == "order-1"
    assert replay_event.correlation_id == "correlation-1"
    assert replay_event.status == OutboxEventStatus.PENDING
    assert replay_event.payload == {"order_id": "order-1"}
    assert saved_dead_letter.replayed_at is not None
    assert [event.event_id for event in outbox_events] == [replay_event.event_id]


def test_dead_letter_repository_rejects_duplicate_replay() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        dead_letter_event = DeadLetterEvent(
            event_id="failed-event-1",
            event_type="OrderCreated",
            event_version=1,
            aggregate_type="Order",
            aggregate_id="order-1",
            correlation_id="correlation-1",
            causation_id=None,
            consumer_name="inventory-worker",
            attempt_number=3,
            error="poison event",
            payload={"order_id": "order-1"},
        )
        session.add(dead_letter_event)
        session.commit()

        repository = DeadLetterEventRepository(session)
        repository.replay(dead_letter_event.id)
        session.commit()

        with pytest.raises(ValueError):
            repository.replay(dead_letter_event.id)
