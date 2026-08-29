#!/usr/bin/env python3
"""Parse a WACK output directory and write hash-bound, fail-closed evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from legal.release.wack_qualification import parse_wack_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse WACK output for an exact MSIX package.")
    parser.add_argument("--package", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--execution-status", required=True, choices=("completed", "pass", "failed", "not_run"))
    parser.add_argument("--reason", default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = parse_wack_report(package=args.package, output_root=args.output_root, execution_status=args.execution_status, reason=args.reason)
    target = Path(args.output).resolve(); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
