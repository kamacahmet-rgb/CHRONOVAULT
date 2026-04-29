from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSON, UUID

from app.database import Base

if TYPE_CHECKING:
    from app.models.stamp_subject import StampSubject
    from app.models.user import User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Stamp(Base):
    __tablename__ = "stamps"
    __table_args__ = (Index("ix_stamps_hash_user", "file_hash", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    file_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    author: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    project: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)

    vertical: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, index=True)
    processing_purpose: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    data_category: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    retention_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_reference: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    work_title: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)

    polygon_tx: Mapped[Optional[str]] = mapped_column(String(66), nullable=True)
    polygon_url: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    polygon_block: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    polygon_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)

    ots_file_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ots_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    ots_bitcoin_block: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    ots_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    chain: Mapped[str] = mapped_column(String(20), default="both", nullable=False)

    idempotency_key: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    credits_charged: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    user: Mapped["User"] = relationship("User", back_populates="stamps")
    subjects: Mapped[List["StampSubject"]] = relationship(
        "StampSubject", back_populates="stamp", cascade="all, delete-orphan"
    )
