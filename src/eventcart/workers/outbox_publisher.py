"""Outbox publisher worker."""

from __future__ import annotations

import asyncio
from typing import Protocol

from sqlalchemy.orm import Session

from eventcart.database import SessionLocal
from eventcart.modules.events import (
    EventEnvelope,
    NatsEventPublisher,
    OutboxEvent,
    OutboxRepository,
)


class EventPublisher(Protocol):
    async def publish(self, envelope: EventEnvelope) -> None: ...


def envelope_from_outbox_event(event: OutboxEvent) -> EventEnvelope:
    return EventEnvelope.model_validate(event)


async def publish_pending_batch(
    session: Session,
    publisher: EventPublisher,
    *,
    limit: int = 50,
) -> int:
    repository = OutboxRepository(session)
    events = repository.fetch_pending(limit=limit)

    for event in events:
        try:
            await publisher.publish(envelope_from_outbox_event(event))
            repository.mark_published(event.event_id)
        except Exception as error:
            repository.mark_failed(event.event_id, str(error))

    session.commit()
    return len(events)


async def run_once(limit: int = 50) -> int:
    publisher = NatsEventPublisher()
    try:
        await publisher.connect()
        with SessionLocal() as session:
            return await publish_pending_batch(session, publisher, limit=limit)
    finally:
        await publisher.close()


def main() -> None:
    asyncio.run(run_once())


if __name__ == "__main__":
    main()
