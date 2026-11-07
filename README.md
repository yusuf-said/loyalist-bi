# FlyUp3 · Apache Superset BI

Milano istasyonunun 6 müşterisi, 48. hafta kapasitesi ve 200.000 USD sadakat bütçesi. Python 3.11, Apache Superset **6.1.0**, resmi **fastmcp** extra'sı. Kendi BI veya MCP sunucumuz yok.

```sh
uv sync
cp .env.example .env
# .env: SUPERSET_SECRET_KEY (rastgele ve kalıcı), admin kullanıcı/parola alanlarını doldurun.
# Anahtar üretme: uv run python -c 'import secrets; print(secrets.token_urlsafe(48))'
uv run flyup3-load
scripts/setup.sh --target duckdb
scripts/superset.sh run -h 127.0.0.1 -p 8088 --no-reload
```

**Kaynak dosyalar olmadan (depo klonu):** vaka dosyaları (`vaka/`, Excel'ler, `mip/`, `dashboard/`) git'e alınmadı. Depodaki `data/flyup3.duckdb` anlık görüntüsü bu durumda kullanılır: `uv run flyup3-load` adımını atlayın; `scripts/setup.sh --target duckdb` dosyayı `out/`'a kopyalar. Kaynaklara bağlı referans testleri atlanır. Kaynaklar değişince görüntüyü yenileyin: `uv run flyup3-load && cp out/flyup3.duckdb data/`.

Açın: http://127.0.0.1:8088/superset/dashboard/flyup3-duckdb/ . Kurulum migration, admin, init, bağlantı, **8 tablo + 7 view dataset'i** ve 14 kart içeren dashboard'u kurar. DuckDB verisi kurulumda yeniden yüklenir; komutu Superset ve MCP kapalıyken çalıştırın. YAML/ZIP `out/flyup3_dashboard_duckdb.zip` dosyasına üretilir ve Superset'in v1 importer'ıyla gerçekten import edilir. Aynı komut tekrar çalıştırılabilir; dataset ve grafikler ayrı v1 overwrite importlarıyla güncellenir, mevcut admin parolası değiştirilmez. Dashboard import hatası kurulum komutunu başarısız yapar, dataset'ler kaydedilmiş olur.

`.env` / ortam değişkenleri okunur; sırlar repoya veya export ZIP'e yazılmaz. Metadata `out/superset.db`, Superset ve FastMCP çalışma dizinleri `out/` altındadır. **Superset'i wrapper ile başlatın:** Superset varsayılan `DATA_DIR`'ı custom config'ten önce seçer. `SUPERSET_SECRET_KEY` değerini metadata DB kurulduktan sonra değiştirmeyin. Yerel DuckDB bağlantısı salt okunurdur; yükleyiciyi Superset ve MCP süreçleri kapalıyken yeniden çalıştırın.

```sh
# İkinci terminal; aynı .env
scripts/superset.sh mcp run --host 127.0.0.1 --port 5008
# İstemciye kaydetme (komutları kullanıcı çalıştırır):
claude mcp add --transport http loyalist http://127.0.0.1:5008/mcp
codex mcp add loyalist --url http://127.0.0.1:5008/mcp
```

**Claude Desktop (stdio):** sunucu açmaya gerek yok; uygulama `scripts/mcp_stdio.sh`'i kendisi başlatır. `~/Library/Application Support/Claude/claude_desktop_config.json` içine:

```json
"mcpServers": { "loyalist": { "command": "/Users/yusuf/FlyUp3/scripts/mcp_stdio.sh" } }
```

Grafik linklerinin açılması için Superset web sunucusu (`scripts/superset.sh run ...`) çalışıyor olmalı.

MCP, streamable HTTP `/mcp` endpoint'ini kullanır. Yerel modda `MCP_DEV_USERNAME` metadata DB'de var olan kullanıcı olmalı; yetkileri RBAC ile uygulanır. Ağ kimlik doğrulaması bu yerel profilde kapalıdır ve servis yalnız loopback'e bağlanır. Ağda yayınlama için resmi JWT ayarları (`MCP_AUTH_ENABLED`, `MCP_JWKS_URI` veya `MCP_JWT_PUBLIC_KEY`/`MCP_JWT_SECRET`, issuer/audience) ve kullanıcı çözümlemesi gerekir. Bu proje yerel geliştirme profili sağlar.

Snowflake için `.env.example` alanlarını doldurun. Önce `sql/snowflake/00_setup.sql` çalıştırın (rol ve warehouse seçilmiş olmalı), ardından:

```sh
uv sync --extra snowflake
uv run flyup3-load --target snowflake
scripts/setup.sh --target snowflake
# Alternatif stage yüklemesi:
uv run flyup3-load --target parquet
# SnowSQL/CLI: sırasıyla 00_setup, 01_tables, 03_load_from_stage, 02_views SQL dosyaları
```

Yükleyici, hedefteki sekiz tabloyu yeniler; kaynağa yazmaz. Snowflake database/schema varsayılanı `FLYUP3.BI`; özel adlar `.env` üzerinden doğrudan yükleyicide desteklenir, elle kullanılan SQL dosyalarında adları uyarlayın. `PUT` yerel istemciden proje kökünde çalışır. `COPY` aynı staged dosyayı tekrar yüklemez; veri yenilenecekse tabloları boşaltıp yükleme geçmişini dikkate alın. Kaynaklar `.gitignore` içinde kalır.

Şema: `DIM_CUSTOMER`, `DIM_PRODUCT_PRIORITY`, `DIM_LOYALTY_BENEFIT`; `FACT_W48_DEMAND`, `FACT_W48_CAPACITY`, `FACT_W48_ALLOCATION`, `FACT_W48_SCENARIO`, `FACT_LOYALTY_COST`. Müşteri, ürün, avantaj ve senaryo anahtarları açık sütunlardır; tahsis grain'i senaryo × müşteri × gönderi × moddur. View'lar aynı SQL ile DuckDB/Snowflake'te çalışır. Belirsizlik kaynağı olmadığından sayısal güven skoru üretilmez. Makro grup SoW ≥%60 ve birim gelir ×%25 ≥0,50 USD/kg eşikleriyle; kademeler hesaplanmış `Özet` sayfasından alınır.

Model katkısı ertelenen geliri ve RFS maliyetini içerir; **net48 ×%25 ile farklıdır**. Plan A: 390.900 net48 / 102.725 model katkısı; Plan B: 374.200 / 99.600 USD. Renklerin tek kaynağı `src/flyup3/palette.py`; Power BI tema dosyası `uv run python -m flyup3.palette` ile güncellenir. Lisanslı tkText gömülmez, sistem sans-serif kullanılır. THY PANTONE 7620 C ekran karşılığı yaklaşık #B7312C yalnız referans notudur; uygulama Turkish Cargo web paletini kullanır.

[Power BI bağlantısı, ilişkiler ve DAX](powerbi/README.md).

```sh
uv run ruff check
uv run pytest
# Kurulumdan sonra gerçek HTTP + grafik sorguları + MCP araç listesi:
uv run python scripts/verify_runtime.py
```

`flask-caching<2.4`, 2.5'in Superset metastore cache çağrısıyla uyumsuzluğu nedeniyle sabittir. SQLGlot 28 Snowflake SQL'ini parse eder; SnowSQL `PUT` yalnız genel komut olarak tanınır ve ayrıca komut biçimi kontrol edilir. Snowflake hesabı ve Windows Power BI Desktop olmadan bu iki dış bağlantı doğrulanamaz.

Kaynak doğrulama: kurulu `superset/config.py`, `superset/mcp_service/{mcp_config,auth,server}.py`; [resmi Superset MCP](https://superset.apache.org/admin-docs/6.1.0/configuration/mcp-server/) ve [OpenAI Docs MCP/CLI sözdizimi](https://developers.openai.com/learn/docs-mcp).

[Bu teslimatın doğrulama raporu ve grafik listesi](VALIDATION.md). Mevcut `.env` ile kurulu dashboard, DuckDB, metadata DB ve YAML ZIP `out/` altında hazırdır. HTTP doğrulaması 8098/5018 geçici portlarını kullanır; yalnız kendi süreçlerini kapatır.

Üst menü THY yatay logosunu kullanır; açık/koyu tema token'ları `brandLogoUrl`, `brandLogoAlt`, `brandLogoHref`, `brandLogoHeight` ile tanımlıdır. Logo dashboard'a bağlanır. `FLASK_APP_MUTATOR`, `/flyup3-assets/` altında yalnız izin verilen SVG'leri proje dizininden servis eder; paket dizinine kopyalama veya data URI kullanılmaz. `APP_ICON`, `APP_NAME`, `LOGO_TARGET_PATH`, `LOGO_TOOLTIP`, `LOGO_RIGHT_TEXT` ve SVG `FAVICONS` de ayarlıdır. Orijinaller korunur; beyaz yazılı logo ve kırpılmış favicon `assets/thy/generated/` altına kurulumda türetilir.

Senaryo filtresi tek seçimli ve varsayılan **Plan A**'dır; net gelir, taşınan ton ve tahsis grafiğini etkiler. Plan karşılaştırması iki planı birlikte korur. Müşteri filtresi gelir, segmentasyon, tahsis ve sadakat kartlarına uygulanır. Taşınan KPI'sı 49. hafta pazartesi dahil taşınan toplamı gösterir. Bütçe paydası müşteri filtresinde de $200,000 kalır. Normal kapasitesi eksik kalemler ayrı tabloda yer alır; sıfır olarak çizilmez. Avantaj matrisinde maliyetler $ ve garantiler t cinsindendir; sıfır tahsis edilmemiş avantaj anlamındadır.


MCP sunucu adı her iki taşımada **loyalist**; Superset arayüz adı **THY · FlyUp3** kalır.
`mcp_branding.apply()` mevcut THY talimatlarını, veri kataloğunu ve Vega önizleme
renklerini koruyarak simülasyonları resmi `superset_core.mcp.decorators.tool` API'siyle
host bağlamında (ad öneki olmadan) bir kez kaydeder. HTTP CLI mutator
çağrısından sonra MCP modülünü yüklediği için resmi `APP_INITIALIZER.post_init`
kancası da aynı idempotent `apply()` fonksiyonunu çağırır. Statik vaka simülasyonları
`protect=False`, readOnly/non-destructive olarak kaydolur; veritabanına erişmez.
Paketin `superset_core.mcp` kökü Superset 6.1'de `tool` export etmez.

- `simulate_capacity_w48`: `passive_consent=True`, `allow_charter=False`,
  `rule="product_priority"` (alternatifler `pure_contribution`, `relationship_cost`),
  müşteri bazında `p`, `delay_usd=50`, ton bazında `capacities` (`krg`, `bel`, `akt`, `rfs`, `pzt`).
  Plan A varsayılandır; `passive_consent=False` Plan B verir. Charter başabaşı,
  öncelik cezası hariç iki optimal plan arasındaki ödenebilir kiralama bedelidir.
- `simulate_loyalty_cost`: müşteri bazında `tier_overrides`, `growth_overrides`,
  `stress_growth_overrides`, `visit_overrides`; kademe bazında `benefit_overrides`.
  Avantaj anahtarları: `cip`, `s247`, `zirve`, `karne`, `dijital`, `ziy`, `rate`, `base`, `cap`.
  `dijital` 1/0 anahtarı, dijital kullanımı %50 altındaki müşterilerin eğitimini açar/kapatır.
  Rebate bazı `total`, `above` veya `-`; oranlar 0–1. Baz ve stres maliyeti birlikte döner.
- `simulate_program_roi`: `impact=0.5`, `margin=0.25`, `rebate_multiplier=1`,
  `opportunity_cost=0`, `weeks=52` (ilk yıl, 1–52). Seçili ufuk ve 52 haftalık seri,
  0,01 adımlı başabaş, analitik eşik ve yıllık 108 koşuluk ızgara döner.
- `simulate_churn_risk`: müşteri bazında `signal_overrides` ve `uncertainty_overrides` (0–100).
  Sinyal anahtarları: `volume`, `competitor_share`, `complaints`, `csat`, `nps`, `contract`,
  `visits`, `offload`, `rival`, `decision_maker`, `planned_offload`; değerler sinyal
  puanlarıdır (her birinin kaynak paneldeki üst sınırı uygulanır). Varsayılan tahsis Plan A'dır.

Her araç kullanılan girdileri, sonuçları, Türkçe özeti ve varsayımları döndürür.
"Ya şöyle olsaydı?" soruları için `simulate_*` kullanılır. MIP ve panel sabitleri
`src/flyup3/sim/` içindedir; çalışma anında `mip/`, panel veya Excel import edilmez.
Testler orijinal MIP JSON'u, Excel'in hesaplanmış hücreleri ve Node'da çalıştırılan
kaynak JS ile karşılaştırır. JS'ye göre orta etki +71.301,75 USD, düşük etki
−15.388,875 USD, başabaş 0,30 ve 108 koşudan 52'si pozitiftir; önceki oturum
notlarındaki yaklaşık 68 bin / −19 bin / 0,31 / 50 sonuçlarından farklıdır.

```sh
uv run python scripts/verify_simulations_runtime.py
# İsteğe bağlı farklı geçici HTTP portu:
uv run python scripts/verify_simulations_runtime.py --http-port 5018
/opt/homebrew/bin/node scripts/simulation_reference.cjs
```

Simülasyon duman testi stdio wrapper'ını ve geçici HTTP sunucusunu kullanır;
8088/5008'deki mevcut süreçleri kapatmaz. Geçici HTTP sürecini kendi kapatır.
Yeni kodun 5008'deki mevcut sürece yüklenmesi, o sürecin sahibi tarafından
sonradan yeniden başlatılmasını gerektirir. Claude Desktop yapılandırması otomatik değiştirilmez.
