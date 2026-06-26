from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from eventcart.database import Base
from eventcart.modules.events import EventEnvelope, OutboxEvent
from eventcart.modules.inventory import InventoryItem
from eventcart.workers.inventory_worker import handle_order_created


def test_inventory_worker_reserves_stock_and_emits_reserved_event() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            InventoryItem(
                sku="ticket-standard",
                name="Standard Ticket",
                quantity_available=10,
                unit_price_cents=4500,
            )
        )
        session.commit()

        outbox_event = handle_order_created(
            session,
            make_order_created_event(quantity=3),
        )
        assert outbox_event is not None

        saved_inventory = session.scalars(select(InventoryItem)).one()
        saved_outbox_event = session.get_one(OutboxEvent, outbox_event.event_id)

    assert saved_inventory.quantity_available == 7
    assert saved_outbox_event.event_type == "InventoryReserved"
    assert saved_outbox_event.aggregate_id == "order-1"
    assert saved_outbox_event.correlation_id == "correlation-1"
    assert saved_outbox_event.causation_id == "event-1"
    assert saved_outbox_event.payload["order_id"] == "order-1"


def test_inventory_worker_emits_failed_event_when_stock_is_insufficient() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            InventoryItem(
                sku="ticket-standard",
                name="Standard Ticket",
                quantity_available=1,
                unit_price_cents=4500,
            )
        )
        session.commit()

        outbox_event = handle_order_created(
            session,
            make_order_created_event(quantity=3),
        )
        assert outbox_event is not None

        saved_inventory = session.scalars(select(InventoryItem)).one()
        saved_outbox_event = session.get_one(OutboxEvent, outbox_event.event_id)

    assert saved_inventory.quantity_available == 1
    assert saved_outbox_event.event_type == "InventoryReservationFailed"
    assert saved_outbox_event.aggregate_id == "order-1"
    assert "Insufficient inventory" in str(saved_outbox_event.payload["reason"])


def test_inventory_worker_skips_duplicate_order_created_event() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            InventoryItem(
                sku="ticket-standard",
                name="Standard Ticket",
                quantity_available=10,
                unit_price_cents=4500,
            )
        )
        session.commit()

        event = make_order_created_event(quantity=3)
        first_result = handle_order_created(session, event)
        second_result = handle_order_created(session, event)

        saved_inventory = session.scalars(select(InventoryItem)).one()
        outbox_events = session.scalars(select(OutboxEvent)).all()

    assert first_result is not None
    assert second_result is None
    assert saved_inventory.quantity_available == 7
    assert len(outbox_events) == 1
    assert outbox_events[0].event_type == "InventoryReserved"


def make_order_created_event(quantity: int) -> EventEnvelope:
    return EventEnvelope(
        event_id="event-1",
        event_type="OrderCreated",
        event_version=1,
        aggregate_type="Order",
        aggregate_id="order-1",
        correlation_id="correlation-1",
        causation_id=None,
        occurred_at=datetime(2026, 6, 26, tzinfo=UTC),
        payload={
            "order_id": "order-1",
            "customer_email": "ada@example.com",
            "status": "PENDING",
            "items": [
                {
                    "sku": "ticket-standard",
                    "quantity": quantity,
                    "unit_price_cents": 4500,
                    "product_name": "Standard Ticket",
                }
            ],
        },
    )
