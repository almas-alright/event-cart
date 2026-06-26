from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, selectinload

from eventcart.database import Base
from eventcart.modules.orders import Order, OrderItem, OrderStatus


def test_order_with_items_persists() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        order = Order(
            customer_email="ada@example.com",
            items=[
                OrderItem(
                    sku="sku-123",
                    quantity=2,
                    unit_price_cents=1299,
                    product_name="Event Ticket",
                )
            ],
        )
        session.add(order)
        session.commit()

    with Session(engine) as session:
        saved_order = session.scalars(
            select(Order).options(selectinload(Order.items))
        ).one()

    assert saved_order.status == OrderStatus.PENDING
    assert saved_order.customer_email == "ada@example.com"
    assert len(saved_order.items) == 1
    assert saved_order.items[0].sku == "sku-123"
    assert saved_order.items[0].quantity == 2
    assert saved_order.items[0].unit_price_cents == 1299
