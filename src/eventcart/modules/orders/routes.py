"""Order HTTP routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.orm import Session

from eventcart.database import get_session
from eventcart.modules.idempotency import (
    IdempotencyConflictError,
    IdempotencyInProgressError,
    IdempotencyService,
)
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
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> OrderRead:
    idempotency_service = IdempotencyService(session)
    if idempotency_key is not None:
        try:
            stored_response = idempotency_service.start_request(
                key=idempotency_key,
                request_body=payload.model_dump(mode="json"),
            )
        except IdempotencyConflictError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(error),
            ) from error
        except IdempotencyInProgressError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(error),
            ) from error

        if stored_response is not None:
            response.status_code = stored_response.status_code
            return OrderRead.model_validate(stored_response.response_body)

    try:
        order = create_order(session, payload)
    except InventoryItemNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    order_response = OrderRead.model_validate(order)
    if idempotency_key is not None:
        idempotency_service.store_response(
            key=idempotency_key,
            response_body=order_response.model_dump(mode="json"),
            status_code=status.HTTP_201_CREATED,
        )
        session.commit()

    return order_response


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
