import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from eventcart.app import create_app
from eventcart.database import Base, get_session
from eventcart.modules.inventory import InventoryItem


@pytest.mark.anyio
async def test_order_can_be_created_and_retrieved() -> None:
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
        create_response = await client.post(
            "/api/v1/orders",
            json={
                "customer_email": "ada@example.com",
                "items": [{"sku": "ticket-standard", "quantity": 2}],
            },
        )

        assert create_response.status_code == 201
        created_order = create_response.json()
        order_id = created_order["id"]

        get_response = await client.get(f"/api/v1/orders/{order_id}")

    assert created_order["status"] == "PENDING"
    assert created_order["customer_email"] == "ada@example.com"
    assert created_order["items"] == [
        {
            "id": created_order["items"][0]["id"],
            "sku": "ticket-standard",
            "quantity": 2,
            "unit_price_cents": 4500,
            "product_name": "Standard Ticket",
        }
    ]
    assert get_response.status_code == 200
    retrieved_order = get_response.json()
    assert retrieved_order["id"] == created_order["id"]
    assert retrieved_order["status"] == "PENDING"
    assert retrieved_order["customer_email"] == "ada@example.com"
    assert retrieved_order["items"] == created_order["items"]
