from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from eventcart.database import Base
from eventcart.modules.events import EventEnvelope, OutboxEvent
from eventcart.modules.notifications import Notification, NotificationStatus
from eventcart.workers.notification_worker import handle_invoice_created


def test_notification_worker_records_notification_and_emits_event() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        outbox_event = handle_invoice_created(
            session,
            make_invoice_created_event(),
        )
        assert outbox_event is not None

        notification = session.scalars(select(Notification)).one()
        saved_outbox_event = session.get_one(OutboxEvent, outbox_event.event_id)

    assert notification.order_id == "order-1"
    assert notification.notification_type == "invoice_created"
    assert notification.status == NotificationStatus.SENT
    assert notification.recipient_email == "ada@example.com"
    assert notification.payload == {
        "invoice_id": "invoice-1",
        "amount_cents": 9000,
    }
    assert saved_outbox_event.event_type == "NotificationSent"
    assert saved_outbox_event.aggregate_id == "order-1"
    assert saved_outbox_event.correlation_id == "correlation-1"
    assert saved_outbox_event.causation_id == "event-1"
    assert saved_outbox_event.payload == {
        "order_id": "order-1",
        "invoice_id": "invoice-1",
        "notification_id": notification.id,
        "notification_type": "invoice_created",
    }


def make_invoice_created_event() -> EventEnvelope:
    return EventEnvelope(
        event_id="event-1",
        event_type="InvoiceCreated",
        event_version=1,
        aggregate_type="Order",
        aggregate_id="order-1",
        correlation_id="correlation-1",
        causation_id="payment-authorized-event",
        occurred_at=datetime(2026, 6, 26, tzinfo=UTC),
        payload={
            "order_id": "order-1",
            "payment_id": "payment-1",
            "invoice_id": "invoice-1",
            "amount_cents": 9000,
            "customer_email": "ada@example.com",
        },
    )
