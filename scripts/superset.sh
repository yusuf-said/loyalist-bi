#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
# Superset DATA_DIR'ı custom config yüklenmeden önce seçer.
export SUPERSET_HOME="$PWD/out"
export SUPERSET_CONFIG_PATH="$PWD/superset_config.py"
export FASTMCP_HOME="$PWD/out/fastmcp"
export FLASK_APP=superset
mkdir -p "$SUPERSET_HOME"
exec uv run superset "$@"
