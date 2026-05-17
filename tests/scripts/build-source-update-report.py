#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.production import SourceUpdateEngine


def main() -> int:
    parser = argparse.ArgumentParser(description="Build source freshness/diff report for official authority snapshots.")
    parser.add_argument("--data-root", type=Path, required=True, help="External data root.")
    parser.add_argument("--previous-manifest", type=Path, default=None)
    parser.add_argument("--max-age-days", type=int, default=120)
    args = parser.parse_args()
    report = SourceUpdateEngine(
        data_root=args.data_root,
        previous_manifest=args.previous_manifest,
        max_age_days=args.max_age_days,
    ).run(write_report=True)
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
