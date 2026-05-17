#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.release import AttributionKitBuilder


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate public attribution/license kit for GitHub staging.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--output", default="public_attribution_kit_report.json")
    args = parser.parse_args()
    report = AttributionKitBuilder(project_root=args.project_root).build(write=True)
    Path(args.output).write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
