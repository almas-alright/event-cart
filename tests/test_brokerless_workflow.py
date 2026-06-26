from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from eventcart.database import Base
from eventcart.modules.events import OutboxEvent, OutboxEventStatus
from eventcart.modules.inventory import InventoryItem
from eventcart.modules.orders import Order, OrderStatus
from eventcart.modules.orders.schemas import OrderCreate, OrderItemCreate
from eventcart.modules.orders.service import create_order
from eventcart.workers.brokerless_dispatcher import dispatch_until_idle


def test_brokerless_dispatcher_runs_successful_order_workflow_without_nats() -> None:
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

        dispatched_count = dispatch_until_idle(session)

        saved_order = session.get_one(Order, order.id)
        saved_inventory = session.scalars(select(InventoryItem)).one()
        outbox_events = session.scalars(select(OutboxEvent)).all()

    assert dispatched_count == 5
    assert saved_order.status == OrderStatus.COMPLETED
    assert saved_inventory.quantity_available == 8
    assert [event.event_type for event in outbox_events] == [
        "OrderCreated",
        "InventoryReserved",
        "PaymentAuthorized",
        "InvoiceCreated",
        "NotificationSent",
    ]
    assert {event.status for event in outbox_events} == {OutboxEventStatus.PUBLISHED}
