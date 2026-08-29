from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "dist" / "release" / "v7.0.0" / "evidence"


def load(name: str) -> dict:
    path = EVIDENCE / name
    if not path.is_file():
        pytest.skip(
            "Archived v7 authority-acceptance evidence is unavailable in this checkout; "
            "this is an external release-evidence blocker, not a source-test pass."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def test_authority_acceptance_identifies_active_direct_build() -> None:
    report = load("04_authority_acceptance.json")

    assert report["decision"] == "PASS"
    assert report["authority_root"].lower() == r"c:\dev\me_fm_llm_data"
    assert report["live_update"]["executed"] is True
    assert report["live_update"]["failed"] == 0
    assert report["live_update"]["fixture_mode"] is False
    assert report["active_build_id"]
    assert report["store_ga_blockers"] == []
    assert report["enterprise_ga_blockers"] == ["attorney_reviewed_citation_and_quote_gold_absent"]


def test_authority_metadata_citations_and_verifiers_are_evidence_backed() -> None:
    report = load("04_authority_acceptance.json")

    assert report["sources"]["total"] >= 38
    assert report["sources"]["all_required_metadata_present"] is True
    assert all(
        field["missing"] == 0
        for field in report["sources"]["metadata_completeness"].values()
    )
    assert report["citations"]["rule"]["status"] == "found"
    assert report["citations"]["statute"]["status"] == "found"
    assert report["citations"]["pinpoint"]["status"] == "found"
    assert report["citations"]["pinpoint"]["metadata"]["source_span"]
    assert report["citations"]["law_court_case"]["status"] == "found"
    assert report["citations"]["fake"]["status"] == "not_found"
    assert report["quote_results"]["exact"]["start_offset"] == 0
    assert report["quote_results"]["fuzzy_review_required"]["review_required"] is True
    assert report["current_law_fail_closed"]["pass"] is True
    assert report["authority_ranking"]["pass"] is True


def test_retrieval_metrics_and_package_boundary_are_honest() -> None:
    metrics = load("04_retrieval_verifier_metrics.json")
    report = load("04_authority_acceptance.json")

    assert metrics["status"] == "pass_with_enterprise_limitations"
    assert metrics["retrieval"]["sample_count"] == 25
    assert metrics["retrieval"]["recall_at_20"] == 1.0
    assert metrics["retrieval"]["dataset_type"].endswith("not attorney-reviewed gold")
    assert metrics["citation_existence"]["dataset_type"].startswith("committed synthetic seed")
    assert report["package_boundary"]["status"] == "pass"
    assert report["package_boundary"]["forbidden_msix_hits"] == {}
    assert report["package_boundary"]["external_store_directories_inside_repository"] == []
    msix = Path(report["package_boundary"]["msix"])
    assert hashlib.sha256(msix.read_bytes()).hexdigest() == report["package_boundary"]["msix_sha256"]
