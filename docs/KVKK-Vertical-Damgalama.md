# TurkDamga — Sektörel damgalama ve KVKK (Türkiye)

Bu belge; **müzik**, **mimari proje**, **görsel**, **hasta arşivi** ve **belediye belge / ruhsat** gibi kullanım türlerinde zaman damgasının **Kişisel Verilerin Korunması Kanunu (KVKK)** ile uyumlu biçimde tasarlanması için veri sınıfları, hukuki dayanak ilkeleri ve teknik-organizasyonel tedbirleri özetler. **Hukuki danışmanlık değildir**; her sektör için ayrıntılı **aydınlatma metni**, **açık rıza** (gerektiğinde), **VERBİS** ve sözleşmeler için uzman desteği şarttır.

---

## 1. Ortak KVKK ilkeleri (tüm dikeyler)

| İlke | Uygulama yönü |
|------|----------------|
| **Hukuka uygunluk ve dürüstlük** | Damgalama yalnızca tanımlı iş amacı için; hash/metadata işlenmesi amaçla bağlı. |
| **Doğruluk ve güncellik** | Metadata düzeltme politikası; zincirdeki hash değişmez (yeni sürüm = yeni damga). |
| **Belirli, açık ve meşru amaçlar** | `vertical` + `processing_purpose` alanlarında kayıt (şema: `TurkDamga-Backend.md`). |
| **Sınırlı ve ölçülü işleme** | Mümkünse **yalnızca hash**; dosya içeriği arşivde ise ayrı sözleşme ve minimizasyon (`docs/Arsiv-Mimari.md`). |
| **Saklama süresi** | `retention_until` veya kurumsal politika; süre dolunca silme / anonimleştirme. |
| **Bütünlük ve gizlilik** | Şifreleme, erişim kontrolü, log (`SECURITY.md`); hasta arşivinde en sıkı seviye. |

---

## 2. Dikey bazında özet

### 2.1 Müzik

- **Veri:** eser dosyaları, mastering, oturum kayıtları, sözleşmeler; sanatçı / yapımcı **kimliği** metadata’da geçebilir.
- **Öneri:** telif ve lisans işlemleri için **sözleşme** dayanağı; açık rıza gerektiren alanlarda rıza kaydı.
- **Damga:** dosya bütünlüğü + zaman kanıtı; metadata’da `vertical=music`, `work_title` (kişisel veri içerebilir → KVKK).
- **Sertifika:** Belge olmayan medya için de **damga sertifikası** üretilir (parça / yayın adı, hash, zaman); bkz. `docs/Medya-Damga-Sertifikasi.md`.

### 2.2 Mimari proje

- **Veri:** CAD, PDF, görselleştirme, müşteri ve proje adı (ticari sır + kişisel veri riski).
- **Öneri:** kurumsal **imza yetkisi** ve NDA; `vertical=architecture`, proje kodu ile minimizasyon (gerçek kişi adı yerine iç kod).

### 2.3 Görsel (genel)

- **Veri:** görüntü dosyaları; yüz / plaka gibi **kimlik tespiti** mümkün içerik → kişisel veri.
- **Mevcut ürün:** SHA-256 + pHash + CLIP (`TurkDamga-ImageStamp-Backend.md`); arama ve saklama `Arsiv-Mimari` ve `Arama-ve-TC-Erisim-Mimarisi` ile uyumlu.
- **Öneri:** `vertical=visual`; halka açık doğrulama yalnızca **hash** düzeyinde; ham görsel paylaşımı sınırlı.
- **Sertifika:** Tasarım / görsel ürün için `work_title` ile medya sertifikası; `docs/Medya-Damga-Sertifikasi.md`.

### 2.4 Hasta arşivi (özen gösterilmesi gereken alan)

- **KVKK m.6** kapsamında **özel nitelikli kişisel veri** (sağlık) yüksek ihtimalle söz konusudur.
- **Genelde:** **açık rıza** veya kanunda öngörülen diğer şartlar; **KVKK Aydınlatma Metni**; veri işleme sözleşmesi (hastane / klinik / laboratuvar).
- **Teknik:** uçtan uca şifreleme, ayrı **veri işleme ortamı**, erişim **rol + amaç** bazlı, **audit log**, saklama süresi (hizmet + yasal zorunlu süre).
- **Damga:** hash kanıtı sızdırılmaz içerik sırrını çözmez; yine de **işlenen veri seti** ve **erişen kişiler** KVKK envanterine yazılmalıdır.
- **Şema:** `vertical=health_archive`, `data_category=special_health` (işaret); üretimde hukuk onayı olmadan işleme yapılmamalıdır.

#### 2.4.1 Hastane adli dosyaları ve asıl evrak (özellikle vurgu)

- **Arşiv damgalaması yeterli değildir:** Zaman damgası / hash kanıtı, **asıl tıbbi, idari veya adli evrakın** (ör. imzalı rapor, resmi başvuru nüshası, mevzuatın öngördüğü biçimde tutulması gereken dosya) **yerine geçmez**.
- **Yasal saklama:** Hekimlik, adli tıp, savcılık / mahkeme süreçleri ve kurum içi arşiv yönetmelikleri kapsamında **orijinal veya hukuken eşdeğer nüshanın**, öngörülen **sürelerde ve ortamda** muhafazası; erişim, yetki ve imha **tamamen kurumun hukuki ve idari yükümlülüğüdür**.
- **KVKK ve sözleşme:** Aydınlatma metni, veri işleme / hizmet sözleşmeleri ve **KVKK işleme envanteri**nde, damgalamanın yalnızca **bütünlük / zaman kanıtı** sağladığı; **asıl saklama ve hukuki sürelerin** kuruma ait olduğu **açık cümlelerle** yazılmalıdır (`docs/Kullanici-Saklama-Yukumlulugu.md` ile tutarlı).

### 2.5 Belediye belge / ruhsat

- **Veri:** başvuru formları, kimlik örnekleri, adres, ticari unvan — çoğunlukla kişisel / kurumsal veri.
- **Hukuki:** kamu hukuku ve idari işlem dayanağı ile sınırlı işleme; **amaç** “ruhsat süreci ve arşiv” olarak dokümante.
- **Öneri:** `vertical=municipal_license`; belediye **VERBİS** ve **bilgi güvenliği** politikaları; paylaşımlı doğrulama için yalnızca hash veya yetkili portal.

---

## 3. Teknik: dikey ve uyumluluk alanları

Damga isteğine (ve veritabanına) eklenebilecek **isteğe bağlı** alanlar (`StampRequest` / `Stamp` şablonu — `TurkDamga-Backend.md`):

| Alan | Amaç |
|------|------|
| `vertical` | `music` \| `architecture` \| `visual` \| `health_archive` \| `municipal_license` \| `other` |
| `processing_purpose` | Kısa metin veya kod (ör. `integrity_proof`, `license_application_archive`) |
| `data_category` | `general` \| `personal` \| `special_health` (işaret; iş akışı ve DPA tetikler) |
| `retention_until` | ISO tarih; politika ile uyumlu saklama üst sınırı |
| `consent_reference` | İç referans (rıza kaydı ID’si veya sözleşme no — ham rıza metnini burada tutmayın) |
| `work_title` | Parça / yayın / ürün adı — medya sertifikasında (`docs/Medya-Damga-Sertifikasi.md`); kişisel veri riskine dikkat |

**Not:** Bu alanlar tek başına KVKK uyumu sağlamaz; **iş süreci + hukuk + teknik** birlikte tasarlanmalıdır.

---

## 4. Mevcut mimari ile ilişki

- **Arşiv / nesne depo:** `docs/Arsiv-Mimari.md` — hasta ve belediye dosyalarında bölge ve şifreleme politikası kritik.
- **Arama ve TC:** `docs/Arama-ve-TC-Erisim-Mimarisi.md` — hasta arşivinde TC/hash araması **çok sıkı** yetkilendirme ve audit.
- **Toptan / kurum kredi:** `docs/Toptan-Satis-Kredi-Kontrat.md` — kurumsal sözleşmelerle bağlantı.

---

## 5. Özet kontrol listesi (ürün ekibi)

1. Her `vertical` için **işleme envanteri** ve **aydınlatma** metni.  
2. `health_archive` için **m.6** süreçleri ve alt bilgi güvenliği; hastane **adli dosya** senaryolarında damganın asıl evrak saklamanın yerine geçmediğinin KVKK ve sözleşme metinlerinde vurgulanması.  
3. `municipal_license` için **idari** meşruiyet ve saklama süreleri.  
4. Üretimde **VERBİS** ve **teknik tedbirler** dokümantasyonu.  
5. Damga API’sinde **amaç** ve **dikey** zorunluluğu (policy flag ile) değerlendirin.

Şema güncellemeleri `backend/TurkDamga-Backend.md` içindeki `Stamp` / `StampRequest` bloklarına yansıtılmıştır; veritabanı için Alembic migrasyonu `20260425_03_stamp_vertical_kvkk.py` ile eklenmiştir.

**Arayüz:** `frontend/turkdamga-arsiv-ui.html` içinde **Damgalanacak ürün / proje kategorisi** (sürükle-bırak kutusunda, `vertical`), işleme amacı, veri sınıfı, saklama tarihi ve rıza referansı alanları ile hasta / belediye uyarı kutuları bulunur; geçmiş ve sertifika metnine yansır. Mimari-inşaat ve program çıktıları bu seçimle tanımlanır.
