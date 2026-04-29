# TurkDamga — Proje Dosyaları

Blockchain tabanlı dijital arşiv ve zaman damgası servisi.
SHA-256 + pHash + CLIP Embedding — üç katmanlı görsel analiz.

## Klasör Yapısı

```
TURKDAMGA/
├── tests/
│   └── test_smoke.py                 ← unittest duman testleri
├── frontend/
│   ├── turkdamga-landing.html      ← Landing page (beyaz/yeşil tema)
│   ├── turkdamga-arsiv-ui.html     ← Arşiv web arayüzü (damgala/doğrula/geçmiş)
│   ├── turkdamga-image-verify.html ← Görsel damgalama & 3 katmanlı arama
│   ├── turkdamga-user-panel.html   ← Kullanıcı paneli (özet, damgalar, arama, API ayarı)
│   └── vercel.json                   ← HSTS, CSP ve diğer güvenlik HTTP başlıkları
├── backend/
│   ├── app/                          ← FastAPI uygulaması (main, config, db yardımcıları)
│   ├── requirements.txt              ← pip bağımlılıkları
│   ├── .env.example                  ← Örnek ortam değişkenleri
│   ├── alembic.ini                   ← Alembic (DB migrasyonları)
│   ├── alembic/versions/             ← stamp_subjects, wholesale / kredi tabloları
│   ├── TurkDamga-Backend.md        ← FastAPI + PostgreSQL tam kaynak kod
│   │   İçeriği:
│   │   ├── app/main.py               FastAPI uygulama girişi
│   │   ├── app/config.py             Ayarlar (.env)
│   │   ├── app/database.py           Async PostgreSQL bağlantısı
│   │   ├── app/models/               SQLAlchemy modeller
│   │   ├── app/schemas/              Pydantic şemalar
│   │   ├── app/routers/              API endpoint'leri
│   │   │   ├── auth.py               JWT + API key kimlik doğrulama
│   │   │   ├── stamps.py             Damgalama endpoint'leri
│   │   │   ├── verify.py             Public doğrulama
│   │   │   └── webhooks.py           Webhook yönetimi
│   │   └── app/services/             İş mantığı
│   │       ├── polygon.py            EVM tabanlı zincir TX (servis modülü)
│   │       ├── opentimestamps.py     Zaman damgası (OTS) doğrulama
│   │       └── webhook_dispatcher.py HMAC + retry
│   └── TurkDamga-ImageStamp-Backend.md ← Görsel damgalama backend
│       İçeriği:
│       ├── image_fingerprint.py      SHA-256 + pHash + CLIP embedding
│       ├── search_service.py         pgvector 3 katmanlı arama
│       └── router_images.py          FastAPI görsel endpoint'leri
├── android/
│   └── TurkDamga-Android.md        ← React Native / Expo Android uygulaması
│       İçeriği:
│       ├── App.tsx                   Navigation (3 sekme)
│       ├── src/screens/
│       │   ├── StampScreen.tsx       Dosya seç + damgala
│       │   ├── HistoryScreen.tsx     Geçmiş listesi
│       │   └── VerifyScreen.tsx      Hash doğrulama
│       ├── src/engine/timestamp.ts   SHA-256 + blockchain + AsyncStorage
│       └── src/theme.ts              Renk/stil değişkenleri
├── docs/
│   ├── Deployment-Yol-Haritasi.md    ← Sıfırdan production'a tam rehber
│   ├── Arsiv-Mimari.md               ← Belge saklama, nesne depo, presigned akış
│   ├── Arama-ve-TC-Erisim-Mimarisi.md ← Gelişmiş arama, TC ile erişim, KVKK çerçeve
│   ├── Toptan-Satis-Kredi-Kontrat.md   ← Toptan satış: coin, kredi, kontrat, B2B API
│   └── KVKK-Vertical-Damgalama.md      ← Müzik, mimari, görsel, hasta arşivi, belediye / KVKK
│       İçeriği:
│       ├── Domain satın alma         Cloudflare Registrar
│       ├── Sunucu kurulum            Hetzner CPX41 + AWS RDS
│       ├── Backend deploy            Docker + Nginx + SSL
│       ├── Frontend deploy           Vercel
│       ├── Blockchain RPC kurulum    Alchemy + cüzdan (EVM)
│       ├── Play Store yayınlama      EAS Build + Google Console
│       └── Güvenlik & izleme        Sentry + BetterStack
├── infra/
│   ├── docker-compose.yml   PostgreSQL 16 + Redis 7 (yalnızca localhost’a bağlı portlar)
│   ├── .env.example
│   └── nginx/               Kenar sunucu için örnek Nginx + güvenlik başlıkları
├── SECURITY.md              Güvenlik ilkeleri, CSP/Vercel notları, olay müdahalesi
└── README.md
```

Statik ön yüz Vercel’de `frontend/vercel.json` ile HSTS ve CSP başlıkları alır.

## API Endpoint Özeti

```
POST   /api/v1/auth/register       Kayıt
POST   /api/v1/auth/login          JWT (username veya e-posta)
GET    /api/v1/auth/me             Oturum özeti + `credit_balance`, damga başına `stamp_credit_cost` (GAS×çarpan)
POST   /api/v1/auth/api-keys       API anahtarı oluştur (ham anahtar yalnızca bir kez)
GET    /api/v1/auth/api-keys       Anahtar listesi
DELETE /api/v1/auth/api-keys/{id}  Anahtarı iptal et

POST   /api/v1/stamps/             Damgala (kredi düşümü: `POLYGON_GAS_COST_CENTS_ESTIMATE × 10` sabit; yetersizse **402**; isteğe bağlı `idempotency_key`, `subject_tc`; webhook yalnızca yeni kayıtta)
GET    /api/v1/stamps/             Liste
GET    /api/v1/stamps/{id}         Detay
GET    /api/v1/verify/{hash}       Public hash doğrulama (JWT gerekmez, ~120/dk/IP)

POST   /api/v1/images/stamp        Görsel damgala
POST   /api/v1/images/search       3 katmanlı görsel arama
GET    /api/v1/images/search       Hash ile hızlı arama

GET    /api/v1/search/stamps       Birleşik arama (scope=self|by_verified_subject, ~60/dk/IP)
POST   /api/v1/admin/subject-stamps/lookup  Kurumsal TC→parmak izi damga listesi (org_admin/superadmin, ~10/saat/IP)

POST   /api/v1/b2b/contracts           Toptan kontrat (superadmin)
POST   /api/v1/b2b/credits/allocate      Kurum kredisi yükle
GET    /api/v1/b2b/credits/balance/me    Kurumsal kredi bakiyesi (panel)

POST   /api/v1/webhooks/           Webhook oluştur (secret yalnızca bir kez; HMAC imza)
GET    /api/v1/webhooks/           Listele
DELETE /api/v1/webhooks/{id}       Sil
GET    /health                     Sağlık kontrolü
```

## Yerel çalıştırma (ön yüz)

Docker zorunlu değil. Repo kökünde:

```bash
python -m http.server 8765 --bind 127.0.0.1 --directory frontend
```

Tarayıcıda örnek: `http://127.0.0.1:8765/turkdamga-landing.html` — Arşiv: `turkdamga-arsiv-ui.html`, Panel: `turkdamga-user-panel.html`.

**Veri katmanı (isteğe bağlı):** [Docker Desktop](https://www.docker.com/products/docker-desktop/) kuruluysa `infra/.env` oluşturup (`infra/.env.example` kopyası) `docker compose -f infra/docker-compose.yml up -d` ile PostgreSQL ve Redis yerelde ayağa kalkar. Bu makinede Docker bulunamadıysa yalnızca statik HTML ile devam edebilirsiniz.

## Test

```bash
pip install -r backend/requirements.txt   # FastAPI /health testi için (bir kez)
python -m unittest discover -s tests -v
```

Duman testleri: `backend/app` ve Alembic `*.py` derlemesi, ön yüz HTML, `docs/` varlığı; bağımlılıklar yüklüyse FastAPI `/health` uçları.

## Kurulum

```bash
# Backend (FastAPI iskeleti — backend/app)
cd backend
pip install -r requirements.txt
# İsteğe bağlı: cp .env.example .env  ve DATABASE_URL ekleyin (PostgreSQL)
# Şema: alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Android
npx create-expo-app TurkDamgaApp --template blank-typescript
npx expo run:android
```

## Aylık Maliyet
~$284/ay (Hetzner + AWS RDS + Alchemy + Vercel + Cloudflare)

## Teknoloji Stack
- Backend: Python / FastAPI / PostgreSQL / pgvector / Redis
- Blockchain: TurkDamga tek kanıt katmanı (EVM + OTS; ayrıntı `backend/TurkDamga-Backend.md`)
- AI: CLIP ViT-B/32 (görsel embedding)
- Frontend: Vanilla JS / HTML5
- Android: React Native / Expo
- Deploy: Docker / Nginx / Vercel / Cloudflare
