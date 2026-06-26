"""Dead-letter replay command helpers."""

from __future__ import annotations

import argparse

from eventcart.database import SessionLocal
from eventcart.modules.events import DeadLetterEventRepository, OutboxEvent


def replay_dead_letter_event(dead_letter_id: str) -> OutboxEvent:
    with SessionLocal() as session:
        replay_event = DeadLetterEventRepository(session).replay(dead_letter_id)
        session.commit()
        return replay_event


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay a dead-letter event.")
    parser.add_argument("dead_letter_id")
    args = parser.parse_args()

    replay_event = replay_dead_letter_event(args.dead_letter_id)
    print(replay_event.event_id)


if __name__ == "__main__":
    main()
