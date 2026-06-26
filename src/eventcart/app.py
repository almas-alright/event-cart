"""Application entrypoint placeholder for EventCart."""

from eventcart import __version__


def get_app_name() -> str:
    """Return the display name used by future application setup."""
    return "EventCart"


__all__ = ["__version__", "get_app_name"]

