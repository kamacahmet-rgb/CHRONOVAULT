from __future__ import annotations

from datetime import datetime
from typing import List
from uuid import UUID

from pydantic import BaseModel, Field


class AdminSubjectLookupRequest(BaseModel):
    """Kurumsal admin: TC parmak izisi ile aynı organization kapsamındaki damgalar."""

    tc: str = Field(min_length=11, max_length=11, pattern=r"^[0-9]{11}$")


class StampSummary(BaseModel):
    id: UUID
    file_name: str
    file_hash: str
    file_size: int
    polygon_status: str
    ots_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StampSearchResponse(BaseModel):
    total: int
    page: int
    per_page: int
    items: List[StampSummary]
