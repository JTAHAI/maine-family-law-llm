from __future__ import annotations

from pathlib import Path

from legal.evals import FullReleaseEvalRunner, build_passing_fixture_metrics
from legal.production.release_gates import ReleaseMetric
from legal.security import LegalRedTeamRunner

ROOT = Path(__file__).resolve().parents[1]


def test_pass46_full_release_eval_allows_only_real_threshold_passing_metrics():
    report = FullReleaseEvalRunner(project_root=ROOT).run(
        measured_metrics=build_passing_fixture_metrics()
    ).as_dict()

    assert report["status"] == "pass"
    assert report["ship_decision"] == "ship"
    assert report["release_allowed"] is True
    assert not report["blockers"]
    assert report["gate_report"]["readiness"] == "production_release_allowed"


def test_pass46_full_release_eval_blocks_synthetic_or_undersized_metrics():
    metrics = build_passing_fixture_metrics()
    metrics["citation_support"] = ReleaseMetric(
        "citation_support",
        1.0,
        "synthetic_seed_metric",
        500,
        True,
    )
    metrics["quote_span_verification"] = ReleaseMetric(
        "quote_span_verification",
        0.99,
        "attorney_reviewed_release_eval",
        10,
        True,
    )

    report = FullReleaseEvalRunner(project_root=ROOT).run(measured_metrics=metrics).as_dict()

    assert report["ship_decision"] == "no_ship"
    assert "insufficient_metric_basis:citation_support" in report["blockers"]
    assert "minimum_sample_size_not_met:quote_span_verification" in report["blockers"]


def test_pass46_current_repo_release_eval_is_no_ship_until_real_external_evidence_exists():
    report = FullReleaseEvalRunner(project_root=ROOT, eval_root=ROOT / "eval_data").run().as_dict()

    assert report["status"] == "pass"
    assert report["ship_decision"] == "no_ship"
    assert report["release_allowed"] is False
    assert any(blocker.startswith("missing_metric:") or blocker.startswith("minimum_sample_size_not_met:") for blocker in report["blockers"])


def test_pass47_legal_red_team_suites_fail_safely_and_block_filing_ready_bypass():
    report = LegalRedTeamRunner(project_root=ROOT).run().as_dict()

    assert report["status"] == "pass", report
    assert report["no_filing_ready_bypass"] is True
    categories = {result["category"] for result in report["results"]}
    assert set(report["required_categories"]).issubset(categories)
    assert all(result["safe"] is True for result in report["results"])
    bypass = [r for r in report["results"] if r["category"] == "filing_ready_bypass_tests"][0]
    assert "filing_ready_bypass_blocked" in bypass["blockers"]
