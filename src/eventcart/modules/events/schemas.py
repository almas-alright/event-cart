"""Event envelope schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EventEnvelope(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    event_version: int = Field(ge=1)
    aggregate_type: str = Field(min_length=1)
    aggregate_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    causation_id: str | None = None
    occurred_at: datetime
    payload: dict[str, object]

