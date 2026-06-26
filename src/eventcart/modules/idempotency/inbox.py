"""Consumer inbox idempotency helpers."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import TypeVar

from sqlalchemy.orm import Session

from eventcart.modules.events import EventEnvelope
from eventcart.modules.idempotency.models import InboxEvent

T = TypeVar("T")


class ConsumerInbox:
    def __init__(self, session: Session, *, consumer_name: str) -> None:
        self.session = session
        self.consumer_name = consumer_name

    def has_processed(self, event_id: str) -> bool:
        return self.session.get(InboxEvent, (self.consumer_name, event_id)) is not None

    def process_once(
        self,
        event: EventEnvelope,
        handler: Callable[[EventEnvelope], T],
    ) -> T | None:
        if self.has_processed(event.event_id):
            return None

        result = handler(event)
        self.session.add(
            InboxEvent(
                consumer_name=self.consumer_name,
                event_id=event.event_id,
                processed_at=datetime.now(UTC),
            )
        )
        self.session.flush()
        return result

