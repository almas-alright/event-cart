import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from eventcart.app import create_app
from eventcart.database import Base, get_session
from eventcart.modules.events import OutboxEvent
from eventcart.modules.inventory import InventoryItem
from eventcart.modules.orders import Order


@pytest.mark.anyio
async def test_duplicate_order_request_returns_stored_response() -> None:
    engine = create_test_engine()
    seed_inventory(engine)
    app = create_test_app(engine)
    transport = ASGITransport(app=app)

    payload = {
        "customer_email": "ada@example.com",
        "items": [{"sku": "ticket-standard", "quantity": 2}],
    }
    headers = {"Idempotency-Key": "order-key-1"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first_response = await client.post(
            "/api/v1/orders",
            json=payload,
            headers=headers,
        )
        second_response = await client.post(
            "/api/v1/orders",
            json=payload,
            headers=headers,
        )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert second_response.json() == first_response.json()

    with Session(engine) as session:
        assert len(session.scalars(select(Order)).all()) == 1
        assert len(session.scalars(select(OutboxEvent)).all()) == 1


@pytest.mark.anyio
async def test_same_idempotency_key_with_different_body_returns_conflict() -> None:
    engine = create_test_engine()
    seed_inventory(engine)
    app = create_test_app(engine)
    transport = ASGITransport(app=app)

    headers = {"Idempotency-Key": "order-key-1"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first_response = await client.post(
            "/api/v1/orders",
            json={
                "customer_email": "ada@example.com",
                "items": [{"sku": "ticket-standard", "quantity": 1}],
            },
            headers=headers,
        )
        second_response = await client.post(
            "/api/v1/orders",
            json={
                "customer_email": "ada@example.com",
                "items": [{"sku": "ticket-standard", "quantity": 2}],
            },
            headers=headers,
        )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert "different request body" in second_response.json()["detail"]


def create_test_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


def seed_inventory(engine) -> None:
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


def create_test_app(engine):
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_session():
        with testing_session() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session
    return app
