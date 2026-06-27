# EventCart

**EventCart** is a learning-focused FastAPI backend for understanding
event-driven order workflows with durable event storage, idempotency, workers,
retry handling, and local Docker infrastructure.

It is not a full e-commerce platform. The goal is to make event-driven backend
architecture easy to inspect through a compact order-processing example.

## Why This Shreded Scope?

EventCart demonstrates:

- Event-driven architecture with explicit event envelopes
- FastAPI backend design with Pydantic request and response models
- PostgreSQL transactional outbox
- API idempotency with `Idempotency-Key`
- Consumer inbox pattern
- At-least-once delivery safety
- NATS JetStream publisher mode
- PostgreSQL brokerless dispatch with outbox polling and LISTEN/NOTIFY wake-ups
- Saga-style order workflow and compensation
- Retry, dead-letter, and replay handling
- Correlation IDs, structured logs, Prometheus metrics, and OpenTelemetry setup
- Docker Compose local runtime for API, PostgreSQL, Redis, NATS, and observability

Important principle:

> This project does not assume duplicate events will never happen.
> Instead, it assumes duplicate events can happen and makes event handlers
> idempotent so duplicates become harmless.

Also:

> Idempotency does not remove duplication. Idempotency makes duplication safe.

## Tech Stack

| Area | Tool |
| --- | --- |
| API | FastAPI |
| Language | Python 3.12+ |
| Validation | Pydantic v2 |
| Database | PostgreSQL |
| ORM / migrations | SQLAlchemy 2.x / Alembic |
| Broker mode | NATS JetStream publisher |
| Brokerless mode | PostgreSQL outbox polling plus LISTEN/NOTIFY wake-up |
| Cache / coordination | Redis |
| Tests | Pytest + HTTPX |
| Quality | Ruff + Pyright |
| Observability | OpenTelemetry, Prometheus, Grafana, Jaeger |
| Runtime | Docker Compose |
| Docs | Markdown + Mermaid |

## Current Runtime Status

The repository currently includes:

- A runnable FastAPI API container
- PostgreSQL, Redis, NATS JetStream, Prometheus, Grafana, Jaeger, and OTel
  Collector services in `docker-compose.yml`
- Order and inventory HTTP endpoints
- Transactional outbox tables and repository logic
- A NATS outbox publisher module
- A brokerless dispatcher module that routes outbox events to local handlers
- Worker handler modules for inventory, payment, invoice, notification, order
  projection, compensation, and dead-letter replay

The Compose file does not currently define long-running worker services such as
`inventory-worker` or `payment-worker`, and there is no Event Monitor UI in this
repo yet. The workflow is runnable through the API plus the brokerless
dispatcher module, and the full behavior is covered by tests.

## Architecture Overview

```mermaid
flowchart LR
    Client["HTTP client"] --> API["FastAPI API"]

    API --> Orders[("orders")]
    API --> Inventory[("inventory_items")]
    API --> Idempotency[("idempotency_keys")]
    API --> Outbox[("outbox_events")]

    Outbox --> Publisher["NATS outbox publisher"]
    Publisher --> NATS["NATS JetStream"]

    Outbox --> Dispatcher["brokerless dispatcher"]
    Dispatcher --> Handlers["worker handlers"]

    Handlers --> Inbox[("inbox_events")]
    Handlers --> Domain[("business tables")]
    Handlers --> Attempts[("event_processing_attempts")]
    Handlers --> DeadLetter[("dead_letter_events")]
    Handlers --> Outbox

    API --> Metrics["/metrics"]
    API --> Traces["OpenTelemetry"]
```

The API writes business state and event state to PostgreSQL. The outbox table is
the durable handoff point. Events can be published to NATS, or dispatched inside
PostgreSQL brokerless mode by polling pending outbox rows and invoking local
handlers.

## Order Event Flow

Success path:

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant Outbox
    participant Inventory
    participant Payment
    participant Invoice
    participant Notification
    participant Projection

    Client->>API: POST /api/v1/orders
    API->>Outbox: OrderCreated
    Outbox->>Inventory: OrderCreated
    Inventory->>Outbox: InventoryReserved
    Outbox->>Payment: InventoryReserved
    Payment->>Outbox: PaymentAuthorized
    Outbox->>Invoice: PaymentAuthorized
    Invoice->>Outbox: InvoiceCreated
    Outbox->>Notification: InvoiceCreated
    Notification->>Outbox: NotificationSent
    Outbox->>Projection: NotificationSent
    Projection->>Projection: order COMPLETED
```

Failure path:

```mermaid
sequenceDiagram
    participant API
    participant Inventory
    participant Payment
    participant Projection

    API->>Inventory: OrderCreated
    Inventory->>Payment: InventoryReserved
    Payment->>Inventory: PaymentFailed
    Inventory->>Projection: InventoryReleased
    Projection->>Projection: order CANCELLED
```

## Order Lifecycle

The stored order model currently uses these final status values:

```mermaid
stateDiagram-v2
    [*] --> PENDING
    PENDING --> COMPLETED: NotificationSent
    PENDING --> CANCELLED: InventoryReservationFailed
    PENDING --> CANCELLED: InventoryReleased after PaymentFailed
```

Intermediate workflow steps are represented as events and related business
tables rather than as separate order status values.

## Transactional Outbox

A common distributed-system mistake is:

1. Save business data to the database.
2. Publish an event to a broker.
3. Hope both actions succeed together.

Those two writes are not part of one transaction. EventCart uses the
transactional outbox pattern instead:

```mermaid
flowchart TD
    Request["POST /api/v1/orders"] --> Tx["database transaction"]
    Tx --> SaveOrder["save order and order_items"]
    Tx --> SaveEvent["save OrderCreated in outbox_events"]
    SaveOrder --> Commit["commit"]
    SaveEvent --> Commit
    Commit --> Delivery["publisher or brokerless dispatcher"]
    Delivery --> Worker["worker handler"]
```

The API writes the order and `OrderCreated` event in the same PostgreSQL
transaction. A separate delivery step later reads pending outbox rows.

## Idempotency

EventCart has three idempotency layers:

| Layer | Mechanism |
| --- | --- |
| API | `Idempotency-Key` stores request hash, status code, and response body. |
| Publisher | `event_id` is the publish identity and NATS message ID where supported. |
| Consumer | `consumer_name + event_id` inbox rows prevent repeated side effects. |

API behavior:

| Request | Result |
| --- | --- |
| Same key + same body | Returns the stored response. |
| Same key + different body | Returns `409 Conflict`. |
| No key | Creates a normal request without replay protection. |

Consumer inbox flow:

```mermaid
flowchart TD
    Event["incoming event"] --> Check{"consumer_name + event_id exists?"}
    Check -->|yes| Skip["skip duplicate"]
    Check -->|no| Process["apply side effect"]
    Process --> Save["save inbox_events row"]
    Save --> Emit["emit next outbox event"]
```

This matters because practical event systems often provide at-least-once
delivery. Duplicate delivery is expected, not surprising.

## Delivery Modes

### NATS JetStream Publisher Mode

```mermaid
flowchart LR
    Outbox[("outbox_events")] --> Publisher["outbox publisher"]
    Publisher --> NATS["NATS JetStream"]
```

The repository includes a NATS JetStream publisher that reads pending outbox
events and publishes them with a stable subject convention:

```txt
eventcart.<aggregate>.<event>
```

Example subjects:

```txt
eventcart.order.ordercreated
eventcart.order.inventoryreserved
eventcart.order.paymentauthorized
```

Long-running NATS consumer services are not wired into `docker-compose.yml` yet.
The worker business handlers exist and are tested, while brokerless dispatch is
the currently runnable local end-to-end workflow.

### PostgreSQL Brokerless Mode

```mermaid
flowchart LR
    Outbox[("outbox_events")]
    Notify["LISTEN/NOTIFY wake-up"]
    Poller["brokerless dispatcher"]
    Router["event type router"]
    Handler["local handler"]
    State[("business tables")]

    Outbox --> Poller
    Outbox -.-> Notify
    Notify -.-> Poller
    Poller --> Router
    Router --> Handler
    Handler --> State
    Handler --> Outbox
```

PostgreSQL `LISTEN/NOTIFY` is not a full replacement for NATS, Kafka, or
RabbitMQ. It is a lightweight wake-up signal. Durability comes from
`outbox_events`, and polling provides reliability.

## Installation

### Prerequisites

For the Docker-first path:

- Git
- Docker
- Docker Compose

For local development without containers:

- Python 3.12+

### Clone

```bash
git clone git@github.com:almas-alright/event-cart.git
cd event-cart
```

### Environment

Copy the example environment file:

```bash
cp .env.example .env
```

The default `.env.example` values are suitable for the local Docker Compose
stack.

## Run With Docker Compose

Build and start the local stack:

```bash
docker compose up --build -d
```

Initialize the PostgreSQL schema from the API image:

```bash
docker compose run --rm \
  -v "$PWD/alembic.ini:/app/alembic.ini:ro" \
  -v "$PWD/migrations:/app/migrations:ro" \
  api alembic upgrade head
```

Check the API:

```bash
curl http://localhost:8000/health
```

Stop services:

```bash
docker compose down
```

Stop services and remove volumes:

```bash
docker compose down -v
```

### Service URLs

| Service | URL |
| --- | --- |
| FastAPI API | `http://localhost:8000` |
| Swagger UI | `http://localhost:8000/docs` |
| ReDoc | `http://localhost:8000/redoc` |
| Prometheus metrics | `http://localhost:8000/metrics` |
| NATS monitor | `http://localhost:8222` |
| Prometheus | `http://localhost:9090` |
| Grafana | `http://localhost:3000` |
| Jaeger | `http://localhost:16686` |

PostgreSQL is exposed on `localhost:5432`, Redis on `localhost:6379`, and NATS
client connections on `localhost:4222`.

### Docker Commands

View containers:

```bash
docker compose ps
```

View logs:

```bash
docker compose logs -f
```

View API logs:

```bash
docker compose logs -f api
```

Run one brokerless dispatch pass:

```bash
docker compose run --rm \
  -e EVENTCART_EVENT_TRANSPORT=postgres \
  api python -m eventcart.workers.brokerless_dispatcher
```

The dispatcher processes the currently pending batch. Repeat the command after
creating an order to advance newly emitted events, or use the tests to observe
the full workflow automatically.

Publish pending outbox events to NATS:

```bash
docker compose run --rm api python -m eventcart.workers.outbox_publisher
```

Replay a dead-letter event by ID:

```bash
docker compose run --rm api python -m eventcart.workers.dead_letter_replay <dead_letter_id>
```

## Local Python Development

Create a virtual environment:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

If you are using the Docker PostgreSQL service from `.env.example`, export the
local database URL and run migrations:

```bash
export DATABASE_URL="postgresql+psycopg://eventcart:eventcart@localhost:5432/eventcart"
alembic upgrade head
```

Run the API locally:

```bash
uvicorn eventcart.main:app --reload
```

## API Usage

### Create Inventory

```bash
curl -X POST http://localhost:8000/api/v1/admin/inventory-items \
  -H "Content-Type: application/json" \
  -d '{
    "sku": "ticket-standard",
    "name": "Standard Ticket",
    "quantity_available": 100,
    "unit_price_cents": 4500
  }'
```

### Create An Order

```bash
curl -X POST http://localhost:8000/api/v1/orders \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: order-demo-1" \
  -H "X-Correlation-ID: demo-correlation-1" \
  -d '{
    "customer_email": "ada@example.com",
    "items": [
      {"sku": "ticket-standard", "quantity": 2}
    ]
  }'
```

### Retry The Same Request

Run the same order request again with the same `Idempotency-Key`. EventCart
returns the stored response instead of creating a duplicate order.

### Trigger An Idempotency Conflict

```bash
curl -i -X POST http://localhost:8000/api/v1/orders \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: order-demo-1" \
  -d '{
    "customer_email": "ada@example.com",
    "items": [
      {"sku": "ticket-standard", "quantity": 3}
    ]
  }'
```

Expected result: `409 Conflict`.

### Read An Order

```bash
curl http://localhost:8000/api/v1/orders/<order_id>
```

### Read Metrics

```bash
curl http://localhost:8000/metrics
```

## Actual HTTP Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Health check |
| `GET` | `/metrics` | Prometheus metrics |
| `POST` | `/api/v1/admin/inventory-items` | Create inventory for demos |
| `POST` | `/api/v1/orders` | Create an order |
| `GET` | `/api/v1/orders/{order_id}` | Read an order |

There are no public `/events`, `/outbox`, `/inbox`, or `/dead-letter` HTTP
endpoints yet. Those concepts are implemented in repositories, worker modules,
tables, tests, and docs.

## Event Envelope

Events use this envelope shape:

```json
{
  "event_id": "uuid",
  "event_type": "OrderCreated",
  "event_version": 1,
  "aggregate_type": "Order",
  "aggregate_id": "uuid",
  "correlation_id": "uuid",
  "causation_id": "uuid|null",
  "occurred_at": "2026-06-26T10:00:00Z",
  "payload": {}
}
```

Current event types:

- `OrderCreated`
- `InventoryReserved`
- `InventoryReservationFailed`
- `PaymentAuthorized`
- `PaymentFailed`
- `InvoiceCreated`
- `NotificationSent`
- `InventoryReleased`

## Testing

Run the full suite:

```bash
.venv/bin/python -m pytest
```

Run quality checks:

```bash
.venv/bin/ruff check .
.venv/bin/pyright
```

Run selected learning areas:

```bash
.venv/bin/python -m pytest tests/test_orders_outbox.py
.venv/bin/python -m pytest tests/test_orders_idempotency.py
.venv/bin/python -m pytest tests/test_brokerless_workflow.py
.venv/bin/python -m pytest tests/test_dead_letter_events.py
```

The tests are intentionally educational. They show API behavior, event envelope
shape, outbox persistence, idempotency, worker side effects, brokerless dispatch,
retry, DLQ, replay, metrics, tracing setup, and Compose config validation.

## Learning Path

1. Start the Docker Compose stack.
2. Open Swagger UI at `http://localhost:8000/docs`.
3. Create an inventory item.
4. Create an order with an `Idempotency-Key`.
5. Repeat the same request and confirm the duplicate is safe.
6. Run brokerless dispatch passes to process outbox events locally.
7. Read the order again and observe status changes.
8. Read `docs/architecture/transactional-outbox.md`.
9. Read `docs/architecture/idempotency.md`.
10. Finish with `docs/testing-guide.md` to connect tests to concepts.

## Production Notes

EventCart is an educational architecture showcase, not production-ready
commerce software.

Before applying similar ideas in production, consider adding:

- Authentication and authorization
- Secrets management
- Stronger event schema governance
- Long-running worker deployments
- NATS consumer processes if broker mode is the primary runtime
- Operational dashboards and alerts
- More complete integration tests against PostgreSQL and NATS
- Rate limiting
- Real payment provider integration
- CI/CD deployment infrastructure

## Deeper Docs

- [Curl examples](docs/examples/README.md)
- [Architecture diagrams](docs/diagrams/)
- [Architecture decisions](docs/architecture-decisions.md)
- [Architecture overview](docs/architecture/overview.md)
- [Order lifecycle](docs/domain/order-lifecycle.md)
- [Transactional outbox](docs/architecture/transactional-outbox.md)
- [NATS JetStream mode](docs/architecture/nats-jetstream-mode.md)
- [Idempotency](docs/architecture/idempotency.md)
- [Saga workflow](docs/architecture/saga-workflow.md)
- [Broker vs brokerless](docs/architecture/broker-vs-brokerless.md)
- [Retry, dead letter, and replay](docs/architecture/retry-dead-letter-replay.md)
- [Observability](docs/architecture/observability.md)
- [Testing guide](docs/testing-guide.md)

## Notes

This repository is designed to be read phase by phase. The code favors explicit
modules and focused tests over hidden framework magic. Each architecture doc
explains one event-driven concept, and each test maps to a behavior worth
learning.
