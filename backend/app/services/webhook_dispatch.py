"""Webhook tetikleme — HMAC-SHA256 gövde imzası."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session_factory
from app.models.stamp import Stamp
from app.models.webhook import Webhook

logger = logging.getLogger(__name__)


def _sign_body(body_bytes: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()


async def dispatch_stamp_created(
    db: AsyncSession,
    user_id: uuid.UUID,
    stamp: Stamp,
) -> None:
    """Aynı oturumda webhooks satırlarını günceller; çağıran commit eder."""
    payload = {
        "event": "stamp.created",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "stamp": {
            "id": str(stamp.id),
            "file_name": stamp.file_name,
            "file_hash": stamp.file_hash,
            "file_size": stamp.file_size,
            "polygon_status": stamp.polygon_status,
            "ots_status": stamp.ots_status,
            "chain": stamp.chain,
        },
    }
    body_bytes = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")

    r = await db.execute(
        select(Webhook).where(
            Webhook.user_id == user_id,
            Webhook.is_active.is_(True),
        )
    )
    hooks = list(r.scalars().all())
    if not hooks:
        return

    async with httpx.AsyncClient(timeout=8.0) as client:
        for h in hooks:
            evs = h.events or []
            if "stamp.created" not in evs:
                continue
            sig = _sign_body(body_bytes, h.secret)
            h.total_deliveries += 1
            h.last_triggered_at = datetime.now(timezone.utc)
            try:
                resp = await client.post(
                    h.url,
                    content=body_bytes,
                    headers={
                        "Content-Type": "application/json; charset=utf-8",
                        "X-TurkDamga-Event": "stamp.created",
                        "X-TurkDamga-Signature": "sha256=" + sig,
                    },
                )
                if resp.status_code >= 400:
                    h.failed_deliveries += 1
            except Exception:
                h.failed_deliveries += 1


async def dispatch_stamp_created_background(
    user_id: uuid.UUID,
    stamp_id: uuid.UUID,
) -> None:
    """
    Damga HTTP cevabından sonra çalışır: ayrı oturum + commit.
    İstek süresini bloklamaz (FastAPI BackgroundTasks).
    """
    factory = get_session_factory()
    if factory is None:
        return
    async with factory() as session:
        try:
            stamp = await session.get(Stamp, stamp_id)
            if stamp is None:
                return
            await dispatch_stamp_created(session, user_id, stamp)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception(
                "Webhook stamp.created arka plan hatası user_id=%s stamp_id=%s",
                user_id,
                stamp_id,
            )
