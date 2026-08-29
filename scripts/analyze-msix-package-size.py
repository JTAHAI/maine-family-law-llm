#!/usr/bin/env python3
"""Write exact MSIX package-size/tier evidence without unpacking private data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from legal.release.package_size_budget import analyze_msix_package


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an MSIX package against the offline tier budget.")
    parser.add_argument("--package", required=True)
    parser.add_argument("--tier", required=True, choices=("essential", "full"))
    parser.add_argument("--tier-config", default=str(ROOT / "configs" / "store_feature_tiers.json"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = analyze_msix_package(package=args.package, tier_config=args.tier_config, requested_tier=args.tier)
    target = Path(args.output).resolve(); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
