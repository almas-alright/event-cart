from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from eventcart.database import Base
from eventcart.modules.events import (
    OUTBOX_NOTIFY_CHANNEL,
    OutboxEvent,
    notify_outbox_event,
    outbox_listen_sql,
)


def test_notify_outbox_event_noops_outside_postgresql() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

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

        did_notify = notify_outbox_event(session, event)

    assert did_notify is False
    assert event.event_id is not None


def test_outbox_listen_sql_uses_shared_channel_name() -> None:
    assert OUTBOX_NOTIFY_CHANNEL == "eventcart_outbox"
    assert outbox_listen_sql() == "LISTEN eventcart_outbox"
