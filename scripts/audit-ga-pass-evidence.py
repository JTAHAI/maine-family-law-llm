#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.production.ga_pass_evidence import GAPassEvidenceAuditor


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit real evidence before reducing the true-GA pass count.")
    parser.add_argument("--data-root", type=Path, default=None, help="External authority/data root.")
    parser.add_argument("--eval-root", type=Path, default=None, help="External attorney-reviewed eval root.")
    parser.add_argument("--security-root", type=Path, default=None, help="External security/governance evidence root.")
    parser.add_argument("--pilot-root", type=Path, default=None, help="External pilot/signoff evidence root.")
    parser.add_argument("--tracker", type=Path, default=None, help="Optional alternate GA tracker JSON.")
    parser.add_argument("--requirements", type=Path, default=None, help="Optional alternate evidence requirements JSON.")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path.")
    args = parser.parse_args()
    report = GAPassEvidenceAuditor(
        project_root=ROOT,
        data_root=args.data_root,
        eval_root=args.eval_root,
        security_root=args.security_root,
        pilot_root=args.pilot_root,
        tracker_path=args.tracker,
        requirements_path=args.requirements,
    ).run()
    payload = report.as_dict()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if report.pass_evidence_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
