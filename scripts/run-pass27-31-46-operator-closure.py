#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the consolidated operator/source-backed closure lane for Passes 27-31 and 46. "
            "This is not attorney review, legal signoff, pilot signoff, or production shipment."
        )
    )
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--eval-root", type=Path)
    parser.add_argument("--parsed-authority-root", type=Path)
    parser.add_argument("--authority-index", type=Path)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()

    data_root = args.data_root.resolve()
    eval_root = (args.eval_root or data_root / "eval_store").resolve()
    parsed_root = (args.parsed_authority_root or data_root / "parsed_authority_store").resolve()
    authority_index = (args.authority_index or data_root / "authority_layer" / "citation_index.json").resolve()
    output = (args.output or data_root / "pass27_31_46_operator_source_backed_closure.json").resolve()

    steps = [
        (
            "build_operator_source_backed_gold_pack",
            [
                "scripts/build-operator-source-backed-gold-pack.py",
                "--eval-root", str(eval_root),
                "--parsed-authority-root", str(parsed_root),
                "--authority-index", str(authority_index),
                "--limit", str(args.limit),
                "--overwrite",
            ],
        ),
        (
            "run_pass29_verifier_metrics",
            [
                "scripts/run-pass29-verifier-metrics.py",
                "--review-mode", "operator_source_backed",
                "--eval-root", str(eval_root),
                "--authority-index", str(authority_index),
                "--parsed-authority-root", str(parsed_root),
                "--output", str(data_root / "pass29_verifier_metrics.json"),
                "--measurement-output", str(data_root / "release_metric_measurements.pass29.partial.json"),
                "--require-ready",
            ],
        ),
        (
            "audit_pass29_verifier_metrics",
            [
                "scripts/audit-pass29-verifier-production.py",
                "--review-mode", "operator_source_backed",
                "--metrics", str(data_root / "pass29_verifier_metrics.json"),
                "--output", str(data_root / "pass29_verifier_metrics_audit.json"),
                "--require-ready",
            ],
        ),
        (
            "run_pass30_claim_support_metrics",
            [
                "scripts/run-pass30-claim-support-metrics.py",
                "--review-mode", "operator_source_backed",
                "--eval-root", str(eval_root),
                "--parsed-authority-root", str(parsed_root),
                "--output", str(data_root / "pass30_claim_support_metrics.json"),
                "--measurement-output", str(data_root / "release_metric_measurements.pass30.partial.json"),
                "--require-ready",
            ],
        ),
        (
            "audit_pass30_claim_support_metrics",
            [
                "scripts/audit-pass30-claim-support-production.py",
                "--review-mode", "operator_source_backed",
                "--metrics", str(data_root / "pass30_claim_support_metrics.json"),
                "--output", str(data_root / "pass30_claim_support_metrics_audit.json"),
                "--require-ready",
            ],
        ),
        (
            "run_pass31_staleness_jurisdiction_metrics",
            [
                "scripts/run-pass31-staleness-jurisdiction-metrics.py",
                "--review-mode", "operator_source_backed",
                "--eval-root", str(eval_root),
                "--output", str(data_root / "pass31_staleness_jurisdiction_metrics.json"),
                "--measurement-output", str(data_root / "release_metric_measurements.pass31.partial.json"),
                "--require-ready",
            ],
        ),
        (
            "audit_pass31_staleness_jurisdiction_metrics",
            [
                "scripts/audit-pass31-staleness-jurisdiction-production.py",
                "--review-mode", "operator_source_backed",
                "--metrics", str(data_root / "pass31_staleness_jurisdiction_metrics.json"),
                "--output", str(data_root / "pass31_staleness_jurisdiction_metrics_audit.json"),
                "--require-ready",
            ],
        ),
        (
            "run_pass46_operator_release_eval",
            [
                "scripts/run-pass46-operator-source-backed-release-eval.py",
                "--data-root", str(data_root),
                "--eval-root", str(eval_root),
                "--output", str(data_root / "pass46_operator_source_backed_release_eval.json"),
                "--measurement-output", str(data_root / "release_metric_measurements.operator_source_backed.json"),
                "--require-ready",
            ],
        ),
    ]

    results: list[dict[str, Any]] = []
    blockers: list[str] = []
    for name, command in steps:
        completed = subprocess.run(
            [sys.executable, *command],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        payload = _parse_last_json(completed.stdout)
        result = {
            "name": name,
            "returncode": completed.returncode,
            "status": payload.get("status") if isinstance(payload, dict) else None,
            "readiness": payload.get("readiness") if isinstance(payload, dict) else None,
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
        }
        results.append(result)
        if completed.returncode != 0:
            blockers.append(f"{name}_failed")
            break

    status = "pass" if not blockers else "blocked"
    summary = {
        "schema_version": "pass27_31_46_operator_source_backed_closure_v1",
        "status": status,
        "readiness": "operator_source_backed_pass27_31_46_closed" if status == "pass" else "operator_source_backed_pass27_31_46_blocked",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passes_closed_when_ready": [27, 28, 29, 30, 31, 46],
        "review_mode": "operator_source_backed",
        "attorney_reviewed": False,
        "legal_signoff": False,
        "pilot_signoff": False,
        "true_ga_release_allowed": False,
        "operator_release_allowed": status == "pass",
        "data_root": str(data_root),
        "eval_root": str(eval_root),
        "parsed_authority_root": str(parsed_root),
        "authority_index": str(authority_index),
        "blockers": blockers,
        "steps": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.require_ready and status != "pass":
        return 2
    return 0 if status == "pass" else 1


def _parse_last_json(text: str) -> Any:
    # Tool scripts print one JSON object. Be tolerant of incidental logging.
    start = text.rfind("\n{")
    if start != -1:
        candidate = text[start + 1 :].strip()
    else:
        start = text.find("{")
        candidate = text[start:].strip() if start != -1 else ""
    if not candidate:
        return None
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
