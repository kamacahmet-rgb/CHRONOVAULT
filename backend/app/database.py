from __future__ import annotations

from typing import AsyncGenerator, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def _init_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        return
    raw = get_settings().database_url
    if not raw or not str(raw).strip():
        return
    url = str(raw).strip()
    _engine = create_async_engine(url, pool_pre_ping=True)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


def _pair() -> Optional[Tuple[AsyncEngine, async_sessionmaker[AsyncSession]]]:
    _init_engine()
    if _engine is None or _session_factory is None:
        return None
    return _engine, _session_factory


def get_session_factory() -> Optional[async_sessionmaker[AsyncSession]]:
    """Arka plan görevleri için; DATABASE_URL yoksa None."""
    pair = _pair()
    if pair is None:
        return None
    return pair[1]


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    pair = _pair()
    if pair is None:
        raise HTTPException(
            status_code=503,
            detail="DATABASE_URL yapılandırılmadı; API veritabanı gerektirir.",
        )
    _, factory = pair
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def check_database() -> str:
    pair = _pair()
    if pair is None:
        return "skipped"
    engine, _ = pair
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "error"
