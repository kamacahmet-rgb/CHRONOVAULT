from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import SALE_CREDIT_MULTIPLIER, get_settings
from app.database import get_db
from app.models.api_key import APIKey
from app.models.user import User
from app.schemas.auth import (
    APIKeyCreateRequest,
    APIKeyCreatedResponse,
    APIKeyResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


def user_to_response(user: User) -> UserResponse:
    s = get_settings()
    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        plan=user.plan,
        created_at=user.created_at,
        monthly_quota=user.monthly_quota,
        used_this_month=user.used_this_month,
        credit_balance=user.credit_balance,
        stamp_credit_cost=s.stamp_credit_cost(),
        polygon_gas_cost_cents_estimate=int(s.polygon_gas_cost_cents_estimate),
        sale_credit_multiplier=int(SALE_CREDIT_MULTIPLIER),
    )


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def create_access_token(subject: uuid.UUID) -> str:
    s = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=s.access_token_expire_minutes)
    return jwt.encode(
        {
            "sub": str(subject),
            "exp": int(expire.timestamp()),
            "type": "access",
        },
        s.secret_key,
        algorithm=s.algorithm,
    )


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def get_current_user(
    cred: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if cred is None or cred.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Kimlik doğrulama gerekli")
    token = cred.credentials.strip()
    s = get_settings()

    if token.startswith("cv_live_"):
        key_hash = hashlib.sha256(token.encode()).hexdigest()
        r = await db.execute(
            select(APIKey).where(
                APIKey.key_hash == key_hash,
                APIKey.is_active.is_(True),
            )
        )
        api_key = r.scalar_one_or_none()
        if api_key is None:
            raise HTTPException(status_code=401, detail="Geçersiz API anahtarı")
        if api_key.expires_at is not None:
            exp = api_key.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < _now_utc():
                raise HTTPException(status_code=401, detail="API anahtarı süresi dolmuş")
        api_key.last_used_at = _now_utc()
        user = await db.get(User, api_key.user_id)
    else:
        try:
            payload = jwt.decode(token, s.secret_key, algorithms=[s.algorithm])
            if payload.get("type") not in (None, "access"):
                raise HTTPException(status_code=401, detail="Geçersiz token türü")
            sub = payload.get("sub")
            if not sub:
                raise HTTPException(status_code=401, detail="Geçersiz token")
            uid = uuid.UUID(str(sub))
        except (JWTError, ValueError, TypeError):
            raise HTTPException(status_code=401, detail="Geçersiz token")
        user = await db.get(User, uid)

    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı")
    return user


@router.post("/register", response_model=UserResponse)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> UserResponse:
    dup_e = await db.execute(select(User).where(User.email == body.email))
    if dup_e.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Bu e-posta zaten kayıtlı")
    dup_u = await db.execute(select(User).where(User.username == body.username))
    if dup_u.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Bu kullanıcı adı alınmış")

    s = get_settings()
    user = User(
        email=body.email,
        username=body.username,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        credit_balance=s.signup_bonus_credits,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user_to_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    r = await db.execute(
        select(User).where(
            or_(User.username == body.username, User.email == body.username)
        )
    )
    user = r.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Kullanıcı adı / e-posta veya parola hatalı")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Hesap devre dışı")
    token = create_access_token(user.id)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)) -> UserResponse:
    return user_to_response(user)


@router.post("/api-keys", response_model=APIKeyCreatedResponse, status_code=201)
async def create_api_key(
    body: APIKeyCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIKeyCreatedResponse:
    raw_key, prefix = APIKey.generate()
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    row = APIKey(
        user_id=user.id,
        name=body.name,
        key_hash=key_hash,
        key_prefix=prefix,
        expires_at=body.expires_at,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    base = APIKeyResponse.model_validate(row)
    return APIKeyCreatedResponse(**base.model_dump(), raw_key=raw_key)


@router.get("/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[APIKey]:
    r = await db.execute(
        select(APIKey)
        .where(APIKey.user_id == user.id)
        .order_by(APIKey.created_at.desc())
    )
    return list(r.scalars().all())


@router.delete("/api-keys/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    r = await db.execute(
        select(APIKey).where(APIKey.id == key_id, APIKey.user_id == user.id)
    )
    key = r.scalar_one_or_none()
    if key is None:
        raise HTTPException(status_code=404, detail="API anahtarı bulunamadı")
    key.is_active = False
    return Response(status_code=204)
