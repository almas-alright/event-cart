"""Inventory HTTP routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from eventcart.database import get_session
from eventcart.modules.inventory.schemas import InventoryItemCreate, InventoryItemRead
from eventcart.modules.inventory.service import create_inventory_item

router = APIRouter(prefix="/api/v1/admin/inventory-items", tags=["inventory"])


@router.post("", response_model=InventoryItemRead, status_code=status.HTTP_201_CREATED)
def create_inventory_item_endpoint(
    payload: InventoryItemCreate,
    session: Annotated[Session, Depends(get_session)],
) -> InventoryItemRead:
    item = create_inventory_item(session, payload)
    return InventoryItemRead.model_validate(item)
