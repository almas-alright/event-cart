"""Order application services."""

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from eventcart.modules.events import OutboxEvent, notify_outbox_event
from eventcart.modules.inventory.models import InventoryItem
from eventcart.modules.orders.models import Order, OrderItem
from eventcart.modules.orders.schemas import OrderCreate


class InventoryItemNotFoundError(Exception):
    pass


def create_order(session: Session, payload: OrderCreate) -> Order:
    order_items: list[OrderItem] = []
    event_items: list[dict[str, object]] = []

    for item in payload.items:
        inventory_item = session.scalars(
            select(InventoryItem).where(InventoryItem.sku == item.sku)
        ).one_or_none()
        if inventory_item is None:
            raise InventoryItemNotFoundError(
                f"Inventory item with SKU {item.sku!r} was not found."
            )

        order_items.append(
            OrderItem(
                sku=inventory_item.sku,
                quantity=item.quantity,
                unit_price_cents=inventory_item.unit_price_cents,
                product_name=inventory_item.name,
            )
        )
        event_items.append(
            {
                "sku": inventory_item.sku,
                "quantity": item.quantity,
                "unit_price_cents": inventory_item.unit_price_cents,
                "product_name": inventory_item.name,
            }
        )

    order = Order(customer_email=payload.customer_email, items=order_items)
    session.add(order)
    session.flush()

    outbox_event = OutboxEvent(
        event_type="OrderCreated",
        event_version=1,
        aggregate_type="Order",
        aggregate_id=order.id,
        correlation_id=str(uuid4()),
        causation_id=None,
        payload={
            "order_id": order.id,
            "customer_email": order.customer_email,
            "status": order.status,
            "items": event_items,
        },
    )
    session.add(outbox_event)
    notify_outbox_event(session, outbox_event)
    session.commit()

    saved_order = get_order(session, order.id)
    if saved_order is None:
        raise RuntimeError("Created order could not be loaded.")

    return saved_order


def get_order(session: Session, order_id: str) -> Order | None:
    return session.scalars(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id)
    ).one_or_none()
