#!/usr/bin/env sh
set -eu
URL="${1:-http://127.0.0.1:8000/api/health}"
python - "$URL" <<'PY'
from __future__ import annotations
import json
import sys
import urllib.request
url = sys.argv[1]
with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310 - local smoke test URL
    payload = json.loads(response.read().decode("utf-8"))
if payload.get("status") != "ok":
    raise SystemExit(f"Unexpected health response: {payload!r}")
print(json.dumps(payload, indent=2, sort_keys=True))
PY
