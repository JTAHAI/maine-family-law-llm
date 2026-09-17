"""Read-only migration review: fictional data, no migration/GA claim."""

import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from app.services.local_agent_context_service import LocalAgentAuditStore
from legal.documents import migration_review as mr
from legal.documents import workspace as ws
from maine_family_law_llm import api

KEY = "fictional-migration-review-key-20260909"
HEADERS = {
    "X-User-Role": "reviewer",
    "X-Tenant-Id": "fictional-tenant",
    "X-MFLL-Client-Session": "a" * 48,
}


@pytest.fixture
def legacy(tmp_path, monkeypatch):
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", KEY)
    monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "idempotency"))
    root = tmp_path / "fictional-matter"
    root.mkdir()
    paths = ws.workspace_paths(root)
    folder = paths.documents / ("a" * 32) / "revisions"
    folder.mkdir(parents=True)
    text = "FICTIONAL PRIVATE CANARY: a request is not an agreement."
    revision = {
        "document_id": "a" * 32,
        "revision_id": "b" * 32,
        "content": text,
        "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "status": "committed",
    }
    file = folder / ("b" * 32 + ".json")
    file.write_text(json.dumps(revision), encoding="utf-8")
    paths.index.write_text(
        json.dumps(
            {
                "schema_version": ws.SCHEMA_VERSION,
                "documents": {"a" * 32: {"current_revision_id": "b" * 32}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(api, "active_case_root", lambda: root)
    return root, paths, file, text


def test_review_hashes_real_revisions_without_writes(legacy):
    root, paths, file, text = legacy
    before = {p: p.read_bytes() for p in (file, paths.index)}
    result = mr.review(root)
    assert result["revision_count"] == result["document_count"] == 1
    assert result["revisions"][0]["sha256"] == hashlib.sha256(before[file]).hexdigest()
    assert result["json_bytes"] == sum(map(len, before.values()))
    assert not result["migration_performed"] and result["ready_to_migrate"]
    assert not result["filing_ready"] and result["review_required"]
    assert text not in json.dumps(result) and str(root) not in json.dumps(result)
    assert all(p.read_bytes() == raw for p, raw in before.items())
    assert not (paths.root / ".storage-identity").exists()


@pytest.mark.parametrize("fault", ["hash", "identity", "missing", "unindexed", "shape", "bytes"])
def test_incomplete_or_mutated_inventory_is_not_returned(legacy, monkeypatch, fault):
    root, paths, file, _ = legacy
    if fault == "missing":
        file.unlink()
    elif fault == "unindexed":
        (paths.documents / ("c" * 32)).mkdir()
    elif fault == "bytes":
        monkeypatch.setattr(mr, "MAX_BYTES", 1)
    elif fault == "shape":
        paths.index.write_text("[]")
    else:
        value = json.loads(file.read_bytes())
        value["content_sha256" if fault == "hash" else "document_id"] = "f" * 64
        file.write_text(json.dumps(value))
    with pytest.raises(ws.DocumentWorkspaceError) as failure:
        mr.review(root)
    assert failure.value.code == "workspace_migration_review_unavailable"
    assert str(root) not in str(failure.value)


def test_canonical_route_encrypted_audit_scope_and_role(legacy):
    root, paths, file, text = legacy
    client = TestClient(api.app)
    payload = {"matter_id": api._case_id(root)}
    route = "/api/document-workspace/migration-review"
    for headers in ({}, {**HEADERS, "X-User-Role": "guest"}, {**HEADERS, "X-Tenant-Id": ""}):
        assert client.post(route, json=payload, headers=headers).status_code == 403
    assert client.post(route, json={"matter_id": "other"}, headers=HEADERS).status_code == 409
    result = client.post(route, json=payload, headers=HEADERS)
    assert result.status_code == 200, result.text
    assert result.json()["matter_id"] == payload["matter_id"]
    store = LocalAgentAuditStore(root, encryption_key=KEY)
    raw = store.path.read_bytes()
    assert text.encode() not in raw and b"fictional-tenant" not in raw
    events = store.encryptor.decrypt_json(json.loads(raw))["events"]
    assert events[-1]["action"] == "document_migration_reviewed"
    assert not (paths.root / ".storage-identity").exists()
    assert text in file.read_text()


def test_matter_change_during_scan_does_not_release_old_inventory(legacy, monkeypatch):
    root, _, _, _ = legacy
    original = mr.review

    def switch(path):
        result = original(path)
        monkeypatch.setattr(api, "active_case_root", lambda: root.parent / "other")
        return result

    monkeypatch.setattr("app.api.document_migration.review", switch)
    response = TestClient(api.app).post(
        "/api/document-workspace/migration-review",
        json={"matter_id": api._case_id(root)},
        headers=HEADERS,
    )
    assert response.status_code == 409
    assert "revisions" not in response.text


def test_scan_rechecks_bytes_before_releasing_snapshot(legacy, monkeypatch):
    root, _, file, _ = legacy
    original = ws.read_document_revision

    def change(*args):
        result = original(*args)
        file.write_bytes(file.read_bytes() + b" ")
        return result

    monkeypatch.setattr(ws, "read_document_revision", change)
    with pytest.raises(ws.DocumentWorkspaceError):
        mr.review(root)


def test_audit_failure_withholds_inventory_and_private_exception(legacy, monkeypatch):
    root, _, _, text = legacy

    def fail(*args, **kwargs):
        raise RuntimeError(text)

    monkeypatch.setattr(LocalAgentAuditStore, "record", fail)
    response = TestClient(api.app).post(
        "/api/document-workspace/migration-review",
        json={"matter_id": api._case_id(root)},
        headers=HEADERS,
    )
    assert response.status_code == 409
    assert text not in response.text and "revisions" not in response.text


def test_canonical_review_route_registered_once():
    paths = [
        route.path for route in api.app.routes if "migration-review" in getattr(route, "path", "")
    ]
    assert paths == ["/api/document-workspace/migration-review"]


def test_invalid_request_does_not_echo_private_extra_field(legacy):
    root, _, _, text = legacy
    response = TestClient(api.app).post(
        "/api/document-workspace/migration-review",
        json={"matter_id": api._case_id(root), "unexpected": text},
        headers=HEADERS,
    )
    assert response.status_code == 422
    assert text not in response.text
