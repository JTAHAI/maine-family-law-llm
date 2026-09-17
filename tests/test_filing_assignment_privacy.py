"""Fictional encrypted, revision-bound reviewer assignments and scoped routes."""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from legal.documents import storage
from legal.documents.workspace import (
    DocumentWorkspaceError,
    commit_revision,
    create_document,
    propose_revision,
)
from legal.review import filing_packet as filing
from maine_family_law_llm import api


@pytest.fixture
def fixture(tmp_path):
    case = tmp_path / "fictional-assignment-matter"
    case.mkdir()
    doc = create_document(case, title="Fictional assignment", content="Fictional notice.")
    store = filing.ReviewedFilingPacketStore(case)
    args = dict(
        reviewer_label="Fictional reviewer",
        role="other_reviewer",
        capabilities=["review"],
        expected_revision_id=doc["current_revision_id"],
        exclusive=True,
        note="Fictional private assignment note",
    )
    return case, doc, store, args


def test_encryption_reopen_and_exact_revision(fixture):
    case, doc, store, args = fixture
    entry = store.assign(doc["document_id"], **args)
    raw = store.assignments.read_bytes()
    assert b"Fictional" not in raw and json.loads(raw)["storage_format"] == storage.FORMAT
    history = filing.ReviewedFilingPacketStore(case).assignments_for(doc["document_id"])
    assert history["active"] == [entry] and history["storage_authenticated"]
    proposed = propose_revision(
        case,
        doc["document_id"],
        content="Fictional changed draft.",
        base_revision_id=doc["current_revision_id"],
    )
    commit_revision(
        case,
        doc["document_id"],
        revision_id=proposed["revision_id"],
        confirmation_token=proposed["confirmation_token"],
        confirmed=True,
    )
    stale = store.assignments_for(doc["document_id"])
    assert stale["active"] == [] and stale["history"] == [entry] and stale["review_required"]


def test_legacy_labels_are_inspection_only_and_unchanged(fixture):
    _, doc, store, args = fixture
    entry = store.assign(doc["document_id"], **args)
    raw = (json.dumps(entry) + "\n").encode()
    store.assignments.write_bytes(raw)  # This test's fictional legacy fixture only.
    history = store.assignments_for(doc["document_id"])
    assert not history["storage_authenticated"] and history["read_only"]
    assert history["active"] == [] and history["history"] == [entry]
    with pytest.raises(filing.ReviewedFilingPacketError, match="read-only"):
        store.assign(doc["document_id"], **args)
    assert store.assignments.read_bytes() == raw


@pytest.mark.parametrize("damage", ["wrong_key", "ciphertext", "other_matter"])
def test_authenticated_binding_failure(fixture, monkeypatch, tmp_path, damage):
    _, doc, store, args = fixture
    store.assign(doc["document_id"], **args)
    if damage == "wrong_key":
        monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "different-fictional-assignment-key")
    elif damage == "ciphertext":
        data = json.loads(store.assignments.read_bytes())
        data["envelope"]["ciphertext"] = "AAAA"
        store.assignments.write_text(json.dumps(data), encoding="utf-8")
    else:
        other = tmp_path / "other-fictional"
        other.mkdir()
        other_doc = create_document(other, title="Other fictional", content="Other fictional.")
        target = filing.ReviewedFilingPacketStore(other)
        target.assignments.write_bytes(store.assignments.read_bytes())
        store, doc = target, other_doc
    with pytest.raises(
        (filing.ReviewedFilingPacketError, DocumentWorkspaceError), match="unlocked or verified"
    ):
        store.assignments_for(doc["document_id"])


def test_exclusive_race_and_atomic_failure_preserve_prior(fixture, monkeypatch):
    _, doc, store, args = fixture

    def attempt(_):
        try:
            return store.assign(doc["document_id"], **args)["assignment_id"]
        except filing.ReviewedFilingPacketError as exc:
            return exc.code

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert results.count("reviewer_assignment_conflict") == 1
    before = store.assignments.read_bytes()

    def failed(*args, **kwargs):
        raise OSError("Fictional private failure")

    monkeypatch.setattr(filing, "atomic_write_bytes", failed)
    with pytest.raises(filing.ReviewedFilingPacketError, match="could not be saved"):
        store.assign(doc["document_id"], **{**args, "exclusive": False})
    assert store.assignments.read_bytes() == before


def _headers(case):
    return {
        "X-User-Role": "reviewer",
        "X-Tenant-Id": "local-desktop",
        "X-MFLL-Client-Session": "a" * 32,
        "X-MFLL-Matter-Id": api._case_id(case),
    }


@pytest.mark.parametrize(
    "header,code",
    [
        ("X-User-Role", 403),
        ("X-Tenant-Id", 403),
        ("X-MFLL-Client-Session", 403),
        ("X-MFLL-Matter-Id", 409),
    ],
)
@pytest.mark.parametrize("route", ["status", "diff", "read", "assign", "build", "verify"])
def test_all_json_routes_require_scope(fixture, monkeypatch, header, code, route):
    case, doc, store, args = fixture
    monkeypatch.setattr(api, "active_case_root", lambda: case)
    headers = _headers(case)
    headers[header] = ""
    root = "/api/reviewed-filing-packet"
    routes = {
        "status": ("GET", root + "/status?document_id=" + doc["document_id"], None),
        "diff": ("POST", root + "/documents/" + doc["document_id"] + "/diff", {}),
        "read": ("GET", root + "/documents/" + doc["document_id"] + "/assignments", None),
        "assign": ("POST", root + "/documents/" + doc["document_id"] + "/assignments", args),
        "build": ("POST", root + "/documents/" + doc["document_id"] + "/build", {"approved": True}),
        "verify": ("GET", root + "/verify?build_id=" + "b" * 24, None),
    }
    method, url, payload = routes[route]
    with TestClient(api.app) as client:
        result = client.request(method, url, json=payload, headers=headers)
    assert result.status_code == code
    assert "Fictional" not in result.text
    assert not store.assignments.exists()


def test_canonical_assignment_audit_and_audit_failure(fixture, monkeypatch):
    from app.services.local_agent_context_service import LocalAgentAuditStore

    case, doc, store, args = fixture
    monkeypatch.setattr(api, "active_case_root", lambda: case)
    url = f"/api/reviewed-filing-packet/documents/{doc['document_id']}/assignments"
    client = TestClient(api.app, headers=_headers(case))
    result = client.post(url, json=args)
    assert result.status_code == 200 and result.json()["matter_id"] == api._case_id(case)
    response = client.get(url)
    assert response.status_code == 200 and response.json()["storage_authenticated"]
    import os

    audit = api._local_agent_audit_store(case)
    events = audit.encryptor.decrypt_json(json.loads(audit.path.read_bytes()))["events"]
    assert any(e["action"] == "filing_assignment_write_completed" for e in events)
    assert b"Fictional" not in audit.path.read_bytes()
    before = store.assignments.read_bytes()

    def fail(*args, **kwargs):
        raise OSError("Fictional private error")

    monkeypatch.setattr(LocalAgentAuditStore, "record", fail)
    blocked = client.post(url, json={**args, "exclusive": False})
    assert blocked.status_code == 409 and "Fictional" not in blocked.text
    assert store.assignments.read_bytes() == before


def test_redirect_rejected_before_packet_directory_creation(tmp_path, monkeypatch):
    case = tmp_path / "fictional-redirect"
    case.mkdir()
    create_document(case, title="Fictional", content="Fictional.")
    original = storage._location

    def denied(path):
        if path.name == ".guard":
            raise ValueError("workspace_storage_redirect_refused")
        return original(path)

    monkeypatch.setattr(storage, "_location", denied)
    with pytest.raises(filing.ReviewedFilingPacketError, match="redirected or inaccessible"):
        filing.ReviewedFilingPacketStore(case)
    assert not (case / "19_DOCUMENT_WORKSPACE" / filing.ROOT_FOLDER).exists()


def test_status_redirect_error_is_safe_and_scoped(fixture, monkeypatch):
    case, doc, _, _ = fixture
    monkeypatch.setattr(api, "active_case_root", lambda: case)
    original = storage._location

    def denied(path):
        if path.name == ".guard" and path.parent.name == filing.ROOT_FOLDER:
            raise ValueError("Fictional private path must not escape")
        return original(path)

    monkeypatch.setattr(storage, "_location", denied)
    with TestClient(api.app, headers=_headers(case)) as client:
        response = client.get(
            "/api/reviewed-filing-packet/status", params={"document_id": doc["document_id"]}
        )
    assert response.status_code == 409
    assert response.json()["detail"] == "filing_packet_storage_redirect_refused"
    assert "Fictional" not in response.text
