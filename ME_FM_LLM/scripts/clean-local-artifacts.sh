#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
python "$ROOT/scripts/clean-local-artifacts.py" --repo-root "$ROOT"
