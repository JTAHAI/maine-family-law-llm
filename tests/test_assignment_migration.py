"""Fictional migration: exact originals, no inherited authority, scoped audit."""

import ast
import base64
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_filing_assignment_privacy import _headers
from test_filing_assignment_privacy import fixture as assignment_fixture

from legal.documents import storage
from legal.documents.workspace import create_document
from legal.review import assignment_migration as migration
from legal.review import filing_packet as filing
from maine_family_law_llm import api


@pytest.fixture(name="fixture")
def assignment_setup(tmp_path):
    return assignment_fixture.__wrapped__(tmp_path)


def legacy(fixture):
    _, doc, store, args = fixture
    event = store.assign(doc["document_id"], **args)
    raw = ("\r\n" + json.dumps(event, indent=None, ensure_ascii=False) + "\r\n\r\n").encode()
    store.assignments.write_bytes(raw)
    return raw, dict(
        expected_revision_id=doc["current_revision_id"],
        original_sha256=hashlib.sha256(raw).hexdigest(),
        confirmed=True,
    )


def test_preview_exact_original_idempotence_and_new_assignment(fixture):
    case, doc, store, args = fixture
    raw, request = legacy(fixture)
    before = store.assignments_for(doc["document_id"])
    assert before["migration"]["status"] == "preview"
    assert before["migration"]["original_sha256"] == request["original_sha256"]
    assert before["active"] == [] and store.assignments.read_bytes() == raw
    result = migration.migrate(store, doc["document_id"], **request)
    assert result["active"] == [] and result["storage_authenticated"] and not result["read_only"]
    assert result["history"] == before["history"] and result["review_required"]
    assert result["migration"]["historical_assignments_activated"] is False
    encrypted = store.assignments.read_bytes()
    assert b"Fictional" not in encrypted and b"original_base64" not in encrypted
    payload = storage.decode(store.assignments, encrypted)
    assert base64.b64decode(payload["migration"]["original_base64"]) == raw
    assert migration.migrate(store, doc["document_id"], **request) == result
    assert encrypted == store.assignments.read_bytes()
    new = store.assign(doc["document_id"], **args)
    reopened = filing.ReviewedFilingPacketStore(case).assignments_for(doc["document_id"])
    assert reopened["active"] == [new] and len(reopened["history"]) == 2
    assert reopened["migration"] == result["migration"]
    assert (
        base64.b64decode(
            storage.decode(store.assignments, store.assignments.read_bytes())["migration"][
                "original_base64"
            ]
        )
        == raw
    )


@pytest.mark.parametrize("fault", ["unconfirmed", "hash", "revision", "changed", "atomic_write"])
def test_rejections_preserve_original(fixture, monkeypatch, fault):
    _, doc, store, _ = fixture
    raw, request = legacy(fixture)
    if fault == "unconfirmed":
        request["confirmed"] = False
    elif fault == "hash":
        request["original_sha256"] = "a" * 64
    elif fault == "revision":
        request["expected_revision_id"] = "b" * 32
    elif fault == "changed":
        raw += b"\n"
        store.assignments.write_bytes(raw)
    else:

        def fail(*args, **kwargs):
            raise OSError("Fictional sensitive path")

        monkeypatch.setattr(filing, "atomic_write_bytes", fail)
    with pytest.raises(filing.ReviewedFilingPacketError) as caught:
        migration.migrate(store, doc["document_id"], **request)
    assert "Fictional" not in str(caught.value)
    assert store.assignments.read_bytes() == raw


def test_migration_limit_and_legacy_draft_prerequisite(fixture, monkeypatch):
    _, doc, store, _ = fixture
    raw, request = legacy(fixture)
    monkeypatch.setattr(migration, "MAX_LEGACY_BYTES", 10)
    assert store.assignments_for(doc["document_id"])["migration"]["status"] == "blocked"
    with pytest.raises(filing.ReviewedFilingPacketError):
        migration.migrate(store, doc["document_id"], **request)
    assert store.assignments.read_bytes() == raw
    monkeypatch.setattr(migration, "MAX_LEGACY_BYTES", 1_000_000)
    monkeypatch.setattr(storage, "policy", lambda root: {"legacy_read_only": True})
    assert store.assignments_for(doc["document_id"])["migration"]["blockers"] == [
        "encrypted_draft_workspace_required_first"
    ]


def test_all_document_history_migrates_without_activating_any_prior_label(fixture):
    case, doc, store, args = fixture
    first = store.assign(doc["document_id"], **args)
    other = create_document(case, title="Other fictional draft", content="Other fictional.")
    second = store.assign(
        other["document_id"], **{**args, "expected_revision_id": other["current_revision_id"]}
    )
    raw = (json.dumps(first) + "\n" + json.dumps(second) + "\n").encode()
    store.assignments.write_bytes(raw)
    plan = store.assignments_for(doc["document_id"])["migration"]
    assert plan["event_count"] == 2 and plan["document_count"] == 2
    migration.migrate(
        store,
        doc["document_id"],
        expected_revision_id=doc["current_revision_id"],
        original_sha256=plan["original_sha256"],
        confirmed=True,
    )
    assert store.assignments_for(doc["document_id"])["active"] == []
    assert store.assignments_for(other["document_id"])["active"] == []


def test_external_edit_during_staging_is_not_overwritten(fixture, monkeypatch):
    _, doc, store, _ = fixture
    raw, request = legacy(fixture)
    encode = storage.encode

    def changed(path, payload):
        encrypted = encode(path, payload)
        store.assignments.write_bytes(raw + b"\n")
        return encrypted

    monkeypatch.setattr(storage, "encode", changed)
    with pytest.raises(filing.ReviewedFilingPacketError):
        migration.migrate(store, doc["document_id"], **request)
    assert store.assignments.read_bytes() == raw + b"\n"


def test_completion_audit_failure_can_be_retried_without_second_write(fixture, monkeypatch):
    from app.services.local_agent_context_service import LocalAgentAuditStore

    case, doc, store, _ = fixture
    _, request = legacy(fixture)
    monkeypatch.setattr(api, "active_case_root", lambda: case)
    original = LocalAgentAuditStore.record

    def record(self, action, **kwargs):
        if action == "filing_assignment_migrate_completed":
            raise OSError("Fictional audit failure")
        return original(self, action, **kwargs)

    monkeypatch.setattr(LocalAgentAuditStore, "record", record)
    client = TestClient(api.app, headers=_headers(case))
    url = f"/api/reviewed-filing-packet/documents/{doc['document_id']}/assignments/migrate"
    assert client.post(url, json=request).status_code == 409
    encrypted = store.assignments.read_bytes()
    assert store.assignments_for(doc["document_id"])["migration"]["status"] == "migrated"
    monkeypatch.setattr(LocalAgentAuditStore, "record", original)
    assert client.post(url, json=request).status_code == 200
    assert store.assignments.read_bytes() == encrypted


def test_existing_store_collector_includes_migration_without_building_runtime():
    root = Path(__file__).resolve().parents[1]
    text = (root / "store/pyinstaller/maine_family_law_llm.spec").read_text()
    tree = ast.parse(text)
    function = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "collect_runtime_submodules"
    )
    namespace = {"Path": Path, "importlib": importlib}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "collector", "exec"), namespace)
    assert "legal.review.assignment_migration" in namespace["collect_runtime_submodules"]("legal")


def test_unverified_privacy_preview_is_safe_and_preserves_original(fixture, monkeypatch):
    case, doc, store, _ = fixture
    raw, request = legacy(fixture)
    monkeypatch.setattr(api, "active_case_root", lambda: case)

    def invalid(_root):
        raise ValueError("Fictional private raw path")

    monkeypatch.setattr(storage, "policy", invalid)
    client = TestClient(api.app, headers=_headers(case))
    url = f"/api/reviewed-filing-packet/documents/{doc['document_id']}/assignments"
    for response in (client.get(url), client.post(url + "/migrate", json=request)):
        assert response.status_code == 409
        assert response.json()["detail"] == "assignment_migration_workspace_unverified"
        assert "Fictional" not in response.text
    assert store.assignments.read_bytes() == raw


def test_deleted_document_cannot_confirm_migration(fixture):
    from legal.documents.workspace import commit_soft_delete, request_soft_delete

    case, doc, store, _ = fixture
    raw, request = legacy(fixture)
    intent = request_soft_delete(case, doc["document_id"])
    commit_soft_delete(
        case, doc["document_id"], confirmation_token=intent["confirmation_token"], confirmed=True
    )
    assert store.assignments_for(doc["document_id"])["migration"]["status"] == "blocked"
    with pytest.raises(filing.ReviewedFilingPacketError) as caught:
        migration.migrate(store, doc["document_id"], **request)
    assert caught.value.code == "assignment_migration_document_deleted"
    assert store.assignments.read_bytes() == raw


@pytest.mark.parametrize("fault", ["count", "original", "events", "schema"])
def test_migrated_original_or_history_cannot_be_rebound(fixture, fault):
    _, doc, store, _ = fixture
    _, request = legacy(fixture)
    migration.migrate(store, doc["document_id"], **request)
    payload = storage.decode(store.assignments, store.assignments.read_bytes())
    if fault == "count":
        payload["migration"]["receipt"]["event_count"] = 0
    elif fault == "original":
        payload["migration"]["original_base64"] = base64.b64encode(b"{}").decode()
    elif fault == "events":
        payload["events"][0]["reviewer_label"] = "Changed fictional label"
    else:
        payload["migration"]["receipt"]["unexpected"] = "field"
    store.assignments.write_bytes(storage.encode(store.assignments, payload))
    with pytest.raises(filing.ReviewedFilingPacketError, match="unlocked or verified"):
        store.assignments_for(doc["document_id"])


@pytest.mark.parametrize(
    "header,code",
    [
        ("X-User-Role", 403),
        ("X-Tenant-Id", 403),
        ("X-MFLL-Client-Session", 403),
        ("X-MFLL-Matter-Id", 409),
    ],
)
def test_migration_api_scope_and_no_private_error(fixture, monkeypatch, header, code):
    case, doc, store, _ = fixture
    raw, request = legacy(fixture)
    monkeypatch.setattr(api, "active_case_root", lambda: case)
    headers = _headers(case)
    headers[header] = ""
    result = TestClient(api.app, headers=headers).post(
        f"/api/reviewed-filing-packet/documents/{doc['document_id']}/assignments/migrate",
        json=request,
    )
    assert result.status_code == code and "Fictional" not in result.text
    assert store.assignments.read_bytes() == raw


def test_api_preview_migrate_audit_strict_confirmation_and_audit_failure(fixture, monkeypatch):
    from app.services.local_agent_context_service import LocalAgentAuditStore

    case, doc, store, _ = fixture
    raw, request = legacy(fixture)
    monkeypatch.setattr(api, "active_case_root", lambda: case)
    client = TestClient(api.app, headers=_headers(case))
    url = f"/api/reviewed-filing-packet/documents/{doc['document_id']}/assignments"
    assert client.get(url).json()["migration"]["status"] == "preview"
    assert client.post(url + "/migrate", json={**request, "confirmed": "true"}).status_code == 422
    assert store.assignments.read_bytes() == raw
    record = LocalAgentAuditStore.record

    def fail(*args, **kwargs):
        raise OSError("Fictional secret")

    monkeypatch.setattr(LocalAgentAuditStore, "record", fail)
    response = client.post(url + "/migrate", json=request)
    assert response.status_code == 409 and "Fictional" not in response.text
    assert store.assignments.read_bytes() == raw
    monkeypatch.setattr(LocalAgentAuditStore, "record", record)
    response = client.post(url + "/migrate", json=request)
    assert response.status_code == 200 and response.json()["matter_id"] == api._case_id(case)
    assert response.json()["review_required"] and response.json()["active"] == []
    assert "original_base64" not in response.text and str(case) not in response.text
    # Match the app's vault-backed default as well as explicit test keys.
    audit = api._local_agent_audit_store(case)
    events = audit.encryptor.decrypt_json(json.loads(audit.path.read_bytes()))["events"]
    assert any(e["action"] == "filing_assignment_migrate_completed" for e in events)
    assert b"Fictional" not in audit.path.read_bytes()
    pairs = [
        (r.path, method)
        for r in api.app.routes
        for method in getattr(r, "methods", [])
        if "assignments/migrate" in r.path
    ]
    assert pairs == [(url.replace(doc["document_id"], "{document_id}") + "/migrate", "POST")]


@pytest.mark.parametrize("phase", ["before_commit", "after_commit"])
def test_real_child_exit_preserves_old_or_complete_encrypted_state(fixture, tmp_path, phase):
    case, doc, store, _ = fixture
    raw, request = legacy(fixture)
    program = """import json,os,sys
from pathlib import Path
from legal.review import filing_packet as f, assignment_migration as m
original=f.atomic_write_bytes
def interrupted(*args,**kwargs):
    if sys.argv[4] == "after_commit": original(*args,**kwargs)
    os._exit(73)
f.atomic_write_bytes=interrupted
m.migrate(f.ReviewedFilingPacketStore(Path(sys.argv[1])),sys.argv[2],**json.loads(sys.argv[3]))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            program,
            str(case),
            doc["document_id"],
            json.dumps(request),
            phase,
        ],
        env={**os.environ, "TEMP": str(tmp_path), "TMP": str(tmp_path)},
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 73, result.stderr.decode(errors="replace")
    if phase == "before_commit":
        assert store.assignments.read_bytes() == raw
    else:
        assert store.assignments.read_bytes() != raw
    result = migration.migrate(store, doc["document_id"], **request)
    assert result["migration"]["status"] == "migrated" and result["active"] == []
    assert (
        base64.b64decode(
            storage.decode(store.assignments, store.assignments.read_bytes())["migration"][
                "original_base64"
            ]
        )
        == raw
    )
