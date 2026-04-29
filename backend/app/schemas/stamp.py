from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class StampRequest(BaseModel):
    file_hash: str = Field(min_length=64, max_length=64)
    file_name: str = Field(max_length=500)
    file_size: int = Field(ge=0, default=0)
    file_type: Optional[str] = Field(default=None, max_length=100)
    author: Optional[str] = Field(default=None, max_length=200)
    project: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    chain: Literal["both", "polygon", "bitcoin"] = "both"
    vertical: Optional[
        Literal[
            "music",
            "architecture",
            "visual",
            "health_archive",
            "municipal_license",
            "other",
        ]
    ] = None
    processing_purpose: Optional[str] = Field(default=None, max_length=120)
    data_category: Optional[Literal["general", "personal", "special_health"]] = None
    retention_until: Optional[datetime] = None
    consent_reference: Optional[str] = Field(default=None, max_length=120)
    work_title: Optional[str] = Field(default=None, max_length=300)
    subject_tc: Optional[str] = Field(
        default=None,
        min_length=11,
        max_length=11,
        pattern=r"^[0-9]{11}$",
        description="Ham değer DB'ye yazılmaz; HMAC parmak izi üretilir (stamp_subjects).",
    )
    idempotency_key: Optional[str] = Field(
        default=None,
        max_length=80,
        description="Aynı kullanıcı + aynı anahtar ile tekrar çağrıda mevcut damga döner (webhook yeniden tetiklenmez).",
    )

    @field_validator("idempotency_key")
    @classmethod
    def idempotency_trim(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        return s or None

    @field_validator("file_hash")
    @classmethod
    def lower_hex(cls, v: str) -> str:
        h = v.lower()
        if len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
            raise ValueError("file_hash 64 hex karakter olmalıdır")
        return h


class StampResponse(BaseModel):
    id: UUID
    file_name: str
    file_hash: str
    file_size: int
    author: Optional[str]
    project: Optional[str]
    polygon_tx: Optional[str]
    polygon_url: Optional[str]
    polygon_status: str
    ots_status: str
    ots_bitcoin_block: Optional[int]
    chain: str
    created_at: datetime
    vertical: Optional[str] = None
    processing_purpose: Optional[str] = None
    data_category: Optional[str] = None
    retention_until: Optional[datetime] = None
    consent_reference: Optional[str] = None
    work_title: Optional[str] = None
    credits_charged: int = 0

    model_config = {"from_attributes": True}


class StampListResponse(BaseModel):
    total: int
    page: int
    per_page: int
    items: List[StampResponse]
