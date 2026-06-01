#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.security import LegalRedTeamRunner


def build_report(*, output: Path | None = None) -> dict:
    red_team_report_path = ROOT / "docs" / "sample-evidence" / "pass47_legal_red_team_report.json"
    report = LegalRedTeamRunner(project_root=ROOT).run(output_path=red_team_report_path).as_dict()
    required = set(report.get("required_categories") or [])
    categories = {row.get("category") for row in report.get("results") or []}
    blockers = []
    if report.get("status") != "pass":
        blockers.append("legal_red_team_report_not_pass")
    missing = sorted(required - categories)
    blockers.extend(f"missing_red_team_category:{item}" for item in missing)
    unsafe = [row.get("case_id") for row in report.get("results") or [] if not row.get("safe")]
    blockers.extend(f"unsafe_red_team_case:{case_id}" for case_id in unsafe)
    if not report.get("no_filing_ready_bypass"):
        blockers.append("filing_ready_bypass_detected")
    payload = {
        "schema_version": "pass47_legal_red_team_engineering_closure_v1",
        "stage": "pass47_legal_red_team_engineering_closure",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if not blockers else "blocked",
        "readiness": "pass47_engineering_red_team_closed" if not blockers else "pass47_engineering_red_team_blocked",
        "completed_passes": [47] if not blockers else [],
        "attorney_reviewed": False,
        "operator_source_backed": False,
        "legal_signoff": False,
        "pilot_signoff": False,
        "basis": "deterministic repo red-team harness; not attorney review, not pilot signoff, not final GA ship evidence",
        "required_categories": sorted(required),
        "observed_categories": sorted(categories),
        "case_count": len(report.get("results") or []),
        "safe_case_count": sum(1 for row in report.get("results") or [] if row.get("safe")),
        "no_filing_ready_bypass": bool(report.get("no_filing_ready_bypass")),
        "blockers": sorted(set(blockers)),
        "red_team_report_path": str(red_team_report_path.relative_to(ROOT)),
        "red_team_report": report,
    }
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Pass 47 legal red-team engineering closure evidence.")
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "external-evidence" / "pass47_legal_red_team_engineering_closure_summary.json")
    parser.add_argument("--require-ready", action="store_true", help="Exit non-zero if Pass 47 red-team evidence is blocked.")
    args = parser.parse_args()
    payload = build_report(output=args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.require_ready and payload["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
