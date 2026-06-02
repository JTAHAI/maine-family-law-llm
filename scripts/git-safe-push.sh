#!/usr/bin/env bash
set -euo pipefail
MESSAGE="${1:-Run public-source pre-push gate}"
BRANCH="${2:-main}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python scripts/git-safe-push.py \
  --repo-root . \
  --message "$MESSAGE" \
  --branch "$BRANCH" \
  --output docs/external-evidence/git_safe_push_v192.json
