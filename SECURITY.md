# TurkDamga — Güvenlik ve altyapı ilkeleri

Bu belge ürünün güvenlik sınırını tanımlar: kenar (CDN/Nginx), API, veri ve sırlar.

## Güvenlik açığı bildirimi

Lütfen açıklanmadan önce doğrudan proje sahipleriyle iletişime geçin. Kamuya açıklama, düzeltme veya geçici önlem onaylandıktan sonra yapılmalıdır.

## Mimari özeti

| Katman | Rol |
|--------|-----|
| CDN (ör. Cloudflare) | DDoS azaltma, WAF kuralları, bot koruması, TLS |
| Nginx | TLS sonlandırma, oran sınırlama, güvenlik başlıkları, statik veya ters vekil |
| API (FastAPI) | Kimlik doğrulama, iş mantığı, girdi doğrulama, CORS |
| PostgreSQL / Redis | Ağ izolasyonu, kimlik bilgisi ile erişim |

`infra/docker-compose.yml` yalnızca PostgreSQL ve Redis sağlar; bağlantı noktaları varsayılan olarak `127.0.0.1` ile sınırlandırılmıştır (aynı makineden erişim).

## Zorunlu uygulamalar

1. **Sırlar:** `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `SECRET_KEY`, blok zinciri özel anahtarları asla depoya yazılmaz. Üretimde gizli yönetimi (ör. AWS Secrets Manager, HashiCorp Vault, Cloudflare Workers secrets) kullanın.
2. **TLS:** Herkese açık trafik HTTPS; HSTS etkin (Vercel `vercel.json` ve Nginx şablonunda tanımlı).
3. **API anahtarları:** Ham API anahtarını yalnızca bir kez gösterin; veritabanında yalnızca hash saklayın (tasarım `TurkDamga-Backend.md` ile uyumlu).
4. **CORS:** `ALLOWED_ORIGINS` yalnızca bilinen ön yüz kökenlerini içersin; geliştirmede `*` kullanmayın.
5. **Oran sınırlama:** SlowAPI / Redis ile kimlik doğrulama ve damgalama uçları sınırlandırılmalıdır.
6. **Webhook:** Giden isteklerde HMAC; gelen imza doğrulaması ve yeniden deneme üst sınırı.
7. **Güncellemeler:** Temel imajlar (Postgres, Redis, Nginx) ve Python bağımlılıkları düzenli yenilenmelidir.

## Ön yüz (statik HTML)

- `frontend/vercel.json` güvenlik başlıkları ve bir CSP içerir; API adresiniz farklıysa `connect-src` değerini güncelleyin.
- Satır içi betik ve stil nedeniyle CSP’de `unsafe-inline` kullanılmıştır; ileride nonce veya küçük paketleyici ile sıkılaştırılabilir.

## Nginx şablonu

`infra/nginx/` altındaki dosyalar örnektir: `server_name`, SSL sertifika yolları ve `upstream` hedefini ortamınıza göre düzenleyin. API konteyneri eklendiğinde `upstream` içinde Docker servis adını kullanın.

## Yerel veri katmanı

```bash
cd infra
cp .env.example .env
# .env içinde güçlü parolalar tanımlayın
docker compose up -d
```

Üretimde Postgres/Redis’i yönetilen hizmet (RDS, ElastiCache vb.) ile değiştirmeniz ve şifreleri platform gizli deposundan beslemeniz önerilir.

## Olay müdahalesi (kısa kontrol listesi)

- Şüpheli API anahtarı: anahtarı devre dışı bırakın, audit log inceleyin, gerekirse zincir ücreti cüzdanını dondurun.
- Veritabanı sızıntısı: erişimi kesin, parolaları döndürün, yedekten doğrulanmış kopya ile kıyaslayın.
- DDoS: CDN/WAF kuralları, oran sınırları, origin IP gizleme.
