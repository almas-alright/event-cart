from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from eventcart.database import Base
from eventcart.modules.idempotency import (
    IdempotencyConflictError,
    IdempotencyInProgressError,
    IdempotencyKey,
    IdempotencyService,
)
from eventcart.modules.idempotency.service import hash_request_body


def test_idempotency_service_stores_and_returns_response() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    request_body = {"customer_email": "ada@example.com"}

    with Session(engine) as session:
        service = IdempotencyService(session)

        stored = service.start_request(key="key-1", request_body=request_body)
        assert stored is None

        service.store_response(
            key="key-1",
            response_body={"id": "order-1"},
            status_code=201,
        )
        session.commit()

        replay = service.start_request(key="key-1", request_body=request_body)

    assert replay is not None
    assert replay.response_body == {"id": "order-1"}
    assert replay.status_code == 201


def test_idempotency_service_rejects_same_key_different_request() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        service = IdempotencyService(session)
        service.start_request(key="key-1", request_body={"sku": "ticket-standard"})

        with pytest.raises(IdempotencyConflictError):
            service.start_request(key="key-1", request_body={"sku": "ticket-vip"})


def test_idempotency_service_rejects_duplicate_in_progress_request() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    request_body = {"sku": "ticket-standard"}

    with Session(engine) as session:
        service = IdempotencyService(session)
        service.start_request(key="key-1", request_body=request_body)

        with pytest.raises(IdempotencyInProgressError):
            service.start_request(key="key-1", request_body=request_body)


def test_expired_idempotency_key_can_be_reused() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            IdempotencyKey(
                key="key-1",
                request_hash=hash_request_body({"sku": "old"}),
                response_body={"id": "old-order"},
                status_code=201,
                expires_at=datetime.now(UTC) - timedelta(seconds=1),
            )
        )
        session.commit()

        service = IdempotencyService(session)
        stored = service.start_request(key="key-1", request_body={"sku": "new"})
        saved_record = session.get_one(IdempotencyKey, "key-1")

    assert stored is None
    assert saved_record.request_hash == hash_request_body({"sku": "new"})
    assert saved_record.response_body is None
    assert saved_record.status_code is None
