"""Inventory request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InventoryItemCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    quantity_available: int = Field(ge=0)
    unit_price_cents: int = Field(ge=0)


class InventoryItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sku: str
    name: str
    quantity_available: int
    unit_price_cents: int
    created_at: datetime

