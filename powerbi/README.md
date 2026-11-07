# Power BI bağlantısı

Power BI Desktop Windows üzerinde çalışır. Mac'te bu proje veri ve temayı hazırlar; Desktop doğrulaması yapılmamıştır.

**Snowflake:** `uv run flyup3-load --target snowflake` sonrasında Veri Al → Snowflake → hesap sunucusu (`<account>.snowflakecomputing.com`) ve warehouse → rol ve kimlik doğrulama → `FLYUP3.BI` içindeki 8 tabloyu seçin. Import modu bu küçük vaka için yeterli. Özel database/schema kullanıyorsanız aynı adları seçin.

**Parquet:** `uv run flyup3-load --target parquet`. Desktop'ta Veri Al → Parquet ile `out/parquet/` içindeki sekiz dosyayı ayrı sorgular olarak açın. Tek uzun tabloya birleştirmeyin. Snowflake stage yüklemesi için de aynı dosyalar kullanılır.

Görünüm → Temalar → Temalara göz at → `thy_turkish_cargo.json`. Renk kaynağı `src/flyup3/palette.py`; değişince `uv run python -m flyup3.palette` çalıştırın. Müşteri bazındaki grafiklerde `DIM_CUSTOMER.COLOR_HEX` üzerinden alan değeri biçimlendirmesi kullanın.

İlişkiler tek yönlü, dimension → fact olmalı:

| Tek taraf | Çok taraf |
|---|---|
| DIM_CUSTOMER.CUSTOMER_ID | FACT_W48_DEMAND / FACT_W48_ALLOCATION / FACT_LOYALTY_COST.CUSTOMER_ID |
| DIM_PRODUCT_PRIORITY.PRODUCT_ID | FACT_W48_DEMAND / FACT_W48_ALLOCATION.PRODUCT_ID |
| DIM_LOYALTY_BENEFIT.BENEFIT_ID | FACT_LOYALTY_COST.BENEFIT_ID |
| FACT_W48_SCENARIO.SCENARIO_ID (tekil senaryo başlığı) | FACT_W48_ALLOCATION.SCENARIO_ID |

`FACT_W48_CAPACITY` bağımsız bir kapasite anlık görüntüsüdür. `FACT_W48_DEMAND` ile tahsis tablosunu doğrudan bağlamayın; müşteri ve ürün boyutları ikisini filtreler. `SHIPMENT_ID` gönderi izlenebilirliği sağlar. Talep toplamı her senaryoda yeniden toplanmaz. Kapasite tablosunda toplam hava satırını bileşenlerle birlikte toplamayın: `IS_AIR_COMPONENT` filtresi kullanın. Aktif sınır, hava kapasitesinin alt kısıtıdır; ek kapasite değildir.

Ölçüler (DAX; yerel ayarda virgül yerine noktalı virgül gerekebilir):

```dax
Taşınan t =
IF(HASONEVALUE(FACT_W48_SCENARIO[SCENARIO_ID]),
    CALCULATE(SUM(FACT_W48_ALLOCATION[TONNES]), FACT_W48_ALLOCATION[IS_TRANSPORTED] = TRUE()))

Taşınamayan t =
IF(HASONEVALUE(FACT_W48_SCENARIO[SCENARIO_ID]),
    CALCULATE(SUM(FACT_W48_ALLOCATION[TONNES]), FACT_W48_ALLOCATION[MODE_ID] = "yok"))

Net Gelir 48H =
IF(HASONEVALUE(FACT_W48_SCENARIO[SCENARIO_ID]), SUM(FACT_W48_SCENARIO[NET48_USD]))

Katkı = [Net Gelir 48H] * 0.25

Model Katkısı =
IF(HASONEVALUE(FACT_W48_SCENARIO[SCENARIO_ID]),
    SUM(FACT_W48_SCENARIO[MODEL_CONTRIBUTION_USD]))

Sadakat Maliyeti = SUM(FACT_LOYALTY_COST[BASE_COST_USD])

Stres Maliyeti = SUM(FACT_LOYALTY_COST[STRESS_COST_USD])

Bütçe Kullanımı % = DIVIDE([Sadakat Maliyeti], 200000)

Başabaş Gelir = DIVIDE([Sadakat Maliyeti], 0.25)

Güncel Hava Kapasitesi t =
CALCULATE(SUM(FACT_W48_CAPACITY[CURRENT_TONNES]), FACT_W48_CAPACITY[IS_AIR_COMPONENT] = TRUE())
```

Senaryo dilimleyicisini tek seçim yapın (Plan A önerilen; Plan B Nord pasif onay vermezse). Taşınan ton, 49. hafta pazartesiye erteleneni de içerir; yalnız 48H için `WEEK=48` filtresi ekleyin. Senaryo başlığındaki net gelir müşteri/ürün filtresine dağılmaz; müşteri kırılımında tahsis satırlarının `REVENUE48_USD - RFS_COST_USD` toplamını kullanın. Charter bedeli senaryo düzeyindedir, müşterilere dağıtılmamıştır.

`Katkı` basit %25 ölçüsüdür. Kaynak modelin `MODEL_CONTRIBUTION_USD` değeri ise `(48H brüt + 49H ertelenen gelir) × 0,25 − RFS maliyeti − charter` hesabıdır. Plan A'da 102.725, Plan B'de 99.600 USD; basit ölçüyle aynı değildir. Pasif örtü tarife geliri modelde 2,40 USD/kg'dır.

Sadakat satırları baz ve stresi ayrı sütunlarda tutar. Rebate toplam maliyete dahildir; ara toplam satırları tekrar yüklenmez. Peak garanti nakit birim maliyeti tanımsızdır (`NULL`); nakit maliyetine sıfır katkı, ton garantileri ayrı sütunlardadır. Kurtarma bütçesindeki 3.200 USD sadakat toplamına dahil değildir.

Bağlantı adımları: [Microsoft Snowflake connector](https://learn.microsoft.com/en-us/power-query/connectors/snowflake), [Microsoft Parquet connector](https://learn.microsoft.com/en-us/power-query/connectors/parquet).
