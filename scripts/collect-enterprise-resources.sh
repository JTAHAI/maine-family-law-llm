#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
DATA_ROOT="${DATA_ROOT:-$(cd "$REPO_ROOT/.." && pwd)/ME_FM_LLM_data}"
PYTHON="${PYTHON:-python3}"
mkdir -p "$DATA_ROOT"
cd "$REPO_ROOT"
exec "$PYTHON" scripts/collect-enterprise-resources.py --data-root "$DATA_ROOT" "$@"
