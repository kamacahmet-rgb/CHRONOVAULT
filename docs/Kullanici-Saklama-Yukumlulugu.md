# TurkDamga — Kullanıcı saklama yükümlülüğü ve sözleşme dili

TurkDamga damgalama modelinde **dosya içeriği müşteri tarafında kalır**; sistem yalnızca hash, metadata ve zincir kanıtını işler (`docs/Arsiv-Mimari.md`). Bu belge ürün iletisini ve **hizmet / abonelik sözleşmesine** konabilecek örnek maddeyi özetler. **Hukuki danışmanlık değildir.**

---

## 1. Ürün ilkesi

- **Belgeler, görseller, arşiv paketleri** (ZIP, proje çıktıları vb.) kullanıcının **kendi bilgisayarında ve seçtiği sunucularında** saklanır.
- TurkDamga, müşteri sözleşmesinde açıkça belirtildiği sürece **müşteri dosyasını kalıcı arşiv olarak barındırmayı** taahhüt etmez; nesne depo senaryosu ayrı sözleşme ve teknik tasarım konusudur.
- Arayüzde **kaynak dosyayı indir** (veya çoklu dosyada sırayla indir) ve **sertifika indir** ile kullanıcı, damgalama anında yerel kopyasını yedeklemeye teşvik edilir.

---

## 2. Sözleşmede kullanılmak üzere örnek madde (Türkçe taslak)

> **8.x Saklama ve dosya mülkiyeti.** Hizmet kapsamında İşveren (TurkDamga veya yetkili distribütör), Müşteri’ye yalnızca zaman damgası, hash doğrulama ve ilgili kanıt çıktıları (sertifika, işlem referansı) sağlar. **Müşteri’ye ait dijital dosyaların asıl nüshalarının saklanması, yedeklenmesi ve Müşteri’nin kendi altyapısında veya seçtiği üçüncü taraf depolamada tutulması tamamen Müşteri’nin sorumluluğundadır.** Müşteri, sözleşmeyi imzalayarak bu saklama koşullarının kendisine ait olduğunu bilerek kabul eder. TurkDamga’un Müşteri dosyası üzerinde mülkiyet veya barındırma taahhüdü bulunmadığı, yalnızca sözleşmede ayrıca yazılı nesne depo hizmeti tanımlanmadıkça dosya barındırılmadığı Müşteri tarafından onaylanır.

Metni yerel hukuk ve sözleşme numaralandırmanıza göre uyarlayın.

---

## 2.1 Sağlık kurumu ve hastane adli dosyaları (ek madde taslağı)

> **8.y Sağlık ve adli evrak — damganın sınırı.** Müşteri, hastane, klinik, laboratuvar veya benzeri sağlık kurumlarında **adli dosya**, adli tıp raporu, savcılık / yargı süreçlerine konu belge veya mevzuatla saklanması zorunlu tıbbi kayıtlar bakımından TurkDamga damgalamasının **yalnızca dijital bütünlük ve zaman kanıtı** sağladığını; **asıl evrakın** yasal sürelerde ve mevzuatın öngördüğü biçimde **Müşteri tarafından ayrıca muhafaza edilmesinin zorunlu** olduğunu kabul eder. Damgalama, **asıl saklama, arşivleme ve imha yükümlülüklerini** ortadan kaldırmaz. Bu husus **KVKK aydınlatma ve işleme envanteri** ile **hizmet / iş ortaklığı sözleşmelerinde** açıkça yer alır.

---

## 3. Teknik hatırlatma

- Tarayıcı tabanlı demoda indirme, oturumdaki `File` nesnesinden yapılır; geçmiş listesi yalnızca hash ve metadata tutar — **yeniden oturumda orijinal indirilemez**.
- Üretim API’sinde müşteri dosyası **sunucuya yüklenmiyorsa** bile, istemci SDK’sında “damgalama sonrası yerel kopyayı kaydet” akışı dokümante edilmelidir.

---

## 4. İlgili belgeler

- `docs/Arsiv-Mimari.md` — depo vs DB
- `docs/Medya-Damga-Sertifikasi.md` — sertifika çıktısı
- `docs/Toptan-Satis-Kredi-Kontrat.md` — kurumsal sözleşme çerçevesi
- `docs/KVKK-Vertical-Damgalama.md` — hasta arşivi ve adli dosya vurguları (§2.4.1)
