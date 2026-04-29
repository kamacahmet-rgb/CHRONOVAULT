from __future__ import annotations

import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.limiter import limiter
from app.models.user import User
from app.models.webhook import Webhook
from app.routers.auth import get_current_user
from app.schemas.webhook import WebhookCreateRequest, WebhookCreatedResponse, WebhookResponse

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/", response_model=WebhookCreatedResponse, status_code=201)
@limiter.limit("30/minute")
async def create_webhook(
    request: Request,
    body: WebhookCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WebhookCreatedResponse:
    secret = secrets.token_urlsafe(48)[:99]
    row = Webhook(
        user_id=user.id,
        name=body.name,
        url=str(body.url).rstrip("/"),
        secret=secret,
        events=list(body.events),
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    base = WebhookResponse.model_validate(row)
    return WebhookCreatedResponse(**base.model_dump(), secret=secret)


@router.get("/", response_model=list[WebhookResponse])
async def list_webhooks(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Webhook]:
    r = await db.execute(
        select(Webhook)
        .where(Webhook.user_id == user.id)
        .order_by(Webhook.created_at.desc())
    )
    return list(r.scalars().all())


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    res = await db.execute(
        delete(Webhook).where(
            Webhook.id == webhook_id,
            Webhook.user_id == user.id,
        )
    )
    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="Webhook bulunamadı")
    return Response(status_code=204)
