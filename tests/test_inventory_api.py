import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from eventcart.app import create_app
from eventcart.database import Base, get_session
from eventcart.modules.inventory import InventoryItem


@pytest.mark.anyio
async def test_admin_can_create_inventory_item() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_session():
        with testing_session() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/admin/inventory-items",
            json={
                "sku": "ticket-vip",
                "name": "VIP Ticket",
                "quantity_available": 50,
                "unit_price_cents": 12500,
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["sku"] == "ticket-vip"
    assert body["quantity_available"] == 50

    with Session(engine) as session:
        saved_item = session.scalars(select(InventoryItem)).one()

    assert saved_item.name == "VIP Ticket"
    assert saved_item.unit_price_cents == 12500
