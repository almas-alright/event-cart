# NATS JetStream Mode

EventCart's primary broker mode publishes durable outbox events to NATS
JetStream. The database outbox remains the source of truth until an event is
successfully published.

## Flow

```mermaid
flowchart LR
    A["POST /api/v1/orders"] --> B["orders and outbox_events commit"]
    B --> C["outbox publisher worker"]
    C --> D["NATS JetStream"]
    D --> E["inventory worker"]
    E --> F["inventory update and next outbox event"]
```

## Subject Naming

The publisher maps each event envelope to this subject pattern:

```txt
eventcart.<aggregate_type>.<event_type>
```

Segments are lowercase. Examples:

```txt
eventcart.order.ordercreated
eventcart.order.inventoryreserved
eventcart.order.inventoryreservationfailed
```

The event ID is sent as the NATS message ID so JetStream can deduplicate
publishes where supported.

## Durable Consumers

Workers should use durable consumers so NATS tracks delivery progress by
consumer name. A durable inventory consumer can disconnect and later continue
from the last acknowledged message instead of starting from the beginning.

Durable consumers do not replace application idempotency. EventCart will add an
inbox table in the idempotency phase so repeated deliveries can be skipped
safely by consumer name and event ID.

## Replay

JetStream can replay stored messages to rebuild projections, test workers, or
recover from downstream outages. Replay should be paired with idempotent
handlers because replay intentionally delivers events that may already have been
processed.

The outbox publisher and worker handlers in this phase establish the broker
mode shape. Later phases add broader workflow workers, idempotency, retries,
dead-letter handling, and observability.
