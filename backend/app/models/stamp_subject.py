from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base

if TYPE_CHECKING:
    from app.models.stamp import Stamp


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StampSubject(Base):
    """Damga ↔ kişi: yalnızca HMAC(TC) parmak izi; ham TC yok."""

    __tablename__ = "stamp_subjects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    stamp_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stamps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tc_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    stamp: Mapped["Stamp"] = relationship("Stamp", back_populates="subjects")
