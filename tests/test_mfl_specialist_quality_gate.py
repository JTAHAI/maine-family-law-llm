import json

import pytest

from scripts import summarize_mfl_specialist_quality as quality_module
from scripts.summarize_mfl_specialist_quality import require_quality_evidence, summarize

PACK_HASH = "1" * 64
RELEASE_HASH = "2" * 64
EVALUATOR_HASH = "e" * 64


@pytest.fixture(autouse=True)
def synthetic_baseline(tmp_path, monkeypatch):
    # Unit fixtures are deliberately NOT the real 104/22-case regression evidence.
    original = quality_module.BASELINE_PATH
    path = tmp_path / "synthetic-baseline.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "mfl_specialist_regression_baseline_v1",
                "fixtures": {},
                "evaluators": {
                    "evaluate_mfl_practical_research_v2.py": EVALUATOR_HASH,
                    "evaluate_mfl_evidence_research_v2.py": EVALUATOR_HASH,
                },
            }
        )
    )
    monkeypatch.setattr(quality_module, "BASELINE_PATH", path)
    return original


def checked_summary(capability, reports, *, minimum_cases):
    return summarize(
        capability,
        reports,
        minimum_cases=minimum_cases,
        expected_pack_manifest_sha256=PACK_HASH,
        expected_release_fingerprint=RELEASE_HASH,
    )


def report(path, fixture, *, passed=True, capability="drafting"):
    baseline = json.loads(quality_module.BASELINE_PATH.read_text())
    baseline["fixtures"][path.name] = {
        "capability": capability,
        "sha256": fixture,
        "case_ids": [path.stem],
    }
    quality_module.BASELINE_PATH.write_text(json.dumps(baseline))
    checks = {
        "source_references": passed,
        "quotes_bound_to_correct_sources": passed,
        "no_forbidden_literal": passed,
        "meaning_keywords": passed,
        "review_marker": passed,
        "required_quoted_details": passed,
    }
    path.write_text(
        json.dumps(
            {
                "schema": (
                    "mfl.evidence-research-generation-evaluation.v2"
                    if capability == "evidence_review"
                    else "mfl.practical-research-generation-evaluation.v2"
                ),
                "capability": capability,
                "pack_manifest_sha256": PACK_HASH,
                "release_fingerprint": RELEASE_HASH,
                "engine": "family-worker",
                "evaluator_sha256": EVALUATOR_HASH,
                "adapter_enabled": True,
                "fixtures_unchanged_during_run": True,
                "implementation_unchanged_during_run": True,
                "cleanup_failures": [],
                "total": 1,
                "completed_all_requested_cases": True,
                "fatal_error": None,
                "production_admitted": False,
                "attorney_reviewed": False,
                "passed": int(passed),
                "fixture_sha256": {str(path): fixture},
                "results": [{"case_id": path.stem, "checks": checks, "mechanical_pass": passed}],
            }
        ),
        encoding="utf-8",
    )


def test_all_independent_cases_must_pass_without_claiming_legal_admission(tmp_path):
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    report(first, "a" * 64)
    report(second, "b" * 64)
    result = checked_summary("drafting", [first, second], minimum_cases=2)
    assert result["quality_gate_passed"] is True
    assert result["decision"] == "LOCAL_RESEARCH_QUALITY_PASS"
    assert result["legal_use_approved"] is False
    assert result["production_admitted"] is False


def test_one_failed_check_or_reused_fixture_blocks_candidate(tmp_path):
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    report(first, "a" * 64, capability="evidence_review")
    report(second, "a" * 64, passed=False, capability="evidence_review")
    result = checked_summary("evidence_review", [first, second], minimum_cases=2)
    assert result["quality_gate_passed"] is False
    assert result["decision"] == "BLOCKED"
    assert any(
        row["code"] == "evaluation_fixture_identity_not_unique_or_missing"
        for row in result["failures"]
    )
    assert any(row.get("case_id") == "second" for row in result["failures"])


def test_case_floor_is_fail_closed(tmp_path):
    only = tmp_path / "only.json"
    report(only, "c" * 64, capability="evidence_review")
    result = checked_summary("evidence_review", [only], minimum_cases=2)
    assert result["quality_gate_passed"] is False
    assert any(
        row["code"] == "minimum_independent_case_count_not_met" for row in result["failures"]
    )


@pytest.mark.parametrize(
    ("key", "value"),
    (
        ("pack_manifest_sha256", "3" * 64),
        ("release_fingerprint", "4" * 64),
        ("capability", "evidence_review"),
        ("engine", "mock"),
        ("adapter_enabled", False),
        ("fixtures_unchanged_during_run", False),
        ("implementation_unchanged_during_run", False),
        ("cleanup_failures", ["worker_left_running"]),
        ("total", 2),
        ("passed", 9),
    ),
)
def test_unbound_model_mock_or_tampered_runtime_report_cannot_pass(tmp_path, key, value):
    path = tmp_path / "case.json"
    report(path, "a" * 64)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw[key] = value
    path.write_text(json.dumps(raw), encoding="utf-8")
    result = checked_summary("drafting", [path], minimum_cases=1)
    assert not result["quality_gate_passed"]


def test_empty_check_map_and_missing_expected_candidate_fail_closed(tmp_path):
    path = tmp_path / "case.json"
    report(path, "a" * 64)
    assert not summarize("drafting", [path], minimum_cases=1)["quality_gate_passed"]
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["results"][0]["checks"] = {}
    path.write_text(json.dumps(raw), encoding="utf-8")
    assert not checked_summary("drafting", [path], minimum_cases=1)["quality_gate_passed"]


def test_ui_gate_revalidates_exact_reports_and_refuses_other_weights(tmp_path):
    path = tmp_path / "case.json"
    report(path, "a" * 64)
    quality = checked_summary("drafting", [path], minimum_cases=1)
    inputs = dict(
        capability="drafting",
        pack_manifest_sha256=PACK_HASH,
        release_fingerprint=RELEASE_HASH,
        minimum_cases=1,
    )
    require_quality_evidence(quality, **inputs)
    with pytest.raises(ValueError, match="candidate_mismatch"):
        require_quality_evidence(quality, **{**inputs, "release_fingerprint": "9" * 64})
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="report_changed"):
        require_quality_evidence(quality, **inputs)


def test_ui_gate_rejects_inflated_success_counts(tmp_path):
    path = tmp_path / "case.json"
    report(path, "a" * 64)
    quality = checked_summary("drafting", [path], minimum_cases=1)
    quality["aggregate_semantic_passes"] = 99
    with pytest.raises(ValueError, match="revalidation_failed"):
        require_quality_evidence(
            quality,
            capability="drafting",
            pack_manifest_sha256=PACK_HASH,
            release_fingerprint=RELEASE_HASH,
            minimum_cases=1,
        )


@pytest.mark.parametrize("tamper", ["digest", "case_id", "evaluator", "malformed_binding"])
def test_plausible_hashes_and_success_flags_cannot_replace_pinned_inventory(tmp_path, tamper):
    path = tmp_path / "case.json"
    report(path, "a" * 64)
    payload = json.loads(path.read_text())
    if tamper == "digest":
        payload["fixture_sha256"][str(path)] = "f" * 64
    elif tamper == "case_id":
        payload["results"][0]["case_id"] = "a-different-easier-case"
    elif tamper == "evaluator":
        payload["evaluator_sha256"] = "f" * 64
    else:
        payload["fixture_sha256"] = ["f" * 64]
    path.write_text(json.dumps(payload))
    assert not checked_summary("drafting", [path], minimum_cases=1)["quality_gate_passed"]


def test_lowering_case_floor_cannot_omit_a_required_suite(tmp_path):
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    report(first, "a" * 64)
    report(second, "b" * 64)
    result = checked_summary("drafting", [first], minimum_cases=1)
    assert not result["quality_gate_passed"]
    assert any(
        row["code"] == "approved_regression_inventory_incomplete_or_duplicated"
        for row in result["failures"]
    )


def test_revalidation_rejects_baseline_changed_since_summary(tmp_path):
    path = tmp_path / "case.json"
    report(path, "a" * 64)
    quality = checked_summary("drafting", [path], minimum_cases=1)
    quality_module.BASELINE_PATH.write_text(quality_module.BASELINE_PATH.read_text() + "\n")
    with pytest.raises(ValueError, match="revalidation_failed"):
        require_quality_evidence(
            quality,
            capability="drafting",
            pack_manifest_sha256=PACK_HASH,
            release_fingerprint=RELEASE_HASH,
            minimum_cases=1,
        )


def test_synthetic_unit_reports_cannot_pass_the_real_production_baseline(
    tmp_path, monkeypatch, synthetic_baseline
):
    path = tmp_path / "case.json"
    report(path, "a" * 64)
    monkeypatch.setattr(quality_module, "BASELINE_PATH", synthetic_baseline)
    result = checked_summary("drafting", [path], minimum_cases=1)
    assert not result["quality_gate_passed"]
    assert result["production_admitted"] is False
