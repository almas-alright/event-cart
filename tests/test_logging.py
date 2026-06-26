import json
import logging

import pytest
from httpx import ASGITransport, AsyncClient

from eventcart.app import create_app
from eventcart.shared.logging import JsonLogFormatter, set_correlation_id


def test_json_log_formatter_includes_correlation_and_event_fields() -> None:
    set_correlation_id("correlation-1")
    record = logging.LogRecord(
        name="eventcart.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="handled event",
        args=(),
        exc_info=None,
    )
    record.event_id = "event-1"
    record.event_type = "OrderCreated"
    record.consumer_name = "inventory-worker"

    try:
        formatted = JsonLogFormatter().format(record)
    finally:
        set_correlation_id(None)

    payload = json.loads(formatted)
    assert payload["level"] == "INFO"
    assert payload["logger"] == "eventcart.test"
    assert payload["message"] == "handled event"
    assert payload["correlation_id"] == "correlation-1"
    assert payload["event_id"] == "event-1"
    assert payload["event_type"] == "OrderCreated"
    assert payload["consumer_name"] == "inventory-worker"


@pytest.mark.anyio
async def test_api_correlation_middleware_echoes_header() -> None:
    transport = ASGITransport(app=create_app())

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/health",
            headers={"X-Correlation-ID": "correlation-1"},
        )

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "correlation-1"
