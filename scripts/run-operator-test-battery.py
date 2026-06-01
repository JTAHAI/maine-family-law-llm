#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.ops import OperatorTestBatteryAuditor


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the operator local-test acceptance battery.")
    parser.add_argument("--data-root", default=None, help="External data root. Defaults to policy Windows data root.")
    parser.add_argument("--output", default=str(ROOT / "docs" / "sample-evidence" / "operator_test_battery_evidence.json"))
    parser.add_argument("--no-create-dirs", action="store_true")
    parser.add_argument("--skip-write-probe", action="store_true")
    args = parser.parse_args()

    report = OperatorTestBatteryAuditor(ROOT, args.data_root).write(
        args.output,
        create_external_dirs=not args.no_create_dirs,
        write_probe=not args.skip_write_probe,
    )
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
