import json
import re

import duckdb
import pandas as pd
import pytest
import sqlglot

from flyup3.loader import load_duckdb, load_parquet, read_tables, sources_available
from flyup3.palette import CUSTOMER_COLORS, powerbi_theme
from flyup3.settings import ROOT, snowflake_url

# Bu modül kaynak vaka dosyalarından okur; dosyalar git dışında olduğu için klonlarda atlanır.
pytestmark = pytest.mark.skipif(not sources_available(), reason="kaynak vaka dosyaları git dışında")


@pytest.fixture(scope="module")
def tables():
    return read_tables()


@pytest.fixture(scope="module")
def database(tables, tmp_path_factory):
    path = tmp_path_factory.mktemp("data") / "flyup3.duckdb"
    load_duckdb(tables, path)
    return path


def test_demand_capacity(tables):
    assert tables["FACT_W48_DEMAND"].DEMAND_TONNES.sum() == 221
    capacity = tables["FACT_W48_CAPACITY"]
    assert capacity.loc[capacity.IS_AIR_COMPONENT, "CURRENT_TONNES"].sum() == 175
    assert capacity.loc[capacity.IS_ACTIVE_LIMIT, "CURRENT_TONNES"].item() == 30


def test_customer_results(tables):
    customers = tables["DIM_CUSTOMER"].set_index("CUSTOMER_ID")
    assert customers.loc["Medivia", "ANNUAL_REVENUE_USD"] == 3565000
    assert customers.loc["Nord", "ANNUAL_REVENUE_USD"] == 3570000
    assert customers.TIER.to_dict() == {
        "Medivia": "Elite Plus",
        "Nord": "Classic",
        "Bella": "Elite",
        "Veloce": "Elite",
        "Lago": "Classic",
        "Rossi": "Classic Plus",
    }
    assert customers.MACRO_GROUP.to_dict() == {
        "Medivia": "Saf sadakat",
        "Veloce": "Saf sadakat",
        "Rossi": "Sahte sadakat",
        "Bella": "Kârlı sadakatsizlik",
        "Nord": "Sadakatsizlik",
        "Lago": "Sadakatsizlik",
    }
    assert customers.COLOR_HEX.to_dict() == CUSTOMER_COLORS
    assert (
        customers.loc["Bella", "ALLOTMENT_USE_PCT"] != customers.loc["Bella", "ALLOTMENT_USE_PCT"]
    )
    assert pd.isna(customers.loc["Veloce", "RENEWAL_DAYS"])


@pytest.mark.parametrize(
    "scenario,net,contribution,untransported",
    [("urun_onceligi", 390900, 102725, 1), ("oneri_b", 374200, 99600, 8)],
)
def test_scenario(database, scenario, net, contribution, untransported):
    with duckdb.connect(str(database), read_only=True) as con:
        result = con.execute(
            "SELECT NET48_USD, MODEL_CONTRIBUTION_USD, "
            "UNTRANSPORTED_TONNES, CALCULATED_NET48_USD, "
            "CALCULATED_MODEL_CONTRIBUTION_USD "
            "FROM V_W48_SCENARIO_COMPARE WHERE SCENARIO_ID = ?",
            [scenario],
        ).fetchone()
        assert result == pytest.approx((net, contribution, untransported, net, contribution))
        if scenario == "urun_onceligi":
            row = con.execute(
                "SELECT CUSTOMER_ID, PRODUCT_ID, TONNES FROM FACT_W48_ALLOCATION "
                "WHERE SCENARIO_ID = ? AND MODE_ID = 'yok' AND TONNES > 0",
                [scenario],
            ).fetchone()
            assert row == ("Nord", "TK General", 1.0)


def test_loyalty_budget(database):
    with duckdb.connect(str(database), read_only=True) as con:
        assert con.execute(
            "SELECT BASE_COST_USD, FIXED_COST_USD, REBATE_USD, BUDGET_USD, "
            "STRESS_COST_USD FROM V_LOYALTY_BUDGET"
        ).fetchone() == pytest.approx((102079.5, 52200, 49879.5, 200000, 116114.5))
        assert (
            con.execute("SELECT SUM(BASE_COST_USD) FROM V_CUSTOMER_SUMMARY").fetchone()[0]
            == 102079.5
        )


def test_star_keys_and_conservation(tables, database):
    customers = set(tables["DIM_CUSTOMER"].CUSTOMER_ID)
    products = set(tables["DIM_PRODUCT_PRIORITY"].PRODUCT_ID)
    benefits = set(tables["DIM_LOYALTY_BENEFIT"].BENEFIT_ID)
    for name, frame in tables.items():
        if "CUSTOMER_ID" in frame:
            assert set(frame.CUSTOMER_ID) <= customers, name
        if "PRODUCT_ID" in frame:
            assert set(frame.PRODUCT_ID) <= products, name
        if "BENEFIT_ID" in frame:
            assert set(frame.BENEFIT_ID) <= benefits, name
    allocation = tables["FACT_W48_ALLOCATION"]
    assert not allocation.duplicated(["SCENARIO_ID", "SHIPMENT_ID", "MODE_ID"]).any()
    assert (
        allocation.groupby(["SCENARIO_ID", "SHIPMENT_ID"])
        .TONNES.sum()
        .groupby(level=0)
        .sum()
        .eq(221)
        .all()
    )
    with duckdb.connect(str(database), read_only=True) as con:
        rows = con.execute(
            "SELECT NET48_USD - CALCULATED_NET48_USD, "
            "MODEL_CONTRIBUTION_USD - CALCULATED_MODEL_CONTRIBUTION_USD "
            "FROM V_W48_SCENARIO_COMPARE"
        ).fetchall()
        for row in rows:
            assert row == pytest.approx((0.0, 0.0))


def test_parquet_roundtrip(tables, tmp_path):
    load_parquet(tables, tmp_path)
    for name, frame in tables.items():
        pd.testing.assert_frame_equal(pd.read_parquet(tmp_path / f"{name}.parquet"), frame)


@pytest.mark.parametrize(
    "path", sorted((ROOT / "sql/snowflake").glob("*.sql")), ids=lambda p: p.name
)
def test_snowflake_sql(path):
    statements = sqlglot.parse(
        path.read_text(), read="snowflake", error_level=sqlglot.ErrorLevel.RAISE
    )
    assert statements
    # A parser fallback to Command would hide syntax errors.
    for statement in statements:
        if isinstance(statement, sqlglot.exp.Command):
            # sqlglot 28 parses SnowSQL PUT only as a generic client command.
            assert statement.this == "PUT"
            assert re.fullmatch(
                r"file://out/parquet/[A-Z0-9_]+\.parquet @[A-Z0-9_/]+ "
                r"AUTO_COMPRESS = FALSE OVERWRITE = TRUE",
                statement.expression.strip(),
            )


def test_powerbi_theme():
    assert json.loads((ROOT / "powerbi/thy_turkish_cargo.json").read_text()) == powerbi_theme()


def test_missing_snowflake_credentials(monkeypatch):
    from flyup3 import settings

    monkeypatch.setattr(settings, "load_env", lambda: None)
    for key in ["ACCOUNT", "USER", "PASSWORD", "AUTHENTICATOR", "ROLE", "WAREHOUSE"]:
        monkeypatch.delenv("SNOWFLAKE_" + key, raising=False)
    with pytest.raises(ValueError, match="Snowflake bilgileri eksik"):
        snowflake_url()


def test_snowflake_ddl_matches_frames(tables):
    statements = sqlglot.parse((ROOT / "sql/snowflake/01_tables.sql").read_text(), read="snowflake")
    for statement, (name, frame) in zip(statements, tables.items(), strict=True):
        schema = statement.this
        assert schema.this.name == name
        assert [col.name for col in schema.expressions] == list(frame.columns)


def test_visual_views(database):
    with duckdb.connect(str(database), read_only=True) as con:
        assert con.execute(
            "SELECT SUM(TONNES), SUM(CASE WHEN MODE_ID <> 'yok' THEN TONNES ELSE 0 END) "
            "FROM V_W48_ALLOCATION WHERE SCENARIO_NAME = 'Plan A'"
        ).fetchone() == (221, 220)
        assert con.execute(
            "SELECT NORMAL_TONNES, CURRENT_TONNES FROM V_CAPACITY_COMPARE WHERE CAPACITY_ID = 'C04'"
        ).fetchone() == (230, 175)
        assert con.execute("SELECT COUNT(*) FROM V_CAPACITY_EXTRA").fetchone()[0] == 3
        assert con.execute(
            "SELECT SUM(REBATE_USD), SUM(GUARANTEE_TONNES), SUM(ACTIVE_GUARANTEE_TONNES) "
            "FROM V_LOYALTY_MATRIX"
        ).fetchone() == pytest.approx((49879.5, 55, 20))
        assert con.execute(
            "SELECT SUM(FIXED_COST_USD), SUM(REBATE_USD), MAX(WALLET_SHARE_RATIO) "
            "FROM V_CUSTOMER_SUMMARY"
        ).fetchone()[:2] == pytest.approx((52200, 49879.5))


def test_dashboard_bundle(tables, database, tmp_path, monkeypatch):
    from collections import Counter
    from types import SimpleNamespace

    import yaml

    from flyup3 import superset_setup
    from flyup3.loader import VIEWS
    from flyup3.palette import LABEL_COLORS, TIER_COLORS

    datasets = {}
    with duckdb.connect(str(database), read_only=True) as con:
        for index, name in enumerate([*tables, *VIEWS]):
            datasets[name] = SimpleNamespace(
                id=index + 1,
                table_name=name,
                uuid=superset_setup.stable_id(name),
                columns=[
                    SimpleNamespace(column_name=c[0], type=c[1])
                    for c in con.execute(f"DESCRIBE {name}").fetchall()
                ],
            )
    monkeypatch.setattr(superset_setup, "OUT", tmp_path)
    db = SimpleNamespace(uuid=superset_setup.stable_id("database"), database_name="test")
    path, serialized = superset_setup.dashboard_bundle(db, datasets, "main", "duckdb")
    first = path.read_bytes()
    _, repeated = superset_setup.dashboard_bundle(db, datasets, "main", "duckdb")
    assert serialized == repeated
    assert first
    charts = [yaml.safe_load(v) for k, v in serialized.items() if k.startswith("charts/")]
    assert Counter(c["viz_type"] for c in charts) == {
        "big_number_total": 4,
        "echarts_timeseries_bar": 4,
        "pie": 1,
        "bubble_v2": 1,
        "gauge_chart": 1,
        "table": 3,
    }
    dashboard = yaml.safe_load(serialized["dashboards/flyup3.yaml"])
    assert dashboard["metadata"]["label_colors"] == LABEL_COLORS
    assert {k: LABEL_COLORS[k] for k in CUSTOMER_COLORS} == CUSTOMER_COLORS
    assert {k: LABEL_COLORS[k] for k in TIER_COLORS} == TIER_COLORS
    assert LABEL_COLORS["Taşınamayan"] == "#C90019"
    filters = dashboard["metadata"]["native_filter_configuration"]
    assert [f["name"] for f in filters] == ["Senaryo", "Müşteri"]
    assert filters[0]["defaultDataMask"]["filterState"]["value"] == ["Plan A"]
    assert 9 in filters[0]["scope"]["excluded"]  # comparison keeps both plans
    position = dashboard["position"]
    assert sum(position[c]["meta"]["width"] for c in position["ROW-0"]["children"]) == 12
    assert (
        max(
            c["meta"]["height"]
            for c in position.values()
            if isinstance(c, dict) and c.get("type") == "CHART"
        )
        <= 44
    )
    for chart in charts:
        params = chart["params"]
        assert params["color_scheme"] == "thy"
        assert params.get("show_cell_bars", False) is False
        context = json.loads(chart["query_context"])
        assert context["queries"]
        if chart["viz_type"] == "echarts_timeseries_bar":
            assert context["queries"][0]["post_processing"][0]["operation"] == "pivot"
    for key, value in serialized.items():
        if key.startswith("datasets/"):
            assert all(
                c["verbose_name"] and "_" not in c["verbose_name"]
                for c in yaml.safe_load(value)["columns"]
            )


def test_brand_assets():
    import runpy
    from hashlib import sha256
    from xml.etree import ElementTree as ET

    from flask import Flask

    from flyup3.branding import (
        ASSET_ROOT,
        DARK_LOGO_URL,
        DASHBOARD_URL,
        FAVICON_URL,
        LOGO_URL,
        generate_logo_assets,
        register_brand_assets,
    )
    from flyup3.palette import superset_theme

    original_paths = [
        ASSET_ROOT / n
        for n in [
            "thy_logo_horizontal.svg",
            "thy_logo_compact.svg",
            "SOURCE.md",
        ]
    ]
    original = {p: sha256(p.read_bytes()).hexdigest() for p in original_paths}
    generate_logo_assets()
    assert original == {p: sha256(p.read_bytes()).hexdigest() for p in original_paths}
    source = original_paths[0].read_text()
    white = (ASSET_ROOT / "generated/thy_logo_horizontal_white.svg").read_text()
    assert white == source.replace("fill:#000000", "fill:#FFFFFF")
    emblem = ET.parse(ASSET_ROOT / "generated/thy_emblem.svg").getroot()
    assert emblem.attrib["viewBox"] == "49 49 126 126"
    assert len(list(emblem)) == 2
    app = Flask(__name__)
    register_brand_assets(app)
    with app.test_client() as client:
        for url in [LOGO_URL, DARK_LOGO_URL, FAVICON_URL]:
            response = client.get(url)
            assert response.status_code == 200
            assert response.mimetype == "image/svg+xml"
        assert client.get("/flyup3-assets/SOURCE.md").status_code == 404
    config = runpy.run_path(str(ROOT / "superset_config.py"))
    assert config["APP_NAME"] == "THY · FlyUp3"
    assert config["APP_ICON"] == LOGO_URL
    assert config["FAVICONS"][0]["href"] == FAVICON_URL
    for dark, url in [(False, LOGO_URL), (True, DARK_LOGO_URL)]:
        token = superset_theme(dark)["token"]
        assert token["brandLogoUrl"] == url
        assert token["brandLogoHref"] == DASHBOARD_URL
        assert token["brandLogoHeight"] == "30px"
