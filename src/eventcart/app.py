"""FastAPI application factory for EventCart."""

from eventcart import __version__
from fastapi import FastAPI


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

    return app


__all__ = ["create_app"]
