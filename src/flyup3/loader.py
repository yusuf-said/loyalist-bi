"""Kaynakları yalnız okuyarak FlyUp3 yıldız şemasını yükler."""

import argparse
import json
import os
import re

import duckdb
import pandas as pd
from openpyxl import load_workbook
from sqlalchemy import create_engine, text

from flyup3.palette import CUSTOMER_COLORS
from flyup3.settings import OUT, ROOT, identifier, load_env, snowflake_url

# Kaynak vaka dosyaları git dışında; depoda yalnız yüklenmiş DuckDB anlık görüntüsü var.
SOURCE_FILES = [
    "vaka/FlyUp3_Excel.xlsx",
    "FlyUp3_Cozum_Modeli.xlsx",
    "mip/mip_sonuclari.json",
    "dashboard/index.html",
]
SNAPSHOT = ROOT / "data" / "flyup3.duckdb"


def sources_available(root=ROOT):
    return all((root / name).exists() for name in SOURCE_FILES)


def duckdb_table_names(path=None):
    with duckdb.connect(str(path or OUT / "flyup3.duckdb"), read_only=True) as connection:
        rows = connection.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_type = 'BASE TABLE' ORDER BY table_name"
        ).fetchall()
    return [name for (name,) in rows]


CRM_COLUMNS = [
    "MAIN_PRODUCT",
    "ANNUAL_TONNES",
    "UNIT_REVENUE_USD_KG",
    "WALLET_SHARE_PCT",
    "COMPETITOR_SHARE_PCT",
    "STATION_COUNT",
    "VOLUME_CHANGE_3M_PCT",
    "PRODUCT_COUNT",
    "COMPLAINTS_6M",
    "DIGITAL_BOOKING_PCT",
    "NO_SHOW_PCT",
    "ALLOTMENT_USE_PCT",
    "PAYMENT_DELAY_DAYS",
    "CSAT",
    "NPS",
    "VISITS",
    "RENEWAL_DAYS",
    "Q4_VOLUME_PCT",
]
MODES = {
    "akt": "Aktif konteyner",
    "pas": "Pasif örtü",
    "krg": "Kargo uçağı",
    "bel": "Belly",
    "rfs": "RFS (kamyon)",
    "pzt": "49. hafta pazartesi",
    "yok": "Taşınamayan",
}
VIEWS = [
    "V_CUSTOMER_SUMMARY",
    "V_W48_SCENARIO_COMPARE",
    "V_LOYALTY_BUDGET",
    "V_W48_ALLOCATION",
    "V_CAPACITY_COMPARE",
    "V_CAPACITY_EXTRA",
    "V_LOYALTY_MATRIX",
]


def macro_group(wallet_share, profit):
    loyal, profitable = wallet_share >= 60, profit >= 0.50
    return {
        (True, True): "Saf sadakat",
        (True, False): "Sahte sadakat",
        (False, True): "Kârlı sadakatsizlik",
        (False, False): "Sadakatsizlik",
    }[loyal, profitable]


def product_id(name):
    for prefix, product in [
        ("Pharma", "TK Pharma"),
        ("Valuable", "TK Valuable"),
        ("Courier", "Express Courier"),
        ("Fresh", "TK Fresh"),
        ("Genel", "TK General"),
    ]:
        if name.startswith(prefix):
            return product
    raise ValueError(f"Ürün eşleştirilemedi: {name}")


def read_tables(root=ROOT):
    case = load_workbook(root / "vaka/FlyUp3_Excel.xlsx", data_only=True, read_only=True)
    model = load_workbook(root / "FlyUp3_Cozum_Modeli.xlsx", data_only=True, read_only=True)
    try:
        return _read_tables(root, case, model)
    finally:
        case.close()
        model.close()


def _read_tables(root, case, model):
    crm, summary, loyalty = case["CRM Kaynak"], model["Özet"], model["Sadakat"]
    customers = []
    summary_rows = {summary.cell(r, 1).value: r for r in range(5, 11)}
    for col in range(2, 8):
        name = crm.cell(1, col).value
        customer = {"CUSTOMER_ID": name}
        for row, key in enumerate(CRM_COLUMNS, 2):
            value = crm.cell(row, col).value
            if key == "ALLOTMENT_USE_PCT" and not isinstance(value, (float, int)):
                value = None
            if key == "RENEWAL_DAYS" and not isinstance(value, (float, int)):
                customer["HAS_CONTRACT"] = False
                value = None
            customer[key] = value
        customer.setdefault("HAS_CONTRACT", True)
        r = summary_rows[name]
        for c, key in enumerate(
            [
                "ANNUAL_REVENUE_USD",
                "SEGMENT_SCORE",
                "TIER",
                "SEGMENT",
                "CHURN_SCORE",
                "CHURN_LEVEL",
                "DISCIPLINE_ALERT",
            ],
            2,
        ):
            customer[key] = summary.cell(r, c).value
        if any(customer[k] is None for k in ["TIER", "ANNUAL_REVENUE_USD", "CHURN_SCORE"]):
            raise ValueError(
                "Çözüm modelinde hesaplanmış değer eksik; Excel ile yeniden hesaplayın."
            )
        customer["PROFIT_USD_KG"] = customer["UNIT_REVENUE_USD_KG"] * 0.25
        customer["MACRO_GROUP"] = macro_group(
            customer["WALLET_SHARE_PCT"], customer["PROFIT_USD_KG"]
        )
        # Kaynakta istatistiksel belirsizlik ölçüsü yok; skor uydurulmaz.
        customer["UNCERTAINTY"] = "Ölçülmedi; eşik tabanlı sınıflama"
        customer["COLOR_HEX"] = CUSTOMER_COLORS[name]
        customers.append(customer)

    products = []
    for line in (root / "vaka/organizator_aciklamalari.md").read_text().splitlines():
        match = re.match(r"\|\s*(\d)\s*\|\s*([^|]+)\|\s*([^|]+)\|", line)
        if match:
            priority, name, description = match.groups()
            products.append(
                {
                    "PRODUCT_ID": name.strip(),
                    "PRIORITY": int(priority),
                    "DESCRIPTION": description.strip(),
                }
            )
    if len(products) != 12 or {p["PRIORITY"] for p in products} != set(range(1, 10)):
        raise ValueError("Ürün öncelik tablosu beklenen 12 ürünü / 1–9 önceliklerini içermiyor.")

    benefits = []
    benefit_sheet = case["Sadakat Programı"]
    for r in range(2, 10):
        name, cost, condition = [benefit_sheet.cell(r, c).value for c in range(1, 4)]
        benefits.append(
            {
                "BENEFIT_ID": f"B{r - 1:02}",
                "BENEFIT_NAME": name,
                "UNIT_COST_USD": cost if isinstance(cost, (float, int)) else None,
                "COST_RULE": str(cost),
                "CONDITION": condition,
            }
        )
    # Stable benefit IDs preserve source order; rebate and peak have no fixed cash unit cost.
    costs = []
    for col in range(2, 8):
        name = loyalty.cell(29, col).value
        for r, benefit_id in [
            (33, "B03"),
            (34, "B04"),
            (35, "B05"),
            (36, "B06"),
            (37, "B07"),
            (38, "B08"),
            (43, "B01"),
            (48, "B02"),
        ]:
            base = 0 if r == 48 else loyalty.cell(r, col).value
            stress = loyalty.cell(44, col).value if r == 43 else base
            costs.append(
                {
                    "CUSTOMER_ID": name,
                    "BENEFIT_ID": benefit_id,
                    "BASE_COST_USD": float(base),
                    "STRESS_COST_USD": float(stress),
                    "GUARANTEE_TONNES": float(loyalty.cell(48, col).value) if r == 48 else 0.0,
                    "ACTIVE_GUARANTEE_TONNES": (
                        float(loyalty.cell(49, col).value) if r == 48 else 0.0
                    ),
                }
            )

    demand = []
    sheet = case["48H Talepler"]
    for r in range(2, 10):
        name, shipment, tonnes, rate, allotment, condition = [
            sheet.cell(r, c).value for c in range(1, 7)
        ]
        demand.append(
            {
                "SHIPMENT_ID": f"S{r - 1:02}",
                "CUSTOMER_ID": name,
                "PRODUCT_ID": product_id(shipment),
                "SHIPMENT_NAME": shipment,
                "DEMAND_TONNES": tonnes,
                "RATE_USD_KG": rate,
                "ALLOTMENT_NOTE": allotment,
                "CRITICAL_CONDITION": condition,
            }
        )
    capacity = []
    sheet = case["48H Kapasite"]
    for r in range(2, 10):
        capacity.append(
            {
                "CAPACITY_ID": f"C{r - 1:02}",
                "CAPACITY_NAME": sheet.cell(r, 1).value,
                "NORMAL_TONNES": sheet.cell(r, 2).value,
                "CURRENT_TONNES": sheet.cell(r, 3).value,
                "IS_AIR_COMPONENT": r in [2, 3, 4],
                "IS_ACTIVE_LIMIT": r == 6,
            }
        )

    mip = json.loads((root / "mip/mip_sonuclari.json").read_text())
    params = mip["params"]
    scenarios, allocations = [], []
    for scenario_id, scenario in mip["scenarios"].items():
        scenarios.append(
            {
                "SCENARIO_ID": scenario_id,
                "SCENARIO_NAME": {"urun_onceligi": "Plan A", "oneri_b": "Plan B"}.get(
                    scenario_id, scenario["title"]
                ),
                "DESCRIPTION": scenario["title"],
                "NET48_USD": scenario["net48"],
                "DEFERRED49_USD": scenario["def49"],
                "MODEL_CONTRIBUTION_USD": scenario["contrib"],
                "UNTRANSPORTED_TONNES": sum(r["yok"] for r in scenario["rows"]),
                "OFFLOAD_CUSTOMERS": ", ".join(scenario["offload"]),
                "CHARTER_COUNT": scenario["charter"],
                "CHARTER_COST_USD": scenario["charter"] * params["charter"]["cost"],
            }
        )
        # Validate row identity before assigning shipment keys (source labels differ).
        if len(scenario["rows"]) != len(demand):
            raise ValueError(f"{scenario_id}: gönderi sayısı farklı")
        for row, shipment in zip(scenario["rows"], demand):
            if (row["cust"], row["t"], row["r"], product_id(row["name"])) != (
                shipment["CUSTOMER_ID"],
                shipment["DEMAND_TONNES"],
                shipment["RATE_USD_KG"],
                shipment["PRODUCT_ID"],
            ):
                raise ValueError(f"{scenario_id}: gönderi sırası veya değeri uyuşmuyor")
            if sum(row[m] for m in MODES) != row["t"]:
                raise ValueError(f"{scenario_id}: tahsis talebe eşit değil")
            for mode, label in MODES.items():
                tonnes = row[mode]
                rate = params["passive_rate"] if mode == "pas" else row["r"]
                revenue = 0.0 if mode == "yok" else tonnes * rate * 1000
                rfs_cost = tonnes * params["rfs_cost"] if mode == "rfs" else 0.0
                allocations.append(
                    {
                        "SCENARIO_ID": scenario_id,
                        "CUSTOMER_ID": row["cust"],
                        "SHIPMENT_ID": shipment["SHIPMENT_ID"],
                        "PRODUCT_ID": shipment["PRODUCT_ID"],
                        "MODE_ID": mode,
                        "MODE_NAME": label,
                        "TONNES": float(tonnes),
                        "REVENUE_USD": float(revenue),
                        "RFS_COST_USD": rfs_cost,
                        "REVENUE48_USD": revenue if mode not in ["yok", "pzt"] else 0.0,
                        "REVENUE49_USD": revenue if mode == "pzt" else 0.0,
                        "IS_TRANSPORTED": mode != "yok",
                        "WEEK": 49 if mode == "pzt" else 48,
                    }
                )
    tables = {
        "DIM_CUSTOMER": customers,
        "DIM_PRODUCT_PRIORITY": products,
        "DIM_LOYALTY_BENEFIT": benefits,
        "FACT_W48_DEMAND": demand,
        "FACT_W48_CAPACITY": capacity,
        "FACT_W48_ALLOCATION": allocations,
        "FACT_W48_SCENARIO": scenarios,
        "FACT_LOYALTY_COST": costs,
    }
    return {name: pd.DataFrame(rows) for name, rows in tables.items()}


def view_sql(root=ROOT):
    return (root / "sql/snowflake/02_views.sql").read_text()


def load_duckdb(tables, path=None):
    path = path or OUT / "flyup3.duckdb"
    path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(path)) as connection:
        connection.execute("BEGIN TRANSACTION")
        for name, frame in tables.items():
            connection.register("source_frame", frame)
            connection.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM source_frame")
            connection.unregister("source_frame")
        connection.execute(view_sql())
        connection.execute("COMMIT")


def load_parquet(tables, directory=None):
    directory = directory or OUT / "parquet"
    directory.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.to_parquet(directory / f"{name}.parquet", index=False)


def load_snowflake(tables):
    engine = create_engine(snowflake_url())
    database = identifier(os.getenv("SNOWFLAKE_DATABASE", "FLYUP3"))
    schema = identifier(os.getenv("SNOWFLAKE_SCHEMA", "BI"))
    try:
        with engine.begin() as connection:
            connection.execute(text(f"USE DATABASE {database}"))
            connection.execute(text(f"USE SCHEMA {schema}"))
            ddl = (ROOT / "sql/snowflake/01_tables.sql").read_text()
            for statement in ddl.split(";"):
                if statement.strip():
                    connection.execute(text(statement))
            for name, frame in tables.items():
                # SQLAlchemy Snowflake normalizes unquoted uppercase identifiers to lowercase.
                data = frame.copy()
                data.columns = [col.lower() for col in data.columns]
                connection.execute(text(f"DELETE FROM {name}"))
                data.to_sql(
                    name.lower(),
                    connection,
                    index=False,
                    if_exists="append",
                    method="multi",
                    chunksize=500,
                )
            for statement in view_sql().split(";"):
                if statement.strip():
                    connection.execute(text(statement))
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="FlyUp3 yıldız şema yükleyicisi")
    parser.add_argument("--target", choices=["duckdb", "snowflake", "parquet"], default="duckdb")
    args = parser.parse_args()
    load_env()
    try:
        if args.target == "snowflake":
            snowflake_url()  # Fail before reading any data when credentials are absent.
        tables = read_tables()
        {"duckdb": load_duckdb, "snowflake": load_snowflake, "parquet": load_parquet}[args.target](
            tables
        )
    except ValueError as error:
        parser.exit(2, f"Hata: {error}\n")
    print(f"{args.target}: {len(tables)} tablo yüklendi.")


if __name__ == "__main__":
    main()
