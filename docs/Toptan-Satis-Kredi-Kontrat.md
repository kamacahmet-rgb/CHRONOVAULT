# TurkDamga — Toptan satış: coin, kredi ve kontrat

Bu belge, operasyonel olarak **elde edilen kripto varlıkların** (ör. müşteri ödemeleri, gas için tutulan MATIC, promosyon token’ları) **toptan** veya kurumsal kanalla değerlendirilmesi ile **ön ödemeli kredi** veya **sözleşme (kontrat)** tabanlı satış modellerini tanımlar. **Yatırım tavsiyesi veya hukuki danışmanlık değildir**; ödeme araçları ve sözleşmeler için yerel mevzuat ve muhasebe uzmanı gereklidir.

---

## 0. Damgalama: arka planda Polygon, satışta kredi

TurkDamga’un hedeflediği iş modeli şudur:

1. **Operasyon (treasury):** Şirket, damgalama işlemlerinin zincir üzerinde maliyetini karşılamak için **Polygon** üzerinden native coin (**MATIC**) temin eder (borsa, OTC, köprü vb.). Bu coin’ler **gas ve sözleşme çağrıları** için operasyonel cüzdanda (hot wallet veya imza politikası ile sınırlı alt cüzdan) tutulur; `app/services/polygon.py` benzeri servis bu cüzdanla TX üretir.
2. **Müşteri ürünü:** Son kullanıcı ve kurum **MATIC veya “coin” satın almaz**; **damga kredisi** (veya paketlenmiş API / damgalama birimi) satın alır. Ödeme çoğunlukla **TRY / USD / fatura** ile tahsil edilir; sistemde `credit_ledger` ile bakiye düşülür.
3. **Bağlantı:** Her başarılı damgalama (veya API’de tanımlı birim) **(a)** müşteri kredisinden düşer, **(b)** arka planda treasury’den bir miktar MATIC gas olarak harcanır (kur dalgalanması için iç **dönüşüm tablosu** veya marj: “1 kredi ≈ şu üst sınırda gas” politikası ayrı dokümanda sabitlenir).

Bu ayrım, ürün dilinde **tek TurkDamga blockchain kanıtı** ile uyumludur: müşteri arayüzünde zincir adı şart değildir; operasyon ve muhasebe tarafında Polygon açıkça izlenir.

**Backend uygulama sırası** (kredi kilidi, zincir, telafi): `backend/TurkDamga-Backend.md` içindeki **Damgalama akışı: kurumsal kredi ve Polygon TX sırası** başlığı.

---

## 1. Terimler

| Kavram | Anlamı |
|--------|--------|
| **Operasyonel gas** | Treasury cüzdanından Polygon’da damgalama TX’leri için harcanan native coin (MATIC). Fatura / sözleşmede genelde **kredi birimi** olarak yansır; müşteriye “MATIC aldınız” denmez. |
| **Coin / token** | Cüzdanda veya borsada tutulan kripto varlık (ör. MATIC, USDC) — ağırlıklı olarak **şirket kasası / treasury** likiditesi. |
| **Kredi** | TurkDamga içinde **damgalama kotası** veya **API kullanım birimi** olarak satılan, zincir dışı veya yarı zincirli hak. |
| **Kontrat** | Alıcı ile imzalanan **çerçeve anlaşma**: birim fiyat, süre, minimum hacim, ödeme takvimi, teslimat (kredi yükleme veya token transferi). |

**Toptan satış:** tek seferde yüksek hacim, B2B fiyat listesi, iskonto, faturalı kurumsal alıcı, SLA.

---

## 2. Üç satış kanalı (özet)

### 2.1 Kredi toptan (en sıkı entegrasyon)

- Alıcı kurum **ön ödeme** veya **fatura** ile X adet damgalama / X GB arşiv / X API çağrısı satın alır.
- Sistemde `organization` veya `user` kaydına **kredi bakiyesi** yazılır; kullanım `CreditLedger` ile düşülür.
- Müşteri tarafında **satılan SKU kredidir**; gelir banka veya ödeme kuruluşu ile tahsil edilir. Bkz. **§0**: damgalama gerçekleşirken gas için treasury’deki **Polygon / MATIC** ayrı bir operasyon kalemidir (müşteri MATIC satın almaz).

### 2.2 Coin / token toptan (likidite)

- Şirket kasasındaki token’lar **OTC**, **CEX API** veya **on-chain DEX** üzerinden toplu satılır.
- Bu süreç **TurkDamga uygulama kodunun dışında** (treasury playbook, çoklu imza cüzdanı, muhasebe) yürütülür; uygulama yalnızca **bakiye ve hareket kaydı** tutabilir (denetim için).

### 2.3 Kontrat (çerçeve sözleşme + ekler)

- **MSA** (master agreement) + **sipariş formları** veya **ek protokol**: birim fiyat, toplam kota, geçerlilik, fesih, uyuşmazlık çözümü.
- Teknik tarafta: kontrat ID’si ile `WholesaleContract` satırı; teslimat anında kredi yüklemesi veya token transfer referansı (tx hash) bağlanır.

---

## 3. Veri modeli (öneri)

| Varlık | Alanlar (özet) |
|--------|------------------|
| `wholesale_contracts` | `id`, `buyer_org_id`, `status` (draft/active/fulfilled/closed), `currency` (TRY/USD/USDC/MATIC), `total_amount`, `credit_units` veya `token_amount`, `unit_price`, `valid_from`, `valid_until`, `legal_ref`, `created_at` |
| `credit_ledger` | `id`, `organization_id`, `delta` (+/-), `reason` (wholesale_purchase, stamp_consumption, adjustment), `contract_id` nullable, `balance_after`, `created_at` |
| `treasury_movements` | (opsiyonel) `asset`, `amount`, `direction` (in/out), `counterparty`, `tx_hash`, `note` — muhasebe ile hizalı |

---

## 4. API taslakları (B2B)

Kimlik: **kurumsal API anahtarı** + IP allowlist + ayrı oran sınırı.

```
POST   /api/v1/b2b/contracts              Kontrat taslağı / kayıt (yetkili rol)
GET    /api/v1/b2b/contracts              Liste
GET    /api/v1/b2b/contracts/{id}
POST   /api/v1/b2b/credits/allocate       Kontrata bağlı kredi yükleme (iç onay sonrası)
GET    /api/v1/b2b/credits/ledger         Hareket dökümü
GET    /api/v1/b2b/credits/balance/me     Oturumdaki kullanıcının kurum kredi bakiyesi (panel)
```

Ödeme onayı genelde **webhook** (ödeme sağlayıcı) veya manuel admin onayı ile tetiklenir; kredi yükleme idempotent olmalıdır (`idempotency-key` header).

---

## 5. Coin satışı ve uygulama sınırı

- **DEX/CEX satışı** genelde **otomasyon botu** veya **manuel treasury** ile yapılır; TurkDamga API’sinin doğrudan “coin sat” uç noktası **zorunlu değildir** — güvenlik ve uyumluluk için ayrı servis önerilir.
- İstenirse: `POST /api/v1/internal/treasury/record-sale` yalnızca **muhasebe/denetim** kaydı (tx hash, miktar) için; imza anahtarı uygulama sunucusunda tutulmaz.

---

## 6. Güvenlik ve iç kontrol

- Toptan kredi yükleme: **çift onay** (iki admin veya admin + zaman gecikmesi).
- `SECURITY.md` ile uyum: B2B uçları agresif rate limit, audit log, ayrı `b2b` rolü.
- KVKK / ticari sır: alıcı verisi kontratta; erişim rol bazlı. **Hastane adli dosya ve özel nitelikli sağlık verisi** kullanımında: toptan / B2B sözleşmede veya ek protokolde, **asıl evrakın yasal sürelerde saklanmasının** alıcı kuruma ait olduğu ve **damgalamanın bu yükümlülüğün yerine geçmediği** açıkça yazılmalıdır (`docs/KVKK-Vertical-Damgalama.md` §2.4.1, `docs/Kullanici-Saklama-Yukumlulugu.md` §2.1).

---

## 7. Özet

| Hedef | Öneri |
|--------|--------|
| Kredi toptan | `wholesale_contracts` + `credit_ledger` + B2B API + manuel/onaylı yükleme |
| Coin toptan | Treasury süreci uygulama dışı; isteğe bağlı `treasury_movements` kaydı |
| Kontrat | Yasal belge + sistemde `WholesaleContract` + teslimatı kredi veya ödeme referansı ile bağlama |

Uygulama şablonu güncellemeleri: `backend/TurkDamga-Backend.md` içinde `b2b` router, `wholesale` modelleri ve `schemas/b2b.py`.  
Veritabanı: `backend/alembic/versions/20260424_02_wholesale_b2b.py` (`down_revision`: `20260423_01`).
