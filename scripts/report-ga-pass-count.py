#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.production.ga_pass_tracker import GAPassTracker


def _internal_conversation_pilot_readiness() -> dict[str, object]:
    summary_path = ROOT / "docs" / "external-evidence" / "pass47a_47h_conversation_pilot_readiness_summary.json"
    if not summary_path.is_file():
        return {
            "status": "missing",
            "does_not_reduce_true_ga_count": True,
            "summary_path": str(summary_path),
        }
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    return {
        "status": payload.get("status", "unknown"),
        "completed_internal_passes": payload.get("completed_internal_passes", []),
        "remaining_true_ga_passes": payload.get("remaining_true_ga_passes", []),
        "does_not_reduce_true_ga_count": payload.get("does_not_reduce_true_ga_count", True),
        "summary_path": str(summary_path),
    }


def _internal_product_polish_readiness() -> dict[str, object]:
    summary_path = ROOT / "docs" / "external-evidence" / "pass47i_47t_product_polish_summary.json"
    if not summary_path.is_file():
        return {
            "status": "missing",
            "does_not_reduce_true_ga_count": True,
            "summary_path": str(summary_path),
        }
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    return {
        "status": payload.get("status", "unknown"),
        "completed_internal_passes": payload.get("completed_internal_passes", []),
        "remaining_true_ga_passes": payload.get("remaining_true_ga_passes", []),
        "does_not_reduce_true_ga_count": payload.get("does_not_reduce_true_ga_count", True),
        "emails_sent": payload.get("emails_sent", False),
        "attorney_reviewed": payload.get("attorney_reviewed", False),
        "production_legal_ready": payload.get("production_legal_ready", False),
        "summary_path": str(summary_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Report the formal true-GA Pass 19-51 count.")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path.")
    parser.add_argument("--summary", action="store_true", help="Print a compact text summary instead of JSON.")
    args = parser.parse_args()
    report = GAPassTracker(project_root=ROOT).report()
    payload = report.as_dict()
    payload["internal_conversation_pilot_readiness"] = _internal_conversation_pilot_readiness()
    payload["internal_product_polish_readiness"] = _internal_product_polish_readiness()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if args.summary:
        print(
            f"true_ga_remaining={payload['true_ga_remaining']} "
            f"true_ga_completed={payload['true_ga_completed']} "
            f"next_pass={payload['next_true_ga_pass']} "
            f"next_title={payload['next_true_ga_title']} "
            f"internal_conversation_pilot_readiness={payload['internal_conversation_pilot_readiness']['status']} "
            f"internal_product_polish_readiness={payload['internal_product_polish_readiness']['status']}"
        )
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if report.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
