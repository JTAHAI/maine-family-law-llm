"""Fictional storage qualification, not whole-matter privacy certification."""

import json
import os
import shutil
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from legal.documents import storage
from legal.documents import workspace as ws
from maine_family_law_llm import api

SECRET = "fictional-workspace-secret-20260909"
TEXT = "Fictional private draft CANARY-91: a requested exchange is not an agreement."


@pytest.fixture
def case(monkeypatch, tmp_path):
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", SECRET)
    monkeypatch.setenv("MFL_VAULT_KEY_ROOT", str(tmp_path / "vault"))
    monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "idempotency"))
    root = tmp_path / "fictional-matter"
    root.mkdir()
    return root


def create(case):
    return ws.create_document(
        case,
        title="PRIVATE TITLE CANARY",
        content=TEXT,
        note="PRIVATE NOTE CANARY",
        source_refs=[{"source_id": "PRIVATE SOURCE CANARY"}],
    )


def assert_private_json_encrypted(case):
    files = list(ws.workspace_paths(case).documents.glob("*/revisions/*.json"))
    files.append(ws.workspace_paths(case).index)
    for path in files:
        raw = path.read_bytes()
        assert json.loads(raw)["storage_format"] == storage.FORMAT
        for canary in (
            TEXT,
            "PRIVATE TITLE CANARY",
            "PRIVATE NOTE CANARY",
            "PRIVATE SOURCE CANARY",
        ):
            assert canary.encode() not in raw
    return files


def test_create_propose_commit_reject_restore_keeps_all_json_encrypted(case):
    doc = create(case)
    first = (
        ws.workspace_paths(case).documents
        / doc["document_id"]
        / "revisions"
        / (doc["current_revision_id"] + ".json")
    )
    original = first.read_bytes()
    proposal = ws.propose_revision(
        case,
        doc["document_id"],
        content=TEXT + " Revised.",
        base_revision_id=doc["current_revision_id"],
    )
    committed = ws.commit_revision(
        case,
        doc["document_id"],
        revision_id=proposal["revision_id"],
        confirmation_token=proposal["confirmation_token"],
        confirmed=True,
    )
    assert first.read_bytes() == original
    reject = ws.propose_revision(
        case,
        doc["document_id"],
        content="Fictional rejected text",
        base_revision_id=committed["current_revision_id"],
    )
    ws.reject_revision(case, doc["document_id"], revision_id=reject["revision_id"])
    delete = ws.request_soft_delete(case, doc["document_id"])
    ws.commit_soft_delete(
        case, doc["document_id"], confirmation_token=delete["confirmation_token"], confirmed=True
    )
    restored = ws.restore_document(case, doc["document_id"])
    assert restored["content"] == TEXT + " Revised."
    assert restored["filing_ready"] is False
    assert_private_json_encrypted(case)
    assert ws.verify_audit_chain(case)["valid"] is True
    assert ws.workspace_status(case)["storage"]["all_workspace_files_encrypted"] is False


@pytest.mark.parametrize(
    "mutation",
    [
        "ciphertext",
        "plaintext",
        "other_path",
        "other_workspace",
        "wrong_key",
        "identity_missing",
        "identity_changed",
    ],
)
def test_tampering_and_substitution_fail_closed(case, monkeypatch, mutation):
    doc = create(case)
    index = ws.workspace_paths(case).index
    original = index.read_bytes()
    if mutation == "ciphertext":
        data = json.loads(original)
        data["envelope"]["ciphertext"] = "AAAA" + data["envelope"]["ciphertext"][4:]
        index.write_text(json.dumps(data))
    elif mutation == "plaintext":
        index.write_text(json.dumps({"schema_version": ws.SCHEMA_VERSION, "documents": {}}))
    elif mutation == "other_path":
        revision = (
            ws.workspace_paths(case).documents
            / doc["document_id"]
            / "revisions"
            / (doc["current_revision_id"] + ".json")
        )
        index.write_bytes(revision.read_bytes())
    elif mutation == "other_workspace":
        other = case.parent / "fictional-other"
        other.mkdir()
        create(other)
        index.write_bytes(ws.workspace_paths(other).index.read_bytes())
    elif mutation == "wrong_key":
        monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "wrong-fictional-key-20260909")
    elif mutation == "identity_missing":
        (index.parent / storage.IDENTITY).unlink()
    else:
        (index.parent / storage.IDENTITY).write_text("f" * 32)
    before = index.read_bytes()
    with pytest.raises(ws.DocumentWorkspaceError, match="could not be unlocked") as failure:
        ws.list_documents(case)
    assert failure.value.code == "workspace_storage_unavailable"
    assert index.read_bytes() == before
    assert TEXT not in str(failure.value) and str(case) not in str(failure.value)


def test_legacy_documents_read_without_mutation_and_writes_block(case):
    paths = ws.workspace_paths(case)
    docid, revid = "a" * 32, "b" * 32
    folder = paths.documents / docid / "revisions"
    folder.mkdir(parents=True)
    revision = {
        "document_id": docid,
        "revision_id": revid,
        "content": TEXT,
        "content_sha256": ws._sha256_text(TEXT),
        "status": "committed",
    }
    oldrev = folder / (revid + ".json")
    oldrev.write_text(json.dumps(revision))
    paths.index.write_text(
        json.dumps(
            {
                "schema_version": ws.SCHEMA_VERSION,
                "documents": {
                    docid: {
                        "document_id": docid,
                        "current_revision_id": revid,
                        "status": "review_required",
                    }
                },
            }
        )
    )
    before = {p: p.read_bytes() for p in (oldrev, paths.index)}
    assert ws.get_document(case, docid)["content"] == TEXT
    assert ws.workspace_status(case)["storage"]["legacy_read_only"] is True
    with pytest.raises(ws.DocumentWorkspaceError) as failure:
        create(case)
    assert failure.value.code == "workspace_legacy_storage_migration_required"
    assert not (paths.root / storage.IDENTITY).exists()
    assert all(p.read_bytes() == raw for p, raw in before.items())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("algorithm", "local-pbkdf2-sha256-xor-hmac-demo-envelope"),
        ("kdf", "unrecognized-kdf"),
        ("mac", "unexpected"),
        ("nonce", "AAAA"),
        ("salt", "not-base64!"),
        ("ciphertext", None),
        ("unexpected", "extra"),
    ],
)
def test_new_format_rejects_legacy_and_malformed_envelopes(case, monkeypatch, field, value):
    create(case)
    path = ws.workspace_paths(case).index
    payload = json.loads(path.read_bytes())
    payload["envelope"][field] = value
    path.write_text(json.dumps(payload), encoding="utf-8")
    before = path.read_bytes()

    def must_not_decrypt(*_):
        pytest.fail("Malformed envelope reached decryptor")

    monkeypatch.setattr(storage.LocalEnvelopeEncryptor, "decrypt_json", must_not_decrypt)
    with pytest.raises(ws.DocumentWorkspaceError) as failure:
        ws.list_documents(case)
    assert failure.value.code == "workspace_storage_unavailable"
    assert failure.value.status_code == 409
    assert path.read_bytes() == before


def test_complete_workspace_backup_reopens_elsewhere_with_original_key(case):
    doc = create(case)
    backup = case.parent / "fictional-restored"
    # Only tiny fictional fixtures; never copy runtime, weights or real matters.
    shutil.copytree(case, backup)
    assert ws.get_document(backup, doc["document_id"])["content"] == TEXT
    assert ws.verify_audit_chain(backup)["valid"]
    assert_private_json_encrypted(backup)


def test_existing_incremental_backup_preserves_storage_identity_and_reopens(case, monkeypatch):
    from legal.productivity import ProductivitySuiteStore

    doc = create(case)
    backup_root = case.parent / "fictional-encrypted-backup"
    monkeypatch.setenv("MFL_BACKUP_ROOT", str(backup_root))
    suite = ProductivitySuiteStore(case, encryption_key=SECRET)
    suite.save_backup_schedule({"schedule_id": "fictional_drafts", "enabled": False})
    receipt = suite.run_backup({"schedule_id": "fictional_drafts"})
    assert receipt["verified"] is True
    restored = suite.restore_backup(receipt["backup_id"], {"confirmed": True})
    assert restored["live_matter_overwritten"] is False
    recovery = backup_root / "recovery" / receipt["backup_id"]
    assert ws.get_document(recovery, doc["document_id"])["content"] == TEXT
    assert_private_json_encrypted(recovery)


def test_explicit_text_export_remains_readable_and_is_not_claimed_encrypted(case):
    doc = create(case)
    path = ws.export_text_artifact(case, doc["document_id"], provenance_footer="Review required.")
    assert TEXT in path.read_text(encoding="utf-8")
    assert "Review required." in path.read_text(encoding="utf-8")
    assert ws.workspace_status(case)["storage"]["all_workspace_files_encrypted"] is False


def test_restart_in_fresh_interpreter(case):
    doc = create(case)
    code = (
        "from legal.documents.workspace import get_document; import sys; "
        "d=get_document(__import__('pathlib').Path(sys.argv[1]),sys.argv[2]); "
        "assert d['content']==sys.argv[3]; assert d['filing_ready'] is False"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", code, str(case), doc["document_id"], TEXT],
        capture_output=True,
        text=True,
        timeout=30,
        env={
            **os.environ,
            "PYTHONDONTWRITEBYTECODE": "1",
            "TEMP": str(case.parent),
            "TMP": str(case.parent),
        },
    )
    assert result.returncode == 0, result.stderr


def test_interrupted_index_write_retains_previous_ciphertext(case, monkeypatch):
    create(case)
    path = ws.workspace_paths(case).index
    before = path.read_bytes()

    def fail_replace(*_):
        raise OSError("fictional interrupted replacement")

    monkeypatch.setattr(ws.os, "replace", fail_replace)
    with pytest.raises(OSError):
        ws._write_json(path, {"schema_version": ws.SCHEMA_VERSION, "documents": {}})
    assert path.read_bytes() == before
    assert len(ws.list_documents(case)) == 1
    assert not list(path.parent.glob(".*.tmp"))


def test_vault_default_and_key_failure_do_not_use_literal_development_key(case, monkeypatch):
    monkeypatch.delenv("MAINE_MATTER_STORE_KEY")
    monkeypatch.setattr("legal.security.local_encryption.default_matter_passphrase", lambda: SECRET)
    doc = create(case)
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", SECRET)
    assert ws.get_document(case, doc["document_id"])["content"] == TEXT
    assert_private_json_encrypted(case)


def test_canonical_api_storage_status_and_encrypted_roundtrip(case, monkeypatch):
    monkeypatch.setattr(api, "active_case_root", lambda: case)
    client = TestClient(api.app)
    created = client.post(
        "/api/document-workspace/documents",
        json={
            "title": "PRIVATE TITLE CANARY",
            "content": TEXT,
            "expected_matter_id": api._case_id(case),
        },
    )
    assert created.status_code == 200, created.text
    doc = created.json()["document"]
    assert (
        client.get("/api/document-workspace/documents/" + doc["document_id"]).json()["document"][
            "content"
        ]
        == TEXT
    )
    status = client.get("/api/document-workspace/status").json()["storage"]
    assert status["new_json_writes_encrypted"] and not status["legacy_read_only"]
    assert_private_json_encrypted(case)
