from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.services import AuthorityProductService
from legal.production import AuthorityProductPublisher
from legal.verifiers import ClaimSupportVerifier


def _write_json(path: Path, payload) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _authority_root(tmp_path: Path) -> Path:
    root = tmp_path / "external-authority"
    official = root / "official_authority_store"
    snapshot = official / "snapshots" / "title19a-1653.html"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text(
        "<h1>19-A M.R.S. § 1653</h1><p>Parental rights and responsibilities are decided according to the best interest of the child.</p>",
        encoding="utf-8",
    )
    _write_json(
        official / "source_manifest.json",
        [
            {
                "source_id": "statute-19a-1653",
                "source_class": "statute_section",
                "jurisdiction": "maine",
                "retrieved_at": "2026-07-28T00:00:00+00:00",
                "hash": _sha(snapshot),
                "parser_status": "parsed",
                "freshness_status": "fresh",
                "data_class": "official_public_authority",
                "source_url_or_path": "https://legislature.maine.gov/statutes/19-a/title19-Asec1653.html",
                "snapshot_path": "snapshots/title19a-1653.html",
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
                "source_id": "statute-19a-1653",
                "source_hash": _sha(snapshot),
                "source_class": "statute_section",
                "authority_kind": "statute_section",
                "jurisdiction": "maine",
                "authority_status": "verified_official_maine",
                "freshness_status": "fresh",
                "parser_status": "parsed",
                "source_span": {"start_offset": 0, "end_offset": 110},
                "title": "Best interest of child",
                "citation": "19-A M.R.S. § 1653",
                "source_url_or_path": "https://legislature.maine.gov/statutes/19-a/title19-Asec1653.html",
                "text": "Parental rights and responsibilities are decided according to the best interest of the child.",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        root / "parsed_authority_store" / "parsed_authority_manifest.json",
        {
            "status": "pass",
            "record_counts": {"statutes": 1, "rules": 0, "forms": 0, "opinions": 0},
            "output_files": {"statutes/statute_sections.jsonl": str(parsed)},
        },
    )

    citation_index = _write_json(
        root / "authority_layer" / "citation_index.json",
        [
            {
                "kind": "maine_statute",
                "normalized_citation": "19-A M.R.S. § 1653",
                "source_id": "statute-19a-1653",
                "authority_status": "verified_official_maine",
                "metadata": {"source_class": "statute_section", "freshness_status": "fresh"},
            }
        ],
    )
    source_cards = root / "authority_layer" / "source_cards.jsonl"
    source_cards.parent.mkdir(parents=True, exist_ok=True)
    source_cards.write_text(
        json.dumps(
            {
                "source_id": "statute-19a-1653",
                "title": "Best interest of child",
                "citation": "19-A M.R.S. § 1653",
                "source_class": "statute_section",
                "jurisdiction": "maine",
                "authority_status": "verified_official_maine",
                "freshness_status": "fresh",
                "source_url_or_path": "https://legislature.maine.gov/statutes/19-a/title19-Asec1653.html",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    graph = _write_json(root / "authority_layer" / "authority_graph.json", {"nodes": [], "edges": []})
    _write_json(
        root / "authority_layer" / "authority_layer_report.json",
        {
            "status": "pass",
            "outputs": {
                "citation_index": str(citation_index),
                "authority_graph": str(graph),
                "source_cards": str(source_cards),
            },
        },
    )

    retrieval = root / "embedding_store" / "hybrid" / "retrieval_documents.jsonl"
    retrieval.parent.mkdir(parents=True, exist_ok=True)
    retrieval.write_text(
        json.dumps(
            {
                "record_id": "statute-19a-1653",
                "source_id": "statute-19a-1653",
                "title": "Best interest of child",
                "citation": "19-A M.R.S. § 1653",
                "source_class": "statute_section",
                "jurisdiction": "maine",
                "authority_status": "verified_official_maine",
                "freshness_status": "fresh",
                "text": "19-A M.R.S. § 1653. Parental rights and responsibilities are decided according to the best interest of the child.",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    exact = _write_json(root / "embedding_store" / "hybrid" / "exact_citation_lookup.json", {"19-A M.R.S. § 1653": ["statute-19a-1653"]})
    _write_json(
        root / "embedding_store" / "retrieval_index_manifest.json",
        {
            "status": "pass",
            "document_count": 1,
            "outputs": {"hybrid_documents": str(retrieval), "exact_citation_lookup": str(exact)},
        },
    )
    _write_json(root / "source_update_report.json", {"status": "pass", "freshness_counts": {"fresh": 1, "stale": 0, "unknown": 0}})
    published = AuthorityProductPublisher(data_root=root, repo_root=Path.cwd()).publish(product_version="5.9.0")
    assert published.status == "pass"
    return root


def test_claim_support_returns_exact_source_span_and_reproducible_candidates() -> None:
    verifier = ClaimSupportVerifier()
    source = "A preliminary sentence. Parental rights and responsibilities are decided according to the best interest of the child. Another sentence."
    result = verifier.verify(
        "Parental rights and responsibilities are decided according to the best interest of the child.",
        [source],
        authority_statuses=["verified_official_maine"],
        source_jurisdictions=["maine"],
        source_ids=["statute-19a-1653"],
        source_classes=["statute_section"],
    )
    assert result["status"] == "supported"
    assert result["best_span"]["source_id"] == "statute-19a-1653"
    assert source[result["best_span"]["start_offset"] : result["best_span"]["end_offset"]].startswith("Parental rights")
    assert result["candidate_sources"][0]["matched_terms"]
    assert len(result["claim_sha256"]) == 64


def test_claim_support_does_not_ignore_numeric_or_polarity_conflicts() -> None:
    verifier = ClaimSupportVerifier()
    wrong_number = verifier.verify(
        "A filing deadline is 21 days.",
        ["A filing deadline is 14 days."],
        authority_statuses=["verified_official_maine"],
        source_jurisdictions=["maine"],
    )
    contradicted = verifier.verify(
        "The court may not order contact.",
        ["The court may order contact."],
        authority_statuses=["verified_official_maine"],
        source_jurisdictions=["maine"],
    )
    assert wrong_number["status"] != "supported"
    assert contradicted["status"] in {"contradicted", "unsupported", "partially_supported"}


def test_active_authority_verification_binds_answer_sources_and_receipt(tmp_path: Path) -> None:
    root = _authority_root(tmp_path)
    service = AuthorityProductService(data_root=root)
    text = "Under 19-A M.R.S. § 1653, parental rights and responsibilities are decided according to the best interest of the child."
    first = service.verify_output(text=text, source_ids=["statute-19a-1653"])
    second = service.verify_output(text=text, source_ids=["statute-19a-1653"])

    assert first["status"] == "verified_pending_human_review"
    report = first["verification_report"]
    assert report["citations"][0]["status"] == "found"
    assert report["claims"][0]["status"] == "supported"
    assert report["claims"][0]["best_span"]["source_id"] == "statute-19a-1653"
    assert first["verification_receipt"]["receipt_sha256"] == second["verification_receipt"]["receipt_sha256"]
    assert first["filing_gate"]["filing_ready"] is False
    assert "human_review_complete" in first["filing_gate"]["blockers"]


def test_active_authority_verification_blocks_unsupported_claim(tmp_path: Path) -> None:
    root = _authority_root(tmp_path)
    result = AuthorityProductService(data_root=root).verify_output(
        text="Under 19-A M.R.S. § 1653, Maine requires a purple parenting certificate.",
        source_ids=["statute-19a-1653"],
    )
    assert result["status"] == "review_required"
    assert "claim_unsupported" in result["verification_report"]["blockers"]
    assert result["filing_gate"]["filing_ready"] is False


def test_local_workbench_authority_endpoints_are_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from maine_family_law_llm.api import app

    root = _authority_root(tmp_path)
    monkeypatch.setenv("MAINE_FAMILY_LAW_DATA_ROOT", str(root))
    client = TestClient(app)
    status = client.get("/api/authority/status")
    assert status.status_code == 200
    assert status.json()["active"] is True

    response = client.post(
        "/api/authority/verify-answer",
        json={
            "text": "Under 19-A M.R.S. § 1653, parental rights and responsibilities are decided according to the best interest of the child.",
            "source_ids": ["statute-19a-1653"],
        },
    )
    assert response.status_code == 200
    assert response.json()["verification_report"]["claims"][0]["status"] == "supported"


def test_v56_ui_exposes_in_chat_verification_modal() -> None:
    html = Path("maine_family_law_llm/ui/workbench.html").read_text(encoding="utf-8")
    js = Path("maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    css = Path("maine_family_law_llm/ui/workbench.css").read_text(encoding="utf-8")
    assert "Verify support" in js
    assert "/api/authority/verify-answer" in js
    assert 'id="authority-verification-modal"' in html
    assert "Copy verification receipt" in html
    assert ".authority-verification-modal" in css
    assert "Model confidence is never accepted as verification" in html


def test_authority_verification_rejects_non_maine_scope_and_oversized_text(tmp_path: Path) -> None:
    root = _authority_root(tmp_path)
    service = AuthorityProductService(data_root=root)
    wrong_scope = service.verify_output(text="A claim.", expected_jurisdiction="new_hampshire")
    oversized = service.verify_output(text="x" * 200_001)
    assert wrong_scope["blockers"] == ["verification_jurisdiction_not_allowed"]
    assert oversized["blockers"] == ["verification_text_too_large"]
