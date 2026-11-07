# THY · FlyUp3 doğrulama raporu · 7 Kasım 2026

Python 3.11.16 ve Apache Superset 6.1.0 üzerinde mevcut dashboard yenilendi. Kurulu dashboard: `/superset/dashboard/flyup3-duckdb/`. Metadata veritabanı korundu; kullanıcı `.env` ayarlarıyla hazırdır. Superset ve MCP çalışma sonunda kapalıdır.

## Değişen dosyalar

- `src/flyup3/superset_setup.py`: 14 kart, 12 sütunlu yerleşim, Türkçe dataset/ölçü etiketleri, para/oran/ton biçimleri, native filtreler, v1 YAML bundle ve tekrarlı import.
- `src/flyup3/loader.py`, `sql/snowflake/02_views.sql`: 7 taşınabilir view; uzun tahsise senaryo adı, müşteri özetine cüzdan oranı/sabit hizmet/rebate, karşılaştırılabilir kapasite, ek kapasite ve avantaj matrisi.
- `src/flyup3/palette.py`: müşteri, kademe, mod ve ölçü renkleri tek kaynaktan; açık/koyu tema logo token'ları.
- `src/flyup3/branding.py` (yeni), `superset_config.py`: THY logo/favicon üretimi ve kalıcı proje varlıklarının Flask üzerinden sunumu.
- `assets/thy/generated/thy_logo_horizontal_white.svg`, `assets/thy/generated/thy_emblem.svg` (yeni): türetilmiş varlıklar.
- `scripts/verify_runtime.py`, `tests/test_data.py`: grafik türü/sayısı, etiketler, renkler, logolar, sayılar ve gerçek HTTP filtre sorgularının kontrolü.
- `README.md`, `VALIDATION.md`: güncel kullanım ve kanıtlar.
- `out/`: yenilenen DuckDB, metadata DB, YAML ZIP ve doğrulama çıktıları.

## Grafikler

| Başlık | viz_type |
|---|---|
| 48. hafta · net gelir | `big_number_total` |
| Taşınan / teyitli talep | `big_number_total` |
| Yıllık sadakat maliyeti | `big_number_total` |
| Sadakat bütçesi kullanımı | `big_number_total` |
| Müşteri bazında yıllık gelir · $ | `echarts_timeseries_bar` |
| Kademe bazında yıllık gelir payı | `pie` |
| Segmentasyon · eşikler %60 ve $0,50/kg | `bubble_v2` |
| 48. hafta · müşteri ve taşıma modu · t | `echarts_timeseries_bar` |
| Plan A / B · gelir, katkı ve kayıp | `table` |
| Normal → güncel kapasite · toplam hava 230 → 175 t | `echarts_timeseries_bar` |
| Ek kapasite · normal değer belirtilmemiş | `table` |
| Müşteri başına sadakat maliyeti · $ | `echarts_timeseries_bar` |
| Sadakat bütçesi · üst sınır $200,000 | `gauge_chart` |
| Kime hangi avantaj · yıllık maliyet ($) ve garanti (t) | `table` |

Dört KPI tek satırda, her biri 3/12 genişliğindedir. Grafik kartları 34–44, KPI'lar 16, küçük tablolar 17–28 grid yüksekliği kullanır. Plan karşılaştırması ve ek kapasite tablosu bir sütunda üst üste yer alır. Tablolarda hücre çubukları kapalıdır. Para `$,.0f`, oran `.0%`; ton ve birim kârın birimi Türkçe etiketlerde açıkça belirtilmiştir.

## Logo bağlantısı

`APP_NAME = "THY · FlyUp3"`. Açık tema orijinal yatay SVG'yi, koyu tema siyah dolguları `#FFFFFF` yapılmış varyantı kullanır; kırmızı amblem korunur. Favicon ilk iki amblem path'inden, `viewBox="49 49 126 126"` ile kırpılmıştır. SVG favicon yeterli olduğundan PNG üretilmedi.

`FLASK_APP_MUTATOR`, izinli üç dosyayı `/flyup3-assets/` altında proje dizininden sunar. `brandLogoUrl`, `brandLogoAlt`, `brandLogoHref`, `brandLogoHeight` (30px), `APP_ICON`, `LOGO_TARGET_PATH`, `LOGO_TOOLTIP`, boş `LOGO_RIGHT_TEXT` ve `FAVICONS` ayarlıdır. Logo başlangıç dashboard'una bağlanır. Data URI veya `.venv/.../superset/static` kopyası kullanılmaz.

Anahtarlar kurulu `superset/config.py` ve derlenmiş tema kaynağında; `echarts_timeseries_bar`, `bubble_v2`, `pie`, `big_number_total`, `gauge_chart`, `table` kurulu `static/assets/8115.535b4174a7ea7a91d01a.entry.js` kaydında doğrulandı. Bar renk seçeneği ve ECharts sözleşmeleri kurulu `9059.b2f889ad23bd80f99e2a.entry.js` ve yerel Superset frontend kaynağıyla karşılaştırıldı. Resmi [6.1 yapılandırma kaynağı](https://github.com/apache/superset/blob/6.1.0/superset/config.py) da kontrol edildi.

## Filtreler ve veri anlamı

- **Senaryo** tek seçimlidir, varsayılan **Plan A**. Net gelir, taşınan ton ve taşıma modu tahsis grafiğini etkiler. Plan A/B karşılaştırması iki planı birlikte korur.
- **Müşteri** gelir, donut, segmentasyon, tahsis ve sadakat kartlarını etkiler. Global senaryo KPI'ları ile fiziksel kapasite ve plan karşılaştırması etkilenmez.
- Taşınan ton 49. hafta pazartesi taşınacak yükü de kapsar: Plan A 220/221 t, Plan B 213/221 t.
- Bütçe paydası müşteri filtresinde de $200,000 kalır; gösterge seçili müşterilerin bu bütçeden aldığı paydır.
- Normal kapasitesi belirtilmeyen 3 kalem ayrı tabloda yer alır. Gruplu grafikte normal verisi bulunan 5 kalem gösterilir; toplam hava kapasitesi 230 → 175 t'dir.
- Bubble boyutu yıllık gelirdir; %60 ve $0,50/kg eşikleri başlık/açıklamada verilir. Bubble eklentisinin doğrudan eşik çizgisi seçeneği bulunmadığından çizgi eklenmedi.
- Avantaj matrisi maliyetleri $ ve garantileri t olarak gösterir. Sıfır tahsis edilmemiş avantaj anlamındadır; garantiye nakit maliyeti uydurulmaz.

## Doğrulama

| Kontrol | Sonuç |
|---|---|
| `uv run ruff check` | Geçti |
| `uv run pytest` | 17/17 geçti |
| `scripts/setup.sh --target duckdb` art arda iki kez | İkisi de kod 0; 1 dashboard, 14 grafik, 15 dataset; kopya oluşmadı |
| Kaydedilmiş grafik başlığı/türü ve tüm dataset sütun etiketleri | Kurulum sonunda beklenen tanımlarla birebir doğrulandı |
| `/health` | Gerçek HTTP 200 |
| Açık/koyu logo ve favicon | Üçü de gerçek HTTP 200, `image/svg+xml` |
| `/api/v1/chart/data` | 14/14 grafik hatasız, dolu veri; cache zorla atlandı |
| Plan B sorguları | 3/3 senaryoya bağlı kart hatasız |
| Medivia müşteri filtresi | 9/9 kapsamdaki kart hatasız |
| `label_colors` ve native filtre metadata'sı | Gerçek dashboard API yanıtında doğrulandı |
| Türkçe sütun etiketleri | Dashboard datasets API yanıtında doğrulandı |
| MCP | `tools/list`, `health_check`, `get_instance_info` başarılı |
| Süreç temizliği | Her iki süreç sonlandırıldı; 8088 ve 5008 portlarının kapalı olduğu doğrulandı |
| Snowflake SQL | 4 SQL dosyası Snowflake lehçesinde parse edildi; gerçek hesapta yürütülmedi |

Superset 6.1 dashboard importer'ı bağımlılıklarını `overwrite=False` ile işler. Bu nedenle yükleyici aynı YAML içeriğini önce `ImportDatasetsCommand` ve `ImportChartsCommand` ile `overwrite=True`, sonra `ImportDashboardsCommand` ile içe aktarır. Böylece önceki beş tablo gerçekten güncellenir; sadece layout değişmez. Tek başına dashboard importunda mevcut bağımlılıkların yenileneceği varsayılmamalıdır.

Bilinen rakamlar korundu: Plan A net $390,900 / katkı $102,725 / taşınamayan 1 t; Plan B net $374,200 / katkı $99,600 / taşınamayan 8 t. Sadakat toplamı $102,079.50, sabit hizmet $52,200, rebate $49,879.50, stres $116,114.50; bütçe kullanımı 0.5103975 → ekranda %51. Medivia müşteri filtresinde sadakat toplamı $62,202 ve bütçe payı %31,101.

Ayrıntılı gerçek HTTP verileri: `out/runtime_verification.json`; kurulum kayıtları: `out/setup_redesign_1.log`, `out/setup_redesign_2.log`. Bu dosyalara kimlik bilgileri yazılmadı.

## Sınırlar ve korunan kaynaklar

Ekran görüntüsü ve tarayıcıda görsel kontrol kullanıcı talebi doğrultusunda Claude'a bırakıldı. Gerçek Snowflake yürütmesi bu çalışmada yapılmadı; ortak view SQL'i DuckDB'de yürütüldü ve Snowflake lehçesinde ayrıştırıldı.

`.cache/`, `dashboard/`, `kanvas/`, `mip/`, `vaka/`, `FlyUp3_Cozum_Modeli.xlsx`, orijinal THY SVG'leri, `SOURCE.md` ve `.gitignore` değiştirilmedi. `git add` / `git commit` yapılmadı. `.env` içeriği rapora veya bundle'a aktarılmadı.
