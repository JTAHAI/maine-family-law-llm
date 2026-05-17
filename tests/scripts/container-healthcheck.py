#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(description="Container healthcheck for the Maine Family Law LLM API.")
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/health")
    parser.add_argument("--timeout", type=float, default=3.0)
    args = parser.parse_args()

    try:
        with urllib.request.urlopen(args.url, timeout=args.timeout) as response:  # noqa: S310 - local health URL only
            if response.status != 200:
                print(f"unhealthy: HTTP {response.status}", file=sys.stderr)
                return 1
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"unhealthy: {exc}", file=sys.stderr)
        return 1

    if payload.get("status") != "ok":
        print(f"unhealthy: unexpected payload {payload!r}", file=sys.stderr)
        return 1
    print("healthy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
