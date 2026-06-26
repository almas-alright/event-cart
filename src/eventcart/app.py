"""FastAPI application factory for EventCart."""

from uuid import uuid4

from fastapi import FastAPI, Request
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from eventcart import __version__
from eventcart.config import get_settings
from eventcart.modules.inventory.routes import router as inventory_router
from eventcart.modules.orders.routes import router as orders_router
from eventcart.shared.logging import configure_logging, set_correlation_id
from eventcart.shared.tracing import setup_tracing


def create_app() -> FastAPI:
    """Create and configure the EventCart API application."""
    settings = get_settings()
    configure_logging(level=settings.log_level)
    app = FastAPI(
        title="EventCart",
        version=__version__,
        summary="A learning backend for event-driven order workflows.",
    )
    setup_tracing(app, settings)

    @app.middleware("http")
    async def correlation_middleware(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_correlation_id = request.headers.get("X-Correlation-ID") or str(
            uuid4()
        )
        set_correlation_id(request_correlation_id)
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = request_correlation_id
        set_correlation_id(None)
        return response

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "healthy", "service": "eventcart"}

    app.include_router(inventory_router)
    app.include_router(orders_router)

    return app


__all__ = ["create_app"]
