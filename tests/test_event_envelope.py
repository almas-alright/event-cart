from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from eventcart.database import Base
from eventcart.modules.events import EventEnvelope, OutboxEvent, OutboxEventStatus


def test_event_envelope_contains_required_fields() -> None:
    envelope = EventEnvelope(
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

    assert envelope.event_id == "event-1"
    assert envelope.event_type == "OrderCreated"
    assert envelope.event_version == 1
    assert envelope.aggregate_type == "Order"
    assert envelope.aggregate_id == "order-1"
    assert envelope.correlation_id == "correlation-1"
    assert envelope.causation_id is None
    assert envelope.payload == {"order_id": "order-1"}


def test_outbox_event_persists_event_envelope_fields() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            OutboxEvent(
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
        )
        session.commit()

    with Session(engine) as session:
        saved_event = session.scalars(select(OutboxEvent)).one()

    assert saved_event.status == OutboxEventStatus.PENDING
    assert EventEnvelope.model_validate(saved_event).payload == {"order_id": "order-1"}
