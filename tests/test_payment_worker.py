from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from eventcart.database import Base
from eventcart.modules.events import EventEnvelope, OutboxEvent
from eventcart.modules.payments import Payment, PaymentStatus
from eventcart.workers.payment_worker import handle_inventory_reserved


def test_payment_worker_authorizes_payment_and_emits_event() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        outbox_event = handle_inventory_reserved(
            session,
            make_inventory_reserved_event(),
        )
        assert outbox_event is not None

        payment = session.scalars(select(Payment)).one()
        saved_outbox_event = session.get_one(OutboxEvent, outbox_event.event_id)

    assert payment.order_id == "order-1"
    assert payment.status == PaymentStatus.AUTHORIZED
    assert payment.amount_cents == 9000
    assert payment.failure_reason is None
    assert saved_outbox_event.event_type == "PaymentAuthorized"
    assert saved_outbox_event.aggregate_id == "order-1"
    assert saved_outbox_event.correlation_id == "correlation-1"
    assert saved_outbox_event.causation_id == "event-1"
    assert saved_outbox_event.payload["payment_id"] == payment.id
    assert saved_outbox_event.payload["amount_cents"] == 9000


def test_payment_worker_emits_failed_event_when_payment_is_declined() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        outbox_event = handle_inventory_reserved(
            session,
            make_inventory_reserved_event(payment_should_fail=True),
        )
        assert outbox_event is not None

        payment = session.scalars(select(Payment)).one()
        saved_outbox_event = session.get_one(OutboxEvent, outbox_event.event_id)

    assert payment.status == PaymentStatus.FAILED
    assert payment.failure_reason == "Simulated payment failure."
    assert saved_outbox_event.event_type == "PaymentFailed"
    assert saved_outbox_event.payload["payment_id"] == payment.id
    assert saved_outbox_event.payload["reason"] == "Simulated payment failure."
    assert saved_outbox_event.payload["items"] == [
        {
            "sku": "ticket-standard",
            "quantity": 2,
            "unit_price_cents": 4500,
            "product_name": "Standard Ticket",
        }
    ]


def make_inventory_reserved_event(
    *,
    payment_should_fail: bool = False,
) -> EventEnvelope:
    payload: dict[str, object] = {
        "order_id": "order-1",
        "items": [
            {
                "sku": "ticket-standard",
                "quantity": 2,
                "unit_price_cents": 4500,
                "product_name": "Standard Ticket",
            }
        ],
    }
    if payment_should_fail:
        payload["payment_should_fail"] = True

    return EventEnvelope(
        event_id="event-1",
        event_type="InventoryReserved",
        event_version=1,
        aggregate_type="Order",
        aggregate_id="order-1",
        correlation_id="correlation-1",
        causation_id="order-created-event",
        occurred_at=datetime(2026, 6, 26, tzinfo=UTC),
        payload=payload,
    )
