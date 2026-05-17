#!/usr/bin/env bash
set -euo pipefail
ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
DATA_ROOT="${MAINE_FAMILY_LAW_DATA_ROOT:-/tmp/ME_FM_LLM_data}"
cd "$ROOT"
export MAINE_FAMILY_LAW_DATA_ROOT="$DATA_ROOT"
export PYTHONPATH="$ROOT"
if [[ "${INSTALL:-0}" == "1" ]]; then
  python -m pip install --upgrade pip
  python -m pip install -e ".[dev,api]"
fi
python scripts/clean-local-artifacts.py --repo-root "$ROOT"
python -m pytest "${PYTEST_ARGS:--q}"
