from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from legal.documents.workspace import commit_revision, create_document, propose_revision
from legal.production import AuthorityProductPublisher
from legal.review import (
    AuthorityChangeImpactStore,
    AuthorityImpactError,
    commit_review_decision,
    prepare_review_request,
)
from maine_family_law_llm import api as api_module


def _write_json(path: Path, payload) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _external_authority_root(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "external-authority"
    official = root / "official_authority_store"
    snapshot = official / "snapshots" / "title19a.html"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text("Title 19-A section 1653 initial text", encoding="utf-8")
    _write_json(
        official / "source_manifest.json",
        [
            {
                "source_id": "maine-title-19a",
                "source_class": "statute_title_index",
                "jurisdiction": "maine",
                "retrieved_at": "2026-07-27T12:00:00+00:00",
                "hash": _sha(snapshot),
                "parser_status": "parsed",
                "freshness_status": "fresh",
                "data_class": "official_public_authority",
                "source_url_or_path": "https://legislature.maine.gov/statutes/19-a/",
                "snapshot_path": "snapshots/title19a.html",
                "parser_audit": {"status": "parsed"},
            }
        ],
    )
    parsed = root / "parsed_authority_store" / "statutes" / "statute_sections.jsonl"
    parsed.parent.mkdir(parents=True, exist_ok=True)
    parsed.write_text(
        json.dumps(
            {
                "record_id": "statute-19a-1653",
                "source_id": "maine-title-19a",
                "source_hash": _sha(snapshot),
                "source_class": "statute_section",
                "jurisdiction": "maine",
                "freshness_status": "fresh",
                "citation": "19-A M.R.S. § 1653",
                "text": "Best interest factors.",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        root / "parsed_authority_store" / "parsed_authority_manifest.json",
        {"record_counts": {"statutes": 1, "rules": 0, "forms": 0, "opinions": 0}, "output_files": {"statutes/statute_sections.jsonl": str(parsed)}},
    )
    citation_index = _write_json(root / "authority_layer" / "citation_index.json", [])
    source_cards = root / "authority_layer" / "source_cards.jsonl"
    source_cards.parent.mkdir(parents=True, exist_ok=True)
    source_cards.write_text("{}\n", encoding="utf-8")
    graph = _write_json(root / "authority_layer" / "authority_graph.json", {})
    _write_json(
        root / "authority_layer" / "authority_layer_report.json",
        {"status": "pass", "outputs": {"citation_index": str(citation_index), "source_cards": str(source_cards), "authority_graph": str(graph)}},
    )
    retrieval = root / "embedding_store" / "hybrid" / "retrieval_documents.jsonl"
    retrieval.parent.mkdir(parents=True, exist_ok=True)
    retrieval.write_text("{}\n", encoding="utf-8")
    exact = _write_json(root / "embedding_store" / "hybrid" / "exact_citation_lookup.json", {})
    _write_json(
        root / "embedding_store" / "retrieval_index_manifest.json",
        {"status": "pass", "document_count": 1, "outputs": {"hybrid_documents": str(retrieval), "exact_citation_lookup": str(exact)}},
    )
    _write_json(root / "source_update_report.json", {"status": "pass", "freshness_counts": {"fresh": 1, "stale": 0, "unknown": 0}})
    return root, snapshot


def _publish_two_generations(tmp_path: Path) -> tuple[Path, str, str]:
    root, snapshot = _external_authority_root(tmp_path)
    publisher = AuthorityProductPublisher(data_root=root, repo_root=Path.cwd())
    first = publisher.publish(product_version="5.14.0")
    assert first.status == "pass" and first.build_id
    snapshot.write_text("Title 19-A section 1653 amended text", encoding="utf-8")
    manifest_path = root / "official_authority_store" / "source_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest[0]["hash"] = _sha(snapshot)
    manifest[0]["retrieved_at"] = "2026-07-28T12:00:00+00:00"
    _write_json(manifest_path, manifest)
    second = publisher.publish(product_version="5.15.0")
    assert second.status == "pass" and second.build_id and second.build_id != first.build_id
    return root, first.build_id, second.build_id


def _reviewed_document(case: Path, authority_build_id: str) -> dict:
    document = create_document(
        case,
        title="Best-interest findings",
        content="The proposed order applies 19-A M.R.S. § 1653.",
        document_type="motion",
        source_refs=[{"source_id": "maine-title-19a", "hash": "a" * 64}],
    )
    authority_result = {
        "status": "review_required",
        "build_id": authority_build_id,
        "sources": [
            {
                "source_id": "maine-title-19a",
                "source_class": "statute_title_index",
                "freshness_status": "fresh",
                "authority_status": "verified_official_maine",
            }
        ],
        "verification_report": {
            "citations": [],
            "quotes": [],
            "claims": [
                {
                    "claim_id": "claim-001",
                    "statement": "The proposed order applies the best-interest statute.",
                    "support_status": "supported",
                    "claim_type": "legal",
                    "source_ids": ["maine-title-19a"],
                }
            ],
            "blockers": [],
        },
        "filing_gate": {
            "mandatory_checks": {
                "authority_verified": True,
                "citations_resolved": True,
                "quotes_found": True,
                "legal_claims_supported": True,
            },
            "blockers": [],
        },
        "review_required": True,
    }
    prepared = prepare_review_request(case, document["document_id"], authority_result=authority_result)
    commit_review_decision(
        case,
        document["document_id"],
        request_id=prepared["request_id"],
        confirmation_token=prepared["confirmation_token"],
        confirmed=True,
        decision="approve_review",
        reviewer_name="Reviewer A",
        reviewer_role="attorney",
        attested=True,
        claim_annotations=[{"claim_id": "claim-001", "status": "accepted"}],
    )
    return document


def test_generation_diff_detects_added_removed_and_hash_changed_sources(tmp_path: Path):
    data_root, first, second = _publish_two_generations(tmp_path)
    case = tmp_path / "case"
    case.mkdir()
    result = AuthorityChangeImpactStore(case, data_root=data_root, repo_root=Path.cwd()).compare(first, second)
    assert result["counts"]["content_hash_changed"] == 1
    assert result["changed_source_ids"] == ["maine-title-19a"]
    assert result["changes"][0]["change_type"] == "content_hash_changed"
    assert result["review_required"] is True


def test_document_impact_invalidates_prior_approval_for_changed_reviewed_source(tmp_path: Path):
    data_root, first, second = _publish_two_generations(tmp_path)
    case = tmp_path / "case"
    case.mkdir()
    document = _reviewed_document(case, first)
    result = AuthorityChangeImpactStore(case, data_root=data_root, repo_root=Path.cwd()).analyze_document(document["document_id"], first, second)
    assert result["impacted_source_ids"] == ["maine-title-19a"]
    assert "authority_change_impacts_reviewed_sources" in result["blockers"]
    assert "prior_review_stale_after_authority_change" in result["blockers"]
    assert result["prior_approval_valid_for_target_generation"] is False
    assert result["filing_ready"] is False


def test_impact_packet_is_deterministic_and_tamper_evident(tmp_path: Path):
    data_root, first, second = _publish_two_generations(tmp_path)
    case = tmp_path / "case"
    case.mkdir()
    document = _reviewed_document(case, first)
    store = AuthorityChangeImpactStore(case, data_root=data_root, repo_root=Path.cwd())
    built = store.build(document["document_id"], first, second, approved=True)
    assert built["status"] == "pass"
    assert store.build(document["document_id"], first, second, approved=True)["build_id"] == built["build_id"]
    assert store.verify(built["build_id"])["status"] == "pass"
    path, _ = store.resolve_artifact(built["build_id"], "authority-change-impact.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["document_title"] = "tampered"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert store.verify(built["build_id"])["status"] == "blocked"
    with pytest.raises(AuthorityImpactError, match="failed verification"):
        store.resolve_artifact(built["build_id"], "authority-change-impact.html")


def test_document_edit_makes_authority_impact_artifacts_stale(tmp_path: Path):
    data_root, first, second = _publish_two_generations(tmp_path)
    case = tmp_path / "case"
    case.mkdir()
    document = _reviewed_document(case, first)
    store = AuthorityChangeImpactStore(case, data_root=data_root, repo_root=Path.cwd())
    built = store.build(document["document_id"], first, second, approved=True)
    proposal = propose_revision(
        case,
        document["document_id"],
        content="The revised proposed order applies a different analysis.",
        base_revision_id=document["current_revision_id"],
    )
    commit_revision(
        case,
        document["document_id"],
        revision_id=proposal["revision_id"],
        confirmation_token=proposal["confirmation_token"],
        confirmed=True,
    )
    with pytest.raises(AuthorityImpactError, match="stale because the document changed"):
        store.active(built["build_id"])
    with pytest.raises(AuthorityImpactError, match="stale because the document changed"):
        store.resolve_artifact(built["build_id"], "authority-change-impact.html")


def test_authority_impact_api_and_ui(monkeypatch, tmp_path: Path):
    data_root, first, second = _publish_two_generations(tmp_path)
    case = tmp_path / "case"
    case.mkdir()
    document = _reviewed_document(case, first)
    monkeypatch.setenv("MAINE_FAMILY_LAW_DATA_ROOT", str(data_root))
    monkeypatch.setattr(api_module, "active_case_root", lambda: case)
    client = TestClient(api_module.app)

    status = client.get(f"/api/authority-change-impact/status?document_id={document['document_id']}")
    assert status.status_code == 200
    assert len(status.json()["generations"]) == 2
    analyzed = client.post(
        "/api/authority-change-impact/analyze",
        json={"document_id": document["document_id"], "base_build_id": first, "target_build_id": second},
    )
    assert analyzed.status_code == 200
    assert analyzed.json()["prior_approval_valid_for_target_generation"] is False
    built = client.post(
        "/api/authority-change-impact/build",
        json={"document_id": document["document_id"], "base_build_id": first, "target_build_id": second, "approved": True},
    )
    assert built.status_code == 200
    assert built.json()["artifacts"]

    html = Path("maine_family_law_llm/ui/workbench.html").read_text(encoding="utf-8")
    js = Path("maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    css = Path("maine_family_law_llm/ui/workbench.css").read_text(encoding="utf-8")
    assert 'id="authority-impact-build"' in html
    assert "/api/authority-change-impact" in js
    assert "prior approval valid" in js.lower()
    assert ".authority-impact-source" in css


def test_authority_data_root_inside_repo_is_refused(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    inside = Path.cwd() / ".authority-impact-test-root"
    inside.mkdir(exist_ok=True)
    try:
        with pytest.raises(AuthorityImpactError, match="outside the source repository"):
            AuthorityChangeImpactStore(case, data_root=inside, repo_root=Path.cwd())
    finally:
        inside.rmdir()
