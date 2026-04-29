# TurkDamga Backend — FastAPI + PostgreSQL

Arama, TC ile kişi kapsamı ve arşiv: `docs/Arama-ve-TC-Erisim-Mimarisi.md`, `docs/Arsiv-Mimari.md`.  
Toptan satış, kredi ve kontrat: `docs/Toptan-Satis-Kredi-Kontrat.md`.  
Sektör dikeyleri ve KVKK: `docs/KVKK-Vertical-Damgalama.md`.  
Medya / belge dışı sertifika: `docs/Medya-Damga-Sertifikasi.md`.

**İş modeli (özet):** Damgalama zincir üzerindeki maliyet, operasyon olarak **Polygon üzerinde MATIC (gas)** ile karşılanır; müşteriye satılan ürün **damga kredisi** (ve/veya kontratlı toptan kredi) şeklindedir — kredi tüketimi ile gas harcaması `CreditLedger` + treasury politikası ile bağlanır. Ayrıntı: `docs/Toptan-Satis-Kredi-Kontrat.md` §0.

## Proje Yapısı

```
turkdamga-api/
├── .env
├── requirements.txt
├── alembic.ini              # Repo kökü: backend/alembic.ini
├── alembic/
│   ├── env.py               # DATABASE_URL → sync driver (migrasyon)
│   ├── script.py.mako
│   └── versions/
│       ├── 20260423_01_stamp_subjects_identity_search.py
│       ├── 20260424_02_wholesale_b2b.py
│       ├── 20260425_03_stamp_vertical_kvkk.py
│       ├── 20260426_04_stamp_idempotency_credits.py
│       └── 20260427_05_stamp_work_title.py
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── stamp.py
│   │   ├── stamp_subject.py   # TC parmak izi ↔ damga (KVKK: ham TC saklanmaz)
│   │   ├── wholesale.py       # Toptan kontrat + kredi defteri + org bakiyesi
│   │   └── webhook.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── stamp.py
│   │   ├── search.py          # Birleşik arama + admin TC sorgusu şemaları
│   │   ├── b2b.py             # B2B kontrat / kredi yükleme şemaları
│   │   └── webhook.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── stamps.py
│   │   ├── search.py          # Filtreli / metin araması
│   │   ├── admin_stamps.py    # Kurumsal: TC → damga listesi (yetkili rol)
│   │   ├── b2b.py             # Toptan kontrat + kredi tahsisi (superadmin)
│   │   ├── verify.py
│   │   └── webhooks.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── polygon.py
│   │   ├── opentimestamps.py
│   │   ├── subject_fingerprint.py  # HMAC(TC) türetimi
│   │   └── webhook_dispatcher.py
│   └── middleware/
│       ├── __init__.py
│       └── rate_limit.py
```

---

## requirements.txt

```txt
fastapi==0.111.0
uvicorn[standard]==0.29.0
sqlalchemy==2.0.30
asyncpg==0.29.0
alembic==1.13.1
psycopg2-binary==2.9.9
pydantic[email]==2.7.1
pydantic-settings==2.2.1
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.9
httpx==0.27.0
web3==6.18.0
opentimestamps==0.4.2
redis==5.0.4
slowapi==0.1.9
celery==5.4.0
python-dotenv==1.0.1
alembic==1.13.1
```

---

## .env

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/turkdamga

# JWT
SECRET_KEY=supersecretkey_change_in_production_min32chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=30

# Blockchain
POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY
POLYGON_PRIVATE_KEY=0xYOUR_PRIVATE_KEY
POLYGON_CHAIN_ID=137

# OpenTimestamps
OTS_CALENDAR_URL=https://alice.btc.calendar.opentimestamps.org

# Redis (rate limiting + celery)
REDIS_URL=redis://localhost:6379/0

# Kurumsal kredi: tek damgalama için düşülecek birim (OrganizationCreditBalance)
STAMP_CREDIT_COST=1

# App
APP_NAME=TurkDamga
APP_VERSION=1.0.0
DEBUG=false
ALLOWED_ORIGINS=http://localhost:3000,https://yourapp.com

# Kişi (TC) parmak izi — ham TC veritabanına yazılmaz; üretimde güçlü rastgele değer
SUBJECT_TC_HMAC_SECRET=degistir_en_az_32_karakter_rastgele
```

---

## app/config.py

```python
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    polygon_rpc_url: str
    polygon_private_key: str
    polygon_chain_id: int = 137

    ots_calendar_url: str = "https://alice.btc.calendar.opentimestamps.org"

    redis_url: str = "redis://localhost:6379/0"

    app_name: str = "TurkDamga"
    app_version: str = "1.0.0"
    debug: bool = False
    allowed_origins: str = "http://localhost:3000"

    # KVKK: TC ile eşleştirme için HMAC anahtarı (ham TC saklanmaz)
    subject_tc_hmac_secret: str

    # Kurumsal damgalama: org bakiyesinden düşülecek kredi (≥1)
    stamp_credit_cost: int = 1

    class Config:
        env_file = ".env"

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

---

## app/database.py

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

---

## app/models/user.py

```python
import uuid
import secrets
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str]    = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200))

    is_active: Mapped[bool]  = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Plan: free | pro | enterprise
    plan: Mapped[str] = mapped_column(String(20), default="free")
    monthly_quota: Mapped[int] = mapped_column(Integer, default=100)
    used_this_month: Mapped[int] = mapped_column(Integer, default=0)

    # Rol: user | org_admin | superadmin (kurumsal TC sorgusu için org_admin+)
    role: Mapped[str] = mapped_column(String(20), default="user", index=True)
    # Çok kiracılı kurumsal model; org_admin yalnızca kendi organization_id kapsamını sorgular
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    # KYC sonrası: kullanıcıya ait TC’nin HMAC parmak izi (ham TC tutulmaz)
    subject_tc_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    subject_binding_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    api_keys: Mapped[list["APIKey"]] = relationship("APIKey", back_populates="user", cascade="all, delete")
    stamps:   Mapped[list["Stamp"]]  = relationship("Stamp",  back_populates="user", cascade="all, delete")
    webhooks: Mapped[list["Webhook"]] = relationship("Webhook", back_populates="user", cascade="all, delete")


class APIKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    name: Mapped[str]       = mapped_column(String(100), nullable=False)
    key_hash: Mapped[str]   = mapped_column(String(255), unique=True, nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False)  # "cv_live_xxxx" gösterim için

    is_active: Mapped[bool]       = mapped_column(Boolean, default=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None]   = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="api_keys")

    @staticmethod
    def generate() -> tuple[str, str]:
        """(raw_key, prefix) döndürür. raw_key bir kez gösterilir."""
        raw = "cv_live_" + secrets.token_urlsafe(32)
        prefix = raw[:12]
        return raw, prefix
```

---

## app/models/stamp.py

```python
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, BigInteger, Text, JSON, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

class Stamp(Base):
    __tablename__ = "stamps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    # Dosya bilgileri
    file_name: Mapped[str]       = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str]       = mapped_column(String(64), nullable=False, index=True)
    file_size: Mapped[int]       = mapped_column(BigInteger, default=0)
    file_type: Mapped[str | None] = mapped_column(String(100))

    # Metadata
    author:      Mapped[str | None] = mapped_column(String(200))
    project:     Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    tags:        Mapped[dict | None] = mapped_column(JSON, default=list)

    # KVKK / sektör dikeyi (docs/KVKK-Vertical-Damgalama.md)
    vertical: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    # music | architecture | visual | health_archive | municipal_license | other
    processing_purpose: Mapped[str | None] = mapped_column(String(120), nullable=True)
    data_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # general | personal | special_health
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Medya / eser sertifikasında gösterim (docs/Medya-Damga-Sertifikasi.md)
    work_title: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # Polygon
    polygon_tx:   Mapped[str | None] = mapped_column(String(66))
    polygon_url:  Mapped[str | None] = mapped_column(String(200))
    polygon_block: Mapped[int | None] = mapped_column(BigInteger)
    polygon_status: Mapped[str] = mapped_column(String(20), default="pending")
    # pending | confirmed | failed

    # Bitcoin / OTS
    ots_file_data: Mapped[str | None] = mapped_column(Text)  # base64 .ots dosyası
    ots_status: Mapped[str] = mapped_column(String(20), default="pending")
    # pending | submitted | confirmed
    ots_bitcoin_block: Mapped[int | None] = mapped_column(BigInteger)
    ots_confirmed_at:  Mapped[datetime | None] = mapped_column(DateTime)

    # Zincir seçimi
    chain: Mapped[str] = mapped_column(String(20), default="both")
    # both | polygon | bitcoin

    # Idempotency + kurumsal kredi (Damgalama akışı bölümü)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    credits_charged: Mapped[int] = mapped_column(Integer, default=0)  # bu damga için düşülen org kredi birimi (0 = yalnızca aylık kota)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="stamps")
    subjects: Mapped[list["StampSubject"]] = relationship(
        "StampSubject", back_populates="stamp", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_stamps_hash_user", "file_hash", "user_id"),
    )

# Tam metin araması için Alembic ile eklenebilir:
#   ALTER TABLE stamps ADD COLUMN search_vector tsvector
#     GENERATED ALWAYS AS (to_tsvector('turkish', coalesce(description,'') || ' ' || coalesce(file_name,''))) STORED;
#   CREATE INDEX ix_stamps_search_vector ON stamps USING GIN (search_vector);
```

---

## app/models/stamp_subject.py

```python
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class StampSubject(Base):
    """Damga ↔ gerçek kişi bağlantısı: yalnızca HMAC(TC) parmak izi; ham TC yok."""

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
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    stamp: Mapped["Stamp"] = relationship("Stamp", back_populates="subjects")

    __table_args__ = (
        Index("ix_stamp_subject_fp_org", "tc_fingerprint", "organization_id"),
    )
```

---

## app/models/webhook.py

```python
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, JSON, ForeignKey, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

class Webhook(Base):
    __tablename__ = "webhooks"

    id: Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    name: Mapped[str]    = mapped_column(String(100), nullable=False)
    url: Mapped[str]     = mapped_column(String(500), nullable=False)
    secret: Mapped[str]  = mapped_column(String(100), nullable=False)  # HMAC imzalama için
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Hangi eventlerde tetiklensin
    # ["stamp.polygon.confirmed", "stamp.bitcoin.confirmed", "stamp.created", "stamp.failed"]
    events: Mapped[list] = mapped_column(JSON, default=list)

    # İstatistikler
    total_deliveries:  Mapped[int] = mapped_column(Integer, default=0)
    failed_deliveries: Mapped[int] = mapped_column(Integer, default=0)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="webhooks")
    deliveries: Mapped[list["WebhookDelivery"]] = relationship("WebhookDelivery", back_populates="webhook", cascade="all, delete")


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[uuid.UUID]         = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    webhook_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("webhooks.id", ondelete="CASCADE"), index=True)
    stamp_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    event:          Mapped[str]       = mapped_column(String(100))
    payload:        Mapped[dict]      = mapped_column(JSON)
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_body:  Mapped[str | None]  = mapped_column(Text)
    success:        Mapped[bool]        = mapped_column(Boolean, default=False)
    attempt:        Mapped[int]         = mapped_column(Integer, default=1)
    delivered_at:   Mapped[datetime]    = mapped_column(DateTime, default=datetime.utcnow)

    webhook: Mapped["Webhook"] = relationship("Webhook", back_populates="deliveries")
```

---

## app/schemas/auth.py

```python
from pydantic import BaseModel, EmailStr, Field
from uuid import UUID
from datetime import datetime

class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8)
    full_name: str | None = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class RefreshRequest(BaseModel):
    refresh_token: str

class UserResponse(BaseModel):
    id: UUID
    email: str
    username: str
    full_name: str | None
    plan: str
    monthly_quota: int
    used_this_month: int
    created_at: datetime
    role: str | None = None
    organization_id: UUID | None = None

    model_config = {"from_attributes": True}

class APIKeyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    expires_at: datetime | None = None

class APIKeyResponse(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    expires_at: datetime | None

    model_config = {"from_attributes": True}

class APIKeyCreatedResponse(APIKeyResponse):
    raw_key: str  # Sadece bir kez gösterilir!
```

---

## app/schemas/stamp.py

```python
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Literal

class StampRequest(BaseModel):
    file_hash: str = Field(min_length=64, max_length=64, pattern="^[a-f0-9]{64}$")
    file_name: str = Field(max_length=500)
    file_size: int = Field(ge=0, default=0)
    file_type: str | None = None
    author:      str | None = Field(default=None, max_length=200)
    project:     str | None = Field(default=None, max_length=200)
    description: str | None = None
    tags: list[str] = []
    chain: Literal["both", "polygon", "bitcoin"] = "both"
    # Opsiyonel: damganın bağlandığı kişi (KVKK — ayrıntı docs/Arama-ve-TC-Erisim-Mimarisi.md)
    subject_tc: str | None = Field(
        default=None,
        min_length=11,
        max_length=11,
        pattern="^[0-9]{11}$",
        description="Ham değer DB'ye yazılmaz; sunucu HMAC parmak izi üretir.",
    )
    vertical: Literal[
        "music",
        "architecture",
        "visual",
        "health_archive",
        "municipal_license",
        "other",
    ] | None = None
    processing_purpose: str | None = Field(default=None, max_length=120)
    data_category: Literal["general", "personal", "special_health"] | None = None
    retention_until: datetime | None = None
    consent_reference: str | None = Field(default=None, max_length=120)
    work_title: str | None = Field(
        default=None,
        max_length=300,
        description="Parça / yayın / ürün adı — müzik, video vb. sertifikada (KVKK: kişisel veri riski).",
    )

class StampResponse(BaseModel):
    id: UUID
    file_name: str
    file_hash: str
    file_size: int
    author: str | None
    project: str | None
    polygon_tx: str | None
    polygon_url: str | None
    polygon_status: str
    ots_status: str
    ots_bitcoin_block: int | None
    chain: str
    created_at: datetime
    vertical: str | None = None
    processing_purpose: str | None = None
    data_category: str | None = None
    retention_until: datetime | None = None
    consent_reference: str | None = None
    work_title: str | None = None

    model_config = {"from_attributes": True}

class StampListResponse(BaseModel):
    total: int
    page: int
    per_page: int
    items: list[StampResponse]

class VerifyResponse(BaseModel):
    found: bool
    stamp: StampResponse | None = None
    message: str
```

---

## app/schemas/search.py

```python
from typing import Literal
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime


class StampSearchParams(BaseModel):
    """GET /search/stamps sorgu parametreleri (query string)."""

    q: str | None = Field(default=None, max_length=500, description="file_name / description / author / project ILIKE")
    file_hash: str | None = Field(default=None, min_length=64, max_length=64)
    from_date: datetime | None = None
    to_date: datetime | None = None
    polygon_status: str | None = None
    ots_status: str | None = None
    chain: str | None = None
    tag: str | None = Field(default=None, max_length=100)
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    # self: oturum kullanıcısının damgaları | by_verified_subject: KYC parmak izisiyle eşleşen kayıtlar
    scope: Literal["self", "by_verified_subject"] = "self"


class AdminSubjectLookupRequest(BaseModel):
    """Kurumsal admin: TC ile aynı organization_id kapsamındaki tüm damgalar."""

    tc: str = Field(min_length=11, max_length=11, pattern="^[0-9]{11}$")


class StampSummary(BaseModel):
    id: UUID
    file_name: str
    file_hash: str
    file_size: int
    polygon_status: str
    ots_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StampSearchResponse(BaseModel):
    total: int
    page: int
    per_page: int
    items: list[StampSummary]
```

---

## app/schemas/webhook.py

```python
from pydantic import BaseModel, HttpUrl, Field
from uuid import UUID
from datetime import datetime
from typing import Literal

WEBHOOK_EVENTS = Literal[
    "stamp.created",
    "stamp.polygon.confirmed",
    "stamp.bitcoin.confirmed",
    "stamp.failed",
]

class WebhookCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: HttpUrl
    events: list[WEBHOOK_EVENTS]

class WebhookResponse(BaseModel):
    id: UUID
    name: str
    url: str
    events: list[str]
    is_active: bool
    total_deliveries: int
    failed_deliveries: int
    last_triggered_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}

class WebhookCreatedResponse(WebhookResponse):
    secret: str  # Sadece oluşturulunca gösterilir (HMAC doğrulama için)
```

---

## app/routers/auth.py

```python
import hashlib
import secrets
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.database import get_db
from app.config import get_settings
from app.models.user import User, APIKey
from app.schemas.auth import (
    RegisterRequest, LoginRequest, TokenResponse,
    RefreshRequest, UserResponse,
    APIKeyCreateRequest, APIKeyResponse, APIKeyCreatedResponse,
)

router   = APIRouter(prefix="/auth", tags=["Auth"])
settings = get_settings()
pwd_ctx  = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer   = HTTPBearer(auto_error=False)


# ── JWT helpers ────────────────────────────────────────────────
def create_token(data: dict, expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + expires_delta
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


# ── Auth dependency ────────────────────────────────────────────
async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    exc = HTTPException(status_code=401, detail="Geçersiz ya da süresi dolmuş token")
    if not creds:
        raise exc
    token = creds.credentials

    # JWT mi, API key mi?
    if token.startswith("cv_live_"):
        key_hash = hashlib.sha256(token.encode()).hexdigest()
        result = await db.execute(
            select(APIKey).where(APIKey.key_hash == key_hash, APIKey.is_active == True)
        )
        api_key = result.scalar_one_or_none()
        if not api_key:
            raise exc
        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            raise HTTPException(status_code=401, detail="API key süresi dolmuş")
        api_key.last_used_at = datetime.utcnow()
        user = await db.get(User, api_key.user_id)
    else:
        try:
            payload = decode_token(token)
            if payload.get("type") != "access":
                raise exc
            user_id = UUID(payload["sub"])
        except (JWTError, ValueError):
            raise exc
        user = await db.get(User, user_id)

    if not user or not user.is_active:
        raise exc
    return user


# ── Endpoints ──────────────────────────────────────────────────
@router.post("/register", response_model=UserResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Duplicate kontrol
    existing = await db.execute(
        select(User).where((User.email == body.email) | (User.username == body.username))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Bu email veya kullanıcı adı zaten kullanımda")

    user = User(
        email=body.email,
        username=body.username,
        hashed_password=pwd_ctx.hash(body.password),
        full_name=body.full_name,
    )
    db.add(user)
    await db.flush()
    return user


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not pwd_ctx.verify(body.password, user.hashed_password):
        raise HTTPException(401, "Email veya şifre hatalı")

    access_token = create_token(
        {"sub": str(user.id), "type": "access"},
        timedelta(minutes=settings.access_token_expire_minutes),
    )
    refresh_token = create_token(
        {"sub": str(user.id), "type": "refresh"},
        timedelta(days=settings.refresh_token_expire_days),
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError
        user_id = UUID(payload["sub"])
    except (JWTError, ValueError):
        raise HTTPException(401, "Geçersiz refresh token")

    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "Kullanıcı bulunamadı")

    access_token = create_token(
        {"sub": str(user.id), "type": "access"},
        timedelta(minutes=settings.access_token_expire_minutes),
    )
    refresh_token_new = create_token(
        {"sub": str(user.id), "type": "refresh"},
        timedelta(days=settings.refresh_token_expire_days),
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_new,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user


# ── API Keys ───────────────────────────────────────────────────
@router.post("/api-keys", response_model=APIKeyCreatedResponse, status_code=201)
async def create_api_key(
    body: APIKeyCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    raw_key, prefix = APIKey.generate()
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    api_key = APIKey(
        user_id=user.id,
        name=body.name,
        key_hash=key_hash,
        key_prefix=prefix,
        expires_at=body.expires_at,
    )
    db.add(api_key)
    await db.flush()

    response = APIKeyCreatedResponse.model_validate(api_key)
    response.raw_key = raw_key  # Sadece bir kez!
    return response


@router.get("/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(APIKey).where(APIKey.user_id == user.id).order_by(APIKey.created_at.desc())
    )
    return result.scalars().all()


@router.delete("/api-keys/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(APIKey).where(APIKey.id == key_id, APIKey.user_id == user.id)
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(404, "API key bulunamadı")
    key.is_active = False
```

---

## app/services/polygon.py

```python
import asyncio
from web3 import AsyncWeb3
from web3.middleware import async_geth_poa_middleware
from eth_account import Account
from app.config import get_settings
import json

settings = get_settings()

_w3: AsyncWeb3 | None = None

def get_web3() -> AsyncWeb3:
    global _w3
    if _w3 is None:
        _w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(settings.polygon_rpc_url))
        _w3.middleware_onion.inject(async_geth_poa_middleware, layer=0)
    return _w3

async def stamp_on_polygon(file_hash: str, metadata: dict) -> dict:
    w3 = get_web3()
    account = Account.from_key(settings.polygon_private_key)

    payload = json.dumps({
        "app": "TurkDamga",
        "hash": file_hash,
        **{k: v for k, v in metadata.items() if v},
    }, ensure_ascii=False)

    nonce = await w3.eth.get_transaction_count(account.address)
    gas_price = await w3.eth.gas_price

    tx = {
        "from":     account.address,
        "to":       account.address,
        "value":    0,
        "data":     w3.to_hex(text=payload),
        "gas":      60000,
        "gasPrice": int(gas_price * 1.1),  # %10 buffer
        "nonce":    nonce,
        "chainId":  settings.polygon_chain_id,
    }

    signed    = w3.eth.account.sign_transaction(tx, account.key)
    tx_hash   = await w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt   = await w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

    if receipt.status != 1:
        raise Exception(f"Polygon TX başarısız: {tx_hash.hex()}")

    return {
        "tx_hash":      tx_hash.hex(),
        "block_number": receipt.blockNumber,
        "explorer_url": f"https://polygonscan.com/tx/{tx_hash.hex()}",
    }
```

---

## app/services/opentimestamps.py

```python
import asyncio
import base64
import io
from opentimestamps.core.timestamp import Timestamp
from opentimestamps.core.op import OpSHA256
from opentimestamps.calendar import RemoteCalendar
from opentimestamps.core.serialize import StreamSerializationContext, StreamDeserializationContext
from app.config import get_settings

settings = get_settings()

async def submit_to_ots(file_hash_hex: str) -> str:
    """
    Hash'i OpenTimestamps'e gönderir.
    base64 encode edilmiş .ots dosyasını döndürür.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _submit_sync, file_hash_hex)

def _submit_sync(file_hash_hex: str) -> str:
    hash_bytes = bytes.fromhex(file_hash_hex)

    # Timestamp objesi oluştur
    ts = Timestamp(hash_bytes)

    # Calendar'a gönder
    calendar = RemoteCalendar(settings.ots_calendar_url)
    calendar_ts = calendar.submit(hash_bytes)
    ts.merge(calendar_ts)

    # .ots dosyasını serialize et
    ctx = StreamSerializationContext(io.BytesIO())
    ts.serialize(ctx)
    ots_bytes = ctx.fd.getvalue()

    return base64.b64encode(ots_bytes).decode()

async def verify_ots(ots_base64: str, file_hash_hex: str) -> dict:
    """OTS dosyasını Bitcoin'e karşı doğrular."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _verify_sync, ots_base64, file_hash_hex)

def _verify_sync(ots_base64: str, file_hash_hex: str) -> dict:
    try:
        ots_bytes  = base64.b64decode(ots_base64)
        hash_bytes = bytes.fromhex(file_hash_hex)
        ctx = StreamDeserializationContext(io.BytesIO(ots_bytes))
        ts  = Timestamp.deserialize(ctx, hash_bytes)

        # upgrade dene
        calendar = RemoteCalendar(settings.ots_calendar_url)
        ts.merge(calendar.get_timestamp(hash_bytes))

        # attestations kontrol
        for attestation in ts.all_attestations():
            if hasattr(attestation, 'height'):
                return {"confirmed": True, "bitcoin_block": attestation.height}

        return {"confirmed": False, "bitcoin_block": None}
    except Exception as e:
        return {"confirmed": False, "error": str(e)}
```

---

## app/services/webhook_dispatcher.py

```python
import hashlib
import hmac
import json
import asyncio
from datetime import datetime
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.webhook import Webhook, WebhookDelivery
from app.database import AsyncSessionLocal

async def dispatch_event(event: str, stamp_id: UUID, payload: dict):
    """Bir event'i ilgili tüm webhook'lara gönderir."""
    async with AsyncSessionLocal() as db:
        # Bu event'i dinleyen aktif webhook'ları bul
        result = await db.execute(
            select(Webhook).where(Webhook.is_active == True)
        )
        webhooks = result.scalars().all()
        active = [w for w in webhooks if event in (w.events or [])]

        tasks = [_deliver(db, w, event, stamp_id, payload) for w in active]
        await asyncio.gather(*tasks, return_exceptions=True)
        await db.commit()

async def _deliver(
    db: AsyncSession,
    webhook: Webhook,
    event: str,
    stamp_id: UUID,
    payload: dict,
    max_retries: int = 3,
):
    body = json.dumps({
        "event":     event,
        "stamp_id":  str(stamp_id),
        "timestamp": datetime.utcnow().isoformat(),
        "data":      payload,
    })

    # HMAC-SHA256 imzası
    signature = hmac.new(
        webhook.secret.encode(),
        body.encode(),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "Content-Type":          "application/json",
        "X-TurkDamga-Event":   event,
        "X-TurkDamga-Sig":     f"sha256={signature}",
        "X-TurkDamga-StampId": str(stamp_id),
    }

    success       = False
    response_status = None
    response_body   = None

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(str(webhook.url), content=body, headers=headers)
                response_status = resp.status_code
                response_body   = resp.text[:500]
                success = 200 <= resp.status_code < 300
                if success:
                    break
        except Exception as e:
            response_body = str(e)

        if not success and attempt < max_retries:
            await asyncio.sleep(2 ** attempt)  # exponential backoff

    # Delivery kaydı
    delivery = WebhookDelivery(
        webhook_id=webhook.id,
        stamp_id=stamp_id,
        event=event,
        payload=json.loads(body),
        response_status=response_status,
        response_body=response_body,
        success=success,
        attempt=attempt,
    )
    db.add(delivery)

    webhook.total_deliveries += 1
    if not success:
        webhook.failed_deliveries += 1
    webhook.last_triggered_at = datetime.utcnow()
```

---

## app/services/subject_fingerprint.py

```python
import hashlib
import hmac


def normalize_tc(raw: str) -> str:
    s = raw.replace(" ", "").strip()
    return s


def tc_fingerprint(secret: str, tc: str) -> str:
    """
    Ham TC yerine saklanacak sabit uzunluklu parmak izi (HMAC-SHA256 hex).
    secret: settings.subject_tc_hmac_secret — üretimde KMS/HSM ile yönetilmesi önerilir.
    """
    norm = normalize_tc(tc)
    if len(norm) != 11 or not norm.isdigit():
        raise ValueError("Geçersiz T.C. kimlik numarası formatı")
    return hmac.new(secret.encode("utf-8"), norm.encode("utf-8"), hashlib.sha256).hexdigest()
```

---

## app/middleware/rate_limit.py

```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from app.config import get_settings

settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url,
)

def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": f"Çok fazla istek. Limit: {exc.limit}",
            "retry_after": exc.limit.reset_time,
        },
        headers={"Retry-After": str(exc.limit.reset_time)},
    )
```

---

## Damgalama akışı: kurumsal kredi ve Polygon TX sırası

Bu bölüm `POST /stamps` ile **`stamp_on_polygon`** (ve isteğe bağlı OTS) arasında **kredi düşümü**, **commit sırası** ve **zincir hatasında telafi**yi tanımlar. İş modeli özeti: `docs/Toptan-Satis-Kredi-Kontrat.md` §0.

### Hedefler

- **Çift tüketim yok:** Aynı istek tekrarlandığında yalnızca tek `stamp_consume` ledger satırı.
- **Tutarlılık:** Kredi, müşteri bakiyesinden düşmeden önce veya sonra gas hatası yüzünden “sessizce” kaybolmamalı; zincir başarısızsa **telafi** (iade) veya açıkça tanımlı “kredi yanar, yeniden dene” politikası seçilmeli (varsayılan: telafi).
- **Gas:** Polygon MATIC harcaması treasury cüzdanından; müşteri yalnızca **damga kredisi** görür.

### Aşama 1 — İstek içi (tercihen tek DB transaction, commit önce)

1. Mevcut doğrulamalar: kimlik (`get_current_user`), KVKK / `consent_reference`, aynı `file_hash` için çakışma (`409`), kota (`monthly_quota` vb.).
2. **Kurumsal kredi** (`user.organization_id` dolu ve org kredi modeli aktifse):
   - İstemci **`Idempotency-Key`** göndermelidir (ledger satırı `consume:{header}` ile eşlenir; aşağıdaki taslakta zorunlu).
   - `SELECT ... FROM organization_credit_balances WHERE organization_id = ? FOR UPDATE` (veya eşdeğer satır kilidi).
   - `STAMP_CREDIT_COST` (config, örn. `settings.stamp_credit_cost`, varsayılan `1`) ile `balance >= cost` kontrolü. Değilse **`402 Payment Required`** ve örnek gövde: `{"error":"insufficient_credits","balance":N,"required":cost}` (projede `403` de seçilebilir; tek tip seçin).
   - `CreditLedgerEntry`: `delta = -cost`, `reason = "stamp_consume"`, `balance_after`, `idempotency_key` = `consume:` + header değeri (unique).
   - `OrganizationCreditBalance.balance` güncelle.
3. `Stamp` ekle: `polygon_status = "pending"`, OTS kullanılıyorsa `ots_status = "pending"`. İsteğe bağlı: `credit_ledger_entry_id` FK ile tüketim satırına geri bağla (denetim / rapor).
4. `user.used_this_month` (bireysel kota) veya org düzeyinde ek kota bu transaction içinde güncellenir.
5. **COMMIT** — Bu noktadan sonra kredi düşümü kalıcıdır; zincir/OTS arka planda başarısız olursa **Aşama 3**.

Bireysel planda sadece `monthly_quota` kullanılıyorsa org kredi adımları atlanır; ikisi birlikte tanımlıysa önce hangisinin düşeceği ürün kararıdır (ör. önce org kredisi, bitince aylık kota).

### Aşama 2 — Zincir (arka plan: `BackgroundTasks` / Celery)

`_process_stamp` (veya kuyruk worker):

1. `await stamp_on_polygon(file_hash, metadata)`.
2. **Başarılı:** `polygon_tx`, `polygon_url`, `polygon_block`, `polygon_status = "confirmed"`, commit; `dispatch_event("stamp.polygon.confirmed", ...)`.
3. **Başarısız** (RPC, revert, timeout, nonce): Commit sonrası **Aşama 3** (telafi) + `polygon_status = "failed"`; `dispatch_event("stamp.failed", ...)`.

OTS (`submit_to_ots`) aynı worker’da veya zincirden sonra çalışıyorsa:

- OTS ücretsiz / marj içi sayılıyorsa: sadece `ots_status` güncellenir, kredi iadesi yok.
- OTS ayrı “birim” tüketiyorsa: iş modelinde ayrı `reason` ve kısmi iade dokümante edilir.

### Aşama 3 — Telafi (zincir hatası sonrası kredi iadesi)

- Aynı `organization_id` için yeni `CreditLedgerEntry`: `delta = +cost`, `reason = "stamp_refund_polygon_failed"`, `balance_after` güncel, **`idempotency_key = "refund:" + str(stamp_id)`** (unique) ile worker çift çalışsa bile tek iade.
- `Stamp.polygon_status = "failed"`.
- İlgili `stamp_consume` satırına `stamp_id` ile raporlama (opsiyonel FK) hatayı izlemeyi kolaylaştırır.

### Idempotency (`POST /stamps`)

- İstemci **`Idempotency-Key`** (UUID önerilir) gönderir. Aynı anahtar + aynı gövde ile tekrar istek: mevcut `Stamp` ve HTTP `201` veya `200` ile aynı cevap dönülür; **ikinci `stamp_consume` yazılmaz** (önce `CreditLedgerEntry` / `Stamp` üzerinde bu anahtar aranır).

### HTTP özeti (öneri)

| Durum | Kod | `error` (örnek) |
|--------|-----|------------------|
| Kurumsal kredi yetersiz | `402` | `insufficient_credits` |
| Yinelenen hash (aynı kullanıcı) | `409` | (mevcut mesaj) |
| Aylık kota | `429` | (mevcut mesaj) |
| Idempotency çakışması (farklı body, aynı key) | `409` | `idempotency_conflict` |

### Uygulama notu

Aşağıdaki `app/routers/stamps.py` taslağı **Damgalama akışı** bölümündeki Aşama 1–3 ile hizalıdır (org kredisi + idempotency + Polygon hata iadesi). Alembic: `backend/alembic/versions/20260426_04_stamp_idempotency_credits.py` (`stamps.idempotency_key`, `stamps.credits_charged`, kısmi unique index).

---

## app/routers/stamps.py

```python
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.config import get_settings
from app.models.user import User
from app.models.stamp import Stamp
from app.models.stamp_subject import StampSubject
from app.models.wholesale import OrganizationCreditBalance, CreditLedgerEntry
from app.schemas.stamp import StampRequest, StampResponse, StampListResponse
from app.routers.auth import get_current_user
from app.services.subject_fingerprint import tc_fingerprint
from app.services.polygon import stamp_on_polygon
from app.services.opentimestamps import submit_to_ots
from app.services.webhook_dispatcher import dispatch_event
from app.middleware.rate_limit import limiter

router = APIRouter(prefix="/stamps", tags=["Stamps"])
settings = get_settings()


async def _consume_org_stamp_credit(
    db: AsyncSession,
    organization_id: UUID,
    cost: int,
    ledger_idempotency_key: str,
) -> int:
    """Kilitli bakiyeden kredi düşer; balance_after döner. ledger_idempotency_key unique olmalı."""
    dup = await db.execute(
        select(CreditLedgerEntry).where(CreditLedgerEntry.idempotency_key == ledger_idempotency_key)
    )
    if dup.scalar_one_or_none():
        raise HTTPException(409, "idempotency_conflict")

    r = await db.execute(
        select(OrganizationCreditBalance)
        .where(OrganizationCreditBalance.organization_id == organization_id)
        .with_for_update()
    )
    bal = r.scalar_one_or_none()
    if not bal:
        bal = OrganizationCreditBalance(organization_id=organization_id, balance=0)
        db.add(bal)
        await db.flush()

    if bal.balance < cost:
        raise HTTPException(
            status_code=402,
            detail={"error": "insufficient_credits", "balance": bal.balance, "required": cost},
        )

    new_bal = bal.balance - cost
    bal.balance = new_bal
    db.add(
        CreditLedgerEntry(
            organization_id=organization_id,
            delta=-cost,
            balance_after=new_bal,
            reason="stamp_consume",
            idempotency_key=ledger_idempotency_key,
        )
    )
    return new_bal


async def _refund_org_stamp_credit_polygon_failed(
    db: AsyncSession,
    organization_id: UUID,
    cost: int,
    stamp_id: UUID,
) -> None:
    """Polygon TX başarısızlığında tek seferlik iade (idempotent)."""
    if cost <= 0:
        return
    refund_key = f"refund:{stamp_id}"
    exists = await db.execute(
        select(CreditLedgerEntry).where(CreditLedgerEntry.idempotency_key == refund_key)
    )
    if exists.scalar_one_or_none():
        return

    r = await db.execute(
        select(OrganizationCreditBalance)
        .where(OrganizationCreditBalance.organization_id == organization_id)
        .with_for_update()
    )
    bal = r.scalar_one_or_none()
    if not bal:
        bal = OrganizationCreditBalance(organization_id=organization_id, balance=0)
        db.add(bal)
        await db.flush()

    new_bal = bal.balance + cost
    bal.balance = new_bal
    db.add(
        CreditLedgerEntry(
            organization_id=organization_id,
            delta=cost,
            balance_after=new_bal,
            reason="stamp_refund_polygon_failed",
            idempotency_key=refund_key,
        )
    )


async def _process_stamp(stamp_id: UUID, chain: str):
    """Background task: Polygon (+ isteğe bağlı OTS). Polygon hata → org kredisi iadesi."""
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        stamp = await db.get(Stamp, stamp_id)
        if not stamp:
            return

        user = await db.get(User, stamp.user_id)
        org_id = user.organization_id if user else None
        cost = stamp.credits_charged or 0

        metadata = {
            "file_name": stamp.file_name,
            "author": stamp.author,
            "project": stamp.project,
            "stamp_id": str(stamp.id),
        }

        if chain in ("both", "polygon"):
            try:
                result = await stamp_on_polygon(stamp.file_hash, metadata)
                stamp.polygon_tx = result["tx_hash"]
                stamp.polygon_url = result["explorer_url"]
                stamp.polygon_block = result["block_number"]
                stamp.polygon_status = "confirmed"
                await db.commit()

                await dispatch_event(
                    "stamp.polygon.confirmed",
                    stamp.id,
                    {"file_hash": stamp.file_hash, "polygon_tx": stamp.polygon_tx, "polygon_url": stamp.polygon_url},
                )
            except Exception as e:
                stamp.polygon_status = "failed"
                if org_id and cost > 0:
                    await _refund_org_stamp_credit_polygon_failed(db, org_id, cost, stamp.id)
                await db.commit()
                await dispatch_event("stamp.failed", stamp.id, {"error": str(e), "chain": "polygon"})

        if chain in ("both", "bitcoin"):
            try:
                ots_b64 = await submit_to_ots(stamp.file_hash)
                stamp.ots_file_data = ots_b64
                stamp.ots_status = "submitted"
                await db.commit()
            except Exception as e:
                stamp.ots_status = "failed"
                await db.commit()
                # İş modeli: OTS ayrı ücretlendiriliyorsa stamp_refund_ots_failed + kısmi iade burada


@router.post("", response_model=StampResponse, status_code=201)
@limiter.limit("30/minute")
async def create_stamp(
    body: StampRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if idempotency_key:
        prev = await db.execute(
            select(Stamp).where(Stamp.user_id == user.id, Stamp.idempotency_key == idempotency_key)
        )
        prev_stamp = prev.scalar_one_or_none()
        if prev_stamp:
            if prev_stamp.file_hash != body.file_hash:
                raise HTTPException(409, "idempotency_conflict")
            return prev_stamp

    if user.used_this_month >= user.monthly_quota:
        raise HTTPException(429, f"Aylık kota aşıldı ({user.monthly_quota} damgalama)")

    existing = await db.execute(
        select(Stamp).where(Stamp.file_hash == body.file_hash, Stamp.user_id == user.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Bu dosya zaten damgalandı")

    if (
        body.vertical == "health_archive"
        and body.data_category == "special_health"
        and not body.consent_reference
    ):
        raise HTTPException(
            400,
            "Hasta arşivi (özel nitelikli sağlık verisi) için consent_reference ve hukuki süreç zorunludur.",
        )

    cost = 0
    if user.organization_id is not None:
        cost = settings.stamp_credit_cost
        ledger_key = f"consume:{idempotency_key}" if idempotency_key else None
        if not ledger_key:
            raise HTTPException(400, "Kurumsal damgalama için Idempotency-Key header zorunludur")
        await _consume_org_stamp_credit(db, user.organization_id, cost, ledger_key)

    stamp = Stamp(
        user_id=user.id,
        file_name=body.file_name,
        file_hash=body.file_hash,
        file_size=body.file_size,
        file_type=body.file_type,
        author=body.author,
        project=body.project,
        description=body.description,
        tags=body.tags,
        chain=body.chain,
        vertical=body.vertical,
        processing_purpose=body.processing_purpose,
        data_category=body.data_category,
        retention_until=body.retention_until,
        consent_reference=body.consent_reference,
        work_title=body.work_title,
        idempotency_key=idempotency_key,
        credits_charged=cost,
    )
    db.add(stamp)
    user.used_this_month += 1
    await db.flush()

    if body.subject_tc:
        fp = tc_fingerprint(settings.subject_tc_hmac_secret, body.subject_tc)
        db.add(
            StampSubject(
                stamp_id=stamp.id,
                tc_fingerprint=fp,
                organization_id=user.organization_id,
            )
        )
        await db.flush()

    await db.commit()

    await dispatch_event("stamp.created", stamp.id, {"file_name": stamp.file_name, "file_hash": stamp.file_hash})

    background_tasks.add_task(_process_stamp, stamp.id, body.chain)

    return stamp


@router.get("", response_model=StampListResponse)
@limiter.limit("60/minute")
async def list_stamps(
    page: int = 1,
    per_page: int = 20,
    project: str | None = None,
    chain: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    per_page = min(per_page, 100)
    query = select(Stamp).where(Stamp.user_id == user.id)
    if project:
        query = query.where(Stamp.project.ilike(f"%{project}%"))
    if chain:
        query = query.where(Stamp.chain == chain)

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar()

    query = query.order_by(Stamp.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    items  = result.scalars().all()

    return StampListResponse(total=total, page=page, per_page=per_page, items=items)


@router.get("/{stamp_id}", response_model=StampResponse)
async def get_stamp(
    stamp_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stamp = await db.get(Stamp, stamp_id)
    if not stamp or stamp.user_id != user.id:
        raise HTTPException(404, "Damgalama bulunamadı")
    return stamp
```

---

## app/routers/search.py

```python
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.database import get_db
from app.models.user import User
from app.models.stamp import Stamp
from app.models.stamp_subject import StampSubject
from app.schemas.search import StampSearchResponse, StampSummary
from app.routers.auth import get_current_user
from app.middleware.rate_limit import limiter

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("/stamps", response_model=StampSearchResponse)
@limiter.limit("60/minute")
async def search_stamps(
    request: Request,
    q: str | None = Query(None, max_length=500),
    file_hash: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    polygon_status: str | None = None,
    ots_status: str | None = None,
    chain: str | None = None,
    tag: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    scope: str = Query("self", pattern="^(self|by_verified_subject)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Birleşik damga araması. scope=self: kendi damgalarınız.
    scope=by_verified_subject: KYC sonrası subject_tc_fingerprint ile eşleşen tüm damgalar
    (aynı organization_id kapsamında stamp_subjects).
    """
    if scope == "self":
        query = select(Stamp).where(Stamp.user_id == user.id)
    else:
        if not user.subject_tc_fingerprint:
            raise HTTPException(
                400,
                "by_verified_subject için hesaba KYC ile kimlik bağlantısı (subject_tc_fingerprint) gerekir.",
            )
        org_clause = (
            StampSubject.organization_id == user.organization_id
            if user.organization_id is not None
            else StampSubject.organization_id.is_(None)
        )
        query = (
            select(Stamp)
            .join(StampSubject, StampSubject.stamp_id == Stamp.id)
            .where(
                StampSubject.tc_fingerprint == user.subject_tc_fingerprint,
                org_clause,
            )
            .distinct()
        )

    if file_hash:
        query = query.where(Stamp.file_hash == file_hash.lower().strip())
    if from_date:
        query = query.where(Stamp.created_at >= from_date)
    if to_date:
        query = query.where(Stamp.created_at <= to_date)
    if polygon_status:
        query = query.where(Stamp.polygon_status == polygon_status)
    if ots_status:
        query = query.where(Stamp.ots_status == ots_status)
    if chain:
        query = query.where(Stamp.chain == chain)
    if q:
        ilike = f"%{q}%"
        query = query.where(
            or_(
                Stamp.file_name.ilike(ilike),
                Stamp.description.ilike(ilike),
                Stamp.author.ilike(ilike),
                Stamp.project.ilike(ilike),
            )
        )
    if tag:
        query = query.where(Stamp.tags.contains([tag]))

    subq = query.subquery()
    total = (await db.execute(select(func.count()).select_from(subq))).scalar_one()

    query = query.order_by(Stamp.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    items = list(result.scalars().all())

    return StampSearchResponse(
        total=total, page=page, per_page=per_page, items=[StampSummary.model_validate(s) for s in items]
    )
```

---

## app/routers/admin_stamps.py

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.config import get_settings
from app.models.user import User
from app.models.stamp import Stamp
from app.models.stamp_subject import StampSubject
from app.schemas.search import AdminSubjectLookupRequest, StampSummary
from app.routers.auth import get_current_user
from app.services.subject_fingerprint import tc_fingerprint
from app.middleware.rate_limit import limiter

router = APIRouter(prefix="/admin/subject-stamps", tags=["Admin"])
settings = get_settings()


def require_org_admin(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("org_admin", "superadmin"):
        raise HTTPException(403, "org_admin veya superadmin rolü gerekli")
    if user.role == "org_admin" and user.organization_id is None:
        raise HTTPException(400, "Kurumsal admin için organization_id gerekli")
    return user


@router.post("/lookup", response_model=list[StampSummary])
@limiter.limit("10/hour")
async def admin_lookup_stamps_by_tc(
    request: Request,
    body: AdminSubjectLookupRequest,
    admin: User = Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Kurumsal: verilen TC’nin parmak izi ile eşleşen stamp_subjects üzerinden damga listesi.
    Ham TC loglara yazılmamalı; üretimde audit_logs tablosuna admin_id + zaman önerilir.
    superadmin: organization filtresi uygulanmaz (tüm kiracılar — dikkatli kullanın).
    """
    fp = tc_fingerprint(settings.subject_tc_hmac_secret, body.tc)
    q = (
        select(Stamp)
        .join(StampSubject, StampSubject.stamp_id == Stamp.id)
        .where(StampSubject.tc_fingerprint == fp)
        .order_by(Stamp.created_at.desc())
    )
    if admin.role != "superadmin":
        q = q.where(StampSubject.organization_id == admin.organization_id)

    result = await db.execute(q)
    stamps = result.scalars().unique().all()
    return [StampSummary.model_validate(s) for s in stamps]
```

---

## app/models/wholesale.py

```python
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, BigInteger, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class OrganizationCreditBalance(Base):
    """Kurum başına ön ödemeli damgalama kredisi (toptan satış sonrası yüklenir)."""

    __tablename__ = "organization_credit_balances"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True
    )
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class WholesaleContract(Base):
    """
    Toptan sözleşme kaydı: kredi satışı veya token teslimatı taahhüdü.
    Coin’in fiziksel satışı genelde treasury dışı; burada ticari kayıt ve kredi bağlantısı.
    """

    __tablename__ = "wholesale_contracts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    buyer_organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    contract_type: Mapped[str] = mapped_column(String(32), default="credits")
    # credits | token_commitment (token taahhüdü — teslim tx ayrı alanda)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    # draft | active | fulfilled | cancelled

    credit_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_price_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # kuruş / minor unit
    pricing_currency: Mapped[str] = mapped_column(String(8), default="TRY")

    external_legal_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    settlement_token_symbol: Mapped[str | None] = mapped_column(String(20), nullable=True)
    settlement_token_amount: Mapped[str | None] = mapped_column(String(64), nullable=True)
    settlement_tx_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)

    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    ledger_entries: Mapped[list["CreditLedgerEntry"]] = relationship(
        "CreditLedgerEntry", back_populates="contract", cascade="all, delete-orphan"
    )


class CreditLedgerEntry(Base):
    """Kredi hareketleri (+ tahsis, − tüketim)."""

    __tablename__ = "credit_ledger_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    # wholesale_allocate | stamp_consume | stamp_refund_polygon_failed | stamp_refund_ots_failed | manual_adjust
    contract_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wholesale_contracts.id", ondelete="SET NULL"),
        nullable=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(80), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    contract: Mapped["WholesaleContract | None"] = relationship(
        "WholesaleContract", back_populates="ledger_entries"
    )
```

---

## app/schemas/b2b.py

```python
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Literal


class WholesaleContractCreate(BaseModel):
    buyer_organization_id: UUID
    contract_type: Literal["credits", "token_commitment"] = "credits"
    credit_quantity: int | None = Field(default=None, ge=1)
    unit_price_minor: int | None = Field(default=None, ge=0)
    pricing_currency: str = Field(default="TRY", max_length=8)
    external_legal_ref: str | None = Field(default=None, max_length=120)
    notes: str | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None


class WholesaleContractResponse(BaseModel):
    id: UUID
    buyer_organization_id: UUID
    contract_type: str
    status: str
    credit_quantity: int | None
    unit_price_minor: int | None
    pricing_currency: str
    external_legal_ref: str | None
    settlement_tx_hash: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreditAllocateRequest(BaseModel):
    organization_id: UUID
    credits: int = Field(ge=1)
    contract_id: UUID | None = None
    idempotency_key: str | None = Field(default=None, max_length=80)


class CreditLedgerResponse(BaseModel):
    id: UUID
    organization_id: UUID
    delta: int
    balance_after: int
    reason: str
    contract_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreditBalanceMeResponse(BaseModel):
    """Giriş yapan kullanıcının kurumuna ait ön ödemeli kredi bakiyesi."""

    organization_id: UUID | None = None
    balance: int = 0
    has_organization: bool = False
```

---

## app/routers/b2b.py

```python
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.wholesale import (
    WholesaleContract,
    CreditLedgerEntry,
    OrganizationCreditBalance,
)
from app.schemas.b2b import (
    WholesaleContractCreate,
    WholesaleContractResponse,
    CreditAllocateRequest,
    CreditLedgerResponse,
    CreditBalanceMeResponse,
)
from app.routers.auth import get_current_user
from app.middleware.rate_limit import limiter

router = APIRouter(prefix="/b2b", tags=["B2B / Toptan"])


def require_superadmin(user: User = Depends(get_current_user)) -> User:
    if user.role != "superadmin":
        raise HTTPException(403, "Yalnızca superadmin")
    return user


@router.post("/contracts", response_model=WholesaleContractResponse, status_code=201)
@limiter.limit("30/minute")
async def create_wholesale_contract(
    request: Request,
    body: WholesaleContractCreate,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Toptan kontrat taslağı / kayıt (kredi veya token taahhüdü meta verisi)."""
    if body.contract_type == "credits" and not body.credit_quantity:
        raise HTTPException(400, "credits tipinde credit_quantity gerekli")
    row = WholesaleContract(
        buyer_organization_id=body.buyer_organization_id,
        contract_type=body.contract_type,
        status="draft",
        credit_quantity=body.credit_quantity,
        unit_price_minor=body.unit_price_minor,
        pricing_currency=body.pricing_currency,
        external_legal_ref=body.external_legal_ref,
        notes=body.notes,
        valid_from=body.valid_from,
        valid_until=body.valid_until,
    )
    db.add(row)
    await db.flush()
    return row


@router.get("/contracts", response_model=list[WholesaleContractResponse])
async def list_contracts(
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(WholesaleContract).order_by(WholesaleContract.created_at.desc()))
    return list(r.scalars().all())


@router.post("/credits/allocate", response_model=CreditLedgerResponse)
@limiter.limit("20/minute")
async def allocate_credits(
    request: Request,
    body: CreditAllocateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Toptan satış sonrası kurum kredisini artırır. İdempotent anahtar önerilir.
    Damga tüketimi bu bakiyeden düşecek şekilde stamps router ile entegre edilmelidir (sıra ve telafi: aşağıdaki **Damgalama akışı** bölümü).
    """
    key = body.idempotency_key or idempotency_key
    if key:
        ex = await db.execute(
            select(CreditLedgerEntry).where(CreditLedgerEntry.idempotency_key == key)
        )
        if ex.scalar_one_or_none():
            raise HTTPException(409, "Bu idempotency_key ile işlem zaten yapıldı")

    bal = await db.get(OrganizationCreditBalance, body.organization_id)
    if not bal:
        bal = OrganizationCreditBalance(organization_id=body.organization_id, balance=0)
        db.add(bal)
        await db.flush()

    new_balance = bal.balance + body.credits
    bal.balance = new_balance
    entry = CreditLedgerEntry(
        organization_id=body.organization_id,
        delta=body.credits,
        balance_after=new_balance,
        reason="wholesale_allocate",
        contract_id=body.contract_id,
        idempotency_key=key,
    )
    db.add(entry)
    await db.flush()
    return entry


@router.get("/credits/ledger", response_model=list[CreditLedgerResponse])
async def credit_ledger(
    organization_id: UUID | None = None,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    q = select(CreditLedgerEntry).order_by(CreditLedgerEntry.created_at.desc()).limit(500)
    if organization_id:
        q = q.where(CreditLedgerEntry.organization_id == organization_id)
    r = await db.execute(q)
    return list(r.scalars().all())


@router.get("/credits/balance/me", response_model=CreditBalanceMeResponse)
@limiter.limit("60/minute")
async def my_organization_credit_balance(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Kullanıcının organization_id kapsamındaki toptan yüklenen kredi bakiyesi (JWT)."""
    if not user.organization_id:
        return CreditBalanceMeResponse(
            organization_id=None, balance=0, has_organization=False
        )
    bal = await db.get(OrganizationCreditBalance, user.organization_id)
    amount = bal.balance if bal else 0
    return CreditBalanceMeResponse(
        organization_id=user.organization_id,
        balance=amount,
        has_organization=True,
    )
```

---

## app/routers/verify.py

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.stamp import Stamp
from app.schemas.stamp import VerifyResponse, StampResponse

router = APIRouter(prefix="/verify", tags=["Verify"])

@router.get("/{file_hash}", response_model=VerifyResponse)
async def verify_by_hash(file_hash: str, db: AsyncSession = Depends(get_db)):
    """Public endpoint — auth gerektirmez."""
    if len(file_hash) != 64:
        return VerifyResponse(found=False, message="Geçersiz hash formatı")

    result = await db.execute(
        select(Stamp).where(Stamp.file_hash == file_hash.lower())
    )
    stamp = result.scalar_one_or_none()

    if not stamp:
        return VerifyResponse(found=False, message="Bu hash için kayıt bulunamadı")

    return VerifyResponse(
        found=True,
        stamp=StampResponse.model_validate(stamp),
        message="Doğrulandı — dosya değiştirilmemiş",
    )
```

---

## app/routers/webhooks.py

```python
import secrets
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.webhook import Webhook, WebhookDelivery
from app.schemas.webhook import (
    WebhookCreateRequest, WebhookResponse, WebhookCreatedResponse
)
from app.routers.auth import get_current_user

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

@router.post("", response_model=WebhookCreatedResponse, status_code=201)
async def create_webhook(
    body: WebhookCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    secret = secrets.token_hex(32)
    webhook = Webhook(
        user_id=user.id,
        name=body.name,
        url=str(body.url),
        secret=secret,
        events=body.events,
    )
    db.add(webhook)
    await db.flush()
    resp = WebhookCreatedResponse.model_validate(webhook)
    resp.secret = secret
    return resp

@router.get("", response_model=list[WebhookResponse])
async def list_webhooks(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Webhook).where(Webhook.user_id == user.id)
    )
    return result.scalars().all()

@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Webhook).where(Webhook.id == webhook_id, Webhook.user_id == user.id)
    )
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(404, "Webhook bulunamadı")
    await db.delete(webhook)

@router.get("/{webhook_id}/deliveries")
async def get_deliveries(
    webhook_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Webhook).where(Webhook.id == webhook_id, Webhook.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404)
    deliveries = await db.execute(
        select(WebhookDelivery)
        .where(WebhookDelivery.webhook_id == webhook_id)
        .order_by(WebhookDelivery.delivered_at.desc())
        .limit(50)
    )
    return deliveries.scalars().all()
```

---

## app/main.py

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.database import engine, Base
from app.middleware.rate_limit import limiter, rate_limit_exceeded_handler
from app.routers import auth, stamps, search, admin_stamps, b2b, verify, webhooks

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tabloları oluştur (production'da alembic kullan)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(
    title="TurkDamga API",
    version=settings.app_version,
    description="Blockchain tabanlı dijital zaman damgası servisi",
    lifespan=lifespan,
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router,        prefix="/api/v1")
app.include_router(stamps.router,      prefix="/api/v1")
app.include_router(search.router,      prefix="/api/v1")
app.include_router(admin_stamps.router, prefix="/api/v1")
app.include_router(b2b.router,           prefix="/api/v1")
app.include_router(verify.router,       prefix="/api/v1")
app.include_router(webhooks.router,     prefix="/api/v1")

@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.app_version}

@app.exception_handler(Exception)
async def global_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": "Sunucu hatası", "detail": str(exc)})
```

---

## API Referansı

```
POST   /api/v1/auth/register          Kayıt
POST   /api/v1/auth/login             Giriş → JWT
POST   /api/v1/auth/refresh           Token yenile
GET    /api/v1/auth/me                Profil
POST   /api/v1/auth/api-keys          API key oluştur
GET    /api/v1/auth/api-keys          API key listesi
DELETE /api/v1/auth/api-keys/{id}     API key iptal

POST   /api/v1/stamps                 Yeni damgalama (opsiyonel subject_tc → stamp_subjects)
GET    /api/v1/stamps?page=1          Damgalama listesi
GET    /api/v1/stamps/{id}            Damgalama detayı

GET    /api/v1/search/stamps          Birleşik arama (q, tarih, hash, etiket, scope=self|by_verified_subject)
POST   /api/v1/admin/subject-stamps/lookup  Kurumsal TC → damga listesi (org_admin+, 10/saat)

POST   /api/v1/b2b/contracts            Toptan kontrat kaydı (superadmin)
GET    /api/v1/b2b/contracts              Kontrat listesi
POST   /api/v1/b2b/credits/allocate       Kurum kredisi yükle (Idempotency-Key önerilir)
GET    /api/v1/b2b/credits/ledger        Kredi hareket dökümü
GET    /api/v1/b2b/credits/balance/me    Kurumsal kredi bakiyesi (oturum, organization_id)

GET    /api/v1/verify/{hash}          Hash doğrula (public)

POST   /api/v1/webhooks               Webhook oluştur
GET    /api/v1/webhooks               Webhook listesi
DELETE /api/v1/webhooks/{id}          Webhook sil
GET    /api/v1/webhooks/{id}/deliveries  Teslimat geçmişi

GET    /health                        Sağlık kontrolü
GET    /docs                          Swagger UI
```

---

## Alembic migrasyonları

Gerçek dosyalar repo içinde: `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/` altında sırayla:

1. `20260423_01_stamp_subjects_identity_search.py`
2. `20260424_02_wholesale_b2b.py` (`down_revision`: `20260423_01`)
3. `20260425_03_stamp_vertical_kvkk.py` (`down_revision`: `20260424_02`)

**İçerik özeti (`20260423_01`):**

- `users`: `role`, `organization_id`, `subject_tc_fingerprint`, `subject_binding_verified_at` + indeksler
- `stamp_subjects` tablosu + FK `stamps.id` (CASCADE) + indeksler
- `stamps.search_vector` — `tsvector` **GENERATED** sütunu + **GIN** indeksi (`simple` dil yapılandırması; Türkçe için sunucuda `turkish` varsa migration SQL’inde değiştirin)

**İçerik özeti (`20260424_02`):**

- `organization_credit_balances`, `wholesale_contracts`, `credit_ledger_entries` (toptan kontrat / kredi defteri)

**İçerik özeti (`20260425_03`):**

- `stamps`: `vertical`, `processing_purpose`, `data_category`, `retention_until`, `consent_reference` + indeks `ix_stamps_vertical`

**Çalıştırma:**

```bash
cd backend
set DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/turkdamga
alembic upgrade head
```

`env.py`, `+asyncpg` / `+psycopg` sonekini kaldırarak sync `postgresql://` URL üretir.

**Zincir:** `20260423_01` için `down_revision = None` — mevcut başka bir başlangıç migrasyonunuz varsa bu ID’yi ona bağlayın; ardından `20260424_02` zincirde onu takip eder.

---

## Kurulum

```bash
# 1. Proje oluştur
mkdir turkdamga-api && cd turkdamga-api
python -m venv venv && source venv/bin/activate

# 2. Bağımlılıklar
pip install -r requirements.txt

# 3. PostgreSQL + Redis (Docker)
docker run -d --name cv-postgres \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=turkdamga \
  -p 5432:5432 postgres:16

docker run -d --name cv-redis \
  -p 6379:6379 redis:7-alpine

# 4. .env dosyasını doldur (yukarıdaki şablonu kullan)

# 5. Çalıştır
uvicorn app.main:app --reload --port 8000

# Swagger UI: http://localhost:8000/docs
```

---

## Webhook Doğrulama (istemci tarafı)

```python
import hmac, hashlib

def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

# Flask/FastAPI handler örneği:
@app.post("/my-webhook")
async def receive(request: Request):
    payload   = await request.body()
    sig       = request.headers.get("X-TurkDamga-Sig", "")
    if not verify_webhook_signature(payload, sig, MY_WEBHOOK_SECRET):
        raise HTTPException(401)
    data = json.loads(payload)
    print(f"Event: {data['event']} — Stamp: {data['stamp_id']}")
```
