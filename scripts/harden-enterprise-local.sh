#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
DATA_ROOT="${DATA_ROOT:-$(cd "$REPO_ROOT/.." && pwd)/ME_FM_LLM_data}"
PYTHON="${PYTHON:-python3}"
mkdir -p "$DATA_ROOT"
cd "$REPO_ROOT"
"$PYTHON" -m pip install -e .
"$PYTHON" scripts/run-quality-checks.py
"$PYTHON" scripts/build-enterprise-local-plan.py --repo-root "$REPO_ROOT" --data-root "$DATA_ROOT"
"$PYTHON" scripts/run-enterprise-local-hardening.py --data-root "$DATA_ROOT" "$@"
