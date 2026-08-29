#!/usr/bin/env python3
"""Verify signed, hash-bound Store metadata without downloading or updating anything."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from legal.release.signed_update_metadata import verify_update_metadata


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify signed Store update metadata against an exact MSIX.")
    parser.add_argument("--package", required=True)
    parser.add_argument("--metadata", help="Signed metadata JSON; omission produces a blocked evidence record")
    parser.add_argument("--trust-config", default=str(ROOT / "configs" / "store_update_trust.json"))
    parser.add_argument("--release-scope", default=str(ROOT / "configs" / "v800_release_scope.json"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = verify_update_metadata(package=args.package, metadata_path=args.metadata, trust_config=args.trust_config, release_scope=args.release_scope)
    output = Path(args.output).resolve(); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
