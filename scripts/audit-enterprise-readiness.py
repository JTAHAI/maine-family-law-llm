#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.production import EnterpriseReadinessAuditor


def main() -> int:
    parser = argparse.ArgumentParser(description="Run combined enterprise readiness audit.")
    parser.add_argument("--data-root", type=Path, required=True, help="External data root.")
    parser.add_argument("--eval-root", type=Path, default=ROOT / "eval_data")
    args = parser.parse_args()
    report = EnterpriseReadinessAuditor(
        project_root=ROOT,
        data_root=args.data_root,
        eval_root=args.eval_root,
    ).run()
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.production_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
