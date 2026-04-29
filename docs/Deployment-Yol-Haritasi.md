# TurkDamga + Masalcı — Kurumsal Deployment Yol Haritası
## Sıfırdan Production'a Tam Rehber

---

## Genel Mimari (Hedef)

```
Internet
    │
    ├── masalci.com          → Cloudflare CDN → Vercel (Frontend)
    ├── turkdamga.app      → Cloudflare CDN → Vercel (Frontend)
    └── api.turkdamga.app  → Cloudflare → AWS/Hetzner (Backend)
                                              ├── FastAPI (Docker)
                                              ├── PostgreSQL (RDS)
                                              ├── Redis (ElastiCache)
                                              └── pgvector
```

---

# AŞAMA 1 — DOMAIN (1-2 Gün)

## 1.1 Domain Satın Alma

**Önerilen kayıt şirketi:** Cloudflare Registrar (en ucuz, gizlilik ücretsiz)
→ https://cloudflare.com/products/registrar

**Satın alınacak domainler:**
```
masalci.com          ~$10/yıl   (varsa: masalci.io, masalci.app)
turkdamga.app      ~$14/yıl
turkdamga.io       ~$35/yıl   (yedek)
```

**Cloudflare'e ekle:**
1. Cloudflare hesabı aç → Add Site
2. Domain nameserver'larını Cloudflare'e yönlendir
3. SSL/TLS → Full (Strict) seç
4. "Always Use HTTPS" → ON
5. HSTS → ON (max-age: 1 yıl)

## 1.2 DNS Yapısı

```
masalci.com          A    →  Vercel IP (otomatik)
www.masalci.com      CNAME→  cname.vercel-dns.com
api.masalci.com      A    →  Sunucu IP

turkdamga.app      A    →  Vercel IP
www.turkdamga.app  CNAME→  cname.vercel-dns.com
api.turkdamga.app  A    →  Sunucu IP
```

---

# AŞAMA 2 — SUNUCU ALTYAPISI (2-3 Gün)

## 2.1 Kurumsal Hosting Seçeneği: Hetzner + AWS Hibrit

```
Hetzner (Avrupa, GDPR uyumlu, ucuz güçlü)
  → Ana API sunucusu
  → CPX41: 8 vCPU, 16 GB RAM, 160 GB SSD = ~€27/ay

AWS (yedeklilik ve managed servisler için)
  → RDS PostgreSQL (Multi-AZ)
  → ElastiCache Redis
  → S3 (yedekleme)
  → CloudFront (medya CDN)
```

**Neden Hetzner + AWS?**
- Hetzner: GB başına en ucuz compute (AWS'nin 1/4 fiyatı)
- AWS managed: Veritabanı, cache, backup için güvenilir
- GDPR: Hetzner Frankfurt = AB veri merkezi

## 2.2 Hetzner Sunucu Kurulumu

```bash
# 1. Hetzner Cloud hesabı aç → hetzner.com/cloud
# 2. Proje oluştur: "turkdamga-prod"
# 3. Sunucu oluştur:
#    Location: Nuremberg (veya Helsinki)
#    Image: Ubuntu 24.04 LTS
#    Type: CPX41 (8 vCPU, 16 GB)
#    Networking: Public IPv4 + IPv6
#    SSH Key: kendi public key'ini ekle
#    Firewall: aşağıdaki kurallar

# Firewall kuralları:
# Inbound:
#   22/tcp   → sadece senin IP'n (SSH)
#   80/tcp   → Anywhere (HTTP redirect)
#   443/tcp  → Anywhere (HTTPS)
# Outbound: All
```

## 2.3 Sunucu İlk Kurulum

```bash
# Sunucuya bağlan
ssh root@SUNUCU_IP

# Sistem güncelle
apt update && apt upgrade -y

# Gerekli araçlar
apt install -y \
  docker.io docker-compose-plugin \
  nginx certbot python3-certbot-nginx \
  git curl wget htop ufw fail2ban

# Güvenlik duvarı
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable

# Fail2ban (brute force koruması)
systemctl enable fail2ban
systemctl start fail2ban

# Docker grubuna ekle
usermod -aG docker $USER

# Deploy kullanıcısı oluştur (root ile çalışma!)
adduser deploy
usermod -aG docker deploy
usermod -aG sudo deploy
```

## 2.4 AWS RDS PostgreSQL (Multi-AZ)

```
AWS Console → RDS → Create Database
  Engine: PostgreSQL 16
  Template: Production
  DB Instance: db.t3.medium (2 vCPU, 4 GB) → başlangıç
  Multi-AZ: Yes (yüksek erişilebilirlik)
  Storage: 100 GB gp3, Auto Scaling ON
  VPC: default (Hetzner'dan erişim için public + SSL zorunlu)
  
Güvenlik Grubu:
  Inbound: 5432/tcp → Hetzner sunucu IP'si

pgvector extension:
  RDS bağlandıktan sonra:
  psql -h RDS_ENDPOINT -U postgres turkdamga
  CREATE EXTENSION IF NOT EXISTS vector;

Maliyet: ~$50-80/ay (Multi-AZ db.t3.medium)
```

## 2.5 AWS ElastiCache Redis

```
AWS Console → ElastiCache → Redis OSS
  Node type: cache.t3.medium
  Replicas: 2 (yüksek erişilebilirlik)
  Multi-AZ: Yes
  Encryption: At-rest + In-transit
  
Maliyet: ~$30/ay
```

---

# AŞAMA 3 — BACKEND DEPLOY (3-5 Gün)

## 3.1 Docker Compose (Production)

```yaml
# /home/deploy/turkdamga/docker-compose.prod.yml

version: '3.9'

services:

  api:
    image: turkdamga-api:latest
    restart: always
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - SECRET_KEY=${SECRET_KEY}
      - POLYGON_RPC_URL=${POLYGON_RPC_URL}
      - POLYGON_PRIVATE_KEY=${POLYGON_PRIVATE_KEY}
      - REDIS_URL=${REDIS_URL}
      - ALLOWED_ORIGINS=https://turkdamga.app,https://masalci.com
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '4'

  worker:
    image: turkdamga-api:latest
    restart: always
    command: celery -A app.celery worker --loglevel=info --concurrency=4
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - POLYGON_RPC_URL=${POLYGON_RPC_URL}
      - POLYGON_PRIVATE_KEY=${POLYGON_PRIVATE_KEY}

  beat:
    image: turkdamga-api:latest
    restart: always
    command: celery -A app.celery beat --loglevel=info
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}

  nginx:
    image: nginx:alpine
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
      - /var/www/certbot:/var/www/certbot:ro
    depends_on:
      - api
```

## 3.2 Dockerfile

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Sistem bağımlılıkları (CLIP için)
RUN apt-get update && apt-get install -y \
    libpq-dev gcc g++ curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# CLIP modelini build sırasında indir (cold start önleme)
RUN python -c "from transformers import CLIPModel, CLIPProcessor; \
    CLIPModel.from_pretrained('openai/clip-vit-base-patch32'); \
    CLIPProcessor.from_pretrained('openai/clip-vit-base-patch32')"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
```

## 3.3 Nginx Konfigürasyonu

```nginx
# nginx.conf
events { worker_connections 1024; }

http {
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=30r/m;
    limit_req_zone $binary_remote_addr zone=search:10m rate=10r/m;

    # Gzip
    gzip on;
    gzip_types application/json;

    # API sunucusu
    server {
        listen 80;
        server_name api.turkdamga.app;
        return 301 https://$host$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name api.turkdamga.app;

        ssl_certificate     /etc/letsencrypt/live/api.turkdamga.app/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/api.turkdamga.app/privkey.pem;
        ssl_protocols       TLSv1.2 TLSv1.3;
        ssl_ciphers         HIGH:!aNULL:!MD5;

        # Security headers
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Frame-Options DENY always;
        add_header X-Content-Type-Options nosniff always;
        add_header X-XSS-Protection "1; mode=block" always;

        # Max upload (görsel için)
        client_max_body_size 55M;

        location / {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://api:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 120s;
        }

        location /api/v1/images/search {
            limit_req zone=search burst=5 nodelay;
            proxy_pass http://api:8000;
            proxy_set_header Host $host;
            proxy_read_timeout 180s;  # CLIP için uzun timeout
        }
    }
}
```

## 3.4 SSL Sertifikası (Let's Encrypt)

```bash
# Sunucuda çalıştır
certbot certonly --nginx \
  -d api.turkdamga.app \
  --email admin@turkdamga.app \
  --agree-tos \
  --non-interactive

# Otomatik yenileme (crontab)
echo "0 3 * * * certbot renew --quiet && docker compose restart nginx" | crontab -
```

## 3.5 CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker image
        run: docker build -t turkdamga-api:${{ github.sha }} .

      - name: Push to registry
        run: |
          echo ${{ secrets.DOCKER_PASSWORD }} | \
            docker login -u ${{ secrets.DOCKER_USERNAME }} --password-stdin
          docker tag turkdamga-api:${{ github.sha }} \
            yourdockerhub/turkdamga-api:latest
          docker push yourdockerhub/turkdamga-api:latest

      - name: Deploy to server
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.SERVER_IP }}
          username: deploy
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /home/deploy/turkdamga
            docker compose -f docker-compose.prod.yml pull
            docker compose -f docker-compose.prod.yml up -d --no-deps api worker
            docker compose -f docker-compose.prod.yml exec -T api \
              alembic upgrade head
            echo "Deploy tamamlandı: $(date)"
```

---

# AŞAMA 4 — FRONTEND DEPLOY (1 Gün)

## 4.1 Vercel (Masalcı + TurkDamga)

```bash
# Vercel CLI kur
npm i -g vercel

# Masalcı deploy
cd masalci-frontend
vercel --prod
# Domain ekle: masalci.com

# TurkDamga deploy
cd turkdamga-frontend
vercel --prod
# Domain ekle: turkdamga.app
```

**Vercel Dashboard'da:**
```
Settings → Domains:
  masalci.com       → Production
  www.masalci.com   → Redirect to masalci.com
  
  turkdamga.app   → Production
  www.turkdamga.app → Redirect to turkdamga.app

Environment Variables:
  NEXT_PUBLIC_API_URL = https://api.turkdamga.app
```

## 4.2 Cloudflare Ayarları

```
Her domain için:
  SSL/TLS: Full (Strict)
  Speed → Optimization:
    Auto Minify: JS, CSS, HTML → ON
    Brotli: ON
  Caching:
    Browser Cache TTL: 1 year (static assets)
    Cache Level: Standard
  Security:
    Security Level: Medium
    Bot Fight Mode: ON
    WAF: ON (Pro plan önerilir)
```

---

# AŞAMA 5 — POLYGON CÜZDAN KURULUMU (1 Gün)

## 5.1 Production Cüzdan

```bash
# Özel cüzdan oluştur (MetaMask veya hardhat)
# KESİNLİKLE:
# - Private key'i .env'e yaz, asla git'e ekleme
# - Cüzdana minimum MATIC koy (aylık tahmini gas)
# - Ayrı bir "hot wallet" kullan, kişisel cüzdanı kullanma

# MATIC tahmini maliyet:
# 1 damgalama = ~0.001 MATIC = ~$0.0006
# 10.000 damgalama/ay = 10 MATIC = ~$6/ay
```

## 5.2 Alchemy RPC (Güvenilir, Kurumsal)

```
1. alchemy.com → Sign up
2. Create App:
   Network: Polygon Mainnet
   Name: turkdamga-prod
3. API Key al
4. .env'e ekle:
   POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY

Alchemy özellikleri:
  - 99.9% uptime SLA
  - Aylık 300M compute units ücretsiz
  - Webhook (TX onayı bildirimi)
  - Growth plan: $49/ay (sınırsız)
```

## 5.3 .env Production

```env
# /home/deploy/turkdamga/.env
# Bu dosyayı git'e EKLEME — .gitignore'a ekle

DATABASE_URL=postgresql+asyncpg://user:pass@RDS_ENDPOINT:5432/turkdamga
SECRET_KEY=en_az_64_karakter_rastgele_string_buraya
ALGORITHM=HS256

POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/API_KEY
POLYGON_PRIVATE_KEY=0xPRIVATE_KEY_BURAYA
POLYGON_CHAIN_ID=137

REDIS_URL=redis://ELASTICACHE_ENDPOINT:6379/0

ALLOWED_ORIGINS=https://turkdamga.app,https://masalci.com

# Opsiyonel
SENTRY_DSN=https://...@sentry.io/...   # Hata takibi
```

---

# AŞAMA 6 — ANDROID APK / PLAY STORE (5-7 Gün)

## 6.1 Google Play Developer Hesabı

```
1. play.google.com/console → Hesap aç
2. Tek seferlik kayıt ücreti: $25
3. Kimlik doğrulama: 1-3 gün sürer
4. Ödeme profili oluştur (Türkiye için)
```

## 6.2 Expo ile Production Build

```bash
# EAS CLI kur
npm install -g eas-cli

# Giriş yap
eas login

# eas.json oluştur
cat > eas.json << 'EOF'
{
  "cli": { "version": ">= 10.0.0" },
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal"
    },
    "preview": {
      "distribution": "internal",
      "android": { "buildType": "apk" }
    },
    "production": {
      "android": { "buildType": "aab" }
    }
  },
  "submit": {
    "production": {
      "android": {
        "serviceAccountKeyPath": "./google-services.json",
        "track": "internal"
      }
    }
  }
}
EOF

# Production AAB build (Play Store için)
eas build --platform android --profile production

# Build bitti → .aab dosyası indir
```

## 6.3 Play Store Uygulama Oluşturma

```
Play Console → Create app:
  App name: TurkDamga
  Default language: Turkish
  App or game: App
  Free or paid: Free (başlangıç)

Zorunlu bilgiler:
  ├── App icon: 512x512 PNG
  ├── Feature graphic: 1024x500 PNG
  ├── Screenshots: min 2 adet (telefon)
  ├── Short description: max 80 karakter
  ├── Full description: max 4000 karakter
  ├── Privacy Policy URL: turkdamga.app/privacy
  └── Content rating: Herkese uygun

Release:
  Internal testing → Closed testing → Production
  (Her aşama 1-3 gün onay sürer)
```

## 6.4 Play Store Onay Süreci

```
İç Test (Internal)     → Anında (ekip üyeleri)
Kapalı Test (Closed)   → 1-3 gün inceleme
Açık Test (Open)       → 1-3 gün inceleme
Üretim (Production)    → 3-7 gün inceleme (ilk uygulama)

Toplam: ~2 hafta (ilk kez)
Sonraki güncellemeler: 1-3 gün
```

---

# AŞAMA 7 — GÜVENLİK & İZLEME (2 Gün)

## 7.1 Sentry (Hata Takibi)

```bash
pip install sentry-sdk[fastapi]

# app/main.py'a ekle:
import sentry_sdk
sentry_sdk.init(
    dsn=settings.sentry_dsn,
    traces_sample_rate=0.2,
    environment="production",
)
```

## 7.2 Uptime İzleme

```
BetterStack (betterstack.com):
  - Her 1 dakika ping
  - SMS + Email + Slack uyarı
  - Public status sayfası
  - Ücretsiz plan yeterli

Eklenecek URL'ler:
  https://api.turkdamga.app/health
  https://turkdamga.app
  https://masalci.com
```

## 7.3 Yedekleme

```bash
# PostgreSQL otomatik yedek (crontab)
# Her gece 02:00'de S3'e yedek

cat > /home/deploy/backup.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
PGPASSWORD=$DB_PASS pg_dump \
  -h $DB_HOST -U $DB_USER $DB_NAME \
  | gzip \
  | aws s3 cp - s3://turkdamga-backups/db-$DATE.sql.gz
echo "Yedek tamamlandı: $DATE"
EOF

chmod +x /home/deploy/backup.sh
echo "0 2 * * * /home/deploy/backup.sh" | crontab -
```

## 7.4 Güvenlik Checklist

```
✓ SSL: Let's Encrypt (otomatik yenileme)
✓ HSTS: max-age 1 yıl
✓ Firewall: sadece 80/443 açık
✓ Fail2ban: SSH brute force koruması
✓ Private key: .env'de, git'te asla yok
✓ DB: sadece sunucu IP erişilebilir
✓ Rate limiting: Nginx + SlowAPI
✓ CORS: sadece kendi domainler
✓ Dependency audit: pip audit
✓ Docker: root olmayan kullanıcı
```

---

# MALIYET ÖZETİ (Aylık)

```
Hetzner CPX41 (API sunucu)    ~€27    (~$29)
AWS RDS PostgreSQL Multi-AZ   ~$65
AWS ElastiCache Redis          ~$30
Cloudflare Pro (2 domain)     ~$40
Alchemy Polygon RPC           ~$49
Vercel Pro (2 frontend)       ~$40
BetterStack izleme            ~$0    (ücretsiz)
AWS S3 yedekleme              ~$5
Sentry (hata takibi)          ~$26
─────────────────────────────────────
TOPLAM                        ~$284/ay

Domain (yıllık):
  masalci.com                 ~$10/yıl
  turkdamga.app             ~$14/yıl

Play Store (tek seferlik):    $25
```

---

# ZAMAN ÇİZELGESİ

```
Hafta 1
  Gün 1-2: Domain + Cloudflare kurulum
  Gün 3-4: Sunucu kurulum + Docker
  Gün 5-7: Backend deploy + SSL

Hafta 2
  Gün 8-9:  Frontend Vercel deploy
  Gün 10:   Polygon cüzdan + Alchemy
  Gün 11-12: Test + hata düzeltme
  Gün 13-14: Güvenlik + izleme

Hafta 3
  Gün 15-17: Android build + Play Store hesabı
  Gün 18-21: Play Store materyal hazırlama + yükleme

Hafta 4-5
  Play Store inceleme süreci (~7-14 gün)

TOPLAM: ~5 hafta
```

---

# BAŞLANGIÇ SIRASI (Öncelik)

```
1. ✅ Domain al (Cloudflare) ─────────────── 30 dakika
2. ✅ Hetzner sunucu kur ─────────────────── 2 saat
3. ✅ .env hazırla ───────────────────────── 30 dakika
4. ✅ Docker ile API deploy ──────────────── 3 saat
5. ✅ SSL sertifikası al ─────────────────── 30 dakika
6. ✅ Frontend Vercel'e yükle ────────────── 1 saat
7. ✅ Alchemy hesabı + Polygon cüzdan ────── 1 saat
8. ✅ Test et (tüm endpoint'ler) ─────────── 2 saat
9. ✅ Play Store hesabı aç ───────────────── 1 gün (onay)
10.✅ Android build + yükleme ────────────── 2 gün
```
