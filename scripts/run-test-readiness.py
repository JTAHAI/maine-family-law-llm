#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.ops import LocalTestReadinessAuditor


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local enterprise test-readiness certification.")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--output", default=str(ROOT / "docs" / "sample-evidence" / "local_test_readiness_report.json"))
    parser.add_argument("--skip-pytest", action="store_true")
    parser.add_argument("--include-quality-checks", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    args = parser.parse_args()
    report = LocalTestReadinessAuditor(args.repo_root, args.data_root).write(
        args.output,
        run_pytest=not args.skip_pytest,
        include_quality_checks=args.include_quality_checks,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
