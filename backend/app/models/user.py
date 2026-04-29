from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base

if TYPE_CHECKING:
    from app.models.api_key import APIKey
    from app.models.stamp import Stamp
    from app.models.webhook import Webhook


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    plan: Mapped[str] = mapped_column(String(20), default="free", nullable=False)
    monthly_quota: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    used_this_month: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    credit_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False, index=True)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    subject_tc_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    subject_binding_verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    stamps: Mapped[List["Stamp"]] = relationship(
        "Stamp", back_populates="user", cascade="all, delete-orphan"
    )
    api_keys: Mapped[List["APIKey"]] = relationship(
        "APIKey", back_populates="user", cascade="all, delete-orphan"
    )
    webhooks: Mapped[List["Webhook"]] = relationship(
        "Webhook", back_populates="user", cascade="all, delete-orphan"
    )
