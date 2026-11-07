#!/bin/sh
# Superset MCP'yi stdio modunda başlatır (Claude Desktop gibi istemciler kendisi çalıştırır).
# stdout yalnızca MCP protokolüne ayrılmıştır; uv ve Superset çıktıları stderr'e gider.
set -eu
cd "$(dirname "$0")/.."
# Claude Desktop PATH'i kısıtlı başlatır; uv'yi bilinen konumlarda ara.
PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
export SUPERSET_HOME="$PWD/out"
export SUPERSET_CONFIG_PATH="$PWD/superset_config.py"
export FASTMCP_HOME="$PWD/out/fastmcp"
export FASTMCP_TRANSPORT=stdio
export FLASK_APP=superset
mkdir -p "$SUPERSET_HOME"
exec uv run --quiet python -m superset.mcp_service
