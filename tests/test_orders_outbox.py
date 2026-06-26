import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from eventcart.app import create_app
from eventcart.database import Base, get_session
from eventcart.modules.events import OutboxEvent, OutboxEventStatus
from eventcart.modules.inventory import InventoryItem


@pytest.mark.anyio
async def test_order_creation_persists_order_created_outbox_event() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with Session(engine) as session:
        session.add(
            InventoryItem(
                sku="ticket-standard",
                name="Standard Ticket",
                quantity_available=100,
                unit_price_cents=4500,
            )
        )
        session.commit()

    def override_get_session():
        with testing_session() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/orders",
            json={
                "customer_email": "ada@example.com",
                "items": [{"sku": "ticket-standard", "quantity": 2}],
            },
        )

    assert response.status_code == 201
    order_id = response.json()["id"]

    with Session(engine) as session:
        outbox_event = session.scalars(select(OutboxEvent)).one()

    assert outbox_event.event_type == "OrderCreated"
    assert outbox_event.event_version == 1
    assert outbox_event.aggregate_type == "Order"
    assert outbox_event.aggregate_id == order_id
    assert outbox_event.correlation_id
    assert outbox_event.causation_id is None
    assert outbox_event.status == OutboxEventStatus.PENDING
    assert outbox_event.payload == {
        "order_id": order_id,
        "customer_email": "ada@example.com",
        "status": "PENDING",
        "items": [
            {
                "sku": "ticket-standard",
                "quantity": 2,
                "unit_price_cents": 4500,
                "product_name": "Standard Ticket",
            }
        ],
    }
