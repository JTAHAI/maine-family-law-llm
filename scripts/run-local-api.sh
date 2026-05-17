#!/usr/bin/env bash
set -euo pipefail
ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
DATA_ROOT="${MAINE_FAMILY_LAW_DATA_ROOT:-/tmp/ME_FM_LLM_data}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
cd "$ROOT"
export PYTHONPATH="$ROOT"
export MAINE_FAMILY_LAW_DATA_ROOT="$DATA_ROOT"
echo "Starting API on http://$HOST:$PORT"
echo "Health: http://$HOST:$PORT/api/health"
echo "Version: http://$HOST:$PORT/api/version"
echo "Swagger: http://$HOST:$PORT/docs"
python -m uvicorn app.api.main:app --host "$HOST" --port "$PORT"
