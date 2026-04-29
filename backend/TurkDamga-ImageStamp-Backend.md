# TurkDamga — Görsel Damgalama Backend

Bu dosya üç Python modülünü birleştirir:
1. image_fingerprint.py
2. search_service.py  
3. router_images.py

**Sertifika:** Görsel / tasarım damgası belge formatında olmayabilir; müşteriye sunulacak **zaman damgası sertifikası** (hash, tarih, isteğe bağlı `work_title`) için bkz. `docs/Medya-Damga-Sertifikasi.md`.
# ============================================================
# TurkDamga — Görsel Parmak İzi Servisi
# SHA-256 + pHash + CLIP Embedding (üç katmanlı)
# ============================================================
# pip install Pillow imagehash torch torchvision transformers
#             pgvector sqlalchemy asyncpg numpy

"""
app/services/image_fingerprint.py

Üç katman:
  1. SHA-256       → tam bit-eşit kopya tespiti
  2. pHash         → yeniden boyutlandırma/sıkıştırma sonrası benzerlik
  3. CLIP Embedding → motif/renk/ölçek bağımsız desen benzerliği
"""

import io
import hashlib
import struct
import numpy as np
from PIL import Image
import imagehash
from functools import lru_cache
from typing import Optional

# CLIP sadece ilk çağrıda yüklenir (~1.5 GB, ama sonra cache'lenir)
_clip_model  = None
_clip_preprocess = None
_clip_device = None


@lru_cache(maxsize=1)
def _load_clip():
    """CLIP modelini lazy-load eder."""
    import torch
    from transformers import CLIPProcessor, CLIPModel

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model  = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
    proc   = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    model  = model.to(device)
    model.eval()
    return model, proc, device


# ── 1. SHA-256 ────────────────────────────────────────────────
def compute_sha256(image_bytes: bytes) -> str:
    """Ham byte SHA-256 — birebir aynı dosya tespiti."""
    return hashlib.sha256(image_bytes).hexdigest()


# ── 2. pHash (Perceptual Hash) ────────────────────────────────
def compute_phash(image_bytes: bytes) -> str:
    """
    64-bit perceptual hash.
    Yeniden boyutlandırma, hafif renk düzeltmesi, JPEG yeniden
    sıkıştırması sonrasında bile aynı veya çok yakın hash üretir.
    Hamming mesafesi ≤ 8 → benzer görsel.
    """
    img  = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    phash = imagehash.phash(img, hash_size=8)  # 64-bit
    return str(phash)


def phash_distance(h1: str, h2: str) -> int:
    """İki pHash arasındaki Hamming mesafesi (0 = aynı, 64 = tam farklı)."""
    return imagehash.hex_to_hash(h1) - imagehash.hex_to_hash(h2)


def phash_to_int(phash_hex: str) -> int:
    """pHash'i PostgreSQL bigint'e çevirir (bit operasyonları için)."""
    return int(phash_hex, 16)


# ── 3. CLIP Embedding ─────────────────────────────────────────
def compute_clip_embedding(image_bytes: bytes) -> list[float]:
    """
    512 boyutlu CLIP görsel vektörü.
    Aynı motifin farklı renk, ölçek veya perspektif versiyonları
    vektör uzayında birbirine yakın olur.
    Cosine benzerliği ≥ 0.85 → güçlü motif benzerliği.
    """
    import torch

    model, proc, device = _load_clip()
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    inputs = proc(images=img, return_tensors="pt").to(device)

    with torch.no_grad():
        features = model.get_image_features(**inputs)
        # L2 normalize (cosine similarity için)
        features = features / features.norm(dim=-1, keepdim=True)

    return features.squeeze().cpu().numpy().tolist()


# ── Tam Parmak İzi ────────────────────────────────────────────
def compute_full_fingerprint(image_bytes: bytes) -> dict:
    """
    Tüm üç katmanı tek seferde hesaplar.
    Döndürür:
      sha256:    str   — tam eşleşme
      phash:     str   — benzer görsel
      phash_int: int   — DB bit operasyonları için
      embedding: list  — motif benzerliği (512 float)
      width:     int
      height:    int
      format:    str
    """
    img = Image.open(io.BytesIO(image_bytes))
    width, height = img.size
    fmt = img.format or "UNKNOWN"

    sha256    = compute_sha256(image_bytes)
    phash_hex = compute_phash(image_bytes)
    phash_int = phash_to_int(phash_hex)
    embedding = compute_clip_embedding(image_bytes)

    return {
        "sha256":    sha256,
        "phash":     phash_hex,
        "phash_int": phash_int,
        "embedding": embedding,
        "width":     width,
        "height":    height,
        "format":    fmt,
    }


# ── pHash Lite (tarayıcı tarafı için) ─────────────────────────
def compute_phash_bytes(phash_hex: str) -> bytes:
    """pHash'i 8 byte binary'e çevirir (PostgreSQL bit operasyonu)."""
    return bytes.fromhex(phash_hex)
# ============================================================
# app/models/image_stamp.py  +  app/services/search_service.py
# PostgreSQL + pgvector
# ============================================================

# ── KURULUM ───────────────────────────────────────────────────
# PostgreSQL'e pgvector extension ekle:
#   CREATE EXTENSION IF NOT EXISTS vector;
#
# pip install pgvector sqlalchemy asyncpg


# ============================================================
# models/image_stamp.py
# ============================================================
"""
ImageStamp modeli:
  - sha256      → tam eşleşme (B-tree index)
  - phash_int   → benzer görsel (bit XOR + popcount, GIST index)
  - embedding   → motif benzerliği (pgvector IVFFlat index)
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    String, DateTime, BigInteger, Integer,
    Boolean, Text, JSON, ForeignKey, Index, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from app.database import Base


class ImageStamp(Base):
    __tablename__ = "image_stamps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    # ── Dosya bilgileri ──────────────────────────────────────
    file_name:  Mapped[str]       = mapped_column(String(500))
    file_size:  Mapped[int]       = mapped_column(BigInteger, default=0)
    mime_type:  Mapped[str|None]  = mapped_column(String(100))
    width:      Mapped[int|None]  = mapped_column(Integer)
    height:     Mapped[int|None]  = mapped_column(Integer)

    # ── Parmak izleri ────────────────────────────────────────
    sha256:     Mapped[str]       = mapped_column(String(64),  nullable=False, index=True)
    phash:      Mapped[str]       = mapped_column(String(16),  nullable=False)
    phash_int:  Mapped[int]       = mapped_column(BigInteger,  nullable=False)
    # 512-boyutlu CLIP vektörü
    embedding:  Mapped[list|None] = mapped_column(Vector(512), nullable=True)

    # ── Metadata ─────────────────────────────────────────────
    author:      Mapped[str|None] = mapped_column(String(200))
    description: Mapped[str|None] = mapped_column(Text)
    tags:        Mapped[list]     = mapped_column(JSON, default=list)
    is_public:   Mapped[bool]     = mapped_column(Boolean, default=True)

    # ── Blockchain ───────────────────────────────────────────
    polygon_tx:      Mapped[str|None] = mapped_column(String(66))
    polygon_url:     Mapped[str|None] = mapped_column(String(200))
    polygon_status:  Mapped[str]      = mapped_column(String(20), default="pending")
    ots_status:      Mapped[str]      = mapped_column(String(20), default="pending")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        # pHash bit XOR araması için GIST index
        Index("ix_image_stamps_phash_int", "phash_int"),
        # Vektör araması için IVFFlat index (pgvector)
        # Not: Alembic migration'da manuel ekle:
        # CREATE INDEX ix_image_stamps_embedding ON image_stamps
        #   USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
    )


# ============================================================
# services/search_service.py
# ============================================================
"""
Üç katmanlı arama:
  1. SHA-256 exact match  → O(log n) — B-tree
  2. pHash similarity     → Hamming ≤ threshold — bit XOR
  3. CLIP cosine search   → top-K nearest neighbor — ivfflat
"""

from uuid import UUID
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.models.image_stamp import ImageStamp
from app.services.image_fingerprint import phash_distance


# ── Eşik değerleri ────────────────────────────────────────────
PHASH_THRESHOLD     = 10   # Hamming ≤ 10 → benzer (64 bit üzerinden)
CLIP_THRESHOLD      = 0.82  # Cosine ≥ 0.82 → motif benzerliği
CLIP_TOP_K          = 20    # İlk K sonuç


class SearchResult:
    def __init__(self, stamp: ImageStamp, match_type: str,
                 score: float, detail: str):
        self.stamp      = stamp
        self.match_type = match_type   # "exact" | "similar" | "motif"
        self.score      = score        # 0.0–1.0
        self.detail     = detail       # insan okunabilir açıklama


async def search_image(
    db: AsyncSession,
    sha256:    str,
    phash:     str,
    phash_int: int,
    embedding: list[float],
    scope:     str = "public",   # "public" | "own" | "all"
    user_id:   Optional[UUID] = None,
) -> list[SearchResult]:
    """
    Tüm üç katmanı çalıştırır ve birleştirilmiş sonuç döner.
    scope:
      "public" → is_public=True olan tüm kayıtlar
      "own"    → sadece user_id'nin kayıtları
      "all"    → her ikisi (giriş yapmış kullanıcı için)
    """
    results: list[SearchResult] = []
    seen_ids = set()

    # ── Katman 1: SHA-256 tam eşleşme ─────────────────────────
    exact = await _search_exact(db, sha256, scope, user_id)
    for stamp in exact:
        if stamp.id not in seen_ids:
            results.append(SearchResult(
                stamp=stamp,
                match_type="exact",
                score=1.0,
                detail="Birebir aynı dosya — SHA-256 tam eşleşme",
            ))
            seen_ids.add(stamp.id)

    # ── Katman 2: pHash benzerlik ──────────────────────────────
    similar = await _search_phash(db, phash_int, scope, user_id)
    for stamp in similar:
        if stamp.id not in seen_ids:
            dist  = phash_distance(phash, stamp.phash)
            score = round(1.0 - dist / 64.0, 3)
            results.append(SearchResult(
                stamp=stamp,
                match_type="similar",
                score=score,
                detail=f"Görsel benzerlik — Hamming mesafesi: {dist}/64 ({int(score*100)}% benzer)",
            ))
            seen_ids.add(stamp.id)

    # ── Katman 3: CLIP motif benzerliği ───────────────────────
    if embedding:
        motif = await _search_embedding(db, embedding, scope, user_id)
        for stamp, cosine_sim in motif:
            if stamp.id not in seen_ids:
                results.append(SearchResult(
                    stamp=stamp,
                    match_type="motif",
                    score=round(float(cosine_sim), 3),
                    detail=f"Motif/desen benzerliği — Cosine: {cosine_sim:.3f} ({int(cosine_sim*100)}% benzer)",
                ))
                seen_ids.add(stamp.id)

    # Skora göre sırala (en yüksek önce)
    results.sort(key=lambda r: r.score, reverse=True)
    return results


# ── Katman 1: Exact ───────────────────────────────────────────
async def _search_exact(
    db: AsyncSession,
    sha256: str,
    scope: str,
    user_id: Optional[UUID],
) -> list[ImageStamp]:
    q = select(ImageStamp).where(ImageStamp.sha256 == sha256)
    q = _apply_scope(q, scope, user_id)
    result = await db.execute(q)
    return result.scalars().all()


# ── Katman 2: pHash Hamming ────────────────────────────────────
async def _search_phash(
    db: AsyncSession,
    phash_int: int,
    scope: str,
    user_id: Optional[UUID],
    threshold: int = PHASH_THRESHOLD,
) -> list[ImageStamp]:
    """
    PostgreSQL bit_count(a XOR b) ile Hamming mesafesi hesaplar.
    phash_int: 64-bit signed bigint
    """
    # PostgreSQL'de bit XOR ve popcount
    # bit_count() PostgreSQL 14+ gerektirir
    # Alternatif: (a # b)::bit(64) için bit_count kullanımı
    sql = text("""
        SELECT *
        FROM image_stamps
        WHERE
            bit_count(
                (phash_int # :phash_int)::bigint::bit(64)
            ) <= :threshold
            {scope_clause}
        ORDER BY
            bit_count(
                (phash_int # :phash_int)::bigint::bit(64)
            ) ASC
        LIMIT 50
    """.format(scope_clause=_scope_sql(scope, user_id)))

    params = {"phash_int": phash_int, "threshold": threshold}
    if user_id and scope != "public":
        params["user_id"] = str(user_id)

    result = await db.execute(sql, params)
    rows = result.fetchall()
    return [ImageStamp(**dict(row._mapping)) for row in rows]


# ── Katman 3: CLIP Cosine ─────────────────────────────────────
async def _search_embedding(
    db: AsyncSession,
    embedding: list[float],
    scope: str,
    user_id: Optional[UUID],
    threshold: float = CLIP_THRESHOLD,
    top_k: int = CLIP_TOP_K,
) -> list[tuple[ImageStamp, float]]:
    """
    pgvector <=> operatörü ile cosine distance araması.
    cosine_similarity = 1 - cosine_distance
    """
    vec_str = "[" + ",".join(f"{v:.6f}" for v in embedding) + "]"

    sql = text("""
        SELECT *, (1 - (embedding <=> :embedding::vector)) AS cosine_sim
        FROM image_stamps
        WHERE
            embedding IS NOT NULL
            AND (1 - (embedding <=> :embedding::vector)) >= :threshold
            {scope_clause}
        ORDER BY embedding <=> :embedding::vector ASC
        LIMIT :top_k
    """.format(scope_clause=_scope_sql(scope, user_id)))

    params = {
        "embedding": vec_str,
        "threshold": threshold,
        "top_k": top_k,
    }
    if user_id and scope != "public":
        params["user_id"] = str(user_id)

    result = await db.execute(sql, params)
    rows = result.fetchall()
    return [
        (ImageStamp(**{k: v for k, v in row._mapping.items() if k != "cosine_sim"}),
         row.cosine_sim)
        for row in rows
    ]


# ── Yardımcılar ───────────────────────────────────────────────
def _apply_scope(query, scope: str, user_id: Optional[UUID]):
    if scope == "public":
        return query.where(ImageStamp.is_public == True)
    elif scope == "own" and user_id:
        return query.where(ImageStamp.user_id == user_id)
    elif scope == "all" and user_id:
        from sqlalchemy import or_
        return query.where(
            or_(ImageStamp.is_public == True, ImageStamp.user_id == user_id)
        )
    return query.where(ImageStamp.is_public == True)


def _scope_sql(scope: str, user_id: Optional[UUID]) -> str:
    if scope == "public":
        return "AND is_public = TRUE"
    elif scope == "own" and user_id:
        return "AND user_id = :user_id"
    elif scope == "all" and user_id:
        return "AND (is_public = TRUE OR user_id = :user_id)"
    return "AND is_public = TRUE"
# ============================================================
# app/routers/images.py
# Görsel yükleme, damgalama ve üç katmanlı arama endpoint'leri
# ============================================================

import uuid
from datetime import datetime
from typing import Optional, Literal
from fastapi import (
    APIRouter, Depends, HTTPException,
    UploadFile, File, Form, BackgroundTasks, Query
)
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.image_stamp import ImageStamp
from app.routers.auth import get_current_user
from app.services.image_fingerprint import compute_full_fingerprint
from app.services.search_service import search_image, SearchResult
from app.services.polygon import stamp_on_polygon
from app.services.webhook_dispatcher import dispatch_event
from app.middleware.rate_limit import limiter

router = APIRouter(prefix="/images", tags=["Images"])

# İzin verilen MIME türleri
ALLOWED_MIME = {
    "image/jpeg", "image/png", "image/webp",
    "image/tiff", "image/bmp", "image/gif"
}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


# ── Şemalar ───────────────────────────────────────────────────
class ImageStampResponse(BaseModel):
    id:             str
    file_name:      str
    file_size:      int
    width:          Optional[int]
    height:         Optional[int]
    sha256:         str
    phash:          str
    author:         Optional[str]
    description:    Optional[str]
    tags:           list
    is_public:      bool
    polygon_tx:     Optional[str]
    polygon_url:    Optional[str]
    polygon_status: str
    ots_status:     str
    created_at:     str

    @classmethod
    def from_orm(cls, s: ImageStamp) -> "ImageStampResponse":
        return cls(
            id=str(s.id), file_name=s.file_name, file_size=s.file_size,
            width=s.width, height=s.height, sha256=s.sha256, phash=s.phash,
            author=s.author, description=s.description, tags=s.tags or [],
            is_public=s.is_public, polygon_tx=s.polygon_tx,
            polygon_url=s.polygon_url, polygon_status=s.polygon_status,
            ots_status=s.ots_status,
            created_at=s.created_at.isoformat(),
        )


class SearchMatch(BaseModel):
    match_type:  str    # exact | similar | motif
    score:       float  # 0.0 – 1.0
    detail:      str
    stamp:       ImageStampResponse


class SearchResponse(BaseModel):
    found:         bool
    total_matches: int
    exact_count:   int
    similar_count: int
    motif_count:   int
    matches:       list[SearchMatch]
    searched_at:   str


# ── Arka plan: blockchain işlemleri ──────────────────────────
async def _process_blockchain(stamp_id: uuid.UUID, sha256: str, metadata: dict):
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        stamp = await db.get(ImageStamp, stamp_id)
        if not stamp:
            return
        try:
            result = await stamp_on_polygon(sha256, metadata)
            stamp.polygon_tx     = result["tx_hash"]
            stamp.polygon_url    = result["explorer_url"]
            stamp.polygon_status = "confirmed"
            await db.commit()
            await dispatch_event("stamp.polygon.confirmed", stamp.id, {
                "file_name": stamp.file_name,
                "sha256":    stamp.sha256,
                "polygon_tx": stamp.polygon_tx,
            })
        except Exception as e:
            stamp.polygon_status = "failed"
            await db.commit()


# ══════════════════════════════════════════════════════════════
# POST /api/v1/images/stamp
# Görsel yükle + parmak izi hesapla + blockchain damgala
# ══════════════════════════════════════════════════════════════
@router.post("/stamp", response_model=ImageStampResponse, status_code=201)
@limiter.limit("20/minute")
async def stamp_image(
    background_tasks: BackgroundTasks,
    file:        UploadFile = File(...),
    author:      str        = Form(default=""),
    description: str        = Form(default=""),
    tags:        str        = Form(default=""),     # virgülle ayrılmış
    is_public:   bool       = Form(default=True),
    chain:       str        = Form(default="both"),
    user: User = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    # ── Doğrulama ──────────────────────────────────────────
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(415, f"Desteklenmeyen format: {file.content_type}")

    image_bytes = await file.read()
    if len(image_bytes) > MAX_FILE_SIZE:
        raise HTTPException(413, "Dosya boyutu 50 MB'ı aşıyor")

    # ── Parmak izi hesapla ─────────────────────────────────
    try:
        fp = compute_full_fingerprint(image_bytes)
    except Exception as e:
        raise HTTPException(422, f"Görsel işlenemedi: {e}")

    # ── Aynı SHA-256 zaten var mı? ─────────────────────────
    existing = await db.execute(
        select(ImageStamp).where(
            ImageStamp.sha256 == fp["sha256"],
            ImageStamp.user_id == user.id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Bu görsel zaten damgalandı")

    # ── Kayıt oluştur ──────────────────────────────────────
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    stamp = ImageStamp(
        user_id     = user.id,
        file_name   = file.filename or "image",
        file_size   = len(image_bytes),
        mime_type   = file.content_type,
        width       = fp["width"],
        height      = fp["height"],
        sha256      = fp["sha256"],
        phash       = fp["phash"],
        phash_int   = fp["phash_int"],
        embedding   = fp["embedding"],
        author      = author or user.username,
        description = description,
        tags        = tag_list,
        is_public   = is_public,
    )
    db.add(stamp)
    await db.flush()

    # ── Blockchain arka planda ─────────────────────────────
    background_tasks.add_task(
        _process_blockchain, stamp.id, fp["sha256"],
        {"file_name": stamp.file_name, "author": author, "phash": fp["phash"]}
    )

    return ImageStampResponse.from_orm(stamp)


# ══════════════════════════════════════════════════════════════
# POST /api/v1/images/search
# Üç katmanlı görsel arama (dosya yükle)
# ══════════════════════════════════════════════════════════════
@router.post("/search", response_model=SearchResponse)
@limiter.limit("30/minute")
async def search_by_image(
    file:    UploadFile = File(...),
    scope:   str        = Form(default="all"),
    # scope: "public" | "own" | "all"
    user: Optional[User] = Depends(lambda: None),  # opsiyonel auth
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(415, f"Desteklenmeyen format: {file.content_type}")

    image_bytes = await file.read()
    if len(image_bytes) > MAX_FILE_SIZE:
        raise HTTPException(413, "Dosya boyutu 50 MB'ı aşıyor")

    # Parmak izi
    try:
        fp = compute_full_fingerprint(image_bytes)
    except Exception as e:
        raise HTTPException(422, f"Görsel işlenemedi: {e}")

    # Arama
    results: list[SearchResult] = await search_image(
        db        = db,
        sha256    = fp["sha256"],
        phash     = fp["phash"],
        phash_int = fp["phash_int"],
        embedding = fp["embedding"],
        scope     = scope,
        user_id   = user.id if user else None,
    )

    matches = [
        SearchMatch(
            match_type = r.match_type,
            score      = r.score,
            detail     = r.detail,
            stamp      = ImageStampResponse.from_orm(r.stamp),
        )
        for r in results
    ]

    return SearchResponse(
        found         = len(matches) > 0,
        total_matches = len(matches),
        exact_count   = sum(1 for m in matches if m.match_type == "exact"),
        similar_count = sum(1 for m in matches if m.match_type == "similar"),
        motif_count   = sum(1 for m in matches if m.match_type == "motif"),
        matches       = matches,
        searched_at   = datetime.utcnow().isoformat(),
    )


# ══════════════════════════════════════════════════════════════
# GET /api/v1/images/search?sha256=...
# Hash ile hızlı arama (ön kontrol için)
# ══════════════════════════════════════════════════════════════
@router.get("/search", response_model=SearchResponse)
async def search_by_hash(
    sha256: str = Query(..., min_length=64, max_length=64),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ImageStamp).where(
            ImageStamp.sha256 == sha256,
            ImageStamp.is_public == True
        )
    )
    stamps = result.scalars().all()

    matches = [
        SearchMatch(
            match_type = "exact",
            score      = 1.0,
            detail     = "SHA-256 tam eşleşme",
            stamp      = ImageStampResponse.from_orm(s),
        )
        for s in stamps
    ]

    return SearchResponse(
        found         = len(matches) > 0,
        total_matches = len(matches),
        exact_count   = len(matches),
        similar_count = 0,
        motif_count   = 0,
        matches       = matches,
        searched_at   = datetime.utcnow().isoformat(),
    )


# ══════════════════════════════════════════════════════════════
# GET /api/v1/images/my
# Kullanıcının kendi damgalamaları
# ══════════════════════════════════════════════════════════════
@router.get("/my", response_model=list[ImageStampResponse])
async def my_stamps(
    page:     int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(ImageStamp)
        .where(ImageStamp.user_id == user.id)
        .order_by(ImageStamp.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(q)
    return [ImageStampResponse.from_orm(s) for s in result.scalars().all()]
