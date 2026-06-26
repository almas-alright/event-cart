import pytest
from httpx import ASGITransport, AsyncClient

from eventcart.app import create_app
from eventcart.config import Settings
from eventcart.shared.tracing import setup_tracing


def test_setup_tracing_marks_app_state() -> None:
    app = create_app()

    assert isinstance(app.state.tracing_enabled, bool)


@pytest.mark.anyio
async def test_app_starts_with_tracing_setup() -> None:
    transport = ASGITransport(app=create_app())

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200


def test_setup_tracing_accepts_otlp_endpoint() -> None:
    app = create_app()
    result = setup_tracing(
        app,
        Settings(otel_exporter_otlp_endpoint="http://localhost:4318"),
    )

    assert isinstance(result, bool)
