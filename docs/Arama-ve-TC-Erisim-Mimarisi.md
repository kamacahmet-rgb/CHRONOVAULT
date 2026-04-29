# TurkDamga — Gelişmiş arama ve TC ile kişi bazlı erişim

Bu belge, sitede **kapsamlı arama** ve **T.C. kimlik numarasına (TC)** göre ilgili kişiye ait tüm damgalamalara erişim ihtiyacını teknik ve uyumluluk açısından tanımlar. **Hukuki danışmanlık değildir**; KVKK ve ilgili mevzuat için mutlaka uzman görüşü alınmalıdır.

---

## 1. Hedef özeti

| İhtiyaç | Açıklama |
|---------|----------|
| Her türlü arama | Metin, tarih aralığı, etiket, dosya türü, hash, proje, kullanıcı, durum (damga onaylı/bekliyor) ve (görsel üründe) **benzer görsel / embedding** araması |
| TC ile kişi kapsamı | Belirli bir gerçek kişiye ait **tüm damgalama kayıtlarının** yetkili bağlamda listelenmesi |

---

## 2. TC ve kişisel veri — zorunlu çerçeve

**T.C. kimlik numarası özel nitelikli kişisel veri kapsamında değerlendirilir;** işlenmesi için açık rıza ve/veya kanunda öngörülen şartlar, **amaç bağlılığı**, **veri minimizasyonu** ve **güvenlik** (Teknik ve İdari Tedbirler) gerekir.

### 2.1 Önerilmeyen: herkese açık TC araması

- TC ile **anonim veya genel internet kullanıcısına** açık arama **uygun değildir** (KVKK, kötüye kullanım, kimlik hırsızlığı riski).
- Doğru model: **kimlik doğrulaması** (giriş) + **yetkilendirme** (yalnızca kendi kayıtları veya hukuken yetkili rol: örn. kurum içi denetçi, mahkeme kararı süreçleri ayrı tanımlanır).

### 2.2 Teknik minimizasyon önerileri

1. **Ham TC’yi veritabanında saklamamak** (mümkünse): sunucu tarafı gizli anahtar ile **tek yönlü türetilmiş tanımlayıcı** (ör. `HMAC-SHA256(server_secret, normalized_tc)`), sorgularda aynı dönüşüm uygulanır. Anahtar rotasyonu planlanır.
2. Alternatif / ek: **şifreli sütun** (KMS ile), erişim denetimi ve maskeleme (loglarda asla düz metin TC yok).
3. **Amaç alanı:** “Bu kayıt bu gerçek kişi adına mı?” sorusu yasal metne dayalı net bir **işleme amacı** ile sınırlanmalıdır.
4. **Denetim:** TC veya türevi ile yapılan her listeleme **audit log** (kim, ne zaman, hangi kapsam).

---

## 3. “Her türlü arama” — bileşenler

### 3.1 Yapısal / filtre araması (PostgreSQL)

Önerilen indekslenebilir alanlar (mevcut şemaya uyumlu genişletme):

- `file_hash`, `file_name` (prefix / `ILIKE` sınırlı), `file_type`, `created_at`, `polygon_status`, `ots_status`
- `tags` (JSONB + GIN), `author`, `project`, `description`
- `user_id` (hesap sahibi), kurumsal modelde `organization_id`

**Tam metin:** `description`, `file_name`, serbest metin alanları için `tsvector` + `GIN` (Türkçe dil desteği için PostgreSQL `text search config` seçimi).

### 3.2 Görsel arama (mevcut ürün hattı)

`TurkDamga-ImageStamp-Backend.md` ile uyumlu: **SHA-256**, **pHash**, **CLIP embedding** + **pgvector** — “benzer belge / benzer görsel” araması.

### 3.3 Birleşik arama API’si (taslak)

Tek uç nokta, yetkiye göre kapsam kısıtlanır:

```
GET /api/v1/stamps/search?q=...&from=&to=&tags=&status=&mime=&cursor=
```

- `q`: genel metin (full-text + güvenli hash tam eşleşme ayrı parametre olabilir: `hash=`)
- Sayfalama: `cursor` veya `limit` + `offset` (büyük tabloda cursor tercih).

Görsel için ayrı:

```
POST /api/v1/images/search
```

---

## 4. TC’ye göre “tüm damgalamalar” — erişim modelleri

### 4.1 Bireysel kullanıcı (en sıkı güvenli senaryo)

- Kullanıcı hesabı **KYC / TC doğrulaması** ile bir kez ilişkilendirilir (doğrulama süreci ayrı ürün akışı; TC mümkünse doğrulama sonrası silinir veya türev saklanır).
- Liste: `GET /api/v1/stamps?scope=me` — sunucu **JWT’deki user_id** ile filtreler; istemci TC göndermez.

### 4.2 Kurumsal: “bu TC’ye bağlı tüm işlemler”

- Yalnızca **kurumsal yönetici** veya **hukuken tanımlı rol** + MFA.
- İstek: `GET /api/v1/admin/stamps/by-subject` gövde veya kısıtlı kanalda **türetilmiş kimlik** veya şifreli eşleşme; yanıtta TC **dönülmez**, yalnızca damga meta verisi ve yetkili gösterim.

### 4.3 Veri modeli taslağı

`stamps` veya ayrı tablo `stamp_subjects`:

| Alan | Not |
|------|-----|
| `subject_tc_fingerprint` | HMAC veya KMS şifreli eş; ham TC yok |
| `subject_binding_verified_at` | Doğrulama zamanı |
| `linked_user_id` nullable | Hesap ile ilişki |

Sorgu: `WHERE subject_tc_fingerprint = :fp AND organization_id = :org` (çok kiracılı).

---

## 5. Ön yüz (site) davranışı

- **Genel arama kutusu:** yalnızca **oturum açılmış** kullanıcı için; sonuçlar sunucunun uyguladığı **scope** ile sınırlı (başkasının damgası dönmez).
- **TC alanı:** asla “herkes TC girsin” formu değil; **doğrulanmış oturum** veya **kurumsal panel** içinde, maskeli gösterim ve hız sınırı (rate limit).
- **Doğrulama (public) hash sayfası:** hash ile public doğrulama mevcut tasarımla uyumlu; TC içermez.

---

## 6. Güvenlik ve performans

- Tüm arama uçları: **auth** + **SlowAPI / Redis** oran sınırlama (TC denemelerine karşı özellikle sıkı).
- `EXPLAIN ANALYZE` ile indeks doğrulaması; büyük metin için arama asenkron veya sonuç üst sınırı.
- **SECURITY.md** ile uyum: loglarda kişisel veri minimizasyonu.

---

## 7. Özet

| Konu | Öneri |
|------|--------|
| Her türlü arama | SQL filtreleri + full-text + pgvector görsel; tek arama API’si + yetki |
| TC ile tüm damgalar | Yalnızca yetkili bağlamda; mümkünse **ham TC saklamadan** türetilmiş kimlik; audit |
| Site | Public TC araması yok; authenticated / kurumsal rol bazlı |

## 8. Backend şablon güncellemesi

Uygulama kaynak şablonu `backend/TurkDamga-Backend.md` içinde güncellendi:

- `app/models/stamp_subject.py`, `Stamp.subjects` ilişkisi
- `User`: `role`, `organization_id`, `subject_tc_fingerprint`, `subject_binding_verified_at`
- `StampRequest.subject_tc` → damga oluştururken `StampSubject` satırı
- `app/services/subject_fingerprint.py` (HMAC parmak izi)
- `app/schemas/search.py`, `app/routers/search.py`, `app/routers/admin_stamps.py`
- `SUBJECT_TC_HMAC_SECRET` ve `Settings.subject_tc_hmac_secret`

**Alembic:** `backend/alembic/versions/20260423_01_stamp_subjects_identity_search.py` eklendi; ayrıntı `TurkDamga-Backend.md` → bölüm *Alembic migrasyonları*.

**Sonraki adım:** Şablonu gerçek `app/` Python dosyalarına taşımak ve `alembic upgrade head` ile veritabanını güncellemek.
