from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from eventcart.database import Base
from eventcart.modules.events import OutboxEvent, OutboxEventStatus, OutboxRepository


def test_fetch_pending_returns_oldest_pending_events_up_to_limit() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add_all(
            [
                make_event("event-2", datetime(2026, 6, 26, 10, 1, tzinfo=UTC)),
                make_event("event-1", datetime(2026, 6, 26, 10, 0, tzinfo=UTC)),
                make_event(
                    "event-3",
                    datetime(2026, 6, 26, 10, 2, tzinfo=UTC),
                    status=OutboxEventStatus.PUBLISHED,
                ),
            ]
        )
        session.commit()

        events = OutboxRepository(session).fetch_pending(limit=1)

    assert [event.event_id for event in events] == ["event-1"]


def test_mark_published_updates_status_and_timestamp() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(make_event("event-1", datetime.now(UTC)))
        session.commit()

        repository = OutboxRepository(session)
        repository.mark_published("event-1")
        session.commit()

        saved_event = session.get_one(OutboxEvent, "event-1")

    assert saved_event.status == OutboxEventStatus.PUBLISHED
    assert saved_event.published_at is not None
    assert saved_event.last_error is None


def test_mark_failed_records_failure_metadata() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(make_event("event-1", datetime.now(UTC)))
        session.commit()

        repository = OutboxRepository(session)
        repository.mark_failed("event-1", "transport timeout")
        session.commit()

        saved_event = session.get_one(OutboxEvent, "event-1")

    assert saved_event.status == OutboxEventStatus.FAILED
    assert saved_event.failure_count == 1
    assert saved_event.last_error == "transport timeout"


def make_event(
    event_id: str,
    occurred_at: datetime,
    status: OutboxEventStatus = OutboxEventStatus.PENDING,
) -> OutboxEvent:
    return OutboxEvent(
        event_id=event_id,
        event_type="OrderCreated",
        event_version=1,
        aggregate_type="Order",
        aggregate_id=f"order-{event_id}",
        correlation_id=f"correlation-{event_id}",
        causation_id=None,
        occurred_at=occurred_at + timedelta(microseconds=0),
        payload={"event_id": event_id},
        status=status,
    )
