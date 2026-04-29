from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class VerifyStampPublic(BaseModel):
    """Halka açık doğrulama — kullanıcı / e-posta dönmez."""

    id: UUID
    file_name: str
    file_hash: str
    polygon_tx: Optional[str] = None
    polygon_url: Optional[str] = None
    polygon_status: str
    ots_status: str
    chain: str
    created_at: datetime

    model_config = {"from_attributes": True}


class VerifyResponse(BaseModel):
    found: bool
    stamp: Optional[VerifyStampPublic] = None
    message: str = Field(default="", max_length=500)
