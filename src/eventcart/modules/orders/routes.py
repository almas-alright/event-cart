"""Order HTTP routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from eventcart.database import get_session
from eventcart.modules.orders.schemas import OrderCreate, OrderRead
from eventcart.modules.orders.service import (
    InventoryItemNotFoundError,
    create_order,
    get_order,
)

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def create_order_endpoint(
    payload: OrderCreate,
    session: Annotated[Session, Depends(get_session)],
) -> OrderRead:
    try:
        order = create_order(session, payload)
    except InventoryItemNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return OrderRead.model_validate(order)


@router.get("/{order_id}", response_model=OrderRead)
def get_order_endpoint(
    order_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> OrderRead:
    order = get_order(session, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found.",
        )

    return OrderRead.model_validate(order)

