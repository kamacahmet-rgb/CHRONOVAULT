from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator

ALLOWED_EVENTS = frozenset(
    {
        "stamp.created",
        "stamp.polygon.confirmed",
        "stamp.bitcoin.confirmed",
        "stamp.failed",
    }
)


class WebhookCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: HttpUrl
    events: List[str] = Field(min_length=1)

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: List[str]) -> List[str]:
        for e in v:
            if e not in ALLOWED_EVENTS:
                raise ValueError(f"Geçersiz event: {e}")
        return v


class WebhookResponse(BaseModel):
    id: UUID
    name: str
    url: str
    events: List[str]
    is_active: bool
    total_deliveries: int
    failed_deliveries: int
    last_triggered_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class WebhookCreatedResponse(WebhookResponse):
    secret: str
