from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.limiter import limiter
from app.models.stamp import Stamp
from app.schemas.verify import VerifyResponse, VerifyStampPublic

router = APIRouter(prefix="/verify", tags=["Verify"])


def _normalize_hash(raw: str) -> str:
    h = raw.strip().lower()
    if len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
        raise HTTPException(
            status_code=400,
            detail="Geçersiz SHA-256: 64 hex karakter beklenir.",
        )
    return h


@router.get("/{file_hash}", response_model=VerifyResponse)
@limiter.limit("120/minute")
async def verify_by_hash(
    request: Request,
    file_hash: str,
    db: AsyncSession = Depends(get_db),
) -> VerifyResponse:
    h = _normalize_hash(file_hash)
    r = await db.execute(
        select(Stamp)
        .where(Stamp.file_hash == h)
        .order_by(Stamp.created_at.desc())
        .limit(1)
    )
    stamp = r.scalar_one_or_none()
    if stamp is None:
        return VerifyResponse(
            found=False,
            stamp=None,
            message="Bu hash için kayıt bulunamadı.",
        )
    public = VerifyStampPublic.model_validate(stamp)
    return VerifyResponse(
        found=True,
        stamp=public,
        message="Kayıt bulundu.",
    )
