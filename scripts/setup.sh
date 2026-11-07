#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
exec uv run flyup3-superset "$@"
