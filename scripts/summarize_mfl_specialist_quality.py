"""Aggregate independent specialist evaluations without creating legal admission.

Every supplied report must complete and every mechanical check must pass.  This
is a deliberately strict research gate: one fabricated literal, unbound quote,
missing source reference, failed review marker, or meaning failure blocks the
candidate.  Passing this gate never substitutes for attorney evaluation or a
production-signed admission catalog.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.security.strict_json import strict_json_load_path

BASELINE_PATH = (
    Path(__file__).resolve().parents[1] / "configs/mfl_specialist_regression_baseline.json"
)


def approved_baseline(capability: str) -> tuple[dict[str, Any], str, str]:
    """Use the retained, consulted regression inventory; it is not blind gold."""
    if capability not in {"evidence_review", "drafting"}:
        raise ValueError("specialist_quality_capability_invalid")
    baseline = strict_json_load_path(BASELINE_PATH, max_bytes=256 * 1024, require_object=True)
    if baseline.get("schema_version") != "mfl_specialist_regression_baseline_v1":
        raise ValueError("specialist_quality_baseline_invalid")
    prefix = "mfl_evidence_" if capability == "evidence_review" else "mfl_drafting_"
    fixtures = baseline.get("fixtures")
    if not isinstance(fixtures, dict):
        raise ValueError("specialist_quality_baseline_invalid")
    selected = {
        name: spec
        for name, spec in fixtures.items()
        if isinstance(spec, dict)
        and spec.get("capability", capability if name.startswith(prefix) else "") == capability
    }
    for spec in selected.values():
        ids = spec.get("case_ids")
        if (
            not isinstance(ids, list)
            or not ids
            or any(not isinstance(item, str) or not item for item in ids)
            or len(ids) != len(set(ids))
            or not isinstance(spec.get("sha256"), str)
            or not re.fullmatch(r"[a-f0-9]{64}", spec["sha256"])
        ):
            raise ValueError("specialist_quality_baseline_invalid")
    evaluators = baseline.get("evaluators")
    evaluator = (
        "evaluate_mfl_evidence_research_v2.py"
        if capability == "evidence_review"
        else "evaluate_mfl_practical_research_v2.py"
    )
    expected_evaluator = evaluators.get(evaluator) if isinstance(evaluators, dict) else None
    if (
        not selected
        or not isinstance(expected_evaluator, str)
        or not re.fullmatch(r"[a-f0-9]{64}", expected_evaluator)
    ):
        raise ValueError("specialist_quality_baseline_invalid")
    return selected, expected_evaluator, sha256_file(BASELINE_PATH)


def report_fixture_binding(report: dict[str, Any], fixtures: dict[str, Any]) -> tuple[str, bool]:
    bindings = report.get("fixture_sha256")
    if not isinstance(bindings, dict) or len(bindings) != 1:
        return "", False
    raw_name, digest = next(iter(bindings.items()))
    name = raw_name.replace("\\", "/").rsplit("/", 1)[-1]
    expected = fixtures.get(name)
    if not expected or digest != expected["sha256"]:
        return name, False
    results = report.get("results", [])
    actual_ids = [row.get("case_id") if isinstance(row, dict) else None for row in results]
    return name, actual_ids == expected["case_ids"]


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


REQUIRED_CHECKS = frozenset(
    {
        "source_references",
        "quotes_bound_to_correct_sources",
        "required_quoted_details",
        "no_forbidden_literal",
        "meaning_keywords",
        "review_marker",
    }
)


def summarize(
    capability: str,
    reports: Iterable[Path],
    *,
    minimum_cases: int,
    expected_pack_manifest_sha256: str = "",
    expected_release_fingerprint: str = "",
) -> dict[str, Any]:
    paths = [path.resolve(strict=True) for path in reports]
    if not paths or minimum_cases < 1:
        raise ValueError("specialist_quality_reports_required")
    fixtures, expected_evaluator, baseline_hash = approved_baseline(capability)
    totals: Counter[str] = Counter()
    failures: list[dict[str, Any]] = []
    if not all(
        re.fullmatch(r"[a-f0-9]{64}", value)
        for value in (expected_pack_manifest_sha256, expected_release_fingerprint)
    ):
        failures.append({"code": "expected_candidate_binding_missing"})
    sources: list[dict[str, Any]] = []
    fixture_hashes: set[str] = set()
    used_fixtures: list[str] = []
    for path in paths:
        report = strict_json_load_path(path, max_bytes=32 * 1024**2, require_object=True)
        results = report.get("results")
        if not isinstance(results, list):
            raise ValueError("specialist_quality_results_invalid")
        fixture_name, fixture_matches = report_fixture_binding(report, fixtures)
        used_fixtures.append(fixture_name)
        if not fixture_matches:
            failures.append(
                {"report": str(path), "code": "approved_fixture_or_case_inventory_mismatch"}
            )
        if report.get("evaluator_sha256") != expected_evaluator:
            failures.append({"report": str(path), "code": "approved_evaluator_mismatch"})
        schema = report.get("schema")
        expected_schema = (
            "mfl.evidence-research-generation-evaluation.v2"
            if capability == "evidence_review"
            else "mfl.practical-research-generation-evaluation.v2"
        )
        if (
            schema != expected_schema
            or report.get("capability", "evidence_review") != capability
            or report.get("pack_manifest_sha256") != expected_pack_manifest_sha256
            or report.get("release_fingerprint") != expected_release_fingerprint
        ):
            failures.append({"report": str(path), "code": "evaluation_candidate_binding_mismatch"})
        if (
            report.get("engine") != "family-worker"
            or report.get("adapter_enabled") is not True
            or report.get("fixtures_unchanged_during_run") is not True
            or report.get("implementation_unchanged_during_run") is not True
            or report.get("cleanup_failures") != []
        ):
            failures.append({"report": str(path), "code": "evaluation_runtime_integrity_invalid"})
        sources.append(
            {
                "path": str(path),
                "sha256": sha256_file(path),
                "cases": len(results),
                "passed": int(report.get("passed") or 0),
                "completed": report.get("completed_all_requested_cases") is True,
                "fatal_error": report.get("fatal_error"),
                "fixture_sha256": report.get("fixture_sha256") or {},
            }
        )
        raw_fixture_bindings = report.get("fixture_sha256")
        fixture_values = (
            list(raw_fixture_bindings.values()) if isinstance(raw_fixture_bindings, dict) else []
        )
        if len(fixture_values) != 1 or not all(
            isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value)
            for value in fixture_values
        ):
            failures.append({"report": str(path), "code": "frozen_fixture_binding_invalid"})
        fixture_hashes.update(str(value) for value in fixture_values)
        if report.get("completed_all_requested_cases") is not True or report.get("fatal_error"):
            failures.append({"report": str(path), "code": "evaluation_incomplete_or_fatal"})
        if (
            report.get("production_admitted") is not False
            or report.get("attorney_reviewed") is not False
        ):
            failures.append({"report": str(path), "code": "research_scope_claim_invalid"})
        report_passes = 0
        case_ids: set[str] = set()
        for row in results:
            totals["attempted"] += 1
            checks = row.get("checks") if isinstance(row, dict) else None
            if not isinstance(checks, dict) or not REQUIRED_CHECKS <= set(checks):
                failures.append(
                    {
                        "report": str(path),
                        "case_id": row.get("case_id") if isinstance(row, dict) else None,
                        "code": "mechanical_checks_missing",
                    }
                )
                continue
            case_id = row.get("case_id")
            if not isinstance(case_id, str) or not case_id or case_id in case_ids:
                failures.append({"report": str(path), "code": "case_identity_missing_or_duplicate"})
            else:
                case_ids.add(case_id)
            for name, passed in checks.items():
                totals[f"check:{name}:attempted"] += 1
                if passed is True:
                    totals[f"check:{name}:passed"] += 1
            mechanical = row.get("mechanical_pass") is True and all(
                value is True for value in checks.values()
            )
            if mechanical:
                totals["passed"] += 1
                report_passes += 1
            else:
                failures.append(
                    {
                        "report": str(path),
                        "case_id": str(row.get("case_id") or "unknown"),
                        "code": str(row.get("error") or "mechanical_quality_failed"),
                        "failed_checks": sorted(
                            name for name, passed in checks.items() if passed is not True
                        ),
                    }
                )
        if report.get("total") != len(results) or report.get("passed") != report_passes:
            failures.append({"report": str(path), "code": "evaluation_count_mismatch"})
    if totals["attempted"] < minimum_cases:
        failures.append(
            {
                "code": "minimum_independent_case_count_not_met",
                "actual": totals["attempted"],
                "required": minimum_cases,
            }
        )
    if len(fixture_hashes) != len(paths):
        failures.append({"code": "evaluation_fixture_identity_not_unique_or_missing"})
    if len(used_fixtures) != len(set(used_fixtures)) or set(used_fixtures) != set(fixtures):
        failures.append({"code": "approved_regression_inventory_incomplete_or_duplicated"})
    if sha256_file(BASELINE_PATH) != baseline_hash:
        failures.append({"code": "approved_regression_baseline_changed"})
    technical_pass = not failures and totals["passed"] == totals["attempted"]
    return {
        "schema_version": "mfl_specialist_research_quality_v1",
        "observed_at": datetime.now(UTC).isoformat(),
        "capability": capability,
        "pack_manifest_sha256": expected_pack_manifest_sha256,
        "release_fingerprint": expected_release_fingerprint,
        "regression_baseline_sha256": baseline_hash,
        "evaluation_basis": (
            "previously_consulted_fictional_regression_not_blind_or_attorney_reviewed"
        ),
        "quality_gate_passed": technical_pass,
        "quality_scope": "local_synthetic_mechanical_source_handling_only",
        "legal_use_approved": False,
        "attorney_reviewed": False,
        "production_admitted": False,
        "runnable_research_only": technical_pass,
        "reports": sources,
        "report_count": len(sources),
        "unique_fixture_count": len(fixture_hashes),
        "adapter_case_attempts": totals["attempted"],
        "aggregate_semantic_passes": totals["passed"],
        "check_totals": {key: totals[key] for key in sorted(totals) if key.startswith("check:")},
        "failures": failures,
        "release_blockers": [
            "independent_attorney_evaluation_missing",
            "production_signed_admission_missing",
            "legal_use_approval_missing",
        ],
        "decision": "LOCAL_RESEARCH_QUALITY_PASS" if technical_pass else "BLOCKED",
    }


def require_quality_evidence(
    quality: dict[str, Any],
    *,
    capability: str,
    pack_manifest_sha256: str,
    release_fingerprint: str,
    minimum_cases: int,
) -> None:
    """Revalidate retained reports, not a caller-supplied success boolean."""
    if (
        quality.get("quality_gate_passed") is not True
        or quality.get("decision") != "LOCAL_RESEARCH_QUALITY_PASS"
        or quality.get("capability") != capability
        or quality.get("pack_manifest_sha256") != pack_manifest_sha256
        or quality.get("release_fingerprint") != release_fingerprint
        or quality.get("attorney_reviewed") is not False
        or quality.get("production_admitted") is not False
        or quality.get("failures") != []
    ):
        raise ValueError("specialist_quality_candidate_mismatch_or_blocked")
    references = quality.get("reports")
    if not isinstance(references, list) or not references:
        raise ValueError("specialist_quality_reports_missing")
    paths = []
    for item in references:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError("specialist_quality_report_reference_invalid")
        path = Path(item["path"])
        if path.is_symlink() or sha256_file(path) != item.get("sha256"):
            raise ValueError("specialist_quality_report_changed")
        paths.append(path)
    actual = summarize(
        capability,
        paths,
        minimum_cases=minimum_cases,
        expected_pack_manifest_sha256=pack_manifest_sha256,
        expected_release_fingerprint=release_fingerprint,
    )
    if not actual["quality_gate_passed"] or any(
        actual[key] != quality.get(key)
        for key in (
            "adapter_case_attempts",
            "aggregate_semantic_passes",
            "check_totals",
            "regression_baseline_sha256",
        )
    ):
        raise ValueError("specialist_quality_evidence_revalidation_failed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capability", choices=("evidence_review", "drafting"), required=True)
    parser.add_argument("--report", action="append", type=Path, required=True)
    parser.add_argument("--minimum-cases", type=int, required=True)
    parser.add_argument("--pack-manifest-sha256", required=True)
    parser.add_argument("--release-fingerprint", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(
        args.capability,
        args.report,
        minimum_cases=args.minimum_cases,
        expected_pack_manifest_sha256=args.pack_manifest_sha256,
        expected_release_fingerprint=args.release_fingerprint,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "decision": result["decision"],
                "cases": result["adapter_case_attempts"],
                "output": str(args.output.resolve()),
            },
            sort_keys=True,
        )
    )
    return 0 if result["quality_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
