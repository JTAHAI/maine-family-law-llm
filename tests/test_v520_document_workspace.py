from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from legal.documents.docx_engine import create_docx_from_text, engine_status
from legal.documents.workspace import (
    DocumentWorkspaceError,
    commit_revision,
    commit_soft_delete,
    create_document,
    find_preserved_source,
    get_document,
    list_documents,
    propose_revision,
    request_soft_delete,
    restore_document,
    save_imported_source,
    structured_diff,
    verify_audit_chain,
    workspace_paths,
    workspace_status,
)


def test_revision_workflow_is_immutable_and_confirmation_gated(tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    case_root.mkdir()
    created = create_document(
        case_root,
        title="Parenting plan draft",
        content="Original line\nSecond line",
        document_type="parenting_plan",
        source_refs=[{"source_id": "record-1", "title": "Order", "page": 2}],
    )
    proposal = propose_revision(
        case_root,
        created["document_id"],
        content="Original line revised\nSecond line\nThird line",
        base_revision_id=created["current_revision_id"],
        note="Add requested exchange detail.",
    )
    assert proposal["diff"]["changes_count"] >= 2
    assert proposal["diff"]["original_sha256"] == created["content_sha256"]

    with pytest.raises(DocumentWorkspaceError) as missing_confirmation:
        commit_revision(
            case_root,
            created["document_id"],
            revision_id=proposal["revision_id"],
            confirmation_token=proposal["confirmation_token"],
            confirmed=False,
        )
    assert missing_confirmation.value.code == "explicit_confirmation_required"

    committed = commit_revision(
        case_root,
        created["document_id"],
        revision_id=proposal["revision_id"],
        confirmation_token=proposal["confirmation_token"],
        confirmed=True,
    )
    assert committed["content"].endswith("Third line")
    assert committed["original_revision_id"] == created["current_revision_id"]
    assert committed["current_revision_id"] == proposal["revision_id"]
    assert committed["original_preserved"] is True
    original = json.loads(
        (
            workspace_paths(case_root).documents
            / created["document_id"]
            / "revisions"
            / f"{created['current_revision_id']}.json"
        ).read_text(encoding="utf-8")
    )
    assert original["content"] == "Original line\nSecond line"
    assert original["status"] == "committed"

    with pytest.raises(DocumentWorkspaceError) as token_reuse:
        commit_revision(
            case_root,
            created["document_id"],
            revision_id=proposal["revision_id"],
            confirmation_token=proposal["confirmation_token"],
            confirmed=True,
        )
    assert token_reuse.value.code == "revision_not_pending"


def test_optimistic_concurrency_rejects_stale_editor(tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    case_root.mkdir()
    created = create_document(case_root, title="Memo", content="v1")
    p1 = propose_revision(
        case_root,
        created["document_id"],
        content="v2",
        base_revision_id=created["current_revision_id"],
    )
    commit_revision(
        case_root,
        created["document_id"],
        revision_id=p1["revision_id"],
        confirmation_token=p1["confirmation_token"],
        confirmed=True,
    )
    with pytest.raises(DocumentWorkspaceError) as stale:
        propose_revision(
            case_root,
            created["document_id"],
            content="stale branch",
            base_revision_id=created["current_revision_id"],
        )
    assert stale.value.code == "document_revision_conflict"


def test_soft_delete_is_two_phase_and_recoverable(tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    case_root.mkdir()
    created = create_document(case_root, title="Draft", content="Text")
    request = request_soft_delete(case_root, created["document_id"])
    with pytest.raises(DocumentWorkspaceError):
        commit_soft_delete(
            case_root,
            created["document_id"],
            confirmation_token=request["confirmation_token"],
            confirmed=False,
        )
    deleted = commit_soft_delete(
        case_root,
        created["document_id"],
        confirmation_token=request["confirmation_token"],
        confirmed=True,
    )
    assert deleted["status"] == "deleted"
    assert list_documents(case_root) == []
    assert len(list_documents(case_root, include_deleted=True)) == 1
    restored = restore_document(case_root, created["document_id"])
    assert restored["status"] == "review_required"
    assert restored["content"] == "Text"


def test_hash_chained_audit_detects_tampering(tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    case_root.mkdir()
    create_document(case_root, title="Draft", content="Text")
    assert verify_audit_chain(case_root)["valid"] is True
    audit = workspace_paths(case_root).audit
    lines = audit.read_text(encoding="utf-8").splitlines()
    event = json.loads(lines[0])
    event["action"] = "tampered"
    lines[0] = json.dumps(event, sort_keys=True)
    audit.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = verify_audit_chain(case_root)
    assert result["valid"] is False
    assert result["failure"] == "event_hash_mismatch"


def test_preserved_source_is_hash_verified_and_not_overwritten(tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    case_root.mkdir()
    document = create_document(case_root, title="Imported record", content="Extracted")
    source = b"PK\x03\x04immutable-docx-placeholder"
    digest = __import__("hashlib").sha256(source).hexdigest()
    info = save_imported_source(
        case_root,
        document_id=document["document_id"],
        data=source,
        suffix=".docx",
        source_hash=digest,
    )
    assert info["source_sha256"] == digest
    path = find_preserved_source(case_root, document["document_id"], extension=".docx")
    assert path.read_bytes() == source
    assert path.name.startswith("original-")


def test_workspace_refuses_symlink_root(tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    case_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (case_root / "19_DOCUMENT_WORKSPACE").symlink_to(outside, target_is_directory=True)
    with pytest.raises(DocumentWorkspaceError) as refused:
        create_document(case_root, title="Draft", content="Text")
    assert refused.value.code == "workspace_symlink_refused"


def test_structured_diff_is_data_not_html() -> None:
    result = structured_diff("A\n<script>alert(1)</script>", "A\nSafe")
    assert result["schema_version"] == "document_diff_v1"
    assert result["changes_count"] == 2
    assert all("html" not in row for row in result["rows"])
    assert any(row["content"] == "<script>alert(1)</script>" for row in result["rows"])


def test_docx_export_creates_review_required_word_file(tmp_path: Path) -> None:
    output_root = tmp_path / "exports"
    output_root.mkdir()
    output = output_root / "draft.docx"
    result = create_docx_from_text(
        title="Motion draft",
        content="# Requested relief\n\n- Item one\n- Item two",
        output_path=output,
        allowed_output_root=output_root,
    )
    assert result["review_required"] is True
    assert result["original_preserved"] is True
    assert zipfile.is_zipfile(output)
    with zipfile.ZipFile(output) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
    assert "REVIEW REQUIRED" in document_xml
    assert "Requested relief" in document_xml


def test_workspace_status_reports_guardrails(tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    case_root.mkdir()
    create_document(case_root, title="Draft", content="Text")
    status = workspace_status(case_root)
    assert status["document_count"] == 1
    assert status["audit"]["valid"] is True
    assert status["originals_preserved"] is True
    assert status["destructive_actions_approval_gated"] is True
    docx = engine_status()
    assert docx["license"] == "MIT"
    assert docx["source_overwrite_allowed"] is False


def test_mutations_fail_closed_after_audit_tampering(tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    case_root.mkdir()
    create_document(case_root, title="Draft", content="Text")
    audit = workspace_paths(case_root).audit
    lines = audit.read_text(encoding="utf-8").splitlines()
    event = json.loads(lines[0])
    event["details"] = {"tampered": True}
    lines[0] = json.dumps(event, sort_keys=True)
    audit.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(DocumentWorkspaceError) as blocked:
        create_document(case_root, title="Second draft", content="Blocked")
    assert blocked.value.code == "audit_chain_broken"


def test_document_modules_do_not_add_network_or_code_execution_surface() -> None:
    import ast

    root = Path(__file__).resolve().parents[1]
    forbidden_import_roots = {"socket", "subprocess", "requests", "httpx", "urllib", "ftplib", "paramiko"}
    forbidden_calls = {"eval", "exec", "compile", "__import__"}
    for relative in ("legal/documents/workspace.py", "legal/documents/docx_engine.py"):
        tree = ast.parse((root / relative).read_text(encoding="utf-8"))
        imported: set[str] = set()
        called: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                called.add(node.func.id)
        assert imported.isdisjoint(forbidden_import_roots), (relative, imported & forbidden_import_roots)
        assert called.isdisjoint(forbidden_calls), (relative, called & forbidden_calls)
