#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a Pass 30 claim-support verifier metric report.")
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--review-mode", choices=["attorney_reviewed", "operator_source_backed"], default="attorney_reviewed")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()
    blockers: list[str] = []
    findings: list[dict] = []
    if not args.metrics.exists():
        blockers.append("pass30_metrics_file_missing")
        report = {}
    else:
        try:
            report = json.loads(args.metrics.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            blockers.append("pass30_metrics_parse_error")
            findings.append({"code": "parse_error", "message": str(exc)})
            report = {}
        if report.get("status") != "pass":
            blockers.append("pass30_metrics_not_pass")
        if float(report.get("citation_support") or 0) < 0.95:
            blockers.append("citation_support_below_95_percent")
        if int(report.get("claim_total") or 0) <= 0:
            blockers.append("claim_support_sample_empty")
        if args.review_mode == "attorney_reviewed":
            if report.get("claim_attorney_reviewed_rows") != report.get("claim_total"):
                blockers.append("claim_support_rows_not_fully_attorney_reviewed")
        else:
            if report.get("claim_operator_source_backed_rows") != report.get("claim_total"):
                blockers.append("claim_support_rows_not_fully_operator_source_backed")
        if int(report.get("claim_seed_or_synthetic_rows") or 0):
            blockers.append("claim_support_seed_or_synthetic_rows_present")
        findings.extend(list(report.get("findings", []))[:50])
    payload = {
        "status": "pass" if not blockers else "blocked",
        "readiness": "pass30_true_ga_evidence_ready" if not blockers else "pass30_true_ga_evidence_blocked",
        "metrics_path": str(args.metrics),
        "review_mode": args.review_mode,
        "blockers": sorted(set(blockers)),
        "findings": findings,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.require_ready and payload["status"] != "pass":
        return 2
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
