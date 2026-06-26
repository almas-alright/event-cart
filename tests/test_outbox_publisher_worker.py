from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from eventcart.database import Base
from eventcart.modules.events import EventEnvelope, OutboxEvent, OutboxEventStatus
from eventcart.workers.outbox_publisher import publish_pending_batch


class FakePublisher:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.published: list[EventEnvelope] = []

    async def publish(self, envelope: EventEnvelope) -> None:
        if self.should_fail:
            raise RuntimeError("publish failed")
        self.published.append(envelope)


@pytest.mark.anyio
async def test_outbox_publisher_publishes_pending_events_and_marks_published() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(make_event("event-1"))
        session.commit()

        publisher = FakePublisher()
        processed_count = await publish_pending_batch(session, publisher, limit=10)

        saved_event = session.get_one(OutboxEvent, "event-1")

    assert processed_count == 1
    assert [event.event_id for event in publisher.published] == ["event-1"]
    assert saved_event.status == OutboxEventStatus.PUBLISHED
    assert saved_event.published_at is not None


@pytest.mark.anyio
async def test_outbox_publisher_marks_failed_when_publish_fails() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(make_event("event-1"))
        session.commit()

        publisher = FakePublisher(should_fail=True)
        processed_count = await publish_pending_batch(session, publisher, limit=10)

        saved_event = session.get_one(OutboxEvent, "event-1")

    assert processed_count == 1
    assert saved_event.status == OutboxEventStatus.FAILED
    assert saved_event.failure_count == 1
    assert saved_event.last_error == "publish failed"


def make_event(event_id: str) -> OutboxEvent:
    return OutboxEvent(
        event_id=event_id,
        event_type="OrderCreated",
        event_version=1,
        aggregate_type="Order",
        aggregate_id="order-1",
        correlation_id="correlation-1",
        causation_id=None,
        occurred_at=datetime(2026, 6, 26, tzinfo=UTC),
        payload={"order_id": "order-1"},
    )
