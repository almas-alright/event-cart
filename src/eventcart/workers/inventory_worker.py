"""Inventory worker handlers."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from eventcart.modules.events import EventEnvelope, OutboxEvent
from eventcart.modules.inventory import InventoryItem


class InventoryReservationError(Exception):
    pass


def handle_order_created(session: Session, event: EventEnvelope) -> OutboxEvent:
    order_id = str(event.payload["order_id"])
    requested_items = _payload_items(event.payload)

    try:
        inventory_items = _load_inventory_items(session, requested_items)
        _ensure_inventory_available(inventory_items, requested_items)
    except InventoryReservationError as error:
        outbox_event = _build_result_event(
            source_event=event,
            event_type="InventoryReservationFailed",
            order_id=order_id,
            payload={
                "order_id": order_id,
                "reason": str(error),
                "items": requested_items,
            },
        )
        session.add(outbox_event)
        session.commit()
        return outbox_event

    for requested_item in requested_items:
        sku = str(requested_item["sku"])
        quantity = _quantity(requested_item)
        inventory_items[sku].quantity_available -= quantity

    outbox_event = _build_result_event(
        source_event=event,
        event_type="InventoryReserved",
        order_id=order_id,
        payload={
            "order_id": order_id,
            "items": requested_items,
        },
    )
    session.add(outbox_event)
    session.commit()
    return outbox_event


def _payload_items(payload: dict[str, object]) -> list[dict[str, object]]:
    items = payload.get("items")
    if not isinstance(items, list):
        raise InventoryReservationError("OrderCreated payload has no items.")

    return [dict(item) for item in items if isinstance(item, dict)]


def _load_inventory_items(
    session: Session,
    requested_items: list[dict[str, object]],
) -> dict[str, InventoryItem]:
    skus = [str(item["sku"]) for item in requested_items]
    inventory_items = {
        item.sku: item
        for item in session.scalars(
            select(InventoryItem).where(InventoryItem.sku.in_(skus))
        )
    }

    missing_skus = sorted(set(skus) - set(inventory_items))
    if missing_skus:
        raise InventoryReservationError(
            f"Inventory item not found for SKU {missing_skus[0]!r}."
        )

    return inventory_items


def _ensure_inventory_available(
    inventory_items: dict[str, InventoryItem],
    requested_items: list[dict[str, object]],
) -> None:
    for requested_item in requested_items:
        sku = str(requested_item["sku"])
        quantity = _quantity(requested_item)
        available = inventory_items[sku].quantity_available
        if available < quantity:
            raise InventoryReservationError(
                f"Insufficient inventory for SKU {sku!r}: requested {quantity}, "
                f"available {available}."
            )


def _quantity(requested_item: dict[str, object]) -> int:
    quantity = requested_item.get("quantity")
    if not isinstance(quantity, int):
        raise InventoryReservationError(
            "OrderCreated item quantity must be an integer."
        )
    return quantity


def _build_result_event(
    *,
    source_event: EventEnvelope,
    event_type: str,
    order_id: str,
    payload: dict[str, Any],
) -> OutboxEvent:
    return OutboxEvent(
        event_type=event_type,
        event_version=1,
        aggregate_type="Order",
        aggregate_id=order_id,
        correlation_id=source_event.correlation_id,
        causation_id=source_event.event_id,
        payload=payload,
    )
