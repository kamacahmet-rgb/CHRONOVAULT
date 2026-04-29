# TurkDamga — Medya ve belge dışı damgalar: sertifika

PDF sözleşme veya rapor dışında **müzik, video, yayın kaydı, tasarım dosyası, stem, proje** gibi varlıklar damgalandığında da üçüncü tarafa veya platforma **“bu içerik bu tarihte bu hash ile damgalandı”** kanıtı sunulmalıdır. Bu belge ürün gereksinimini ve şema/API önerisini tanımlar; **hukuki danışmanlık değildir**.

---

## 1. Amaç

| Durum | İhtiyaç |
|--------|---------|
| Belge (PDF, DOCX…) | Klasik “zaman damgası / bütünlük” sertifikası yeterli. |
| **Medya** (ses, video, görsel ham), **yazılım paketi**, **CAD** | Aynı teknik kanıt (SHA-256 + zincir) + **eser/ürün kimliği** alanları ile **medya sertifikası** veya **ürün damga sertifikası** metni. |

Sertifika; dosyanın içeriğini açıklamaz (hash kanıtı), ancak **dosya adı**, isteğe bağlı **eser/ürün adı**, **içerik türü (vertical)**, **damgalayan** ve **zaman** ile telif / lisans / dağıtım süreçlerinde referans oluşturur.

---

## 2. Sertifikada bulunması gereken alanlar (minimum)

1. **Veren:** TurkDamga (marka / yasal unvan üretimde netleştirilir).
2. **Sertifika türü:** Örn. “Medya ve dijital eser zaman damgası sertifikası” veya “Dijital varlık bütünlük sertifikası”.
3. **Sertifika ID** ve **damgalama zamanı** (UTC + yerel gösterim).
4. **Dosya tanımı:** `file_name`, `file_type` / MIME özeti, `SHA-256` tam hash.
5. **İsteğe bağlı tanıtıcı:** `work_title` (parça adı, bölüm, yayın adı) — KVKK: kişisel veri içerebilir; `docs/KVKK-Vertical-Damgalama.md`.
6. **Dikey / işlem:** `vertical` (`music`, `visual`, …), `processing_purpose` kısa metin.
7. **Blockchain özeti:** İşlem referansı veya doğrulama URL’si (ürün dilinde “TurkDamga blockchain” — `TurkDamga-Backend.md`).
8. **Doğrulama:** Public doğrulama URL’si veya QR yükü (hash ile sorgu).
9. **Yasal feragat:** Sertifika teknik bütünlük ve zaman kanıtı sağlar; telif / mahkeme kabulü ayrı hukuk konusudur (kısa not).

---

## 3. Sunum formatları

| Format | Kullanım |
|--------|----------|
| **PDF + QR** | Dağıtım, basım, ek dosya olarak mağaza / aggregator. |
| **Düz metin (.txt) / JSON** | API otomasyonu, arşiv zip içi `CERTIFICATE.txt`. |
| **PNG görsel sertifika** | Sosyal / mağaza vitrin (isteğe bağlı ürün). |

Öneri: `GET /api/v1/stamps/{id}/certificate?format=pdf|txt|json` — yetkili kullanıcı veya public damga ise `is_public` politikasına göre.

---

## 4. Şema ve arayüz

- **API / DB:** `Stamp` / `StampRequest` üzerinde isteğe bağlı `work_title` (max ~300 karakter). Mevcut `file_name`, `author`, `project`, `description`, `vertical` sertifika şablonunu doldurur.
- **Arşiv UI:** `frontend/turkdamga-arsiv-ui.html` — sürükle-bırak alanında **ürün / proje kategorisi** (`vertical`: mimari-inşaat, yazılım çıktısı, medya vb.); ayrıca “Eser / ürün adı (sertifikada)”; indirilen metin şablonu `vertical` ve `work_title` ile **belge** vs **medya** başlığını seçer.
- **Görsel damga:** `TurkDamga-ImageStamp-Backend.md` / `turkdamga-image-verify.html` — zaten dosya + hash odaklı; sertifika üretimi aynı bloklarla hizalanır.

`backend/TurkDamga-Backend.md` içindeki `StampRequest` / `Stamp` taslakları bu alanla güncellenir; Alembic: `stamps.work_title`.

---

## 5. KVKK ve medya

Müzik / görsel / video metadata’sında **sanatçı adı**, **yüz**, **ses kaydındaki konuşmacı** vb. kişisel veri olabilir. Sertifikada yalnızca **gerekli minimum** alanları gösterin; detay için `docs/KVKK-Vertical-Damgalama.md`.

---

## 6. Özet

- Belge olmayan her damga için de **aynı kanıt paketi + sertifika çıktısı** ürün standardı olmalıdır.
- Fark; şablon metni ve isteğe bağlı **eser/ürün adı** (`work_title`) ile **medya sertifikası** vurgusu.
