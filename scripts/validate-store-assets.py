#!/usr/bin/env python3
"""Validate Store screenshots, captions, listing copy, and accepted scope."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from legal.release.store_asset_validator import validate_store_assets


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed Microsoft Store asset validation.")
    parser.add_argument("--submission-root", default=str(ROOT / "dist" / "release" / "v8.0.0" / "store-submission"))
    parser.add_argument("--listing-root", default=str(ROOT / "store" / "listing"))
    parser.add_argument("--release-scope", default=str(ROOT / "configs" / "v800_release_scope.json"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = validate_store_assets(submission_root=args.submission_root, listing_root=args.listing_root, release_scope_path=args.release_scope)
    target = Path(args.output).resolve(); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
