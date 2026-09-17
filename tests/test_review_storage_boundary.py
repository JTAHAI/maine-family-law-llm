"""Fictional review privacy, authenticated consumers and canonical API boundaries."""

import json

import pytest
from fastapi.testclient import TestClient

from legal.documents import storage
from legal.documents.workspace import create_document
from legal.review import review_ledger as ledger
from legal.review.authority_impact import _latest_review_packet
from legal.review.filing_packet import _latest_review_context
from maine_family_law_llm import api


@pytest.fixture
def reviewed(tmp_path):
    case = tmp_path / "fictional"
    case.mkdir()
    doc = create_document(case, title="Fictional review", content="Fictional notice.")
    prepared = ledger.prepare_review_request(
        case,
        doc["document_id"],
        authority_result={"status": "blocked"},
        facts=["Fictional notice."],
    )
    args = dict(
        request_id=prepared["request_id"],
        confirmation_token=prepared["confirmation_token"],
        confirmed=True,
        decision="request_changes",
        reviewer_name="Fictional reviewer",
        reviewer_role="other_reviewer",
        attested=False,
        notes="Fictional private review note",
    )
    return case, doc, prepared, args


def test_encrypted_notes_packets_consumers_and_reopen(reviewed):
    case, doc, prepared, args = reviewed
    decision = ledger.commit_review_decision(case, doc["document_id"], **args)
    files = list((case / "19_DOCUMENT_WORKSPACE/reviews").rglob("*.json"))
    assert len(files) == 3  # Request, decision and authenticated history head.
    for path in files:
        raw = path.read_bytes()
        assert b"Fictional" not in raw and args["confirmation_token"].encode() not in raw
        assert json.loads(raw)["storage_format"] == storage.FORMAT
    for reader in (_latest_review_context, _latest_review_packet):
        loaded, packet = reader(case, doc["document_id"])
        assert loaded == decision and packet["packet_sha256"] == prepared["packet"]["packet_sha256"]
    history = ledger.list_review_history(case, doc["document_id"])
    assert history["storage_authenticated"] and history["review_required"]
    assert history["latest"]["notes"] == args["notes"]
    assert ledger.verify_review_ledger(case, doc["document_id"])["valid"]
    with pytest.raises(ledger.ReviewLedgerError):
        ledger.commit_review_decision(case, doc["document_id"], **args)


def test_plaintext_history_is_visible_but_never_authorizes(reviewed):
    case, doc, _, args = reviewed
    result = ledger.commit_review_decision(case, doc["document_id"], **args)
    path = next((case / "19_DOCUMENT_WORKSPACE/reviews").glob("*/decisions/*.json"))
    # A historical plaintext record with a re-computed unkeyed approval hash.
    result["filing_gate"]["filing_ready"] = True
    result.pop("decision_sha256")
    result["decision_sha256"] = ledger._sha(result)
    raw = json.dumps(result).encode()
    path.write_bytes(raw)
    history = ledger.list_review_history(case, doc["document_id"])
    assert history["decisions"][0]["notes"] == args["notes"]
    assert history["latest"] is None and history["review_required"]
    assert not history["storage_authenticated"]
    for reader in (_latest_review_context, _latest_review_packet):
        assert reader(case, doc["document_id"]) == (None, None)
    assert path.read_bytes() == raw
    assert not ledger.verify_review_ledger(case, doc["document_id"])["valid"]


@pytest.mark.parametrize("damage", ["ciphertext", "plaintext", "wrong_key", "different_path"])
def test_request_authentication_fails_closed(reviewed, monkeypatch, damage):
    case, doc, prepared, args = reviewed
    path = next((case / "19_DOCUMENT_WORKSPACE/reviews").glob("*/requests/*.json"))
    if damage == "wrong_key":
        monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "different-fictional-key")
    elif damage == "plaintext":
        path.write_text(json.dumps(storage.decode(path, path.read_bytes())), encoding="utf-8")
    elif damage == "different_path":
        replacement = path.with_name("e" * 32 + ".json")
        replacement.write_bytes(path.read_bytes())
        args["request_id"] = "e" * 32
    else:
        value = json.loads(path.read_bytes())
        value["envelope"]["ciphertext"] = "AAAA"
        path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ledger.ReviewLedgerError):
        ledger.commit_review_decision(case, doc["document_id"], **args)
    assert not list((path.parent.parent / "decisions").glob("*.json"))


@pytest.mark.parametrize(
    "changed_header,expected",
    [
        ("X-User-Role", 403),
        ("X-Tenant-Id", 403),
        ("X-MFLL-Client-Session", 403),
        ("X-MFLL-Matter-Id", 409),
    ],
)
def test_canonical_scope_protection(reviewed, monkeypatch, changed_header, expected):
    case, doc, _, _ = reviewed
    monkeypatch.setattr(api, "active_case_root", lambda: case)
    headers = {
        "X-User-Role": "reviewer",
        "X-Tenant-Id": "local-desktop",
        "X-MFLL-Client-Session": "a" * 32,
        "X-MFLL-Matter-Id": api._case_id(case),
    }
    headers[changed_header] = ""
    with TestClient(api.app) as client:
        response = client.get(
            f"/api/document-workspace/documents/{doc['document_id']}/reviews", headers=headers
        )
    assert response.status_code == expected
    assert "Fictional" not in response.text


def test_audit_failure_prevents_review_write(reviewed, monkeypatch):
    from app.services.local_agent_context_service import LocalAgentAuditStore

    case, doc, _, _ = reviewed
    monkeypatch.setattr(api, "active_case_root", lambda: case)

    def unavailable(*args, **kwargs):
        raise OSError("Fictional private failure must not escape")

    monkeypatch.setattr(LocalAgentAuditStore, "record", unavailable)
    headers = {
        "X-User-Role": "reviewer",
        "X-Tenant-Id": "local-desktop",
        "X-MFLL-Client-Session": "a" * 32,
        "X-MFLL-Matter-Id": api._case_id(case),
    }
    before = list((case / "19_DOCUMENT_WORKSPACE/reviews").rglob("*.json"))
    client = TestClient(api.app)
    result = client.post(
        f"/api/document-workspace/documents/{doc['document_id']}/review/prepare",
        headers=headers,
        json={"facts": []},
    )
    assert result.status_code == 409 and "Fictional private" not in result.text
    assert list((case / "19_DOCUMENT_WORKSPACE/reviews").rglob("*.json")) == before


def test_source_offsets_refer_to_original_not_casefolded_text():
    text = "Fictional Straße. Notice delivered."
    report = ledger.build_fact_evidence_report(
        ["Notice delivered."], [{"evidence_id": "fictional", "text": text}]
    )
    match = report["facts"][0]["supporting_records"][0]
    assert match["span_start"] == text.index("Notice")
    assert text[match["span_start"] : match["span_end"]] == match["text"] == "Notice delivered."


def test_cross_workspace_ciphertext_is_rejected(reviewed, tmp_path):
    case, doc, prepared, args = reviewed
    other = tmp_path / "fictional-other"
    other.mkdir()
    other_doc = create_document(other, title="Other fictional", content="Other text")
    original = next((case / "19_DOCUMENT_WORKSPACE/reviews").glob("*/requests/*.json"))
    _, requests, _ = ledger._roots(other, other_doc["document_id"])
    (requests / original.name).write_bytes(original.read_bytes())
    with pytest.raises(ledger.ReviewLedgerError):
        ledger.commit_review_decision(other, other_doc["document_id"], **args)


def test_valid_other_tenant_cannot_read_audited_matter(reviewed, monkeypatch):
    case, doc, _, _ = reviewed
    monkeypatch.setattr(api, "active_case_root", lambda: case)
    headers = {
        "X-User-Role": "reviewer",
        "X-Tenant-Id": "local-desktop",
        "X-MFLL-Client-Session": "a" * 32,
        "X-MFLL-Matter-Id": api._case_id(case),
    }
    client = TestClient(api.app)
    route = f"/api/document-workspace/documents/{doc['document_id']}/reviews"
    assert client.get(route, headers=headers).status_code == 200
    denied = client.get(route, headers={**headers, "X-Tenant-Id": "different-tenant"})
    assert denied.status_code == 409 and "Fictional" not in denied.text
    invalid = client.post(
        f"/api/document-workspace/documents/{doc['document_id']}/review/commit",
        headers=headers,
        json={"notes": {"private": "Fictional private validation marker"}},
    )
    assert invalid.status_code == 422 and "Fictional private" not in invalid.text


def test_review_routes_have_one_canonical_registration():
    targets = [
        "/api/document-workspace/review-queue",
        "/api/document-workspace/documents/{document_id}/review/prepare",
        "/api/document-workspace/documents/{document_id}/review/commit",
        "/api/document-workspace/documents/{document_id}/reviews",
        "/api/document-workspace/documents/{document_id}/reviews/verify",
    ]
    pairs = [
        (route.path, method)
        for route in api.app.routes
        if getattr(route, "path", None) in targets
        for method in route.methods
    ]
    assert len(pairs) == len(set(pairs)) == 5


def test_two_processes_cannot_commit_same_token(reviewed):
    import os
    import subprocess
    import sys

    case, doc, _, args = reviewed
    code = """import json,sys
from pathlib import Path
from legal.review.review_ledger import commit_review_decision, ReviewLedgerError
try:
 commit_review_decision(Path(sys.argv[1]), sys.argv[2], **json.loads(sys.argv[3]))
 print('committed')
except ReviewLedgerError:
 print('blocked')
"""
    children = []
    try:
        for _ in range(2):
            children.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        "-B",
                        "-c",
                        code,
                        str(case),
                        doc["document_id"],
                        json.dumps(args),
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env={**os.environ, "TEMP": str(case), "TMP": str(case)},
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            )
        results = [child.communicate(timeout=60) for child in children]
        assert sorted(output.strip() for output, _ in results) == ["blocked", "committed"]
        assert all(child.returncode == 0 for child in children)
        assert ledger.list_review_history(case, doc["document_id"])["decision_count"] == 1
        assert ledger.verify_review_ledger(case, doc["document_id"])["valid"]
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
                child.communicate()
