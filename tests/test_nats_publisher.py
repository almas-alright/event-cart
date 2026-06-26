from datetime import UTC, datetime

import pytest

from eventcart.modules.events import (
    EventEnvelope,
    NatsEventPublisher,
    subject_for_event,
)
from eventcart.modules.events.publisher import decode_event_payload


class FakeJetStream:
    def __init__(self) -> None:
        self.messages: list[tuple[str, bytes, dict[str, str] | None]] = []

    async def publish(
        self,
        subject: str,
        payload: bytes,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.messages.append((subject, payload, headers))


@pytest.mark.anyio
async def test_nats_publisher_publishes_envelope_to_subject_with_dedup_id() -> None:
    jetstream = FakeJetStream()
    publisher = NatsEventPublisher(jetstream=jetstream)
    envelope = make_envelope()

    await publisher.publish(envelope)

    assert len(jetstream.messages) == 1
    subject, payload, headers = jetstream.messages[0]
    assert subject == "eventcart.order.ordercreated"
    assert headers == {"Nats-Msg-Id": "event-1"}
    decoded = decode_event_payload(payload)
    assert decoded["event_id"] == "event-1"
    assert decoded["event_type"] == "OrderCreated"
    assert decoded["payload"] == {"order_id": "order-1"}


def test_subject_for_event_uses_eventcart_aggregate_event_convention() -> None:
    assert subject_for_event(make_envelope()) == "eventcart.order.ordercreated"


def make_envelope() -> EventEnvelope:
    return EventEnvelope(
        event_id="event-1",
        event_type="OrderCreated",
        event_version=1,
        aggregate_type="Order",
        aggregate_id="order-1",
        correlation_id="correlation-1",
        causation_id=None,
        occurred_at=datetime(2026, 6, 26, tzinfo=UTC),
        payload={"order_id": "order-1"},
    )
