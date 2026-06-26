from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from eventcart.database import Base
from eventcart.modules.events import EventEnvelope, OutboxEvent
from eventcart.modules.inventory import InventoryItem
from eventcart.modules.orders import Order, OrderStatus
from eventcart.modules.orders.schemas import OrderCreate, OrderItemCreate
from eventcart.modules.orders.service import create_order
from eventcart.workers.inventory_worker import (
    handle_order_created,
    handle_payment_failed,
)
from eventcart.workers.invoice_worker import handle_payment_authorized
from eventcart.workers.notification_worker import handle_invoice_created
from eventcart.workers.order_projection_worker import (
    handle_inventory_released,
    handle_notification_sent,
)
from eventcart.workers.payment_worker import handle_inventory_reserved


def test_successful_order_workflow_reaches_completed() -> None:
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

        order = create_order(
            session,
            OrderCreate(
                customer_email="ada@example.com",
                items=[OrderItemCreate(sku="ticket-standard", quantity=2)],
            ),
        )

        inventory_event = handle_order_created(
            session,
            _outbox_envelope(session, "OrderCreated"),
        )
        assert inventory_event is not None

        payment_event = handle_inventory_reserved(
            session,
            EventEnvelope.model_validate(inventory_event),
        )
        assert payment_event is not None

        invoice_event = handle_payment_authorized(
            session,
            EventEnvelope.model_validate(payment_event),
        )
        assert invoice_event is not None

        notification_event = handle_invoice_created(
            session,
            EventEnvelope.model_validate(invoice_event),
        )
        assert notification_event is not None

        completed_order = handle_notification_sent(
            session,
            EventEnvelope.model_validate(notification_event),
        )
        assert completed_order is not None

        saved_order = session.get_one(Order, order.id)
        saved_inventory = session.scalars(select(InventoryItem)).one()
        event_types = [
            event.event_type
            for event in session.scalars(select(OutboxEvent)).all()
        ]

    assert saved_order.status == OrderStatus.COMPLETED
    assert saved_inventory.quantity_available == 8
    assert event_types == [
        "OrderCreated",
        "InventoryReserved",
        "PaymentAuthorized",
        "InvoiceCreated",
        "NotificationSent",
    ]


def test_failed_payment_workflow_releases_inventory_and_cancels_order() -> None:
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

        order = create_order(
            session,
            OrderCreate(
                customer_email="ada@example.com",
                items=[OrderItemCreate(sku="ticket-standard", quantity=2)],
            ),
        )

        inventory_event = handle_order_created(
            session,
            _outbox_envelope(session, "OrderCreated"),
        )
        assert inventory_event is not None

        payment_event = handle_inventory_reserved(
            session,
            _with_payment_failure(EventEnvelope.model_validate(inventory_event)),
        )
        assert payment_event is not None
        assert payment_event.event_type == "PaymentFailed"

        inventory_released_event = handle_payment_failed(
            session,
            EventEnvelope.model_validate(payment_event),
        )
        assert inventory_released_event is not None

        cancelled_order = handle_inventory_released(
            session,
            EventEnvelope.model_validate(inventory_released_event),
        )
        assert cancelled_order is not None

        saved_order = session.get_one(Order, order.id)
        saved_inventory = session.scalars(select(InventoryItem)).one()
        event_types = [
            event.event_type
            for event in session.scalars(select(OutboxEvent)).all()
        ]

    assert saved_order.status == OrderStatus.CANCELLED
    assert saved_inventory.quantity_available == 10
    assert event_types == [
        "OrderCreated",
        "InventoryReserved",
        "PaymentFailed",
        "InventoryReleased",
    ]


def _outbox_envelope(session: Session, event_type: str) -> EventEnvelope:
    outbox_event = session.scalars(
        select(OutboxEvent).where(OutboxEvent.event_type == event_type)
    ).one()
    return EventEnvelope.model_validate(outbox_event)


def _with_payment_failure(event: EventEnvelope) -> EventEnvelope:
    return event.model_copy(
        update={"payload": {**event.payload, "payment_should_fail": True}}
    )
