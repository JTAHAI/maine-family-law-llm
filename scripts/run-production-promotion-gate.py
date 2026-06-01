#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.ops import ProductionPromotionGateAuditor


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the hard production-promotion gate for external legal evidence.")
    parser.add_argument("--data-root", default=None, help="External data root. Defaults to C:\\dev\\ME_FM_LLM_data policy path.")
    parser.add_argument("--output", default=str(ROOT / "docs" / "sample-evidence" / "production_promotion_gate_report.json"))
    parser.add_argument("--allow-fail-report", action="store_true", help="Write the report and exit 0 even when production promotion is locked.")
    args = parser.parse_args()

    report = ProductionPromotionGateAuditor(ROOT, args.data_root).write(args.output)
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.status == "pass" or args.allow_fail_report else 1


if __name__ == "__main__":
    raise SystemExit(main())
