"""FastAPI application factory for EventCart."""

from fastapi import FastAPI

from eventcart import __version__
from eventcart.modules.inventory.routes import router as inventory_router


def create_app() -> FastAPI:
    """Create and configure the EventCart API application."""
    app = FastAPI(
        title="EventCart",
        version=__version__,
        summary="A learning backend for event-driven order workflows.",
    )

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "healthy", "service": "eventcart"}

    app.include_router(inventory_router)

    return app


__all__ = ["create_app"]
