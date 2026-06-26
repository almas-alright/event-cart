# Testing Guide

EventCart's tests are part of the learning material. They are intentionally
small and focused so each test points at one event-driven architecture concept.

Run the full suite:

```bash
.venv/bin/python -m pytest
```

Run one concept area:

```bash
.venv/bin/python -m pytest tests/test_orders_outbox.py
.venv/bin/python -m pytest tests/test_orders_idempotency.py
.venv/bin/python -m pytest tests/test_brokerless_workflow.py
```

## Concept Map

| Concept | Test files | What they teach |
| --- | --- | --- |
| API foundation | `tests/test_health.py`, `tests/test_orders_api.py`, `tests/test_inventory_api.py` | FastAPI endpoints can be tested with HTTPX without starting a real server. |
| Database foundation | `tests/test_database.py`, `tests/test_order_models.py` | SQLAlchemy metadata and model relationships can create and persist the local schema. |
| Event envelope | `tests/test_event_envelope.py` | Events carry identity, version, aggregate, correlation, causation, timestamp, and payload fields. |
| Transactional outbox | `tests/test_orders_outbox.py`, `tests/test_outbox_repository.py` | Business rows and event rows are committed together, then fetched and marked by delivery state. |
| NATS broker mode | `tests/test_nats_publisher.py`, `tests/test_outbox_publisher_worker.py` | The publisher maps envelopes to stable subjects and uses event IDs for publish identity. |
| API idempotency | `tests/test_idempotency_service.py`, `tests/test_orders_idempotency.py` | Duplicate command requests return the stored response, while key reuse with a changed body fails. |
| Consumer inbox | `tests/test_inbox_idempotency.py`, `tests/test_inventory_worker.py` | A consumer processes each event ID once per consumer name, even when delivery repeats. |
| Saga success path | `tests/test_inventory_worker.py`, `tests/test_payment_worker.py`, `tests/test_invoice_worker.py`, `tests/test_notification_worker.py`, `tests/test_order_workflow.py` | Each worker performs one local side effect and emits the next event until the order completes. |
| Saga failure path | `tests/test_inventory_worker.py`, `tests/test_payment_worker.py`, `tests/test_order_workflow.py` | Payment failure emits a failure event, releases inventory, and cancels the order. |
| Brokerless mode | `tests/test_config.py`, `tests/test_brokerless_dispatcher.py`, `tests/test_brokerless_workflow.py`, `tests/test_outbox_notify.py` | PostgreSQL outbox polling can dispatch the same workflow without NATS, with LISTEN/NOTIFY as a wake-up hint. |
| Retry and backoff | `tests/test_event_processing_attempts.py`, `tests/test_brokerless_retry.py` | Failed handling attempts are counted per consumer and delayed before retry. |
| Dead letter and replay | `tests/test_dead_letter_events.py`, `tests/test_dead_letter_replay.py` | Poison events move to a dead-letter table and replay creates a new pending outbox event once. |
| Observability | `tests/test_logging.py`, `tests/test_metrics.py`, `tests/test_tracing.py`, `tests/test_observability_compose.py` | Correlation IDs, JSON logs, Prometheus metrics, OpenTelemetry setup, and observability Compose files are wired in. |

## Reading Path

1. Start with `tests/test_orders_api.py` and `tests/test_inventory_api.py` to
   see the command surface.
2. Read `tests/test_orders_outbox.py` to see the transactional outbox solve the
   dual-write problem.
3. Read `tests/test_orders_idempotency.py` and
   `tests/test_inbox_idempotency.py` to see duplicate commands and duplicate
   events handled safely.
4. Read the worker tests in this order:
   `tests/test_inventory_worker.py`, `tests/test_payment_worker.py`,
   `tests/test_invoice_worker.py`, and `tests/test_notification_worker.py`.
5. Read `tests/test_order_workflow.py` for the full success and failure saga.
6. Read `tests/test_brokerless_workflow.py` to see the same workflow run
   without NATS.
7. Finish with retry, dead-letter, replay, and observability tests.

## Why Most Tests Use SQLite

Most tests use in-memory SQLite because the project is meant to be easy to
study without running infrastructure. The concepts under test are repository
behavior, event shape, idempotency rules, and worker orchestration. PostgreSQL
remains the production target because the local runtime depends on durable
tables, row locking, and LISTEN/NOTIFY wake-ups.

Docker Compose tests validate configuration by reading YAML because Docker is
not required for unit-level feedback. Run the full Compose stack manually when
you want to observe NATS, Prometheus, Grafana, Jaeger, and the worker processes
together.
