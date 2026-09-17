"""Confirmed conversion/recovery using tiny fictional legacy workspaces only."""

import json
import os
import shutil
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from test_document_migration_review import HEADERS
from test_document_migration_review import legacy as legacy_fixture

from legal.documents import migration as m
from legal.documents import migration_review as mr
from legal.documents import workspace as ws
from maine_family_law_llm import api


@pytest.fixture
def legacy(tmp_path, monkeypatch):
    return legacy_fixture.__wrapped__(tmp_path, monkeypatch)


def migrate(root, **kwargs):
    return m.execute(
        root,
        expected_manifest=mr.review(root)["manifest_sha256"],
        confirmed=True,
        guard=lambda: None,
        **kwargs,
    )


def test_confirmed_conversion_preserves_exact_recoverable_originals(legacy):
    root, paths, file, text = legacy
    originals = {p.relative_to(paths.root).as_posix(): p.read_bytes() for p in (file, paths.index)}
    result = migrate(root)
    assert result["migration_performed"] and result["original_bytes_recoverable"]
    assert not result["all_workspace_files_encrypted"] and not result["filing_ready"]
    assert m.original_snapshot(root) == originals
    assert ws.get_document(root, "a" * 32)["content"] == text
    assert not (paths.root / m.PENDING).exists()
    assert not ws.workspace_status(root)["storage"]["legacy_read_only"]
    assert ws.workspace_status(root)["storage"]["legacy_migration_performed"] is True
    for path in paths.root.rglob("*.json"):
        assert text.encode() not in path.read_bytes()
    new = ws.create_document(root, title="Fictional successor", content="Review required.")
    assert ws.get_document(root, new["document_id"])["content"] == "Review required."
    restored = root.parent / "fictional-restored-migration"
    shutil.copytree(root, restored)
    assert ws.workspace_status(restored)["storage"]["legacy_migration_performed"]
    assert m.original_snapshot(restored) == originals


@pytest.mark.parametrize("phase", ["backup", "identity", "revision", "index", "receipt"])
def test_interrupted_transaction_recovers_without_duplicate_stage(legacy, monkeypatch, phase):
    root, paths, file, text = legacy
    original_write, original_replace = m.atomic_write_bytes, m.os.replace
    expected = mr.review(root)["manifest_sha256"]

    def write(path, data, **kwargs):
        if (
            (phase == "backup" and path.name == "old-0.json")
            or (phase == "identity" and path.name == ".storage-identity")
            or (phase == "revision" and path == file)
            or (phase == "index" and path == paths.index)
        ):
            raise OSError("fictional interrupted write")
        return original_write(path, data, **kwargs)

    def replace(source, destination):
        if phase == "receipt" and source.name == m.PENDING:
            raise OSError("fictional interrupted finalize")
        return original_replace(source, destination)

    with monkeypatch.context() as patch:
        patch.setattr(m, "atomic_write_bytes", write)
        patch.setattr(m.os, "replace", replace)
        with pytest.raises(ws.DocumentWorkspaceError):
            m.execute(root, expected_manifest=expected, confirmed=True, guard=lambda: None)
    stages = list((paths.root / m.STAGE).iterdir())
    if phase == "backup":
        m.execute(root, expected_manifest=expected, confirmed=True, guard=lambda: None)
    assert ws.get_document(root, "a" * 32)["content"] == text
    assert (paths.root / m.RECEIPT).exists()
    assert list((paths.root / m.STAGE).iterdir()) == stages
    assert text.encode() in next(
        v for k, v in m.original_snapshot(root).items() if k != "document_index.json"
    )


def test_real_child_exit_and_fresh_interpreter_recovery(legacy):
    root, paths, file, text = legacy
    code = (
        "import os,sys; from pathlib import Path; from legal.documents import migration as m; "
        "from legal.documents import migration_review as r; original=m.atomic_write_bytes\n"
        "def cut(path,data,**kwargs):\n"
        " original(path,data,**kwargs)\n"
        " if path==Path(sys.argv[2]): os._exit(71)\n"
        "m.atomic_write_bytes=cut\n"
        "m.execute(Path(sys.argv[1]),expected_manifest=r.review(Path(sys.argv[1]))['manifest_sha256'],confirmed=True,guard=lambda:None)"
    )
    env = {
        **os.environ,
        "TEMP": str(root.parent),
        "TMP": str(root.parent),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    result = subprocess.run(
        [sys.executable, "-B", "-c", code, str(root), str(file)],
        env=env,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 71, result.stderr
    assert (paths.root / m.PENDING).exists()
    restart = (
        "from pathlib import Path; import sys; "
        "from legal.documents.workspace import get_document; "
        "assert get_document(Path(sys.argv[1]),'a'*32)['content']==sys.argv[2]"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", restart, str(root), text],
        env=env,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert not (paths.root / m.PENDING).exists()


def test_changed_preview_and_missing_confirmation_leave_live_files_untouched(legacy):
    root, paths, file, _ = legacy
    before = file.read_bytes()
    for confirmed, digest in [(False, mr.review(root)["manifest_sha256"]), (True, "f" * 64)]:
        with pytest.raises(ws.DocumentWorkspaceError):
            m.execute(root, expected_manifest=digest, confirmed=confirmed, guard=lambda: None)
    assert file.read_bytes() == before and not (paths.root / m.STAGE).exists()


def test_canonical_confirmation_role_scope_and_reopen(legacy):
    root, paths, file, text = legacy
    client = TestClient(api.app)
    body = {
        "matter_id": api._case_id(root),
        "confirmed": True,
        "expected_manifest": mr.review(root)["manifest_sha256"],
    }
    route = "/api/document-workspace/migration-execute"
    assert client.post(route, json=body, headers=HEADERS).status_code == 403
    admin = {**HEADERS, "X-User-Role": "admin"}
    assert client.post(route, json={**body, "confirmed": False}, headers=admin).status_code == 422
    assert client.post(route, json={**body, "matter_id": "other"}, headers=admin).status_code == 409
    response = client.post(route, json=body, headers=admin)
    assert response.status_code == 200, response.text
    assert response.json()["migration_performed"]
    assert (
        client.get("/api/document-workspace/documents/" + "a" * 32).json()["document"]["content"]
        == text
    )
    assert text.encode() not in file.read_bytes()
    assert (
        json.loads(paths.index.read_bytes())["storage_format"]
        == "document_workspace_encrypted_json_v1"
    )


def test_corrupt_candidate_blocks_resume_but_originals_remain_recoverable(legacy, monkeypatch):
    root, paths, file, _ = legacy
    before = file.read_bytes()
    original = m.atomic_write_bytes

    def fail(path, data, **kwargs):
        if path == file:
            raise OSError("fictional interruption")
        return original(path, data, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(m, "atomic_write_bytes", fail)
        with pytest.raises(ws.DocumentWorkspaceError):
            migrate(root)
    stage = next((paths.root / m.STAGE).iterdir())
    (stage / "new-0.json").write_bytes(b"corrupt fictional candidate")
    with pytest.raises(ws.DocumentWorkspaceError) as failure:
        ws.get_document(root, "a" * 32)
    assert failure.value.code == "workspace_migration_recovery_required"
    assert m.original_snapshot(root)[file.relative_to(paths.root).as_posix()] == before
    assert file.read_bytes() == before


def test_capacity_refusal_creates_no_recovery_copies(legacy, monkeypatch):
    root, paths, file, _ = legacy
    before = file.read_bytes()

    def fail(*args):
        raise OSError("fictional capacity refusal")

    monkeypatch.setattr(m, "ensure_write_capacity", fail)
    with pytest.raises(ws.DocumentWorkspaceError):
        migrate(root)
    assert file.read_bytes() == before
    assert not (paths.root / m.STAGE).exists()
    assert not (paths.root / m.PREPARING).exists()


def test_changed_live_file_after_interruption_never_overwritten(legacy, monkeypatch):
    root, paths, file, _ = legacy
    original = m.atomic_write_bytes

    def fail(path, data, **kwargs):
        if path.name == ".storage-identity":
            raise OSError("fictional interruption")
        return original(path, data, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(m, "atomic_write_bytes", fail)
        with pytest.raises(ws.DocumentWorkspaceError):
            migrate(root)
    changed = file.read_bytes() + b" "
    file.write_bytes(changed)
    with pytest.raises(ws.DocumentWorkspaceError):
        ws.get_document(root, "a" * 32)
    assert file.read_bytes() == changed
