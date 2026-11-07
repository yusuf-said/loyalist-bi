import importlib
import sqlite3
import sys
import types

from flyup3 import mcp_branding
from flyup3.palette import COLORS, CUSTOMER_COLORS, PRIMARY


def test_vega_lite_uses_thy_colors():
    spec = {
        "data": {"values": [{"c": "Medivia", "v": 1}, {"c": "Nord", "v": 2}]},
        "mark": "bar",
        "encoding": {
            "color": {"field": "c", "type": "nominal"},
            "opacity": {"field": "v", "scale": {"scheme": "viridis"}},
        },
    }
    mcp_branding.brand_vega_lite(spec)
    assert spec["config"]["range"]["category"] == COLORS
    assert spec["config"]["bar"]["color"] == PRIMARY["main"]
    assert spec["encoding"]["color"]["scale"]["range"] == [
        CUSTOMER_COLORS["Medivia"],
        CUSTOMER_COLORS["Nord"],
    ]
    assert "scheme" not in spec["encoding"]["opacity"]["scale"]


def test_unknown_labels_keep_category_range():
    spec = {
        "data": {"values": [{"c": "x"}, {"c": "y"}]},
        "encoding": {"color": {"field": "c"}},
    }
    mcp_branding.brand_vega_lite(spec)
    assert "scale" not in spec["encoding"]["color"]


def test_catalog_lists_ids_and_columns(tmp_path):
    path = tmp_path / "superset.db"
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE dbs (id INTEGER, database_name TEXT);
        CREATE TABLE dashboards (id INTEGER, dashboard_title TEXT, slug TEXT);
        CREATE TABLE tables (id INTEGER, table_name TEXT);
        CREATE TABLE table_columns (id INTEGER, table_id INTEGER, column_name TEXT,
                                    verbose_name TEXT);
        INSERT INTO dbs VALUES (1, 'FlyUp3 duckdb');
        INSERT INTO dashboards VALUES (1, 'FlyUp3', 'flyup3-duckdb');
        INSERT INTO tables VALUES (9, 'V_CUSTOMER_SUMMARY');
        INSERT INTO table_columns VALUES (1, 9, 'CUSTOMER_ID', 'Müşteri'), (2, 9, 'NPS', NULL);
        """
    )
    con.close()
    text = mcp_branding.catalog_text(path)
    assert 'id 1 "FlyUp3 duckdb"' in text
    assert "/superset/dashboard/flyup3-duckdb/" in text
    assert "9 · V_CUSTOMER_SUMMARY: CUSTOMER_ID (Müşteri), NPS" in text
    assert mcp_branding.catalog_text(tmp_path / "yok.db") == ""


def test_apply_patches_instructions_and_preview(monkeypatch):
    app = types.ModuleType("superset.mcp_service.app")
    app.get_default_instructions = lambda branding="Superset": f"base {branding}"

    def init(name=None, instructions=None):
        return name

    app.init_fastmcp_server = init
    app.mcp = types.SimpleNamespace(_mcp_server=types.SimpleNamespace(name="old"))
    from flyup3 import sim_tools

    registrations = []
    monkeypatch.setattr(sim_tools, "register", lambda mcp: registrations.append(mcp))
    preview = types.ModuleType("superset.mcp_service.chart.tool.get_chart_preview")

    class VegaLitePreviewStrategy:
        def _create_vega_lite_spec(self, data):
            return {"data": {"values": data}, "mark": "bar"}

    preview.VegaLitePreviewStrategy = VegaLitePreviewStrategy
    monkeypatch.setitem(sys.modules, app.__name__, app)
    monkeypatch.setitem(sys.modules, preview.__name__, preview)

    importlib.reload(mcp_branding).apply()
    mcp_branding.apply()  # ikinci çağrı yamayı tekrar sarmamalı

    text = app.get_default_instructions("THY")
    assert text.startswith("base loyalist") and text.count(PRIMARY["main"]) >= 2
    assert text.count("THY corporate color identity") == 1
    assert app.init_fastmcp_server() == "loyalist"
    assert app.mcp._mcp_server.name == "loyalist"
    assert registrations == [app.mcp]
    assert "simulate_program_roi" in text
    spec = VegaLitePreviewStrategy()._create_vega_lite_spec([])
    assert spec["config"]["range"]["category"] == COLORS
