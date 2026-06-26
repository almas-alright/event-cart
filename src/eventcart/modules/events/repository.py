"""Repository helpers for transactional outbox records."""

from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from eventcart.modules.events.models import (
    DeadLetterEvent,
    EventProcessingAttempt,
    OutboxEvent,
    OutboxEventStatus,
)


class OutboxRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def fetch_pending(
        self,
        limit: int,
        *,
        now: datetime | None = None,
    ) -> list[OutboxEvent]:
        ready_at = now or datetime.now(UTC)
        return list(
            self.session.scalars(
                select(OutboxEvent)
                .where(
                    OutboxEvent.status == OutboxEventStatus.PENDING,
                    or_(
                        OutboxEvent.next_attempt_at.is_(None),
                        OutboxEvent.next_attempt_at <= ready_at,
                    ),
                )
                .order_by(OutboxEvent.occurred_at, OutboxEvent.event_id)
                .limit(limit)
            )
        )

    def mark_published(self, event_id: str) -> None:
        event = self._get_event(event_id)
        event.status = OutboxEventStatus.PUBLISHED
        event.published_at = datetime.now(UTC)
        event.next_attempt_at = None
        event.last_error = None

    def mark_retryable_failure(
        self,
        event_id: str,
        *,
        error: str,
        next_attempt_at: datetime,
    ) -> None:
        event = self._get_event(event_id)
        event.status = OutboxEventStatus.PENDING
        event.failure_count += 1
        event.next_attempt_at = next_attempt_at
        event.last_error = error[:500]

    def mark_failed(self, event_id: str, error: str) -> None:
        event = self._get_event(event_id)
        event.status = OutboxEventStatus.FAILED
        event.failure_count += 1
        event.next_attempt_at = None
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


class DeadLetterEventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def move_to_dead_letter(
        self,
        *,
        event: OutboxEvent,
        consumer_name: str,
        attempt_number: int,
        error: str,
    ) -> DeadLetterEvent:
        dead_letter_event = DeadLetterEvent(
            event_id=event.event_id,
            event_type=event.event_type,
            event_version=event.event_version,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            consumer_name=consumer_name,
            attempt_number=attempt_number,
            error=error[:500],
            payload=event.payload,
        )
        self.session.add(dead_letter_event)
        self.session.flush()
        return dead_letter_event

    def replay(self, dead_letter_id: str) -> OutboxEvent:
        dead_letter_event = self.session.get(DeadLetterEvent, dead_letter_id)
        if dead_letter_event is None:
            raise LookupError(f"Dead-letter event {dead_letter_id!r} was not found.")
        if dead_letter_event.replayed_at is not None:
            raise ValueError(
                f"Dead-letter event {dead_letter_id!r} was already replayed."
            )

        replay_event = OutboxEvent(
            event_type=dead_letter_event.event_type,
            event_version=dead_letter_event.event_version,
            aggregate_type=dead_letter_event.aggregate_type,
            aggregate_id=dead_letter_event.aggregate_id,
            correlation_id=dead_letter_event.correlation_id,
            causation_id=dead_letter_event.causation_id,
            payload=dead_letter_event.payload,
        )
        self.session.add(replay_event)
        dead_letter_event.replayed_at = datetime.now(UTC)
        self.session.flush()
        return replay_event
