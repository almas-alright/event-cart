"""Idempotency service helpers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from eventcart.modules.idempotency.models import IdempotencyKey


class IdempotencyConflictError(Exception):
    pass


class IdempotencyInProgressError(Exception):
    pass


@dataclass(frozen=True)
class IdempotencyRecord:
    response_body: dict[str, object]
    status_code: int


class IdempotencyService:
    def __init__(
        self,
        session: Session,
        *,
        ttl: timedelta = timedelta(hours=24),
    ) -> None:
        self.session = session
        self.ttl = ttl

    def start_request(
        self,
        *,
        key: str,
        request_body: Mapping[str, object],
    ) -> IdempotencyRecord | None:
        request_hash = hash_request_body(request_body)
        existing = self.session.get(IdempotencyKey, key)

        if existing is None or _is_expired(existing):
            if existing is not None:
                self.session.delete(existing)
                self.session.flush()

            self.session.add(
                IdempotencyKey(
                    key=key,
                    request_hash=request_hash,
                    expires_at=datetime.now(UTC) + self.ttl,
                )
            )
            self.session.flush()
            return None

        if existing.request_hash != request_hash:
            raise IdempotencyConflictError(
                "Idempotency key was already used with a different request body."
            )

        if existing.response_body is None or existing.status_code is None:
            raise IdempotencyInProgressError(
                "Idempotency key is already processing a request."
            )

        return IdempotencyRecord(
            response_body=existing.response_body,
            status_code=existing.status_code,
        )

    def store_response(
        self,
        *,
        key: str,
        response_body: dict[str, object],
        status_code: int,
    ) -> None:
        record = self.session.get(IdempotencyKey, key)
        if record is None:
            raise LookupError(f"Idempotency key {key!r} was not reserved.")

        record.response_body = response_body
        record.status_code = status_code
        record.updated_at = datetime.now(UTC)
        self.session.flush()


def hash_request_body(request_body: Mapping[str, object]) -> str:
    canonical_body = json.dumps(
        request_body,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical_body.encode("utf-8")).hexdigest()


def _is_expired(record: IdempotencyKey) -> bool:
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= datetime.now(UTC)
