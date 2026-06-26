# Architecture Decisions

EventCart is a learning project, so the architecture favors visible boundaries,
small moving parts, and patterns that are common in production systems without
turning the repository into a platform.

## FastAPI For The API

FastAPI keeps the HTTP layer small while making request and response schemas
explicit through Pydantic. That fits EventCart because readers can move quickly
from route to schema to service behavior.

Why it was chosen:

- It is approachable for Python developers.
- It has strong typing and OpenAPI support by default.
- It works well with HTTPX tests without needing a live server.
- It keeps route handlers thin enough to highlight domain services.

Tradeoff: FastAPI does not teach broker or workflow concepts by itself. EventCart
keeps those concepts in modules and worker entrypoints instead of hiding them in
framework hooks.

## PostgreSQL As Durable State

PostgreSQL stores orders, inventory, payments, invoices, notifications,
idempotency keys, inbox rows, outbox rows, retry attempts, and dead-letter rows.
The database is the source of truth for both business state and event handoff
state.

Why it was chosen:

- Transactions make the outbox pattern easy to demonstrate.
- Relational constraints make duplicate protection understandable.
- Row state makes retry, dead-letter, and replay behavior inspectable.
- LISTEN/NOTIFY can wake a brokerless dispatcher while polling remains durable.

Tradeoff: PostgreSQL is not a message broker. EventCart uses tables for
durability and polling for reliability; LISTEN/NOTIFY is only a responsiveness
hint.

## Transactional Outbox For Event Handoff

Order creation writes the order and an `OrderCreated` outbox row in the same
database transaction. Workers also emit follow-up events by writing outbox rows.

Why it was chosen:

- It solves the dual-write problem in a way readers can see in SQL rows.
- It makes publish retries safe because unpublished events remain in the table.
- It lets both NATS mode and brokerless mode share the same durable source.
- It gives operational status fields for pending, published, and failed events.

Tradeoff: The outbox adds a polling or publishing component. EventCart accepts
that extra process because it makes delivery failure explicit and teachable.

## NATS JetStream As The Broker Mode

NATS JetStream is the primary broker mode. The outbox publisher sends envelopes
to event subjects, and workers consume them with durable consumer semantics.

Why it was chosen:

- It is lightweight enough for Docker Compose.
- Subject naming is simple and easy to teach.
- JetStream introduces durable consumers and replay without a large platform.
- Event IDs can be used as publish identity for deduplication where supported.

Tradeoff: Running a broker adds infrastructure. EventCart keeps a brokerless
mode so readers can compare when a broker is useful and when a database-backed
workflow may be enough.

## PostgreSQL Brokerless Mode

Brokerless mode reads pending outbox rows and invokes local handlers directly.
LISTEN/NOTIFY can wake the dispatcher faster, but polling remains the source of
reliability.

Why it was chosen:

- It teaches that the outbox is the durable queue, not the notification channel.
- It gives a low-infrastructure way to run the same workflow without NATS.
- It makes the tradeoff between operational simplicity and broker capability
  concrete.
- It keeps retry, dead-letter, and replay behavior in the same database model.

Tradeoff: Brokerless mode is not a replacement for every broker use case. It
does not provide the same fan-out, stream retention, or consumer management
features as JetStream.

## Inbox Pattern For Consumer Idempotency

Each consumer records `consumer_name + event_id` before applying side effects.
If the same event arrives again for that consumer, the handler skips it.

Why it was chosen:

- At-least-once delivery means duplicate events are normal.
- Consumer idempotency is easier to trust when the marker is persisted.
- The same event can still be processed independently by different consumers.
- Tests can prove that stock is not reserved twice for the same event.

Tradeoff: The inbox table adds a write to each consumed event. EventCart accepts
that cost because duplicate side effects are harder to reason about than one
small idempotency write.

## Modular Monolith Plus Worker Entrypoints

The codebase is one deployable Python project with clear modules and separate
worker entrypoints. This avoids a microservice sprawl while still teaching
message-driven process boundaries.

Why it was chosen:

- Readers can understand the whole system in one repository.
- Tests can exercise end-to-end behavior without network-heavy integration
  setup.
- Module boundaries mirror the eventual service boundaries: orders, inventory,
  payments, invoices, notifications, events, and idempotency.
- Worker entrypoints make asynchronous processing visible.

Tradeoff: A modular monolith does not force independent deployments. That is a
good fit for this project because the learning goal is event-driven design, not
distributed ownership.

## Observability From The Start

EventCart includes correlation IDs, structured logs, Prometheus metrics,
OpenTelemetry setup, and Compose services for Prometheus, Grafana, Jaeger, and
the OTel Collector.

Why it was chosen:

- Event workflows are hard to understand without traceability.
- Correlation IDs connect HTTP commands to emitted events and worker logs.
- Metrics and traces make the local system easier to inspect.
- The observability stack is present but kept lightweight in tests.

Tradeoff: Observability adds configuration and services. EventCart keeps unit
tests independent from the full stack so local feedback stays quick.
