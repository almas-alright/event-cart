from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from eventcart.database import Base
from eventcart.modules.events import EventEnvelope, OutboxEvent, OutboxEventStatus
from eventcart.workers.brokerless_dispatcher import dispatch_pending_batch


def test_brokerless_dispatcher_routes_pending_event_and_marks_published() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    handled_events: list[EventEnvelope] = []

    with Session(engine) as session:
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

        dispatched_count = dispatch_pending_batch(
            session,
            handlers={
                "OrderCreated": lambda _session, envelope: handled_events.append(
                    envelope
                )
            },
        )

        saved_event = session.get_one(OutboxEvent, event.event_id)

    assert dispatched_count == 1
    assert len(handled_events) == 1
    assert handled_events[0].event_id == event.event_id
    assert saved_event.status == OutboxEventStatus.PUBLISHED
    assert saved_event.published_at is not None
    assert saved_event.last_error is None


def test_brokerless_dispatcher_marks_unsupported_event_failed() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        event = OutboxEvent(
            event_type="UnknownEvent",
            event_version=1,
            aggregate_type="Order",
            aggregate_id="order-1",
            correlation_id="correlation-1",
            causation_id=None,
            payload={"order_id": "order-1"},
        )
        session.add(event)
        session.commit()

        dispatched_count = dispatch_pending_batch(session, handlers={})

        saved_event = session.scalars(select(OutboxEvent)).one()

    assert dispatched_count == 1
    assert saved_event.status == OutboxEventStatus.FAILED
    assert saved_event.failure_count == 1
    assert "No brokerless handler registered" in str(saved_event.last_error)
