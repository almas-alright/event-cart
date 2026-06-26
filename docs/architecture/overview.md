# EventCart Architecture Overview

EventCart is a learning backend for event-driven architecture. It will model an
order workflow where API commands create durable business state and events drive
the rest of the process through workers.

The intended runtime shape is a modular FastAPI application with separate worker
processes:

```txt
API -> PostgreSQL transactional outbox -> event transport -> workers -> PostgreSQL
```

The project will support two event delivery modes:

- NATS JetStream for the primary broker-based mode.
- PostgreSQL outbox with LISTEN/NOTIFY and polling for the brokerless mode.

Core learning topics will include transactional outbox, idempotency, inbox
processing, at-least-once delivery, saga-style compensation, retries,
dead-letter handling, and observability through correlation IDs, logs, metrics,
and traces.

The final README will be polished in the last documentation phase. Until then,
this document is a lightweight placeholder for the architecture intent.
