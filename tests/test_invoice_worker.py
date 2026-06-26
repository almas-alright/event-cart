from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from eventcart.database import Base
from eventcart.modules.events import EventEnvelope, OutboxEvent
from eventcart.modules.invoices import Invoice, InvoiceStatus
from eventcart.workers.invoice_worker import handle_payment_authorized


def test_invoice_worker_creates_invoice_and_emits_event() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        outbox_event = handle_payment_authorized(
            session,
            make_payment_authorized_event(),
        )
        assert outbox_event is not None

        invoice = session.scalars(select(Invoice)).one()
        saved_outbox_event = session.get_one(OutboxEvent, outbox_event.event_id)

    assert invoice.order_id == "order-1"
    assert invoice.payment_id == "payment-1"
    assert invoice.status == InvoiceStatus.CREATED
    assert invoice.amount_cents == 9000
    assert saved_outbox_event.event_type == "InvoiceCreated"
    assert saved_outbox_event.aggregate_id == "order-1"
    assert saved_outbox_event.correlation_id == "correlation-1"
    assert saved_outbox_event.causation_id == "event-1"
    assert saved_outbox_event.payload == {
        "order_id": "order-1",
        "payment_id": "payment-1",
        "invoice_id": invoice.id,
        "amount_cents": 9000,
    }


def make_payment_authorized_event() -> EventEnvelope:
    return EventEnvelope(
        event_id="event-1",
        event_type="PaymentAuthorized",
        event_version=1,
        aggregate_type="Order",
        aggregate_id="order-1",
        correlation_id="correlation-1",
        causation_id="inventory-reserved-event",
        occurred_at=datetime(2026, 6, 26, tzinfo=UTC),
        payload={
            "order_id": "order-1",
            "payment_id": "payment-1",
            "amount_cents": 9000,
        },
    )
