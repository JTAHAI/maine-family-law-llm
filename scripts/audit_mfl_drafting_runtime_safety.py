"""Audit saved Drafting generations through the production source-span boundary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from legal.agent_runtime import ContextSource
from legal.fast_interchange.drafting_output import (
    render_source_bound_draft,
    verify_drafting_output,
)
from scripts.run_mfl_specialist_regression import FIXTURES, ROOT, verify_regression_baseline
from scripts.summarize_mfl_specialist_quality import sha256_file
from scripts.train_mfl_adapter_continuation import write_json


def audit(args: argparse.Namespace) -> dict:
    output = args.output.resolve()
    if output.exists() or not output.is_relative_to((ROOT / "dist").resolve()):
        raise ValueError("new repository-local output required")
    baseline_hash = verify_regression_baseline(args.model_project, "drafting")
    cases: dict[str, dict] = {}
    fixture_hashes: dict[str, str] = {}
    for name in FIXTURES["drafting"]:
        path = args.model_project / "data/evaluation" / name
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("training_use_permitted") is not False:
            raise ValueError("evaluation isolation marker required")
        fixture_hashes[str(path.resolve())] = sha256_file(path)
        for case in document["cases"]:
            if case["id"] in cases:
                raise ValueError("duplicate regression case")
            cases[case["id"]] = case

    observed: set[str] = set()
    results: list[dict] = []
    report_hashes: dict[str, str] = {}
    for path in sorted(args.reports.glob("frozen-*.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        report_hashes[path.name] = sha256_file(path)
        if (
            report.get("fatal_error")
            or not report.get("completed_all_requested_cases")
            or report.get("adapter_enabled") is not True
        ):
            raise ValueError("incomplete or ablated generation report")
        for fixture_path, digest in report["fixture_sha256"].items():
            if fixture_hashes.get(str(Path(fixture_path).resolve())) != digest:
                raise ValueError("generation report fixture binding mismatch")
        for generation in report["results"]:
            case_id = generation["case_id"]
            if case_id in observed or case_id not in cases:
                raise ValueError("generation result identity mismatch")
            observed.add(case_id)
            case = cases[case_id]
            sources = tuple(
                ContextSource(
                    source_id=f"{case_id}-source-{index}",
                    lane="private_record",
                    title="Fictional drafting regression record",
                    locator=f"fictional page {index}",
                    text=text,
                )
                for index, text in enumerate(case["sources"], 1)
            )
            if generation.get("error"):
                results.append(
                    {
                        "case_id": case_id,
                        "render_status": "withheld",
                        "blockers": ["drafting_generation_failed"],
                        "verified_span_count": 0,
                        "unsafe_model_narrative_displayed": False,
                    }
                )
                continue
            boundary = verify_drafting_output(generation["answer"], sources)
            rendered, render_status = "", "withheld"
            if not boundary["blockers"]:
                rendered = render_source_bound_draft(boundary, sources)
                render_status = "verified_extracts"
            elif boundary.get("partial_extracts_available"):
                rendered = render_source_bound_draft(boundary, sources, allow_partial=True)
                render_status = "verified_partial_extracts"
            for span in boundary["source_spans"]:
                source = sources[span["reference"] - 1]
                exact = source.text[span["start_offset"] : span["end_offset"]]
                if rendered and exact not in rendered:
                    raise ValueError("rendered span changed after verification")
            results.append(
                {
                    "case_id": case_id,
                    "render_status": render_status,
                    "blockers": boundary["blockers"],
                    "verified_span_count": len(boundary["source_spans"]),
                    "unsafe_model_narrative_displayed": False,
                }
            )
    if observed != set(cases) or len(results) != 22:
        raise ValueError("all 22 pinned drafting regression generations are required")
    counts = {
        status: sum(row["render_status"] == status for row in results)
        for status in ("verified_extracts", "verified_partial_extracts", "withheld")
    }
    report = {
        "schema": "mfl.drafting-runtime-safety-audit.v1",
        "regression_baseline_sha256": baseline_hash,
        "generation_reports": str(args.reports.resolve()),
        "generation_report_sha256": report_hashes,
        "cases": len(results),
        "counts": counts,
        "results": results,
        "unsafe_model_narrative_displayed": 0,
        "filing_ready": False,
        "review_required": True,
        "factual_claims_verified": False,
        "legal_claims_verified": False,
        "model_quality_gate_passed": False,
        "production_admitted": False,
        "claim_boundary": (
            "Current exact-span fail-closed audit over saved fictional model generations; "
            "not model quality, factual/legal correctness, filing readiness, or desktop E2E."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reports", type=Path, required=True)
    parser.add_argument("--model-project", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    result = audit(parser.parse_args())
    print(json.dumps({"cases": result["cases"], **result["counts"]}))
