"""Proje yolları ve sırları loglamayan bağlantı ayarları."""

import os
import re
from pathlib import Path

from dotenv import load_dotenv
from snowflake.sqlalchemy import URL

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"


def load_env():
    load_dotenv(ROOT / ".env", override=False)


def identifier(value):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError("Snowflake database/schema yalnız harf, rakam ve alt çizgi içermeli.")
    return value.upper()


def snowflake_url():
    load_env()
    required = ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_ROLE", "SNOWFLAKE_WAREHOUSE"]
    missing = [key for key in required if not os.getenv(key)]
    if not (os.getenv("SNOWFLAKE_PASSWORD") or os.getenv("SNOWFLAKE_AUTHENTICATOR")):
        missing.append("SNOWFLAKE_PASSWORD veya SNOWFLAKE_AUTHENTICATOR")
    if missing:
        raise ValueError(
            "Snowflake bilgileri eksik: " + ", ".join(missing) + ". .env dosyasını doldurun."
        )
    options = {
        key: os.environ["SNOWFLAKE_" + key.upper()]
        for key in ["account", "user", "role", "warehouse"]
    }
    for key in ["password", "authenticator"]:
        if os.getenv("SNOWFLAKE_" + key.upper()):
            options[key] = os.environ["SNOWFLAKE_" + key.upper()]
    options.update(
        database=identifier(os.getenv("SNOWFLAKE_DATABASE", "FLYUP3")),
        schema=identifier(os.getenv("SNOWFLAKE_SCHEMA", "BI")),
    )
    return URL(**options)


def prepare_superset_env():
    load_env()
    OUT.mkdir(exist_ok=True)
    # Superset config.py chooses DATA_DIR before loading the custom configuration.
    os.environ["SUPERSET_HOME"] = str(OUT)
    os.environ["SUPERSET_CONFIG_PATH"] = str(ROOT / "superset_config.py")
    os.environ["FLASK_APP"] = "superset"
    # FastMCP uses platformdirs unless explicitly redirected.
    os.environ["FASTMCP_HOME"] = str(OUT / "fastmcp")
