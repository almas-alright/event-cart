from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from eventcart.database import Base
from eventcart.modules.events import EventEnvelope
from eventcart.modules.idempotency import ConsumerInbox, InboxEvent


def test_consumer_inbox_processes_event_once_per_consumer() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    event = make_event()
    calls: list[str] = []

    with Session(engine) as session:
        inbox = ConsumerInbox(session, consumer_name="inventory-worker")

        def record_event(handled_event: EventEnvelope) -> None:
            calls.append(handled_event.event_id)

        first_result = inbox.process_once(event, record_event)
        second_result = inbox.process_once(event, record_event)
        session.commit()

        saved_marker = session.get_one(InboxEvent, ("inventory-worker", "event-1"))

    assert first_result is None
    assert second_result is None
    assert calls == ["event-1"]
    assert saved_marker.consumer_name == "inventory-worker"


def test_consumer_inbox_tracks_consumers_independently() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    event = make_event()
    calls: list[str] = []

    with Session(engine) as session:
        first_inbox = ConsumerInbox(session, consumer_name="inventory-worker")
        second_inbox = ConsumerInbox(session, consumer_name="audit-worker")

        def record_inventory_event(handled_event: EventEnvelope) -> None:
            calls.append(f"inventory:{handled_event.event_id}")

        def record_audit_event(handled_event: EventEnvelope) -> None:
            calls.append(f"audit:{handled_event.event_id}")

        first_inbox.process_once(event, record_inventory_event)
        second_inbox.process_once(event, record_audit_event)
        session.commit()

    assert calls == ["inventory:event-1", "audit:event-1"]


def make_event() -> EventEnvelope:
    return EventEnvelope(
        event_id="event-1",
        event_type="OrderCreated",
        event_version=1,
        aggregate_type="Order",
        aggregate_id="order-1",
        correlation_id="correlation-1",
        causation_id=None,
        occurred_at=datetime(2026, 6, 26, tzinfo=UTC),
        payload={"order_id": "order-1"},
    )
