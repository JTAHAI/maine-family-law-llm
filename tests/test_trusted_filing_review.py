"""Fictional fixture through the shipped HTTP routes and real authority verifier."""

import hashlib
import json

from fastapi.testclient import TestClient

from app.api.production import app
from legal.documents.workspace import create_document
from legal.production import AuthorityProductPublisher
from legal.review.filing_packet import ReviewedFilingPacketStore
from maine_family_law_llm import api
from test_v55_immutable_authority_product import _fixture_data_root


def build_filing_fixture(tmp_path):
    root = _fixture_data_root(tmp_path)
    phrase = "The court considers fictional stability factors."
    citation = "19-A M.R.S. § 1653"
    # This invented proposition is never a claim about the actual statute.
    law = f'{citation}. "{phrase}"'
    card_file = root / "authority_layer" / "source_cards.jsonl"
    card = json.loads(card_file.read_text())
    card.update(authority_status="verified_official_maine",
                url="https://legislature.maine.gov/statutes/19-A/title19-Asec1653.html", text=law)
    card_file.write_text(json.dumps(card) + "\n", encoding="utf-8")
    docs = root / "embedding_store" / "hybrid" / "retrieval_documents.jsonl"
    docs.write_text(json.dumps(card) + "\n", encoding="utf-8")
    assert AuthorityProductPublisher(data_root=root).publish(product_version="9.0.1").status == "pass"
    case = tmp_path / "fictional-case"
    case.mkdir()
    fact = "Parent Example moved on January 3."
    source = case / "original.txt"
    source.write_text(fact, encoding="utf-8")
    indexes = case / "04_INDEXES"
    indexes.mkdir()
    (indexes / "private_search_index.json").write_text(json.dumps([{
        "evidence_id": "fictional-1", "text": fact,
        "source_hash": hashlib.sha256(source.read_bytes()).hexdigest(),
        "private_copy_relpath": source.name,
    }]), encoding="utf-8")
    document = create_document(case, title="Fictional final order", content=f"{law}\n\nFindings of fact\n\n{fact}",
                               document_type="draft")
    return root, case, document, source, fact, phrase, citation, card["source_id"]


def test_trusted_review_filing_download_and_revocation(tmp_path, monkeypatch):
    root, case, document, source, fact, phrase, citation, source_id = build_filing_fixture(tmp_path)
    matter = api._case_id(case)
    for key, value in {
        "MAINE_FAMILY_LAW_DATA_ROOT": str(root),
        "MFL_AUTHORITY_DATA_ROOT": str(root),
        "MFL_FILING_REVIEWER_ID": "fixture-reviewer",
        "MFL_FILING_REVIEWER_TENANT": "local-desktop",
        "MFL_FILING_REVIEWER_MATTER_ID": matter,
        "MFL_FILING_REVIEWER_BEARER_SHA256": hashlib.sha256(b"a" * 64).hexdigest(),
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(api, "active_case_root", lambda: case)
    client = TestClient(app, headers={
        "X-User-Role": "reviewer", "X-Tenant-Id": "local-desktop",
        "X-MFLL-Client-Session": "c" * 32, "X-MFLL-Matter-Id": matter,
    })
    auth = {"Authorization": "Bearer " + "a" * 64}
    doc_id = document["document_id"]
    review = f"/api/document-workspace/documents/{doc_id}/review"
    args = {"facts": [fact], "auto_extract_claims": True,
            "quotes": [{"quoted_text": phrase, "source_id": source_id}],
            "claims": [{"claim": citation + ".", "source_ids": [source_id]},
                       {"claim": phrase, "source_ids": [source_id]}]}
    assert client.post(review + "/prepare", json=args,
                       headers={**auth, "X-Tenant-Id": "other"}).status_code == 403
    prepared_raw = client.post(review + "/prepare", json=args, headers=auth)
    assert prepared_raw.status_code == 200, prepared_raw.text
    prepared = prepared_raw.json()
    commit = {
        "request_id": prepared["request_id"], "confirmation_token": prepared["confirmation_token"],
        "confirmed": True, "attested": True, "privacy_attested": True,
        "reviewer_name": "Caller-controlled name", "reviewer_role": "attorney",
        "claim_annotations": [{"claim_id": row["claim_id"], "status": "accepted"}
                              for row in prepared["packet"]["claims_for_review"]],
    }
    assert client.post(review + "/commit", json=commit).status_code == 403
    recorded = client.post(review + "/commit", json=commit, headers=auth)
    assert recorded.status_code == 200, recorded.text
    assert recorded.json()["reviewer"]["name"] == "fixture-reviewer"
    assert recorded.json()["reviewer"]["role"] != "attorney"
    assert client.post(review + "/commit", json=commit, headers=auth).status_code == 409
    history_url = f"/api/document-workspace/documents/{doc_id}/reviews"
    history = client.get(history_url).json()
    assert history["review_required"] is True
    assert history["filing_recheck_required"] == "current_sources_recheck_required"
    built = client.post(f"/api/reviewed-filing-packet/documents/{doc_id}/build", json={"approved": True})
    assert built.status_code == 200, built.text
    assert built.json()["packet"]["filing_ready"] is True, built.json()["packet"]["blockers"]
    export = next(row for row in built.json()["artifacts"] if row["name"] == "verified-filing-copy.txt")
    build_dir = ReviewedFilingPacketStore(case).builds / built.json()["build_id"]
    assert not (build_dir / export["name"]).exists()
    assert client.get(export["download_url"]).status_code == 403
    download = client.get(export["download_url"], headers=auth)
    assert download.status_code == 200, download.text
    assert download.headers["X-MFLL-Filing-Gate-Status"] == "allowed"
    assert download.content == document["content"].encode("utf-8")
    assert hashlib.sha256(download.content).hexdigest() == export["sha256"]
    assert not (build_dir / export["name"]).exists()
    working = client.post(f"/api/document-workspace/documents/{doc_id}/export-sessions").json()
    assert client.get(working["download_url"]).headers["X-MFLL-Filing-Gate-Status"] == "review_required"
    headers = {**auth, "X-MFLL-Client-Session": "d" * 32}
    assert client.get(export["download_url"], headers=headers).status_code == 404
    # Stale index cannot keep a changed original eligible.
    source.write_text(fact + " altered", encoding="utf-8")
    assert client.get(export["download_url"], headers=auth).status_code == 409
    source.write_text(fact, encoding="utf-8")
    # A different admitted authority generation invalidates the already-issued link.
    assert AuthorityProductPublisher(data_root=root).publish(product_version="9.0.2").status == "pass"
    assert client.get(export["download_url"], headers=auth).status_code == 409
    monkeypatch.setenv("MFL_FILING_REVIEWER_BEARER_SHA256", hashlib.sha256(b"b" * 64).hexdigest())
    assert client.get(history_url).json()["filing_recheck_required"] == "trusted_filing_reviewer_missing_or_revoked"
    assert client.get(export["download_url"], headers=auth).status_code == 403
    assert client.get(export["download_url"], headers={"Authorization": "Bearer " + "b" * 64}).status_code == 409
