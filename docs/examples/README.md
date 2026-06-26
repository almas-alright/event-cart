# EventCart Curl Examples

These examples assume the API is running locally:

```bash
export EVENTCART_API_URL="http://localhost:8000"
```

If you have `jq`, the examples can capture response fields into shell
variables. Without `jq`, copy the `id` value from the JSON response manually.

## Create Inventory

Create an item that orders can reserve:

```bash
curl -sS -X POST "$EVENTCART_API_URL/api/v1/admin/inventory-items" \
  -H "Content-Type: application/json" \
  -d '{
    "sku": "ticket-standard",
    "name": "Standard Ticket",
    "quantity_available": 100,
    "unit_price_cents": 4500
  }'
```

## Create An Order

Send a command with both an idempotency key and a correlation ID:

```bash
export IDEMPOTENCY_KEY="order-demo-1"
export CORRELATION_ID="demo-correlation-1"

curl -sS -X POST "$EVENTCART_API_URL/api/v1/orders" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $IDEMPOTENCY_KEY" \
  -H "X-Correlation-ID: $CORRELATION_ID" \
  -d '{
    "customer_email": "ada@example.com",
    "items": [
      {"sku": "ticket-standard", "quantity": 2}
    ]
  }'
```

To capture the order ID with `jq`:

```bash
export ORDER_ID="$(
  curl -sS -X POST "$EVENTCART_API_URL/api/v1/orders" \
    -H "Content-Type: application/json" \
    -H "Idempotency-Key: order-demo-2" \
    -H "X-Correlation-ID: demo-correlation-2" \
    -d '{
      "customer_email": "grace@example.com",
      "items": [
        {"sku": "ticket-standard", "quantity": 1}
      ]
    }' | jq -r '.id'
)"
```

Read the order:

```bash
curl -sS "$EVENTCART_API_URL/api/v1/orders/$ORDER_ID"
```

The order starts as `PENDING`. Workers move it to `COMPLETED` on the success
path, or `CANCELLED` if payment fails and inventory is released.

## Repeat The Same Idempotent Request

Run the exact same request again with the same `Idempotency-Key`:

```bash
curl -sS -X POST "$EVENTCART_API_URL/api/v1/orders" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $IDEMPOTENCY_KEY" \
  -H "X-Correlation-ID: $CORRELATION_ID" \
  -d '{
    "customer_email": "ada@example.com",
    "items": [
      {"sku": "ticket-standard", "quantity": 2}
    ]
  }'
```

EventCart returns the stored response instead of creating a second order. This
is the API-layer idempotency behavior.

## Try An Idempotency Conflict

Reuse the same key with a different request body:

```bash
curl -i -sS -X POST "$EVENTCART_API_URL/api/v1/orders" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $IDEMPOTENCY_KEY" \
  -d '{
    "customer_email": "ada@example.com",
    "items": [
      {"sku": "ticket-standard", "quantity": 3}
    ]
  }'
```

The API responds with `409 Conflict` because the key is already attached to a
different command body.

## Trace An Event Flow

Use the same correlation ID on the command and then follow it through logs,
metrics, and traces:

```bash
export TRACE_KEY="trace-demo-1"
export TRACE_ID="trace-correlation-1"

curl -sS -X POST "$EVENTCART_API_URL/api/v1/orders" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $TRACE_KEY" \
  -H "X-Correlation-ID: $TRACE_ID" \
  -d '{
    "customer_email": "katherine@example.com",
    "items": [
      {"sku": "ticket-standard", "quantity": 1}
    ]
  }'
```

Read API metrics:

```bash
curl -sS "$EVENTCART_API_URL/metrics"
```

When running with Docker Compose, filter service logs by the correlation ID:

```bash
docker compose logs api outbox-publisher inventory-worker payment-worker invoice-worker notification-worker \
  | grep "$TRACE_ID"
```

Open the local observability tools:

```txt
Prometheus: http://localhost:9090
Grafana:    http://localhost:3000
Jaeger:     http://localhost:16686
```

In Jaeger, search for traces from the API service after submitting the request.
The correlation ID links the HTTP command, event envelope, and worker logs for
one business flow.
