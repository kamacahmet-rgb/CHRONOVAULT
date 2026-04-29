from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=200)


class LoginRequest(BaseModel):
    username: str = Field(
        ...,
        description="Kullanıcı adı veya e-posta adresi",
        min_length=1,
        max_length=255,
    )
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    email: str
    username: str
    full_name: Optional[str]
    plan: str
    created_at: datetime
    monthly_quota: int = 100
    used_this_month: int = 0
    credit_balance: int = 0
    stamp_credit_cost: int = Field(
        default=1,
        description="Bir damgalamada düşülen kredi (Polygon GAS tahmini × çarpan).",
    )
    polygon_gas_cost_cents_estimate: int = Field(
        default=1,
        description="Operasyonel tahmini GAS maliyeti (cent, tam sayı).",
    )
    sale_credit_multiplier: int = Field(
        default=10,
        description="Satış kuralı: damga kredisi = bu sabit × maliyet (cent); kodda 10 sabit.",
    )

    model_config = {"from_attributes": True}


class APIKeyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    expires_at: Optional[datetime] = None


class APIKeyResponse(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class APIKeyCreatedResponse(APIKeyResponse):
    raw_key: str
