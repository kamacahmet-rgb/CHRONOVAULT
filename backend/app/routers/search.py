from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.limiter import limiter
from app.models.stamp import Stamp
from app.models.stamp_subject import StampSubject
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.search import StampSearchResponse, StampSummary

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("/stamps", response_model=StampSearchResponse)
@limiter.limit("60/minute")
async def search_stamps(
    request: Request,
    q: Optional[str] = Query(None, max_length=500),
    file_hash: Optional[str] = Query(None, min_length=64, max_length=64),
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    polygon_status: Optional[str] = None,
    ots_status: Optional[str] = None,
    chain: Optional[str] = None,
    tag: Optional[str] = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    scope: str = Query("self", pattern=r"^(self|by_verified_subject)$"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StampSearchResponse:
    """
    scope=self: oturum kullanıcısının damgaları.
    scope=by_verified_subject: KYC `subject_tc_fingerprint` ile eşleşen stamp_subjects
    (organization_id eşleşmesi).
    """
    stamp_filters = []

    if file_hash:
        fh = file_hash.lower().strip()
        if len(fh) != 64 or any(c not in "0123456789abcdef" for c in fh):
            raise HTTPException(status_code=400, detail="Geçersiz file_hash")
        stamp_filters.append(Stamp.file_hash == fh)
    if from_date is not None:
        stamp_filters.append(Stamp.created_at >= from_date)
    if to_date is not None:
        stamp_filters.append(Stamp.created_at <= to_date)
    if polygon_status:
        stamp_filters.append(Stamp.polygon_status == polygon_status)
    if ots_status:
        stamp_filters.append(Stamp.ots_status == ots_status)
    if chain:
        stamp_filters.append(Stamp.chain == chain)
    if q:
        ilike = f"%{q}%"
        stamp_filters.append(
            or_(
                Stamp.file_name.ilike(ilike),
                Stamp.description.ilike(ilike),
                Stamp.author.ilike(ilike),
                Stamp.project.ilike(ilike),
            )
        )
    if tag:
        stamp_filters.append(Stamp.tags.contains([tag]))

    if scope == "self":
        base_where = and_(Stamp.user_id == user.id, *stamp_filters)
        count_stmt = select(func.count(Stamp.id)).where(base_where)
        list_stmt = (
            select(Stamp).where(base_where).order_by(Stamp.created_at.desc())
        )
    else:
        if not user.subject_tc_fingerprint:
            raise HTTPException(
                status_code=400,
                detail="by_verified_subject için hesaba KYC (subject_tc_fingerprint) gerekir.",
            )
        org_clause = (
            StampSubject.organization_id == user.organization_id
            if user.organization_id is not None
            else StampSubject.organization_id.is_(None)
        )
        join_where = and_(
            StampSubject.tc_fingerprint == user.subject_tc_fingerprint,
            org_clause,
            *stamp_filters,
        )
        ids_subq = (
            select(Stamp.id)
            .join(StampSubject, StampSubject.stamp_id == Stamp.id)
            .where(join_where)
            .distinct()
            .subquery()
        )
        count_stmt = select(func.count()).select_from(ids_subq)
        list_stmt = (
            select(Stamp)
            .join(ids_subq, Stamp.id == ids_subq.c.id)
            .order_by(Stamp.created_at.desc())
        )

    total = int((await db.execute(count_stmt)).scalar_one())
    offset = (page - 1) * per_page
    result = await db.execute(list_stmt.offset(offset).limit(per_page))
    items = [StampSummary.model_validate(s) for s in result.scalars().all()]

    return StampSearchResponse(total=total, page=page, per_page=per_page, items=items)
