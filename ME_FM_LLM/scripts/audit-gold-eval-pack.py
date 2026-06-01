#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.evals import GoldEvalPackAuditor


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit attorney-reviewed gold evaluation pack readiness.")
    parser.add_argument("--eval-root", type=Path, default=ROOT / "eval_data")
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Exit non-zero unless attorney-reviewed gold minimums are met.",
    )
    args = parser.parse_args()
    report = GoldEvalPackAuditor(project_root=ROOT, eval_root=args.eval_root).run()
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    if args.require_ready and not report.production_ready:
        return 2
    return 0 if report.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
