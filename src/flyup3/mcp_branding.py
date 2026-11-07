"""Superset MCP çıktılarını THY kurumsal renklerine bağlar.

Kurulu paketi değiştirmeden, FLASK_APP_MUTATOR üzerinden iki yama uygular:
- MCP talimatlarına renk kuralı ve veri kataloğu eklenir; istemci (ör. Claude Desktop)
  kendi çizdiği grafiklerde de THY paletini kullanır, keşif çağrılarını atlar.
- Vega-Lite önizlemelerine THY renk aralıkları ve sabit etiket renkleri eklenir.
"""

import sqlite3
import sys

from flyup3.palette import COLORS, CUSTOMER_COLORS, LABEL_COLORS, PRIMARY, SECONDARY, STATUS
from flyup3.settings import OUT

RAMP = [PRIMARY[k] for k in ["lighter", "light", "main", "dark", "darker"]]
DIVERGING = [SECONDARY["main"], SECONDARY["base"], "#F2F3F5", PRIMARY["light"], PRIMARY["main"]]

COLOR_GUIDE = f"""

THY corporate color identity (mandatory for every visualization):
When you create a chart in Superset or draw any chart/visualization yourself from this
server's data (artifacts, HTML, SVG, Vega, matplotlib, etc.), use ONLY the Turkish
Airlines / Turkish Cargo palette below. Do not use default library palettes.
- Primary red: {PRIMARY["main"]} (dark {PRIMARY["dark"]}, darker {PRIMARY["darker"]},
  light {PRIMARY["light"]}, lighter {PRIMARY["lighter"]}); secondary navy {SECONDARY["main"]}.
- Categorical order: {", ".join(COLORS)}.
- Fixed customer colors: {", ".join(f"{k} {v}" for k, v in CUSTOMER_COLORS.items())}.
- Sequential (low→high): {", ".join(RAMP)}.
- Status: success {STATUS["success"]}, warning {STATUS["warning"]}, error {STATUS["error"]}.
- Text #222530 / #717784, grid #E1E4EA, background #FFFFFF.
In Superset, set color_scheme to "thy" (the default "supersetColors" is also THY here).
"""


def catalog_text(db_path=OUT / "superset.db"):
    """Metadata DB'den ID/tablo/sütun kataloğu üretir.

    İstemci bu sayede list_*/get_schema keşif turlarını atlayıp doğrudan
    generate_chart/execute_sql çağırır; asıl gecikme bu turlardaki model düşünme süresidir.
    """
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        dbs = con.execute("SELECT id, database_name FROM dbs ORDER BY id").fetchall()
        boards = con.execute(
            "SELECT id, dashboard_title, slug FROM dashboards ORDER BY id"
        ).fetchall()
        tables = con.execute("SELECT id, table_name FROM tables ORDER BY id").fetchall()
        columns = {}
        for table_id, name, label in con.execute(
            "SELECT table_id, column_name, verbose_name FROM table_columns ORDER BY id"
        ):
            columns.setdefault(table_id, []).append(f"{name} ({label})" if label else name)
        con.close()
    except sqlite3.Error:
        return ""
    lines = [
        "",
        "FlyUp3 data catalog (current at server start). Use these IDs and exact column",
        "names directly; do NOT call list_datasets/list_databases/list_dashboards/get_schema",
        "or exploratory SQL first. Prefer ONE execute_sql with the final aggregation, and",
        "send independent tool calls in parallel.",
        "- Databases: " + ", ".join(f'id {i} "{n}" (DuckDB SQL, schema main)' for i, n in dbs),
        "- Dashboards: "
        + ", ".join(
            f'id {i} "{t}"' + (f" /superset/dashboard/{s}/" if s else "") for i, t, s in boards
        ),
        "- Datasets (dataset_id · table: columns):",
    ]
    lines += [f"  {i} · {name}: {', '.join(columns.get(i, []))}" for i, name in tables]
    return "\n".join(lines) + "\n"


def _color_field(encoding):
    color = encoding.get("color") if isinstance(encoding, dict) else None
    return color.get("field") if isinstance(color, dict) else None


def brand_vega_lite(spec):
    """Vega-Lite spec'ine THY renklerini uygular (yerinde değiştirir ve döndürür)."""

    def walk(node):
        if isinstance(node, dict):
            scale = node.get("scale")
            if isinstance(scale, dict) and "scheme" in scale:
                scheme = scale.pop("scheme")
                scale["range"] = DIVERGING if "red" in str(scheme) else RAMP
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(spec)
    config = spec.setdefault("config", {})
    config.setdefault("range", {}).update(
        {"category": COLORS, "ordinal": RAMP, "ramp": RAMP, "heatmap": RAMP, "diverging": DIVERGING}
    )
    for mark in ["mark", "bar", "line", "area", "point", "circle", "arc", "rect"]:
        config.setdefault(mark, {}).setdefault("color", PRIMARY["main"])

    # Değerlerin hepsi bilinen etiketse (müşteri, kademe, mod…) sabit rengini ver.
    field = _color_field(spec.get("encoding"))
    values = spec.get("data", {}).get("values") or []
    if field and values:
        domain = list(dict.fromkeys(row.get(field) for row in values if isinstance(row, dict)))
        if domain and all(v in LABEL_COLORS for v in domain):
            spec["encoding"]["color"].setdefault("scale", {}).update(
                {"domain": domain, "range": [LABEL_COLORS[v] for v in domain]}
            )
    return spec


SIMULATION_GUIDE = """

loyalist simülasyon araçları (salt okunur):
- Kapasite, pasif onay, charter, hangi gönderi taşınır: simulate_capacity_w48.
- Kademe, avantaj, rebate, ziyaret ve sadakat bütçesi: simulate_loyalty_cost.
- Programın etki/marj/fırsat maliyeti, başabaş ve yıllık getirisi: simulate_program_roi.
- Kayıp riski, sinyal ve belirsizlik kötü senaryosu: simulate_churn_risk.
"Ya şöyle olsaydı?" sorularında SQL değil simulate_* araçlarını kullan.
Çıktıdaki inputs, assumptions ve summary alanlarını dikkate al; varsayımları veri gibi sunma.
"""


def apply(app=None):
    """MCP modülleri yüklüyse yamaları uygular; web sunucusunda zararsızdır."""
    app_module = sys.modules.get("superset.mcp_service.app")
    if app_module and not getattr(app_module, "_flyup3_branded", False):
        original = app_module.get_default_instructions
        app_module.get_default_instructions = lambda branding="loyalist": (
            original("loyalist") + COLOR_GUIDE + catalog_text() + SIMULATION_GUIDE
        )
        # __main__.py ve server.py bu fonksiyonu Flask oluşturulmadan önce
        # from-import ile yakalar. Aynı fonksiyon nesnesinin name varsayılanını
        # değiştirmek her iki alias'a da ulaşır; paket ve APP_NAME değişmez.
        init = app_module.init_fastmcp_server
        init.__defaults__ = ("loyalist", *init.__defaults__[1:])
        app_module.mcp._mcp_server.name = "loyalist"
        from flyup3.sim_tools import register

        register(app_module.mcp)
        app_module._flyup3_branded = True

    preview = sys.modules.get("superset.mcp_service.chart.tool.get_chart_preview")
    strategy = getattr(preview, "VegaLitePreviewStrategy", None)
    if strategy and not getattr(strategy, "_flyup3_branded", False):
        create = strategy._create_vega_lite_spec
        strategy._create_vega_lite_spec = lambda self, data: brand_vega_lite(create(self, data))
        strategy._flyup3_branded = True
