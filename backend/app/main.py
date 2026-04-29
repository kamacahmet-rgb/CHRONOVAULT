from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.database import check_database
from app.limiter import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def create_app() -> FastAPI:
    # ORM mapper kaydı (metadata)
    import app.models.api_key  # noqa: F401
    import app.models.stamp  # noqa: F401
    import app.models.stamp_subject  # noqa: F401
    import app.models.user  # noqa: F401
    import app.models.webhook  # noqa: F401

    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    async def _health_payload() -> dict:
        db = await check_database()
        return {
            "status": "ok",
            "service": settings.app_name,
            "version": settings.app_version,
            "db": db,
        }

    @app.get("/health", tags=["health"])
    async def health_root():
        return await _health_payload()

    @app.get("/api/v1/health", tags=["health"])
    async def health_api():
        return await _health_payload()

    @app.get("/", tags=["root"])
    async def root():
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": "/health",
            "api": "/api/v1",
        }

    from app.routers import admin_stamps as admin_stamps_r
    from app.routers import auth as auth_r
    from app.routers import search as search_r
    from app.routers import stamps as stamps_r
    from app.routers import verify as verify_r
    from app.routers import webhooks as webhooks_r

    app.include_router(auth_r.router, prefix="/api/v1")
    app.include_router(stamps_r.router, prefix="/api/v1")
    app.include_router(verify_r.router, prefix="/api/v1")
    app.include_router(search_r.router, prefix="/api/v1")
    app.include_router(admin_stamps_r.router, prefix="/api/v1")
    app.include_router(webhooks_r.router, prefix="/api/v1")

    return app


app = create_app()
