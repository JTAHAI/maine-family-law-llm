#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
DATA_ROOT="${MAINE_FAMILY_LAW_DATA_ROOT:-/tmp/ME_FM_LLM_data}"
cd "$ROOT"
export PYTHONPATH="$ROOT"
python scripts/clean-local-artifacts.py --repo-root "$ROOT"
python scripts/run-local-smoke.py --repo-root "$ROOT" --data-root "$DATA_ROOT" "${@:2}"
