# Order Lifecycle

EventCart starts every order as a durable database record before any event
publishing or worker processing happens.

## Current API Flow

```txt
Inventory item exists
  -> POST /api/v1/orders
  -> Order status: PENDING
  -> GET /api/v1/orders/{order_id}
```

The order API snapshots item details from inventory at creation time:

- SKU
- quantity requested
- unit price in cents
- product name

Inventory is not reserved in this phase. Reservation, payment, invoicing,
notifications, and compensation are added in later event-driven phases.

## States

`PENDING` means the order has been accepted by the API and stored in the
database. It has not completed the event-driven workflow yet.

`COMPLETED` means the order eventually succeeds through the full workflow:
inventory is reserved, payment is authorized, an invoice is created, and a
notification is sent.

`CANCELLED` means the order cannot complete. In the final workflow this can
happen after a failure such as payment failure, followed by compensation such as
releasing reserved inventory.

The current phase only creates and reads `PENDING` orders. Later phases will
move orders to `COMPLETED` or `CANCELLED` from workflow events.
