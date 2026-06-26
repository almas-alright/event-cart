"""NATS JetStream event publisher."""

from __future__ import annotations

import json
from typing import Any, Protocol

import nats

from eventcart.config import get_settings
from eventcart.modules.events.schemas import EventEnvelope


class JetStreamClient(Protocol):
    async def publish(
        self,
        subject: str,
        payload: bytes,
        *,
        headers: dict[str, str] | None = None,
    ) -> Any: ...


def subject_for_event(envelope: EventEnvelope) -> str:
    aggregate = envelope.aggregate_type.lower()
    event_type = envelope.event_type.lower()
    return f"eventcart.{aggregate}.{event_type}"


class NatsEventPublisher:
    def __init__(self, jetstream: JetStreamClient | None = None) -> None:
        self._jetstream = jetstream
        self._nats_client: Any | None = None

    async def connect(self, url: str | None = None) -> None:
        self._nats_client = await nats.connect(url or get_settings().nats_url)
        self._jetstream = self._nats_client.jetstream()

    async def close(self) -> None:
        if self._nats_client is not None:
            await self._nats_client.close()
            self._nats_client = None
            self._jetstream = None

    async def publish(self, envelope: EventEnvelope) -> None:
        if self._jetstream is None:
            await self.connect()

        if self._jetstream is None:
            raise RuntimeError("NATS JetStream client is not connected.")

        await self._jetstream.publish(
            subject_for_event(envelope),
            envelope.model_dump_json().encode("utf-8"),
            headers={"Nats-Msg-Id": envelope.event_id},
        )


def decode_event_payload(payload: bytes) -> dict[str, Any]:
    return json.loads(payload.decode("utf-8"))

