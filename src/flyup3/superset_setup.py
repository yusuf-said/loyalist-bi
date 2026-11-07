"""Superset migration, admin, dataset ve resmi dashboard import kurulumu."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from zipfile import ZipFile

import yaml

from flyup3.branding import generate_logo_assets
from flyup3.loader import (
    SNAPSHOT,
    VIEWS,
    duckdb_table_names,
    load_duckdb,
    read_tables,
    sources_available,
)
from flyup3.palette import LABEL_COLORS
from flyup3.settings import OUT, ROOT, prepare_superset_env, snowflake_url


def stable_id(name):
    return str(uuid5(NAMESPACE_URL, "flyup3/" + name))


COLUMN_LABELS = {
    "CUSTOMER_ID": "Müşteri",
    "TIER": "Kademe",
    "MAIN_PRODUCT": "Ana ürün",
    "ANNUAL_REVENUE_USD": "Yıllık gelir ($)",
    "ANNUAL_TONNES": "Yıllık hacim (t)",
    "WALLET_SHARE_RATIO": "Cüzdan payı",
    "WALLET_SHARE_PCT": "Cüzdan payı (%)",
    "PROFIT_USD_KG": "Kg başına kâr ($/kg)",
    "UNIT_REVENUE_USD_KG": "Birim gelir ($/kg)",
    "COMPETITOR_SHARE_PCT": "Rakip payı (%)",
    "STATION_COUNT": "İstasyon sayısı",
    "VOLUME_CHANGE_3M_PCT": "Son 3 ay hacim değişimi (%)",
    "PRODUCT_COUNT": "Ürün sayısı",
    "COMPLAINTS_6M": "Son 6 ay şikâyet",
    "DIGITAL_BOOKING_PCT": "Dijital rezervasyon (%)",
    "NO_SHOW_PCT": "Yük getirmeme (%)",
    "ALLOTMENT_USE_PCT": "Allotment kullanımı (%)",
    "PAYMENT_DELAY_DAYS": "Ödeme gecikmesi (gün)",
    "CSAT": "Memnuniyet puanı",
    "NPS": "Tavsiye puanı",
    "VISITS": "Ziyaret sayısı",
    "RENEWAL_DAYS": "Yenilemeye kalan gün",
    "Q4_VOLUME_PCT": "Son çeyrek hacim payı (%)",
    "HAS_CONTRACT": "Sözleşmeli",
    "SEGMENT_SCORE": "Segment puanı",
    "SEGMENT": "Segment",
    "CHURN_SCORE": "Kayıp riski puanı",
    "CHURN_LEVEL": "Kayıp riski",
    "DISCIPLINE_ALERT": "Disiplin uyarısı",
    "MACRO_GROUP": "Sadakat grubu",
    "UNCERTAINTY": "Belirsizlik",
    "COLOR_HEX": "Müşteri rengi",
    "PRODUCT_ID": "Ürün",
    "PRIORITY": "Öncelik",
    "DESCRIPTION": "Açıklama",
    "BENEFIT_ID": "Avantaj kodu",
    "BENEFIT_NAME": "Avantaj",
    "UNIT_COST_USD": "Birim maliyet ($)",
    "COST_RULE": "Maliyet kuralı",
    "CONDITION": "Koşul",
    "SHIPMENT_ID": "Gönderi kodu",
    "SHIPMENT_NAME": "Gönderi",
    "DEMAND_TONNES": "Teyitli talep (t)",
    "RATE_USD_KG": "Navlun ($/kg)",
    "ALLOTMENT_NOTE": "Allotment notu",
    "CRITICAL_CONDITION": "Kritik koşul",
    "CAPACITY_ID": "Kapasite kodu",
    "CAPACITY_NAME": "Kapasite kalemi",
    "NORMAL_TONNES": "Normal (t)",
    "CURRENT_TONNES": "Güncel (t)",
    "IS_AIR_COMPONENT": "Hava kapasitesi bileşeni",
    "IS_ACTIVE_LIMIT": "Aktif çözüm sınırı",
    "SCENARIO_ID": "Senaryo kodu",
    "SCENARIO_NAME": "Senaryo",
    "MODE_ID": "Taşıma modu kodu",
    "MODE_NAME": "Taşıma modu",
    "TONNES": "Tahsis (t)",
    "REVENUE_USD": "Gelir ($)",
    "RFS_COST_USD": "Kamyon maliyeti ($)",
    "REVENUE48_USD": "48. hafta gelir ($)",
    "REVENUE49_USD": "49. hafta gelir ($)",
    "IS_TRANSPORTED": "Taşınan",
    "WEEK": "Hafta",
    "NET48_USD": "Net gelir ($)",
    "DEFERRED49_USD": "Ertelenen gelir ($)",
    "MODEL_CONTRIBUTION_USD": "Model katkısı ($)",
    "UNTRANSPORTED_TONNES": "Taşınamayan (t)",
    "OFFLOAD_CUSTOMERS": "Offload müşterileri",
    "CHARTER_COUNT": "Ek sefer sayısı",
    "CHARTER_COST_USD": "Ek sefer maliyeti ($)",
    "BASE_COST_USD": "Sadakat maliyeti ($)",
    "STRESS_COST_USD": "Stres maliyeti ($)",
    "GUARANTEE_TONNES": "Peak garanti (t)",
    "ACTIVE_GUARANTEE_TONNES": "Aktif garanti (t)",
    "BREAK_EVEN_REVENUE_USD": "Başabaş geliri ($)",
    "TRANSPORTED_TONNES": "Taşınan (t)",
    "AIR48_TONNES": "Hava yolu (t)",
    "RFS_TONNES": "Kamyon (t)",
    "DEFERRED_TONNES": "Pazartesi (t)",
    "GROSS48_USD": "Brüt gelir ($)",
    "SIMPLE_CONTRIBUTION48_USD": "Basit katkı ($)",
    "CALCULATED_NET48_USD": "Hesaplanan net ($)",
    "CALCULATED_MODEL_CONTRIBUTION_USD": "Hesaplanan katkı ($)",
    "FIXED_COST_USD": "Sabit hizmet ($)",
    "REBATE_USD": "Rebate ($)",
    "BUDGET_USD": "Bütçe ($)",
    "BUDGET_USE_RATIO": "Bütçe kullanımı",
    "REMAINING_BUDGET_USD": "Kalan bütçe ($)",
    "CIP_USD": "CIP ($)",
    "SUPPORT_USD": "7/24 destek ($)",
    "SUMMIT_USD": "Zirve ($)",
    "SCORECARD_USD": "Karne ($)",
    "TRAINING_USD": "Eğitim ($)",
    "VISITS_USD": "Ziyaret ($)",
}
MONEY = "$,.0f"
NUMBER = ",.0f"
PERCENT = ".0%"


def chart_specs(datasets):
    """6.1'in ECharts eklentilerinin formData sözleşmeleri (pakette doğrulandı)."""

    def col(name, column):
        return next(
            c.column_name for c in datasets[name].columns if c.column_name.upper() == column
        )

    def metric(name, column, label=None, aggregate="SUM", sql=None):
        return {
            "expressionType": "SQL",
            "sqlExpression": sql or f"{aggregate}({col(name, column)})",
            "label": label or COLUMN_LABELS[column],
            "optionName": label or column,
            "hasCustomLabel": True,
        }

    specs = []

    def add(title, name, viz, **params):
        specs.append({"title": title, "dataset": name, "viz": viz, "params": params})

    def big(title, name, column, fmt=MONEY, subtitle="", sql=None):
        add(
            title,
            name,
            "big_number_total",
            metric=metric(name, column, sql=sql),
            y_axis_format=fmt,
            subheader=subtitle,
            header_font_size=0.35,
            subheader_font_size=0.2,
            show_metric_name=False,
        )

    scenario = "V_W48_SCENARIO_COMPARE"
    summary = "V_CUSTOMER_SUMMARY"
    big(
        "48. hafta · net gelir",
        scenario,
        "NET48_USD",
        subtitle="Seçili senaryo · varsayılan Plan A",
    )
    big(
        "Taşınan yük · t",
        scenario,
        "TRANSPORTED_TONNES",
        NUMBER,
        "221 t teyitli talepten · pazartesi dahil",
    )
    big("Yıllık sadakat maliyeti", summary, "BASE_COST_USD", subtitle="Sabit hizmet + rebate")
    big(
        "Sadakat bütçesi kullanımı",
        summary,
        "BASE_COST_USD",
        PERCENT,
        "$200,000 yıllık bütçe",
        sql=f"SUM({col(summary, 'BASE_COST_USD')}) / 200000.0",
    )

    def bar(title, name, x, columns, labels=None, groupby=None, **options):
        metrics = [
            metric(name, c, label) for c, label in zip(columns, labels or [None] * len(columns))
        ]
        add(
            title,
            name,
            "echarts_timeseries_bar",
            x_axis=col(name, x),
            metrics=metrics,
            groupby=[col(name, c) for c in groupby or []],
            orientation="horizontal",
            show_value=True,
            show_legend=True,
            legendOrientation="bottom",
            legendType="plain",
            y_axis_format=options.pop("y_axis_format", MONEY),
            x_axis_title="",
            y_axis_title="",
            truncate_metric=True,
            rich_tooltip=True,
            tooltipTimeFormat="smart_date",
            **options,
        )

    bar(
        "Müşteri bazında yıllık gelir · $",
        summary,
        "CUSTOMER_ID",
        ["ANNUAL_REVENUE_USD"],
        color_by_primary_axis=True,
        x_axis_sort="Yıllık gelir ($)",
        x_axis_sort_asc=False,
    )
    add(
        "Kademe bazında yıllık gelir payı",
        summary,
        "pie",
        groupby=[col(summary, "TIER")],
        metric=metric(summary, "ANNUAL_REVENUE_USD"),
        donut=True,
        innerRadius=55,
        outerRadius=78,
        show_labels=True,
        label_type="percent",
        number_format=MONEY,
        percent_format=".1%",
        show_legend=True,
        legendType="plain",
        legendOrientation="bottom",
        sort_by_metric=True,
    )
    add(
        "Segmentasyon · eşikler %60 ve $0,50/kg",
        summary,
        "bubble_v2",
        # entity ile series aynı sütun olursa tarayıcı "Duplicate column labels" hatası verir.
        entity=col(summary, "CUSTOMER_ID"),
        series=col(summary, "MACRO_GROUP"),
        x=metric(summary, "WALLET_SHARE_RATIO", aggregate="MAX"),
        y=metric(summary, "PROFIT_USD_KG", aggregate="MAX"),
        size=metric(summary, "ANNUAL_REVENUE_USD"),
        xAxisFormat=PERCENT,
        y_axis_format="$.2f",
        tooltipSizeFormat=MONEY,
        x_axis_label="Cüzdan payı (%)",
        y_axis_label="Kg başına kâr ($/kg)",
        x_axis_title_margin=35,
        y_axis_title_margin=45,
        max_bubble_size=32,
        opacity=0.8,
        show_legend=True,
        legendOrientation="bottom",
        x_axis_bounds=[0, 1],
        y_axis_bounds=[0, 1],
        truncateXAxis=True,
        description="Balon boyutu yıllık gelirdir. Sadakat eşiği %60; kârlılık eşiği $0,50/kg.",
    )
    bar(
        "48. hafta · müşteri ve taşıma modu · t",
        "V_W48_ALLOCATION",
        "CUSTOMER_ID",
        ["TONNES"],
        groupby=["MODE_NAME"],
        stack="Stack",
        y_axis_format=NUMBER,
        description="Senaryo filtresi varsayılan Plan A. Pazartesi 49. haftadır; kırmızı taşınamayan yüktür.",
    )

    def table(title, name, columns, **options):
        add(
            title,
            name,
            "table",
            query_mode="raw",
            all_columns=[col(name, c) for c in columns],
            groupby=[],
            metrics=[],
            show_cell_bars=False,
            include_search=False,
            table_timestamp_format="smart_date",
            page_length=0,
            column_config={
                col(name, c): {"d3NumberFormat": MONEY if c.endswith("_USD") else NUMBER}
                for c in columns
                if c.endswith(("_USD", "_TONNES"))
            },
            **options,
        )

    table(
        "Plan A / B · gelir, katkı ve kayıp",
        scenario,
        ["SCENARIO_NAME", "NET48_USD", "MODEL_CONTRIBUTION_USD", "UNTRANSPORTED_TONNES"],
        description="İki plan birlikte gösterilir; senaryo ve müşteri filtrelerinden bağımsızdır.",
    )
    bar(
        "Normal → güncel kapasite · toplam hava 230 → 175 t",
        "V_CAPACITY_COMPARE",
        "CAPACITY_NAME",
        ["NORMAL_TONNES", "CURRENT_TONNES"],
        y_axis_format=NUMBER,
    )
    table(
        "Ek kapasite · normal değer belirtilmemiş",
        "V_CAPACITY_EXTRA",
        ["CAPACITY_NAME", "CURRENT_TONNES"],
    )
    bar(
        "Müşteri başına sadakat maliyeti · $",
        summary,
        "CUSTOMER_ID",
        ["FIXED_COST_USD", "REBATE_USD"],
        labels=["Sabit hizmet", "Rebate"],
        stack="Stack",
    )
    add(
        "Sadakat bütçesi · üst sınır $200,000",
        summary,
        "gauge_chart",
        metric=metric(
            summary,
            "BASE_COST_USD",
            "Bütçe kullanımı",
            sql=f"SUM({col(summary, 'BASE_COST_USD')}) / 200000.0",
        ),
        groupby=[],
        min_val=0,
        max_val=1,
        number_format=PERCENT,
        value_formatter="{value}",
        start_angle=180,
        end_angle=0,
        show_progress=True,
        show_pointer=True,
        show_axis_tick=False,
        show_split_line=False,
        split_number=4,
        font_size=14,
        description="Müşteri filtresi seçili müşterilerin toplam $200,000 bütçeden aldığı payı gösterir.",
    )
    table(
        "Kime hangi avantaj · yıllık maliyet ($) ve garanti (t)",
        "V_LOYALTY_MATRIX",
        [
            "CUSTOMER_ID",
            "REBATE_USD",
            "GUARANTEE_TONNES",
            "ACTIVE_GUARANTEE_TONNES",
            "CIP_USD",
            "SUPPORT_USD",
            "SUMMIT_USD",
            "SCORECARD_USD",
            "TRAINING_USD",
            "VISITS_USD",
        ],
        description="0: avantaj tahsis edilmemiştir. Garanti kapasitesinin doğrudan nakit maliyeti yoktur.",
    )
    return specs


def chart_query(dataset, params, default_filters):
    """Kaydedilen context de tarayıcının ECharts pivot/flatten çıktısını üretir."""
    viz = params["viz_type"]
    metrics = params.get("metrics") or ([params["metric"]] if "metric" in params else [])
    columns = params.get("groupby", [])
    post = []
    if viz == "table":
        columns = params["all_columns"]
    elif viz == "bubble_v2":
        columns = list(dict.fromkeys([params["entity"], params["series"]]))
        metrics = [params[k] for k in ["x", "y", "size"]]
    elif viz == "echarts_timeseries_bar":
        columns = list(dict.fromkeys([params["x_axis"], *columns]))
        post = [
            {
                "operation": "pivot",
                "options": {
                    "index": [params["x_axis"]],
                    "columns": params["groupby"],
                    "aggregates": {m["label"]: {"operator": "mean"} for m in metrics},
                    "drop_missing_columns": True,
                },
            }
        ]
        if params["groupby"] and len(metrics) == 1:
            post.append(
                {
                    "operation": "rename",
                    "options": {
                        "columns": {metrics[0]["label"]: None},
                        "level": 0,
                        "inplace": True,
                    },
                }
            )
        if params.get("x_axis_sort"):
            post.append(
                {
                    "operation": "sort",
                    "options": {
                        "by": params["x_axis_sort"],
                        "ascending": params["x_axis_sort_asc"],
                    },
                }
            )
        post.append({"operation": "flatten"})
    elif viz == "pie":
        post = [
            {
                "operation": "contribution",
                "options": {
                    "columns": [metrics[0]["label"]],
                    "rename_columns": [metrics[0]["label"] + "__contribution"],
                },
            }
        ]
    filters = list(default_filters)
    actual = {c.column_name.upper(): c.column_name for c in dataset.columns}
    if "SCENARIO_NAME" in actual and not filters:
        filters = [{"col": actual["SCENARIO_NAME"], "op": "IN", "val": ["Plan A", "Plan B"]}]
    query = {
        "columns": columns,
        "metrics": metrics,
        "filters": filters,
        "time_range": "No filter",
        "row_limit": 1000,
        "orderby": [],
        "extras": {"having": "", "where": ""},
        "post_processing": post,
    }
    if viz == "echarts_timeseries_bar":
        query["series_columns"] = params["groupby"]
    return {
        "datasource": {"id": dataset.id, "type": "table"},
        "force": False,
        "result_format": "json",
        "result_type": "full",
        "queries": [query],
    }


def dashboard_bundle(database, datasets, schema, target):
    """Superset v1 YAML/ZIP; UUID'ler sabit, bağlantı sırları dışa aktarılmaz."""
    db_uuid = str(database.uuid)
    safe_uri = (
        "duckdb:///" + str(OUT / "flyup3.duckdb")
        if target == "duckdb"
        else "snowflake://placeholder@placeholder/FLYUP3/BI"
    )
    contents = {
        "metadata.yaml": {"version": "1.0.0", "type": "Dashboard"},
        "databases/flyup3.yaml": {
            "database_name": database.database_name,
            "sqlalchemy_uri": safe_uri,
            "uuid": db_uuid,
            "version": "1.0.0",
        },
    }
    for name, dataset in datasets.items():
        contents[f"datasets/flyup3/{name}.yaml"] = {
            "table_name": dataset.table_name,
            "schema": schema,
            "uuid": str(dataset.uuid),
            "database_uuid": db_uuid,
            "version": "1.0.0",
            "columns": [
                {
                    "column_name": c.column_name,
                    "type": c.type,
                    "verbose_name": COLUMN_LABELS[c.column_name.upper()],
                    "groupby": True,
                    "filterable": True,
                }
                for c in dataset.columns
            ],
            "metrics": [
                {
                    "metric_name": "count",
                    "verbose_name": "Kayıt sayısı",
                    "expression": "COUNT(*)",
                    "d3format": NUMBER,
                }
            ],
        }
    specs = chart_specs(datasets)
    for index, spec in enumerate(specs):
        dataset = datasets[spec["dataset"]]
        params = {
            "viz_type": spec["viz"],
            "row_limit": 1000,
            "time_range": "No filter",
            "color_scheme": "thy",
            "adhoc_filters": [],
            "order_desc": True,
            **spec["params"],
        }
        if index == 8:
            column = next(
                c.column_name for c in dataset.columns if c.column_name.upper() == "SCENARIO_NAME"
            )
            params["adhoc_filters"] = [
                {
                    "expressionType": "SIMPLE",
                    "clause": "WHERE",
                    "subject": column,
                    "operator": "IN",
                    "comparator": ["Plan A", "Plan B"],
                }
            ]
        default_filters = []
        if index in [0, 1, 7]:
            column = next(
                c.column_name for c in dataset.columns if c.column_name.upper() == "SCENARIO_NAME"
            )
            default_filters = [{"col": column, "op": "IN", "val": ["Plan A"]}]
        contents[f"charts/chart_{index}.yaml"] = {
            "slice_name": spec["title"],
            "description": params.pop("description", ""),
            "viz_type": spec["viz"],
            "params": params,
            "query_context": json.dumps(chart_query(dataset, params, default_filters)),
            "uuid": stable_id(f"{target}/chart/{index}"),
            "dataset_uuid": str(dataset.uuid),
            "version": "1.0.0",
        }
    position = {
        "DASHBOARD_VERSION_KEY": "v2",
        "ROOT_ID": {"id": "ROOT_ID", "type": "ROOT", "children": ["GRID_ID"]},
        "GRID_ID": {"id": "GRID_ID", "type": "GRID", "parents": ["ROOT_ID"], "children": []},
    }

    def place_chart(index, width, height, parent, parents):
        key = f"CHART-{index}"
        position[parent]["children"].append(key)
        position[key] = {
            "id": key,
            "type": "CHART",
            "parents": [*parents, parent],
            "children": [],
            "meta": {
                "uuid": stable_id(f"{target}/chart/{index}"),
                "chartId": index + 1,
                "width": width,
                "height": height,
                "sliceName": specs[index]["title"],
            },
        }

    rows = [
        ([(0, 3), (1, 3), (2, 3), (3, 3)], 16),
        ([(4, 8), (5, 4)], 36),
        ([(6, 6), (7, 6)], 44),
        ([(9, 7)], 44),
        ([(11, 8), (12, 4)], 34),
        ([(13, 12)], 42),
    ]
    for row, (items, height) in enumerate(rows):
        row_id = f"ROW-{row}"
        position["GRID_ID"]["children"].append(row_id)
        parents = ["ROOT_ID", "GRID_ID"]
        position[row_id] = {
            "id": row_id,
            "type": "ROW",
            "parents": parents,
            "children": [],
            "meta": {"background": "BACKGROUND_TRANSPARENT"},
        }
        for index, width in items:
            place_chart(index, width, height, row_id, parents)
        if row == 3:
            key = "COLUMN-COMPARE"
            position[row_id]["children"].append(key)
            position[key] = {
                "id": key,
                "type": "COLUMN",
                "parents": [*parents, row_id],
                "children": [],
                "meta": {"width": 5, "background": "BACKGROUND_TRANSPARENT"},
            }
            for index, chart_height in [(8, 21), (10, 23)]:
                place_chart(index, 5, chart_height, key, [*parents, row_id])

    def native_filter(name, dataset_name, column, included, default=None):
        dataset = datasets[dataset_name]
        actual = next(c.column_name for c in dataset.columns if c.column_name.upper() == column)
        filters = [{"col": actual, "op": "IN", "val": [default]}] if default else []
        return {
            "id": "NATIVE_FILTER-" + column,
            "name": name,
            "filterType": "filter_select",
            "type": "NATIVE_FILTER",
            "targets": [{"datasetUuid": str(dataset.uuid), "column": {"name": actual}}],
            "cascadeParentIds": [],
            "controlValues": {
                "enableEmptyFilter": False,
                "multiSelect": default is None,
                "searchAllOptions": False,
                "inverseSelection": False,
            },
            "defaultDataMask": {
                "extraFormData": {"filters": filters},
                "filterState": {"value": [default], "label": default} if default else {},
            },
            "scope": {
                "rootPath": ["ROOT_ID"],
                "excluded": [i + 1 for i in range(len(specs)) if i not in included],
            },
        }

    contents["dashboards/flyup3.yaml"] = {
        "dashboard_title": "FlyUp3 · Milano kapasite ve sadakat",
        "slug": "flyup3-" + target,
        "uuid": stable_id(target + "/dashboard"),
        "version": "1.0.0",
        "position": position,
        "metadata": {
            "color_scheme": "thy",
            "label_colors": LABEL_COLORS,
            "native_filter_configuration": [
                native_filter("Senaryo", "V_W48_ALLOCATION", "SCENARIO_NAME", [0, 1, 7], "Plan A"),
                native_filter(
                    "Müşteri", "V_CUSTOMER_SUMMARY", "CUSTOMER_ID", [2, 3, 4, 5, 6, 7, 11, 12, 13]
                ),
            ],
        },
        "published": True,
    }
    serialized = {
        key: yaml.safe_dump(value, allow_unicode=True, sort_keys=False)
        for key, value in contents.items()
    }
    path = OUT / f"flyup3_dashboard_{target}.zip"
    with ZipFile(path, "w") as bundle:
        for key, value in serialized.items():
            bundle.writestr("flyup3/" + key, value)
    return path, serialized


def register(target):
    from flask import g
    from superset import create_app, db

    app = create_app()
    with app.app_context():
        from superset.commands.chart.importers.v1 import ImportChartsCommand
        from superset.commands.dashboard.importers.v1 import ImportDashboardsCommand
        from superset.commands.dataset.importers.v1 import ImportDatasetsCommand
        from superset.connectors.sqla.models import SqlaTable
        from superset.models.core import Database
        from superset.models.dashboard import Dashboard
        from superset.utils.core import override_user

        sm = app.appbuilder.sm
        username = os.environ["SUPERSET_ADMIN_USERNAME"]
        user = sm.find_user(username=username)
        if user is None:
            email = os.getenv("SUPERSET_ADMIN_EMAIL", "admin@example.invalid")
            if sm.find_user(email=email):
                raise ValueError(
                    "Admin e-posta adresi başka kullanıcıda kayıtlı; .env alanlarını kontrol edin."
                )
            user = sm.add_user(
                username=username,
                first_name=os.getenv("SUPERSET_ADMIN_FIRSTNAME", "FlyUp3"),
                last_name=os.getenv("SUPERSET_ADMIN_LASTNAME", "Admin"),
                email=email,
                role=sm.find_role("Admin"),
                password=os.environ["SUPERSET_ADMIN_PASSWORD"],
            )
            if not user:
                raise RuntimeError("Admin kullanıcısı oluşturulamadı.")
        g.user = user
        uri = snowflake_url() if target == "snowflake" else f"duckdb:///{OUT}/flyup3.duckdb"
        schema = os.getenv("SNOWFLAKE_SCHEMA", "BI").lower() if target == "snowflake" else "main"
        name = f"FlyUp3 {target}"
        database = db.session.query(Database).filter_by(database_name=name).one_or_none()
        if database is None:
            database = Database(database_name=name, uuid=uuid5(NAMESPACE_URL, "flyup3/" + target))
            db.session.add(database)
        database.set_sqlalchemy_uri(str(uri))
        database.expose_in_sqllab = True
        if target == "duckdb":
            database.extra = json.dumps({"engine_params": {"connect_args": {"read_only": True}}})
        db.session.commit()
        tables = read_tables() if sources_available() else duckdb_table_names()
        datasets = {}
        for name in [*tables, *VIEWS]:
            table_name = name.lower() if target == "snowflake" else name
            dataset = (
                db.session.query(SqlaTable)
                .filter_by(database_id=database.id, table_name=table_name, schema=schema)
                .one_or_none()
            )
            if dataset is None:
                dataset = SqlaTable(
                    table_name=table_name,
                    schema=schema,
                    database=database,
                    uuid=uuid5(NAMESPACE_URL, f"flyup3/{target}/{name}"),
                )
                db.session.add(dataset)
            dataset.owners = [user]
            dataset.fetch_metadata()
            datasets[name] = dataset
        db.session.commit()
        with override_user(user):
            path, contents = dashboard_bundle(database, datasets, schema, target)
            # Dashboard importer 6.1 intentionally uses overwrite=False for dependencies.
            # Explicitly import the same YAML datasets/charts before importing the layout.
            dependencies = {**contents, "metadata.yaml": "version: 1.0.0\n"}
            ImportDatasetsCommand(dependencies, overwrite=True).run()
            ImportChartsCommand(dependencies, overwrite=True).run()
            ImportDashboardsCommand(contents, overwrite=True).run()
        dashboard = db.session.query(Dashboard).filter_by(slug="flyup3-" + target).one()
        if len(dashboard.slices) != 14:
            raise RuntimeError("Dashboard import sonucu 14 grafik içermiyor.")
        print(
            f"{len(datasets)} dataset ve {len(dashboard.slices)} grafik import edildi: {path.name}"
        )
        print(f"Dashboard: /superset/dashboard/{dashboard.slug}/")


def main():
    parser = argparse.ArgumentParser(description="FlyUp3 Superset kurulumu")
    parser.add_argument("--target", choices=["duckdb", "snowflake"])
    args = parser.parse_args()
    prepare_superset_env()
    generate_logo_assets()
    required = ["SUPERSET_SECRET_KEY", "SUPERSET_ADMIN_USERNAME", "SUPERSET_ADMIN_PASSWORD"]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        parser.exit(2, "Eksik ortam değişkenleri: " + ", ".join(missing) + "\n")
    target = args.target or ("snowflake" if os.getenv("SNOWFLAKE_ACCOUNT") else "duckdb")
    if target == "duckdb":
        if sources_available():
            load_duckdb(read_tables())
        elif SNAPSHOT.exists():
            # Kaynak dosyalar olmayan klonlarda depodaki anlık görüntü kullanılır.
            shutil.copyfile(SNAPSHOT, OUT / "flyup3.duckdb")
            print(f"Kaynak dosyalar yok; {SNAPSHOT.relative_to(ROOT)} kullanıldı.")
        else:
            parser.exit(2, "Ne kaynak vaka dosyaları ne de data/flyup3.duckdb bulundu.\n")
    if target == "snowflake":
        snowflake_url()
    for command in [["db", "upgrade"], ["init"]]:
        subprocess.run(
            [str(Path(sys.executable).parent / "superset"), *command], cwd=ROOT, check=True
        )
    register(target)
    # Re-sync permissions after datasets have been registered.
    subprocess.run([str(Path(sys.executable).parent / "superset"), "init"], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
