# TurkDamga — Arşiv ve belge saklama mimarisi

Bu belge, taranan veya yüklenen belgelerin **nerede** tutulacağını ve zaman damgası (operasyonel: Polygon + OpenTimestamps) ile birlikte **arşivleme altyapısının** nasıl kurgulanacağını tanımlar. Mevcut `Stamp` / görsel damga tasarımıyla uyumludur. **Müşteri tarafında** damgalama genelde **kredi** ile faturalandırılır; gas likiditesi treasury’de tutulur — bkz. `docs/Toptan-Satis-Kredi-Kontrat.md` §0.

---

## 1. İki ayrı sorumluluk

| Katman | İçerik | Amaç |
|--------|--------|------|
| **İlişkisel kayıt (PostgreSQL)** | `file_hash`, `file_name`, `file_size`, `file_type`, kullanıcı, etiketler, zincir alanları (`polygon_tx`, `ots_*`), **depo referansı** | Sorgu, kota, doğrulama, iş akışı, denetim |
| **Nesne depo (object storage)** | Orijinal dosya baytları (PDF, JPEG, TIFF vb.) | Uzun ömür, büyük hacim, ucuz GB, coğrafi dayanıklılık |

**Kural:** Zaman damgası **hash** üzerinden yapılır; hash üretimi ile dosyanın nesne depoya yazılması arasındaki sıra ve tutarlılık iş kurallarında net tanımlanmalıdır (aşağıda).

---

## 2. Nesne depo seçimi

Önerilen: **S3 uyumlu** servis (AWS S3, Cloudflare R2, Wasabi, Backblaze B2, MinIO, Hetzner Object Storage).

- **Şifreleme:** sunucu tarafı (SSE-S3 veya SSE-KMS); gerekirse ek olarak uçtan uca (müşteri anahtarı).
- **Erişim:** varsayılan **private** bucket; indirme/yükleme için **presigned URL** veya arka planda çalışan iç servis hesabı.
- **Sürümleme:** bucket versioning açık — yanlışlıkla üzerine yazma veya silmede kurtarma.
- **Hukuki / uzun süreli arşiv:** sağlayıcı destekliyorsa **Object Lock (WORM)** ve yaşam döngüsü (Standard → IA → Glacier benzeri sınıf).

`SECURITY.md` ve `infra/docker-compose.yml` ile uyum: üretimde Postgres/Redis yönetilen hizmet veya sert ağ segmentasyonu; sırlar `.env` / gizli kasada.

---

## 3. Anahtar (object key) şeması

Tekil ve denetlenebilir isimlendirme örnekleri:

```
{tenant_or_user_id}/{stamp_id}/original{uzantı}
```

veya **içerik adresli** (aynı dosyanın tekrarını önlemek için):

```
blobs/sha256/{ilk2_hex}/{kalan62_hex}
```

**Öneri:** `stamp_id` (UUID) + path’te **hash** kullanın; böylece DB satırı ile depo nesnesi bire bir eşlenir ve migrasyon kolaylaşır.

Örnek:

```
cv-prod/019b2c4e-.../a3f5.../original.pdf
```

---

## 4. Veritabanı genişletmesi (önerilen alanlar)

Mevcut `stamps` (ve görsel damga tablosu) tasarımına eklenebilecek alanlar:

| Alan | Tip | Açıklama |
|------|-----|----------|
| `storage_provider` | `varchar(32)` | `s3`, `r2`, `minio`, … |
| `storage_bucket` | `varchar(255)` | Kovası adı (çok kiracılı yapıda tenant bazlı kova mümkün) |
| `storage_key` | `varchar(1024)` | Nesne anahtarı (path) |
| `storage_version_id` | `varchar(128)` nullable | S3 versioning ID |
| `storage_etag` | `varchar(64)` nullable | Bütünlük kontrolü için |
| `storage_bytes` | `bigint` | Nesnedeki bayt (isteğe bağlı; `file_size` ile çakışmaması için tek kaynak seçin) |
| `storage_sse_mode` | `varchar(20)` nullable | `sse-s3`, `sse-kms` |
| `ingest_status` | `varchar(20)` | `pending_upload` → `stored` → `stamped` → `failed` |
| `content_sha256_verified_at` | `timestamptz` nullable | Depodan okunan içerik ile hash eşleşmesi doğrulandığında |

**Not:** `file_hash` zaten kanıtın parçasıdır; depoya yazılan dosyanın baytlarından tekrar hesaplanan hash ile DB’deki hash **eşleşmeli** (`ingest_status = stored` öncesi veya sonrası doğrulama job’ı).

---

## 5. Yükleme akışları

### 5.1 Sunucu üzerinden (basit, küçük dosyalar)

1. İstemci `multipart` ile API’ye gönderir.
2. API geçici bellek / sınırlı disk buffer ile MIME ve boyut kontrolü, isteğe bağlı AV taraması.
3. Hash üretilir → **önce** veya **sonra** nesne depoya yazım (tercihen: stream sırasında hash, tek geçişte hem hash hem upload).
4. DB kaydı + arka planda Polygon/OTS işleri (Celery kuyruğu önerilir).

**Risk:** büyük dosyalarda API bellek ve zaman aşımı; tercihen 5.2.

### 5.2 Presigned PUT (ölçeklenebilir)

1. İstemci: “yükleme oturumu” ister (`POST /api/v1/uploads` veya damga öncesi `intent`).
2. API: `storage_key`, `content_type`, **kısa ömürlü** presigned PUT URL döner; DB’de `ingest_status=pending_upload`.
3. İstemci dosyayı **doğrudan** nesne depoya yükler.
4. İstemci veya depo **event** (S3 Event Notification → kuyruk) ile API’ye “yükleme tamam” bildirir; worker dosyayı okuyup hash doğrular, `ingest_status=stored`, sonra damgalama kuyruğuna alır.

**Avantaj:** API sunucusu dosya trafiğini taşımaz; CDN/edge ile uyum kolay.

### 5.3 Müşteri kovası (BYOB)

Müşteri kendi IAM / R2 token’ını verir; TurkDamga yalnızca hash ve damgayı tutar. Uyumluluk ve destek maliyeti yüksektir; kurumsal segment için ayrı ürün paketi olarak düşünülebilir.

---

## 6. Zaman damgası sırası (tutarlılık)

İki güvenli seçenek:

**A — Önce depo, sonra zincir**

1. Nesne `stored` ve hash doğrulandı.
2. Aynı hash ile Polygon/OTS gönderimi.
3. Başarısızlıkta: nesne silinmez; `stamped` yeniden denenebilir (idempotent iş kuralları).

**B — Önce hash taahhüdü (commitment)**

1. Yalnızca hash ile zincire iş (daha az yaygın belge senaryosunda).
2. Depo asenkron dolar — yasal olarak “içerik aynı mı?” sorusu için A genelde daha anlaşılır.

Ürün politikası olarak **A** önerilir: “arşivde saklanan bayt” ile “damgalanan hash” aynı doğrulama zincirinde birleşir.

---

## 7. Okuma ve silme

- **İndirme:** kısa süreli presigned GET veya arka uçta yetki kontrolü sonrası stream.
- **Liste / arama:** PostgreSQL + pgvector (görsel arama); nesne depo yalnızca `storage_key` ile çağrılır.
- **Silme:** yumuşak silme (`deleted_at` + depoda lifecycle veya etiket); KVKK için **anonimleştirme** ile metadata kalıp nesne silinebilir — hukuk onayı ile politika yazın.

---

## 8. Yedekleme ve felaket

| Bileşen | Öneri |
|---------|--------|
| PostgreSQL | Sürekli yedek (PITR), haftalık tam image, farklı bölgede kopya |
| Nesne depo | Cross-region replication veya ikincil kova + lifecycle |
| OTS / Polygon | Zincir üzerinde kalıcı; DB’de TX ve OTS artefaktı yedeklenir |

RPO/RTO hedeflerini (ör. RPO 1 saat, RTO 4 saat) dokümante edin.

---

## 9. Ortam değişkenleri (örnek)

```env
STORAGE_PROVIDER=s3
S3_ENDPOINT=https://s3.eu-central-1.amazonaws.com
S3_REGION=eu-central-1
S3_BUCKET=cv-prod-archive
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
# veya IRSA / OIDC ile rol tabanlı erişim (tercih edilir)
```

R2 için `S3_ENDPOINT` R2’nin S3 API uç noktası olur; uygulama kodu aynı boto3 / aioboto3 soyutlaması ile kalır.

---

## 10. Özet

- **Belgeler (binary):** S3 uyumlu nesne depo; **metadata + hash + damga:** PostgreSQL.
- **Yükleme:** mümkün olduğunca **presigned PUT** + **hash doğrulama** job’ı.
- **Tablo:** `storage_provider`, `storage_bucket`, `storage_key`, versioning/etag, `ingest_status`.
- **Güvenlik ve uyum:** `SECURITY.md`; altyapı iskeleti `infra/` altında.

Bu dosya, `TurkDamga-Backend.md` içindeki model ve endpoint’lere alan eklenmesi için referanstır; şema değişikliği için Alembic migrasyonu ayrıca üretilmelidir.
