"""ASGI entrypoint for EventCart."""

from eventcart.app import create_app

app = create_app()

