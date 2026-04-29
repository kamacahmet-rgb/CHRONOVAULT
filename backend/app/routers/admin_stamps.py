from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.limiter import limiter
from app.models.stamp import Stamp
from app.models.stamp_subject import StampSubject
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.search import AdminSubjectLookupRequest, StampSummary
from app.services.subject_fingerprint import tc_fingerprint

router = APIRouter(prefix="/admin/subject-stamps", tags=["Admin"])


def require_org_admin(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("org_admin", "superadmin"):
        raise HTTPException(
            status_code=403, detail="org_admin veya superadmin rolü gerekli"
        )
    if user.role == "org_admin" and user.organization_id is None:
        raise HTTPException(
            status_code=400, detail="Kurumsal admin için organization_id gerekli"
        )
    return user


@router.post("/lookup", response_model=list[StampSummary])
@limiter.limit("10/hour")
async def admin_lookup_stamps_by_tc(
    request: Request,
    body: AdminSubjectLookupRequest,
    admin: User = Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
) -> list[StampSummary]:
    """
    Verilen T.C. parmak izi ile eşleşen damgalar. Ham TC kalıcı loglanmamalıdır.
    superadmin: organization filtresi yok (tüm kiracılar).
    """
    settings = get_settings()
    try:
        fp = tc_fingerprint(settings.subject_tc_hmac_secret, body.tc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    stmt = (
        select(Stamp)
        .join(StampSubject, StampSubject.stamp_id == Stamp.id)
        .where(StampSubject.tc_fingerprint == fp)
        .order_by(Stamp.created_at.desc())
    )
    if admin.role != "superadmin":
        stmt = stmt.where(StampSubject.organization_id == admin.organization_id)

    result = await db.execute(stmt)
    stamps = result.unique().scalars().all()
    return [StampSummary.model_validate(s) for s in stamps]
