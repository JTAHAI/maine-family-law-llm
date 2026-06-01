#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.evals.claim_support_metrics import ClaimSupportMetricRunner


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Pass 30 claim-support production metrics over external attorney-reviewed gold rows."
    )
    parser.add_argument("--eval-root", type=Path, required=True)
    parser.add_argument("--source-text-jsonl", type=Path)
    parser.add_argument("--parsed-authority-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--measurement-output", type=Path)
    parser.add_argument("--allow-non-attorney-reviewed", action="store_true", help="Only for local fixtures; do not use for GA.")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()
    report = ClaimSupportMetricRunner(
        require_attorney_review=not args.allow_non_attorney_reviewed
    ).run(
        eval_root=args.eval_root,
        source_text_jsonl=args.source_text_jsonl,
        parsed_authority_root=args.parsed_authority_root,
        output_path=args.output,
        measurement_output_path=args.measurement_output,
    )
    payload = report.as_dict()
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.require_ready and payload["status"] != "pass":
        return 2
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
