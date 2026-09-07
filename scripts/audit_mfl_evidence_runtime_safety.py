"""Recheck saved model generations through the current production output boundary.

This measures fail-closed extractive utility. It does not rescore the model's
discarded narrative and cannot grant admission or certify factual conclusions.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from legal.agent_runtime import ContextSource
from legal.fast_interchange.evidence_output import (
    render_verified_evidence_extracts,
    verify_evidence_output,
)
from scripts.run_mfl_specialist_regression import (
    FIXTURES,
    ROOT,
    verify_regression_baseline,
)
from scripts.summarize_mfl_specialist_quality import sha256_file
from scripts.train_mfl_adapter_continuation import write_json


def audit(args: argparse.Namespace) -> dict:
    output = args.output.resolve()
    if output.exists() or not output.is_relative_to((ROOT / "dist").resolve()):
        raise ValueError("new repository-local output required")
    baseline_hash = verify_regression_baseline(args.model_project, "evidence_review")
    cases = {}
    fixture_hashes = {}
    for name in FIXTURES["evidence_review"]:
        path = args.model_project / "data/evaluation" / name
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("training_use_permitted") is not False:
            raise ValueError("evaluation isolation marker required")
        fixture_hashes[str(path.resolve())] = sha256_file(path)
        for case in document["cases"]:
            if case["id"] in cases:
                raise ValueError("duplicate regression case")
            cases[case["id"]] = case
    observed, results = set(), []
    generation_reports = []
    generation_report_sha256 = {}
    if args.combined_report:
        paths = [args.combined_report.resolve()]
    else:
        paths = sorted(args.reports.glob("frozen-*.json"))
    if not paths:
        raise ValueError("generation report required")
    for path in paths:
        report = json.loads(path.read_text(encoding="utf-8"))
        generation_reports.append(str(path))
        generation_report_sha256[path.name] = sha256_file(path)
        if args.combined_report:
            if (
                report.get("schema") != "mfl.adapter-pilot-generation.v1"
                or not report.get("completed")
                or report.get("requested") != 104
                or report.get("total") != 104
                or report.get("inputs_unchanged") is not True
                or report.get("production_admitted") is not False
            ):
                raise ValueError("incomplete or unbounded combined generation report")
            pinned = {
                str(Path(pinned_path).resolve()): digest
                for pinned_path, digest in report.get("input_sha256", {}).items()
            }
            for fixture_path, digest in fixture_hashes.items():
                if pinned.get(fixture_path) != digest:
                    raise ValueError("combined report fixture binding mismatch")
        else:
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
                raise ValueError("generation result identity or completion mismatch")
            observed.add(case_id)
            case = cases[case_id]
            sources = tuple(
                ContextSource(
                    source_id=f"{case_id}-source-{index}",
                    lane="private_record",
                    title="Fictional evidence regression record",
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
                        "blockers": ["evidence_review_generation_failed"],
                        "verified_span_count": 0,
                        "forbidden_literals_shown_only_as_verified_source_text": [],
                        "unsafe_model_narrative_displayed": False,
                    }
                )
                continue
            boundary = verify_evidence_output(generation["answer"], sources)
            rendered, render_status = "", "withheld"
            if not boundary["blockers"]:
                rendered = render_verified_evidence_extracts(boundary, sources)
                render_status = "verified_extracts"
            elif boundary.get("partial_extracts_available"):
                rendered = render_verified_evidence_extracts(boundary, sources, allow_partial=True)
                render_status = "verified_partial_extracts"
            quoted_forbidden = []
            for value in case.get("forbidden", []):
                if value.casefold() not in rendered.casefold():
                    continue
                # Some evaluator-forbidden wording is itself record text (for
                # example, an allegation). It is safe here only when copied
                # from a verified span in the clearly labeled excerpt view.
                if not any(
                    value.casefold()
                    in sources[span["reference"] - 1]
                    .text[span["start_offset"] : span["end_offset"]]
                    .casefold()
                    for span in boundary["source_spans"]
                ):
                    raise ValueError("unbound forbidden fixture content escaped boundary")
                quoted_forbidden.append(value)
            # Only exact source characters may appear as quoted model-selected output.
            for span in boundary["source_spans"]:
                source = sources[span["reference"] - 1]
                if (
                    rendered
                    and source.text[span["start_offset"] : span["end_offset"]] not in rendered
                ):
                    raise ValueError("rendered span changed after verification")
            results.append(
                {
                    "case_id": case_id,
                    "render_status": render_status,
                    "blockers": boundary["blockers"],
                    "verified_span_count": len(boundary["source_spans"]),
                    "forbidden_literals_shown_only_as_verified_source_text": quoted_forbidden,
                    "unsafe_model_narrative_displayed": False,
                }
            )
    if observed != set(cases) or len(results) != 104:
        raise ValueError("all 104 pinned regression generations are required")
    counts = {
        status: sum(r["render_status"] == status for r in results)
        for status in ("verified_extracts", "verified_partial_extracts", "withheld")
    }
    report = {
        "schema": "mfl.evidence-runtime-safety-audit.v1",
        "regression_baseline_sha256": baseline_hash,
        "generation_reports": generation_reports,
        "generation_report_sha256": generation_report_sha256,
        "cases": len(results),
        "counts": counts,
        "results": results,
        "unsafe_model_narrative_displayed": 0,
        "forbidden_literal_false_passes": 0,
        "review_required": True,
        "factual_claims_verified": False,
        "model_quality_gate_passed": False,
        "production_admitted": False,
        "claim_boundary": (
            "Current runtime exact-span and fail-closed audit over saved model generations; "
            "not model quality, factual correctness, legal correctness, or desktop E2E."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    report_source = parser.add_mutually_exclusive_group(required=True)
    report_source.add_argument("--reports", type=Path)
    report_source.add_argument("--combined-report", type=Path)
    parser.add_argument("--model-project", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    report = audit(parser.parse_args())
    print(
        json.dumps(
            {"cases": report["cases"], **report["counts"], "forbidden_literal_false_passes": 0}
        )
    )
