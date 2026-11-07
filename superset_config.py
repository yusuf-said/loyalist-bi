"""Superset 6.1 config.py ve mcp_service/mcp_config.py ile doğrulandı."""

import os

from flyup3 import mcp_branding
from flyup3.branding import DASHBOARD_URL, FAVICON_URL, LOGO_URL, register_brand_assets
from flyup3.initialization import FlyUp3AppInitializer
from flyup3.palette import COLORS, PANEL_COLORS, PRIMARY, superset_theme
from flyup3.settings import OUT, load_env

load_env()
OUT.mkdir(exist_ok=True)
DATA_DIR = str(OUT)
SECRET_KEY = os.environ.get("SUPERSET_SECRET_KEY", "")
if not SECRET_KEY:
    raise RuntimeError("SUPERSET_SECRET_KEY ortam değişkenini ayarlayın (.env).")
SQLALCHEMY_DATABASE_URI = f"sqlite:///{OUT}/superset.db?check_same_thread=false"
APP_NAME = "THY · FlyUp3"
APP_ICON = LOGO_URL
LOGO_TARGET_PATH = DASHBOARD_URL
LOGO_TOOLTIP = "Turkish Airlines · FlyUp3"
LOGO_RIGHT_TEXT = ""
FAVICONS = [{"href": FAVICON_URL, "type": "image/svg+xml", "rel": "icon", "sizes": "any"}]


def _mutate_app(app):
    register_brand_assets(app)
    # MCP talimatları ve Vega-Lite önizlemeleri THY renklerini kullansın.
    mcp_branding.apply(app)


FLASK_APP_MUTATOR = _mutate_app
APP_INITIALIZER = FlyUp3AppInitializer
THEME_DEFAULT = superset_theme()
THEME_DARK = superset_theme(dark=True)
EXTRA_CATEGORICAL_COLOR_SCHEMES = [
    {
        "id": "thy",
        "label": "THY Turkish Cargo",
        "description": "Turkish Cargo",
        "isDefault": True,
        "colors": COLORS,
    },
    {
        "id": "flyup3_panel",
        "label": "FlyUp3 Panel",
        "description": "Mevcut panel paleti",
        "colors": list(PANEL_COLORS.values()),
    },
    # 6.1 arayüzü yerleşik "supersetColors" şemasını varsayılan tutuyor ve isDefault'u
    # yok sayıyor; aynı id ile THY renklerini kaydedip yeni grafiklerin (MCP dahil)
    # varsayılan rengini THY yapıyoruz.
    {
        "id": "supersetColors",
        "label": "THY Turkish Cargo (varsayılan)",
        "description": "Turkish Cargo",
        "colors": COLORS,
    },
]
EXTRA_SEQUENTIAL_COLOR_SCHEMES = [
    {
        "id": "thy_red",
        "label": "THY Kırmızı",
        "isDefault": True,
        "isDiverging": False,
        "colors": [PRIMARY[k] for k in ["lighter", "light", "main", "dark", "darker"]],
    },
]
# Yerel DuckDB dosyasını Superset bağlantısı olarak kaydetmeye izin verir.
PREVENT_UNSAFE_DB_CONNECTIONS = False
MCP_SERVICE_HOST = "127.0.0.1"
MCP_SERVICE_PORT = 5008
MCP_DEV_USERNAME = os.environ.get("MCP_DEV_USERNAME") or os.environ.get("SUPERSET_ADMIN_USERNAME")
MCP_AUTH_ENABLED = False
MCP_RBAC_ENABLED = True
SUPERSET_WEBSERVER_ADDRESS = os.getenv("SUPERSET_WEBSERVER_ADDRESS", "http://127.0.0.1:8088")
WEBDRIVER_BASEURL = SUPERSET_WEBSERVER_ADDRESS + "/"
# MCP'nin döndürdüğü grafik/dashboard linkleri bunu kullanır (varsayılan 0.0.0.0:8080).
WEBDRIVER_BASEURL_USER_FRIENDLY = SUPERSET_WEBSERVER_ADDRESS + "/"
