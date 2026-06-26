"""Inventory application services."""

from sqlalchemy.orm import Session

from eventcart.modules.inventory.models import InventoryItem
from eventcart.modules.inventory.schemas import InventoryItemCreate


def create_inventory_item(
    session: Session,
    payload: InventoryItemCreate,
) -> InventoryItem:
    item = InventoryItem(**payload.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    return item

