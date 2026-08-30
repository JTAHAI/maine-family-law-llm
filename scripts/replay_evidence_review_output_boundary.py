"""Replay recorded fictional model outputs through the current host boundary.

This does not perform inference or create independent/attorney evaluation.
Inputs are read-only, already observed regression cases, not hidden gold.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from legal.agent_runtime.contracts import ContextSource
from legal.fast_interchange.evidence_output import (
    render_verified_evidence_extracts,
    verify_evidence_output,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--recorded-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    if not output.is_relative_to((root / "dist").resolve()) or output.exists():
        parser.error("output_must_be_new_inside_repository_dist")
    fixture_raw, report_raw = args.fixtures.read_bytes(), args.recorded_report.read_bytes()
    fixtures, prior = json.loads(fixture_raw), json.loads(report_raw)
    if fixtures.get("data_kind") != "newly_authored_fictional_records":
        parser.error("fictional_fixtures_required")
    cases = {row["id"]: row for row in fixtures["cases"]}
    rows = []
    for result in prior["results"]:
        case = cases[result["case_id"]]
        sources = tuple(ContextSource(
            source_id=f"fictional-replay-{number}", lane="private_record",
            title=f"Fictional record {number}", locator=f"fictional record {number}", text=text,
        ) for number, text in enumerate(case["sources"], 1))
        boundary = verify_evidence_output(result["answer"], sources)
        rendered = "" if boundary["blockers"] else render_verified_evidence_extracts(boundary, sources)
        rows.append({"case_id": result["case_id"],
                     "prior_mechanical_pass": result["mechanical_pass"],
                     "boundary": boundary, "rendered_extracts": rendered,
                     "rendered_sha256": sha256(rendered.encode()).hexdigest()})
    evidence = {
        "schema_version": "evidence_review_recorded_output_replay_v1",
        "created_at": datetime.now(UTC).isoformat(),
        "basis": "observed_fictional_recorded_GPU_outputs_replayed_not_new_inference",
        "attorney_reviewed": False, "production_admitted": False,
        "model_quality_certified": False, "prior_mechanical_passes": prior["passed"],
        "fixture_sha256": sha256(fixture_raw).hexdigest(),
        "recorded_report_sha256": sha256(report_raw).hexdigest(),
        "sample_count": len(rows),
        "extracts_only": sum(not row["boundary"]["blockers"] for row in rows),
        "withheld": sum(bool(row["boundary"]["blockers"]) for row in rows),
        "results": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in evidence.items() if key != "results"}))


if __name__ == "__main__":
    main()
