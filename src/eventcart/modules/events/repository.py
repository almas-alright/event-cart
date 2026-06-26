"""Repository helpers for transactional outbox records."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from eventcart.modules.events.models import (
    EventProcessingAttempt,
    OutboxEvent,
    OutboxEventStatus,
)


class OutboxRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def fetch_pending(self, limit: int) -> list[OutboxEvent]:
        return list(
            self.session.scalars(
                select(OutboxEvent)
                .where(OutboxEvent.status == OutboxEventStatus.PENDING)
                .order_by(OutboxEvent.occurred_at, OutboxEvent.event_id)
                .limit(limit)
            )
        )

    def mark_published(self, event_id: str) -> None:
        event = self._get_event(event_id)
        event.status = OutboxEventStatus.PUBLISHED
        event.published_at = datetime.now(UTC)
        event.last_error = None

    def mark_failed(self, event_id: str, error: str) -> None:
        event = self._get_event(event_id)
        event.status = OutboxEventStatus.FAILED
        event.failure_count += 1
        event.last_error = error[:500]

    def _get_event(self, event_id: str) -> OutboxEvent:
        event = self.session.get(OutboxEvent, event_id)
        if event is None:
            raise LookupError(f"Outbox event {event_id!r} was not found.")
        return event


class EventProcessingAttemptRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record_failure(
        self,
        *,
        event_id: str,
        consumer_name: str,
        error: str,
    ) -> EventProcessingAttempt:
        attempt_number = self.next_attempt_number(
            event_id=event_id,
            consumer_name=consumer_name,
        )
        attempt = EventProcessingAttempt(
            event_id=event_id,
            consumer_name=consumer_name,
            attempt_number=attempt_number,
            error=error[:500],
        )
        self.session.add(attempt)
        self.session.flush()
        return attempt

    def next_attempt_number(self, *, event_id: str, consumer_name: str) -> int:
        latest_attempt = self.session.scalar(
            select(func.max(EventProcessingAttempt.attempt_number)).where(
                EventProcessingAttempt.event_id == event_id,
                EventProcessingAttempt.consumer_name == consumer_name,
            )
        )
        return int(latest_attempt or 0) + 1

    def count_failures(self, *, event_id: str, consumer_name: str) -> int:
        return int(
            self.session.scalar(
                select(func.count()).select_from(EventProcessingAttempt).where(
                    EventProcessingAttempt.event_id == event_id,
                    EventProcessingAttempt.consumer_name == consumer_name,
                )
            )
            or 0
        )
