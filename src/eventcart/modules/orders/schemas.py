"""Order request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from eventcart.modules.orders.models import OrderStatus


class OrderItemCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    quantity: int = Field(gt=0)


class OrderCreate(BaseModel):
    customer_email: str = Field(min_length=3, max_length=320)
    items: list[OrderItemCreate] = Field(min_length=1)


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sku: str
    quantity: int
    unit_price_cents: int
    product_name: str | None


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: OrderStatus
    customer_email: str
    created_at: datetime
    items: list[OrderItemRead]

