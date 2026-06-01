from __future__ import annotations

import json
from pathlib import Path

from maine_family_law_llm.corpus_build import (
    audit_external_corpus,
    build_required_indexes,
    fetch_live_official_corpus,
    normalize_external_corpus,
    parse_external_corpus,
    write_full_corpus_manifest,
)
from maine_family_law_llm.corpus_registry import (
    AUTHORITY_RANKING,
    FEDERAL_JURISDICTION_WARNINGS,
    REQUIRED_ATTORNEY_REVIEWED_EVALS,
    corpus_summary,
    full_corpus_manifest_entries,
)
from maine_family_law_llm.fetch import is_official_url
from maine_family_law_llm.source_manifest import SourceManifestEntry


def test_full_registry_includes_non_legislative_maine_authority() -> None:
    entries = full_corpus_manifest_entries()
    by_id = {entry.id: entry for entry in entries}

    assert "maine-rules-civil-family-division-complete" in by_id
    assert "maine-rule-120-standing-order" in by_id
    assert "maine-professional-conduct-plus" in by_id
    assert "maine-bar-rules-plus" in by_id
    assert "maine-judicial-conduct-code" in by_id
    assert "maine-rules-electronic-court-systems" in by_id
    assert by_id["maine-professional-conduct-plus"].source_type == "professional_conduct_rule"
    assert by_id["maine-rule-120-standing-order"].authority_class == "official_standing_order"


def test_full_registry_includes_district_of_maine_federal_lane() -> None:
    entries = full_corpus_manifest_entries()
    by_id = {entry.id: entry for entry in entries}

    assert "district-maine-local-rules" in by_id
    assert "district-maine-self-representation-forms" in by_id
    assert "district-maine-electronic-filing" in by_id
    assert "uscode-28-1915-ifp" in by_id
    assert by_id["district-maine-local-rules"].jurisdiction == "Federal - District of Maine"
    assert by_id["district-maine-electronic-filing"].corpus_lane == "federal_maine_intake_and_relief"
    assert "MaineECFIntake@med.uscourts.gov" in by_id["district-maine-electronic-filing"].citation_aliases


def test_federal_official_hosts_are_allowed_for_live_fetch() -> None:
    assert is_official_url("https://www.med.uscourts.gov/local-rules")
    assert is_official_url("https://www.uscourts.gov/forms-rules/current-rules-practice-procedure")
    assert is_official_url("https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title28-section1915")
    assert is_official_url("https://www.ca1.uscourts.gov/opinions")


def test_corpus_summary_tracks_ga_requirements_and_warning_doctrines() -> None:
    summary = corpus_summary()

    assert summary["source_count"] >= 40
    assert "federal_maine_intake_and_relief" in summary["lanes"]
    assert "official_maine_professional_conduct" in summary["authority_classes"]
    assert "domestic_relations_exception" in FEDERAL_JURISDICTION_WARNINGS
    assert REQUIRED_ATTORNEY_REVIEWED_EVALS["federal_jurisdiction_blockers_gold.jsonl"] >= 100
    assert AUTHORITY_RANKING.index("federal_rules_primary") < AUTHORITY_RANKING.index(
        "official_federal_district_maine_local_rules"
    )


def test_external_corpus_manifest_and_audit_use_data_root(tmp_path: Path) -> None:
    manifest_path = write_full_corpus_manifest(tmp_path)
    report = audit_external_corpus(tmp_path)

    assert manifest_path == tmp_path / "manifests" / "full_corpus_manifest.json"
    assert manifest_path.is_file()
    assert report["status"] == "blocked"
    assert "official_source_raw_fetch_incomplete" in report["blockers"]
    assert "attorney_reviewed_eval_pack_incomplete" in report["blockers"]
    assert not (tmp_path / ".git").exists()


def test_live_fetch_requires_explicit_allow_live(tmp_path: Path) -> None:
    entry = SourceManifestEntry(
        id="district-maine-local-rules-test",
        title="District of Maine Local Rules test",
        source_type="federal_court_rule",
        jurisdiction="Federal - District of Maine",
        official=True,
        url="https://www.med.uscourts.gov/local-rules",
        effective_date="2025-04-01",
        retrieved_at="2026-05-24T00:00:00Z",
        version_label="test",
        citation_hint="D. Me. Local Rules",
        license_or_terms_note="Official source.",
        source_priority=21,
        notes="test only",
        authority_class="official_federal_district_maine_local_rules",
        corpus_lane="federal_maine_intake_and_relief",
        parser="district_maine_local_rules_parser",
    )

    try:
        fetch_live_official_corpus(tmp_path, [entry], allow_live=False)
    except ValueError as exc:
        assert "allow_live=True" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("live fetch should require explicit allow_live")


def test_external_normalize_parse_and_index_pipeline_with_synthetic_raw(tmp_path: Path) -> None:
    manifest_path = write_full_corpus_manifest(tmp_path)
    entry = full_corpus_manifest_entries()[0]
    raw_dir = tmp_path / "raw" / entry.id
    raw_dir.mkdir(parents=True)
    raw_path = raw_dir / "source.html"
    raw_path.write_text("<h1>Title 19-A</h1><p>Best interest and parental rights text.</p>", encoding="utf-8")
    metadata = entry.to_dict()
    metadata.update({"id": entry.id, "raw_path": str(raw_path), "sha256": "0" * 64})
    (raw_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

    normalized = normalize_external_corpus(tmp_path)
    parsed = parse_external_corpus(tmp_path)
    indexed = build_required_indexes(tmp_path)
    audit = audit_external_corpus(tmp_path)

    assert manifest_path.is_file()
    assert normalized["status"] == "pass"
    assert parsed["status"] == "pass"
    assert indexed["status"] == "pass"
    assert (tmp_path / "indexes" / "exact_citation_index.json").is_file()
    assert "official_source_raw_fetch_incomplete" in audit["blockers"]
    assert "required_indexes_incomplete" not in audit["blockers"]
