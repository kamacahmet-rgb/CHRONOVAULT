from __future__ import annotations

import secrets
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.stamp import Stamp
from app.models.stamp_subject import StampSubject
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.stamp import StampListResponse, StampRequest, StampResponse
from app.services.subject_fingerprint import tc_fingerprint
from app.services.webhook_dispatch import dispatch_stamp_created_background

router = APIRouter(prefix="/stamps", tags=["Stamps"])


def _placeholder_polygon() -> tuple[str, str]:
    tx = "0x" + secrets.token_hex(32)
    url = f"https://polygonscan.com/tx/{tx}"
    return tx, url


@router.post("/", response_model=StampResponse)
async def create_stamp(
    body: StampRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Stamp:
    if (
        body.vertical == "health_archive"
        and body.data_category == "special_health"
        and not (body.consent_reference and body.consent_reference.strip())
    ):
        raise HTTPException(
            status_code=400,
            detail="Hasta arşivi + özel nitelikli sağlık verisi için consent_reference zorunludur.",
        )

    if body.idempotency_key:
        dup = await db.execute(
            select(Stamp).where(
                Stamp.user_id == user.id,
                Stamp.idempotency_key == body.idempotency_key,
            )
        )
        existing = dup.scalar_one_or_none()
        if existing is not None:
            return existing

    settings = get_settings()
    cost = settings.stamp_credit_cost()

    locked = await db.execute(select(User).where(User.id == user.id).with_for_update())
    account = locked.scalar_one()
    if account.credit_balance < cost:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "insufficient_credits",
                "balance": account.credit_balance,
                "required": cost,
                "stamp_credit_cost": cost,
            },
        )

    account.credit_balance -= cost
    account.used_this_month += 1

    poly_tx, poly_url = _placeholder_polygon()
    stamp = Stamp(
        user_id=user.id,
        idempotency_key=body.idempotency_key,
        credits_charged=cost,
        file_name=body.file_name,
        file_hash=body.file_hash,
        file_size=body.file_size,
        file_type=body.file_type,
        author=body.author,
        project=body.project,
        description=body.description,
        tags=list(body.tags),
        vertical=body.vertical,
        processing_purpose=body.processing_purpose,
        data_category=body.data_category,
        retention_until=body.retention_until,
        consent_reference=body.consent_reference,
        work_title=body.work_title,
        polygon_tx=poly_tx,
        polygon_url=poly_url,
        polygon_status="pending",
        ots_status="pending",
        chain=body.chain,
    )
    db.add(stamp)
    await db.flush()

    if body.subject_tc:
        try:
            fp = tc_fingerprint(settings.subject_tc_hmac_secret, body.subject_tc)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        db.add(
            StampSubject(
                stamp_id=stamp.id,
                tc_fingerprint=fp,
                organization_id=user.organization_id,
            )
        )
        await db.flush()

    await db.refresh(stamp)
    background_tasks.add_task(
        dispatch_stamp_created_background,
        user.id,
        stamp.id,
    )
    return stamp


@router.get("/", response_model=StampListResponse)
async def list_stamps(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StampListResponse:
    count_r = await db.execute(
        select(func.count(Stamp.id)).where(Stamp.user_id == user.id)
    )
    total = int(count_r.scalar_one())

    offset = (page - 1) * per_page
    r = await db.execute(
        select(Stamp)
        .where(Stamp.user_id == user.id)
        .order_by(Stamp.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    items = list(r.scalars().all())
    return StampListResponse(total=total, page=page, per_page=per_page, items=items)


@router.get("/{stamp_id}", response_model=StampResponse)
async def get_stamp(
    stamp_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Stamp:
    r = await db.execute(
        select(Stamp).where(Stamp.id == stamp_id, Stamp.user_id == user.id)
    )
    stamp = r.scalar_one_or_none()
    if stamp is None:
        raise HTTPException(status_code=404, detail="Damga bulunamadı")
    return stamp
