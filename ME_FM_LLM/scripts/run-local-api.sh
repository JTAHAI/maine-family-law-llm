#!/usr/bin/env bash
set -euo pipefail
ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
DATA_ROOT="${MAINE_FAMILY_LAW_DATA_ROOT:-/tmp/ME_FM_LLM_data}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
API_MODE="${API_MODE:-LocalWorkbench}"
cd "$ROOT"
export PYTHONPATH="$ROOT/src:$ROOT"
export MAINE_FAMILY_LAW_DATA_ROOT="$DATA_ROOT"
if [[ "$API_MODE" == "Enterprise" ]]; then
  APP_TARGET="app.api.main:app"
else
  APP_TARGET="maine_family_law_llm.api:app"
fi
echo "Starting $API_MODE API on http://$HOST:$PORT"
echo "Chat UI: http://$HOST:$PORT/"
echo "Health: http://$HOST:$PORT/api/health"
echo "Version: http://$HOST:$PORT/api/version"
echo "Swagger: http://$HOST:$PORT/docs"
python -m uvicorn "$APP_TARGET" --host "$HOST" --port "$PORT"
