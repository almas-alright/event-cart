import pytest
from httpx import ASGITransport, AsyncClient

from eventcart.app import create_app


@pytest.mark.anyio
async def test_metrics_endpoint_exposes_prometheus_payload() -> None:
    transport = ASGITransport(app=create_app())

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/health")
        response = await client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "eventcart_http_requests_total" in response.text
    assert 'path="/health"' in response.text
