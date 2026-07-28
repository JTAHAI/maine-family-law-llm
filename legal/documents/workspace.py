"""Local, revision-safe document workspace for drafting and document handling.

The workspace is intentionally data-only. It never executes document content,
never overwrites an imported source, and never treats a model-generated draft as
approved or filing-ready. All mutations are append-only revisions plus a small
atomic index update protected by optimistic concurrency and one-use approval
capabilities.

Architecture patterns were adapted from the MIT-licensed Paparusi/legal-ai-agent
(document history, annotations, structured actions) and independently hardened
for this local-first project.
"""

from __future__ import annotations

import difflib
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

WORKSPACE_FOLDER = "19_DOCUMENT_WORKSPACE"
INDEX_FILENAME = "document_index.json"
AUDIT_FILENAME = "audit_log.jsonl"
SCHEMA_VERSION = "document_workspace_v1"
MAX_DOCUMENTS = 5_000
MAX_CONTENT_CHARS = 1_500_000
MAX_TITLE_CHARS = 240
MAX_NOTE_CHARS = 2_000
MAX_TAGS = 32
MAX_TAG_CHARS = 64
MAX_SOURCE_REFS = 64
MAX_DIFF_LINES = 4_000
MAX_AUDIT_BYTES = 64 * 1024 * 1024
ALLOWED_DOCUMENT_TYPES = {
    "draft",
    "memo",
    "letter",
    "motion",
    "affidavit",
    "parenting_plan",
    "court_form_notes",
    "attorney_review_packet",
    "other",
}
ALLOWED_STATUSES = {"review_required", "approved", "archived", "deleted"}
_ID_RE = re.compile(r"^[a-f0-9]{32}$")
_TOKEN_RE = re.compile(r"^[a-f0-9]{64}$")
_LOCK = threading.RLock()


class DocumentWorkspaceError(RuntimeError):
    """Typed workspace error safe to translate into a local API response."""

    def __init__(self, code: str, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class WorkspacePaths:
    case_root: Path
    root: Path
    documents: Path
    sources: Path
    exports: Path
    index: Path
    audit: Path


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _validate_id(value: str, label: str) -> str:
    candidate = str(value or "").strip().lower()
    if not _ID_RE.fullmatch(candidate):
        raise DocumentWorkspaceError(f"invalid_{label}", f"Invalid {label}.", status_code=404)
    return candidate


def _normalize_title(value: str) -> str:
    title = " ".join(str(value or "").replace("\x00", " ").split()).strip()
    if not title:
        raise DocumentWorkspaceError("title_required", "A document title is required.")
    if len(title) > MAX_TITLE_CHARS:
        raise DocumentWorkspaceError("title_too_long", f"Title exceeds {MAX_TITLE_CHARS} characters.")
    return title


def _normalize_content(value: str) -> str:
    content = str(value or "").replace("\x00", "")
    if len(content) > MAX_CONTENT_CHARS:
        raise DocumentWorkspaceError(
            "document_too_large",
            f"Document text exceeds {MAX_CONTENT_CHARS:,} characters.",
            status_code=413,
        )
    return content


def _normalize_note(value: str) -> str:
    note = str(value or "").replace("\x00", "").strip()
    if len(note) > MAX_NOTE_CHARS:
        raise DocumentWorkspaceError("note_too_long", f"Note exceeds {MAX_NOTE_CHARS} characters.")
    return note


def _normalize_type(value: str) -> str:
    document_type = str(value or "draft").strip().lower().replace("-", "_")
    if document_type not in ALLOWED_DOCUMENT_TYPES:
        raise DocumentWorkspaceError("invalid_document_type", "Unsupported document type.")
    return document_type


def _normalize_tags(values: Iterable[str] | None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in list(values or [])[:MAX_TAGS]:
        tag = " ".join(str(raw or "").replace("\x00", " ").split()).strip()
        if not tag:
            continue
        tag = tag[:MAX_TAG_CHARS]
        key = tag.casefold()
        if key not in seen:
            seen.add(key)
            result.append(tag)
    return result


def _normalize_source_refs(values: Iterable[dict[str, Any]] | None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in list(values or [])[:MAX_SOURCE_REFS]:
        if not isinstance(raw, dict):
            continue
        safe: dict[str, Any] = {}
        for key in ("source_id", "title", "citation", "source_class", "hash", "page", "safe_locator"):
            value = raw.get(key)
            if value is None:
                continue
            if key == "page":
                try:
                    page = int(value)
                except (TypeError, ValueError):
                    continue
                if 0 <= page <= 100_000:
                    safe[key] = page
            else:
                safe[key] = str(value)[:500]
        if safe:
            result.append(safe)
    return result


def _safe_child(root: Path, *parts: str) -> Path:
    candidate = root.joinpath(*parts)
    if candidate.exists() and candidate.is_symlink():
        raise DocumentWorkspaceError("workspace_symlink_refused", "A workspace symlink was refused.", status_code=409)
    resolved_parent = candidate.parent.resolve(strict=True)
    resolved_root = root.resolve(strict=True)
    if resolved_parent != resolved_root and resolved_root not in resolved_parent.parents:
        raise DocumentWorkspaceError("workspace_path_escape", "A workspace path escaped its root.", status_code=409)
    return candidate


def workspace_paths(case_root: Path, *, create: bool = True) -> WorkspacePaths:
    try:
        resolved_case = Path(case_root).expanduser().resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise DocumentWorkspaceError("case_root_missing", "The active case workspace is unavailable.", status_code=409) from exc
    if not resolved_case.is_dir():
        raise DocumentWorkspaceError("case_root_invalid", "The active case workspace is invalid.", status_code=409)

    root = resolved_case / WORKSPACE_FOLDER
    if root.exists() and root.is_symlink():
        raise DocumentWorkspaceError("workspace_symlink_refused", "A workspace symlink was refused.", status_code=409)
    if create:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not root.exists():
        raise DocumentWorkspaceError("workspace_missing", "The document workspace has not been created.", status_code=404)
    resolved_root = root.resolve(strict=True)
    if resolved_case not in resolved_root.parents:
        raise DocumentWorkspaceError("workspace_path_escape", "The workspace escaped the active case.", status_code=409)

    documents = resolved_root / "documents"
    sources = resolved_root / "sources"
    exports = resolved_root / "exports"
    if create:
        for folder in (documents, sources, exports):
            if folder.exists() and folder.is_symlink():
                raise DocumentWorkspaceError("workspace_symlink_refused", "A workspace symlink was refused.", status_code=409)
            folder.mkdir(mode=0o700, exist_ok=True)
    return WorkspacePaths(
        case_root=resolved_case,
        root=resolved_root,
        documents=documents,
        sources=sources,
        exports=exports,
        index=resolved_root / INDEX_FILENAME,
        audit=resolved_root / AUDIT_FILENAME,
    )


def _atomic_write(path: Path, data: bytes, *, mode: int = 0o600) -> None:
    if path.exists() and path.is_symlink():
        raise DocumentWorkspaceError("workspace_symlink_refused", "A workspace symlink was refused.", status_code=409)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(temporary, mode)
        except OSError:
            pass
        os.replace(temporary, path)
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
        except OSError:
            directory_fd = -1
        if directory_fd >= 0:
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass


def _read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    if path.is_symlink():
        raise DocumentWorkspaceError("workspace_symlink_refused", "A workspace symlink was refused.", status_code=409)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise DocumentWorkspaceError("workspace_read_failed", "The local workspace could not be read.", status_code=500) from exc
    if len(raw) > MAX_CONTENT_CHARS * 4:
        raise DocumentWorkspaceError("workspace_index_too_large", "The workspace index is unexpectedly large.", status_code=409)
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DocumentWorkspaceError("workspace_json_invalid", "The local workspace metadata is invalid.", status_code=409) from exc


def _empty_index() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "updated_at": _utc_now(), "documents": {}}


def _load_index(paths: WorkspacePaths) -> dict[str, Any]:
    payload = _read_json(paths.index, _empty_index())
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise DocumentWorkspaceError("workspace_schema_invalid", "The document workspace schema is invalid.", status_code=409)
    if not isinstance(payload.get("documents"), dict):
        raise DocumentWorkspaceError("workspace_index_invalid", "The document workspace index is invalid.", status_code=409)
    return payload


def _write_index(paths: WorkspacePaths, payload: dict[str, Any]) -> None:
    payload = dict(payload)
    payload["schema_version"] = SCHEMA_VERSION
    payload["updated_at"] = _utc_now()
    _atomic_write(paths.index, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"))


def _document_folder(paths: WorkspacePaths, document_id: str) -> Path:
    document_id = _validate_id(document_id, "document_id")
    folder = _safe_child(paths.documents, document_id)
    if folder.exists() and folder.is_symlink():
        raise DocumentWorkspaceError("workspace_symlink_refused", "A document folder symlink was refused.", status_code=409)
    folder.mkdir(mode=0o700, exist_ok=True)
    revisions = folder / "revisions"
    revisions.mkdir(mode=0o700, exist_ok=True)
    return folder


def _revision_path(paths: WorkspacePaths, document_id: str, revision_id: str) -> Path:
    revision_id = _validate_id(revision_id, "revision_id")
    return _document_folder(paths, document_id) / "revisions" / f"{revision_id}.json"


def _read_revision(paths: WorkspacePaths, document_id: str, revision_id: str) -> dict[str, Any]:
    path = _revision_path(paths, document_id, revision_id)
    payload = _read_json(path, None)
    if not isinstance(payload, dict):
        raise DocumentWorkspaceError("revision_not_found", "The requested revision was not found.", status_code=404)
    content = str(payload.get("content") or "")
    if _sha256_text(content) != str(payload.get("content_sha256") or ""):
        raise DocumentWorkspaceError("revision_hash_mismatch", "The revision failed its integrity check.", status_code=409)
    return payload


def _write_revision(paths: WorkspacePaths, payload: dict[str, Any]) -> None:
    path = _revision_path(paths, str(payload["document_id"]), str(payload["revision_id"]))
    if path.exists():
        raise DocumentWorkspaceError("revision_exists", "The revision already exists.", status_code=409)
    _atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"))


def _last_audit_hash(path: Path) -> str:
    """Return the last hash only after validating the complete audit chain.

    Mutations fail closed when any prior event is malformed or tampered with;
    a new valid-looking event can never be appended after a broken chain.
    """
    if not path.exists():
        return "0" * 64
    if path.is_symlink():
        raise DocumentWorkspaceError("workspace_symlink_refused", "An audit-log symlink was refused.", status_code=409)
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise DocumentWorkspaceError("audit_read_failed", "The audit log could not be read.", status_code=500) from exc
    if size > MAX_AUDIT_BYTES:
        raise DocumentWorkspaceError("audit_log_too_large", "The audit log reached its safety limit.", status_code=409)

    previous = "0" * 64
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise DocumentWorkspaceError(
                        "audit_log_invalid",
                        f"The audit log is invalid at event {line_number}.",
                        status_code=409,
                    ) from exc
                if not isinstance(event, dict):
                    raise DocumentWorkspaceError("audit_log_invalid", "The audit log is invalid.", status_code=409)
                claimed = str(event.pop("event_hash", ""))
                if not re.fullmatch(r"[a-f0-9]{64}", claimed):
                    raise DocumentWorkspaceError("audit_log_invalid", "The audit log is invalid.", status_code=409)
                if not hmac.compare_digest(str(event.get("previous_hash") or ""), previous):
                    raise DocumentWorkspaceError("audit_chain_broken", "The document audit chain is broken.", status_code=409)
                actual = _sha256_bytes(_canonical_json(event))
                if not hmac.compare_digest(claimed, actual):
                    raise DocumentWorkspaceError("audit_chain_broken", "The document audit chain is broken.", status_code=409)
                previous = claimed
    except UnicodeDecodeError as exc:
        raise DocumentWorkspaceError("audit_log_invalid", "The audit log is invalid.", status_code=409) from exc
    return previous


def _append_audit(paths: WorkspacePaths, action: str, *, document_id: str = "", revision_id: str = "", details: dict[str, Any] | None = None) -> dict[str, Any]:
    previous_hash = _last_audit_hash(paths.audit)
    event = {
        "schema_version": "document_audit_event_v1",
        "event_id": uuid.uuid4().hex,
        "created_at": _utc_now(),
        "actor": "local_user",
        "action": str(action)[:80],
        "document_id": str(document_id)[:64],
        "revision_id": str(revision_id)[:64],
        "details": dict(details or {}),
        "previous_hash": previous_hash,
    }
    event["event_hash"] = _sha256_bytes(_canonical_json(event))
    line = json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n"
    paths.audit.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
    fd = os.open(paths.audit, flags, 0o600)
    try:
        os.write(fd, line.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    return event


def verify_audit_chain(case_root: Path) -> dict[str, Any]:
    paths = workspace_paths(case_root, create=False)
    if not paths.audit.exists():
        return {"valid": True, "event_count": 0, "last_event_hash": "0" * 64}
    if paths.audit.is_symlink():
        return {"valid": False, "event_count": 0, "failure": "audit_symlink"}
    previous = "0" * 64
    count = 0
    with paths.audit.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                return {"valid": False, "event_count": count, "failure": "invalid_json", "line": line_number}
            claimed = str(event.pop("event_hash", ""))
            if str(event.get("previous_hash")) != previous:
                return {"valid": False, "event_count": count, "failure": "previous_hash_mismatch", "line": line_number}
            actual = _sha256_bytes(_canonical_json(event))
            if not hmac.compare_digest(claimed, actual):
                return {"valid": False, "event_count": count, "failure": "event_hash_mismatch", "line": line_number}
            previous = claimed
            count += 1
    return {"valid": True, "event_count": count, "last_event_hash": previous}


def structured_diff(original: str, revised: str) -> dict[str, Any]:
    original = _normalize_content(original)
    revised = _normalize_content(revised)
    before = original.splitlines()
    after = revised.splitlines()
    matcher = difflib.SequenceMatcher(a=before, b=after, autojunk=False)
    rows: list[dict[str, Any]] = []
    additions = deletions = replacements = 0
    truncated = False
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            values = after[j1:j2]
            row_type = "unchanged"
        elif tag == "insert":
            values = after[j1:j2]
            row_type = "add"
            additions += len(values)
        elif tag == "delete":
            values = before[i1:i2]
            row_type = "delete"
            deletions += len(values)
        else:
            values = before[i1:i2]
            replacement_values = after[j1:j2]
            replacements += max(len(values), len(replacement_values))
            for value in values:
                rows.append({"type": "delete", "content": value, "old_line": i1 + 1, "new_line": None})
                i1 += 1
                deletions += 1
                if len(rows) >= MAX_DIFF_LINES:
                    truncated = True
                    break
            if truncated:
                break
            for value in replacement_values:
                rows.append({"type": "add", "content": value, "old_line": None, "new_line": j1 + 1})
                j1 += 1
                additions += 1
                if len(rows) >= MAX_DIFF_LINES:
                    truncated = True
                    break
            if truncated:
                break
            continue
        for offset, value in enumerate(values):
            if len(rows) >= MAX_DIFF_LINES:
                truncated = True
                break
            rows.append(
                {
                    "type": row_type,
                    "content": value,
                    "old_line": (i1 + offset + 1) if tag in {"equal", "delete"} else None,
                    "new_line": (j1 + offset + 1) if tag in {"equal", "insert"} else None,
                }
            )
        if truncated:
            break
    changed = additions + deletions
    return {
        "schema_version": "document_diff_v1",
        "rows": rows,
        "additions": additions,
        "deletions": deletions,
        "replacements": replacements,
        "changes_count": changed,
        "truncated": truncated,
        "original_sha256": _sha256_text(original),
        "revised_sha256": _sha256_text(revised),
        "summary": f"+{additions} added · -{deletions} removed" if changed else "No textual changes",
    }


def create_document(
    case_root: Path,
    *,
    title: str,
    content: str,
    document_type: str = "draft",
    note: str = "",
    tags: Iterable[str] | None = None,
    source_refs: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    with _LOCK:
        paths = workspace_paths(case_root)
        index = _load_index(paths)
        documents = index["documents"]
        if len(documents) >= MAX_DOCUMENTS:
            raise DocumentWorkspaceError("document_limit_reached", "The workspace document limit was reached.", status_code=409)
        document_id = uuid.uuid4().hex
        revision_id = uuid.uuid4().hex
        now = _utc_now()
        content = _normalize_content(content)
        revision = {
            "schema_version": "document_revision_v1",
            "document_id": document_id,
            "revision_id": revision_id,
            "parent_revision_id": "",
            "status": "committed",
            "operation": "create",
            "created_at": now,
            "actor": "local_user",
            "note": _normalize_note(note),
            "content": content,
            "content_sha256": _sha256_text(content),
            "source_refs": _normalize_source_refs(source_refs),
            "review_required": True,
            "filing_ready": False,
        }
        _write_revision(paths, revision)
        document = {
            "document_id": document_id,
            "title": _normalize_title(title),
            "document_type": _normalize_type(document_type),
            "status": "review_required",
            "created_at": now,
            "updated_at": now,
            "current_revision_id": revision_id,
            "original_revision_id": revision_id,
            "revision_count": 1,
            "pending_revision_ids": [],
            "tags": _normalize_tags(tags),
            "source_refs": revision["source_refs"],
            "review_required": True,
            "filing_ready": False,
            "original_preserved": True,
        }
        documents[document_id] = document
        _write_index(paths, index)
        _append_audit(paths, "document_created", document_id=document_id, revision_id=revision_id, details={"content_sha256": revision["content_sha256"]})
        return {**document, "content": content, "content_sha256": revision["content_sha256"]}


def list_documents(case_root: Path, *, include_deleted: bool = False, limit: int = 200) -> list[dict[str, Any]]:
    with _LOCK:
        paths = workspace_paths(case_root)
        index = _load_index(paths)
        limit = max(1, min(int(limit), 1_000))
        rows = [dict(item) for item in index["documents"].values()]
        if not include_deleted:
            rows = [row for row in rows if row.get("status") != "deleted"]
        rows.sort(key=lambda row: str(row.get("updated_at") or ""), reverse=True)
        return rows[:limit]


def get_document(case_root: Path, document_id: str, *, include_content: bool = True) -> dict[str, Any]:
    with _LOCK:
        paths = workspace_paths(case_root)
        index = _load_index(paths)
        document_id = _validate_id(document_id, "document_id")
        document = index["documents"].get(document_id)
        if not isinstance(document, dict):
            raise DocumentWorkspaceError("document_not_found", "The document was not found.", status_code=404)
        result = dict(document)
        if include_content:
            revision = _read_revision(paths, document_id, str(document["current_revision_id"]))
            result["content"] = revision["content"]
            result["content_sha256"] = revision["content_sha256"]
        revisions_dir = _document_folder(paths, document_id) / "revisions"
        history: list[dict[str, Any]] = []
        for path in sorted(revisions_dir.glob("*.json")):
            payload = _read_json(path, {})
            if not isinstance(payload, dict):
                continue
            history.append(
                {
                    key: payload.get(key)
                    for key in (
                        "revision_id",
                        "parent_revision_id",
                        "status",
                        "operation",
                        "created_at",
                        "note",
                        "content_sha256",
                        "review_required",
                    )
                }
            )
        history.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
        result["revisions"] = history[:500]
        return result


def propose_revision(
    case_root: Path,
    document_id: str,
    *,
    content: str,
    base_revision_id: str,
    note: str = "",
) -> dict[str, Any]:
    with _LOCK:
        paths = workspace_paths(case_root)
        index = _load_index(paths)
        document_id = _validate_id(document_id, "document_id")
        document = index["documents"].get(document_id)
        if not isinstance(document, dict) or document.get("status") == "deleted":
            raise DocumentWorkspaceError("document_not_found", "The document was not found.", status_code=404)
        base_revision_id = _validate_id(base_revision_id, "revision_id")
        if not hmac.compare_digest(base_revision_id, str(document.get("current_revision_id") or "")):
            raise DocumentWorkspaceError(
                "document_revision_conflict",
                "The document changed after it was opened. Reload before proposing edits.",
                status_code=409,
            )
        base = _read_revision(paths, document_id, base_revision_id)
        content = _normalize_content(content)
        if hmac.compare_digest(str(base["content_sha256"]), _sha256_text(content)):
            raise DocumentWorkspaceError("no_document_changes", "The proposed text is unchanged.")
        revision_id = uuid.uuid4().hex
        confirmation_token = secrets.token_hex(32)
        now = _utc_now()
        revision = {
            "schema_version": "document_revision_v1",
            "document_id": document_id,
            "revision_id": revision_id,
            "parent_revision_id": base_revision_id,
            "status": "proposed",
            "operation": "edit",
            "created_at": now,
            "actor": "local_user",
            "note": _normalize_note(note),
            "content": content,
            "content_sha256": _sha256_text(content),
            "source_refs": list(document.get("source_refs") or []),
            "review_required": True,
            "filing_ready": False,
            "confirmation_token_sha256": _sha256_text(confirmation_token),
        }
        _write_revision(paths, revision)
        pending = [str(value) for value in document.get("pending_revision_ids") or [] if _ID_RE.fullmatch(str(value))]
        pending.append(revision_id)
        document["pending_revision_ids"] = list(dict.fromkeys(pending))[-50:]
        document["updated_at"] = now
        _write_index(paths, index)
        diff = structured_diff(str(base["content"]), content)
        _append_audit(paths, "revision_proposed", document_id=document_id, revision_id=revision_id, details={"base_revision_id": base_revision_id, "content_sha256": revision["content_sha256"], "changes_count": diff["changes_count"]})
        return {
            "document_id": document_id,
            "revision_id": revision_id,
            "base_revision_id": base_revision_id,
            "confirmation_token": confirmation_token,
            "expires_when_workspace_changes": True,
            "diff": diff,
            "review_required": True,
            "filing_ready": False,
        }


def commit_revision(
    case_root: Path,
    document_id: str,
    *,
    revision_id: str,
    confirmation_token: str,
    confirmed: bool,
) -> dict[str, Any]:
    with _LOCK:
        if confirmed is not True:
            raise DocumentWorkspaceError("explicit_confirmation_required", "Explicit confirmation is required.", status_code=409)
        token = str(confirmation_token or "").strip().lower()
        if not _TOKEN_RE.fullmatch(token):
            raise DocumentWorkspaceError("invalid_confirmation_token", "The confirmation token is invalid.", status_code=409)
        paths = workspace_paths(case_root)
        index = _load_index(paths)
        document_id = _validate_id(document_id, "document_id")
        revision_id = _validate_id(revision_id, "revision_id")
        document = index["documents"].get(document_id)
        if not isinstance(document, dict) or document.get("status") == "deleted":
            raise DocumentWorkspaceError("document_not_found", "The document was not found.", status_code=404)
        revision = _read_revision(paths, document_id, revision_id)
        if revision.get("status") != "proposed":
            raise DocumentWorkspaceError("revision_not_pending", "The revision is not pending approval.", status_code=409)
        if str(revision.get("parent_revision_id") or "") != str(document.get("current_revision_id") or ""):
            raise DocumentWorkspaceError("document_revision_conflict", "The document changed after this proposal was created.", status_code=409)
        expected = str(revision.get("confirmation_token_sha256") or "")
        if not hmac.compare_digest(expected, _sha256_text(token)):
            raise DocumentWorkspaceError("invalid_confirmation_token", "The confirmation token is invalid.", status_code=409)
        revision["status"] = "committed"
        revision["committed_at"] = _utc_now()
        revision.pop("confirmation_token_sha256", None)
        _atomic_write(_revision_path(paths, document_id, revision_id), json.dumps(revision, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"))
        document["current_revision_id"] = revision_id
        document["updated_at"] = revision["committed_at"]
        document["revision_count"] = int(document.get("revision_count") or 0) + 1
        document["pending_revision_ids"] = [value for value in document.get("pending_revision_ids") or [] if value != revision_id]
        document["status"] = "review_required"
        document["review_required"] = True
        document["filing_ready"] = False
        _write_index(paths, index)
        _append_audit(paths, "revision_committed", document_id=document_id, revision_id=revision_id, details={"content_sha256": revision["content_sha256"]})
        return get_document(case_root, document_id)


def reject_revision(case_root: Path, document_id: str, *, revision_id: str) -> dict[str, Any]:
    with _LOCK:
        paths = workspace_paths(case_root)
        index = _load_index(paths)
        document_id = _validate_id(document_id, "document_id")
        revision_id = _validate_id(revision_id, "revision_id")
        document = index["documents"].get(document_id)
        if not isinstance(document, dict):
            raise DocumentWorkspaceError("document_not_found", "The document was not found.", status_code=404)
        revision = _read_revision(paths, document_id, revision_id)
        if revision.get("status") != "proposed":
            raise DocumentWorkspaceError("revision_not_pending", "The revision is not pending approval.", status_code=409)
        revision["status"] = "rejected"
        revision["rejected_at"] = _utc_now()
        revision.pop("confirmation_token_sha256", None)
        _atomic_write(_revision_path(paths, document_id, revision_id), json.dumps(revision, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"))
        document["pending_revision_ids"] = [value for value in document.get("pending_revision_ids") or [] if value != revision_id]
        document["updated_at"] = revision["rejected_at"]
        _write_index(paths, index)
        _append_audit(paths, "revision_rejected", document_id=document_id, revision_id=revision_id)
        return get_document(case_root, document_id)


def request_soft_delete(case_root: Path, document_id: str) -> dict[str, Any]:
    with _LOCK:
        paths = workspace_paths(case_root)
        index = _load_index(paths)
        document_id = _validate_id(document_id, "document_id")
        document = index["documents"].get(document_id)
        if not isinstance(document, dict) or document.get("status") == "deleted":
            raise DocumentWorkspaceError("document_not_found", "The document was not found.", status_code=404)
        token = secrets.token_hex(32)
        document["delete_confirmation_sha256"] = _sha256_text(token)
        document["delete_requested_at"] = _utc_now()
        _write_index(paths, index)
        _append_audit(paths, "document_delete_requested", document_id=document_id)
        return {"document_id": document_id, "confirmation_token": token, "soft_delete": True, "original_preserved": True}


def commit_soft_delete(case_root: Path, document_id: str, *, confirmation_token: str, confirmed: bool) -> dict[str, Any]:
    with _LOCK:
        if confirmed is not True:
            raise DocumentWorkspaceError("explicit_confirmation_required", "Explicit confirmation is required.", status_code=409)
        token = str(confirmation_token or "").strip().lower()
        if not _TOKEN_RE.fullmatch(token):
            raise DocumentWorkspaceError("invalid_confirmation_token", "The confirmation token is invalid.", status_code=409)
        paths = workspace_paths(case_root)
        index = _load_index(paths)
        document_id = _validate_id(document_id, "document_id")
        document = index["documents"].get(document_id)
        if not isinstance(document, dict) or document.get("status") == "deleted":
            raise DocumentWorkspaceError("document_not_found", "The document was not found.", status_code=404)
        expected = str(document.get("delete_confirmation_sha256") or "")
        if not hmac.compare_digest(expected, _sha256_text(token)):
            raise DocumentWorkspaceError("invalid_confirmation_token", "The confirmation token is invalid.", status_code=409)
        document["status"] = "deleted"
        document["deleted_at"] = _utc_now()
        document["updated_at"] = document["deleted_at"]
        document.pop("delete_confirmation_sha256", None)
        _write_index(paths, index)
        _append_audit(paths, "document_soft_deleted", document_id=document_id)
        return {"document_id": document_id, "status": "deleted", "original_preserved": True}


def restore_document(case_root: Path, document_id: str) -> dict[str, Any]:
    with _LOCK:
        paths = workspace_paths(case_root)
        index = _load_index(paths)
        document_id = _validate_id(document_id, "document_id")
        document = index["documents"].get(document_id)
        if not isinstance(document, dict) or document.get("status") != "deleted":
            raise DocumentWorkspaceError("deleted_document_not_found", "The deleted document was not found.", status_code=404)
        document["status"] = "review_required"
        document["updated_at"] = _utc_now()
        document.pop("deleted_at", None)
        _write_index(paths, index)
        _append_audit(paths, "document_restored", document_id=document_id)
        return get_document(case_root, document_id)


def save_imported_source(
    case_root: Path,
    *,
    document_id: str,
    data: bytes,
    suffix: str,
    source_hash: str = "",
) -> dict[str, Any]:
    """Preserve one imported source as immutable bytes inside the workspace."""
    with _LOCK:
        paths = workspace_paths(case_root)
        document_id = _validate_id(document_id, "document_id")
        if len(data) > 100 * 1024 * 1024:
            raise DocumentWorkspaceError("source_too_large", "The imported source exceeds 100 MB.", status_code=413)
        safe_suffix = suffix.lower() if re.fullmatch(r"\.[a-z0-9]{1,12}", suffix.lower()) else ".bin"
        actual_hash = _sha256_bytes(data)
        if source_hash and not hmac.compare_digest(source_hash.lower(), actual_hash):
            raise DocumentWorkspaceError("source_hash_mismatch", "The imported source failed its hash check.", status_code=409)
        folder = _safe_child(paths.sources, document_id)
        folder.mkdir(mode=0o700, exist_ok=True)
        target = folder / f"original-{actual_hash}{safe_suffix}"
        if target.exists():
            if target.is_symlink() or _sha256_bytes(target.read_bytes()) != actual_hash:
                raise DocumentWorkspaceError("source_integrity_failure", "The preserved source failed its integrity check.", status_code=409)
        else:
            _atomic_write(target, bytes(data), mode=0o400)
        _append_audit(paths, "source_preserved", document_id=document_id, details={"source_sha256": actual_hash, "extension": safe_suffix, "size_bytes": len(data)})
        return {"source_sha256": actual_hash, "extension": safe_suffix, "size_bytes": len(data), "original_preserved": True}


def export_text_artifact(case_root: Path, document_id: str, *, format_name: str = "txt") -> Path:
    with _LOCK:
        paths = workspace_paths(case_root)
        document = get_document(case_root, document_id)
        format_name = str(format_name or "txt").lower()
        if format_name not in {"txt", "md"}:
            raise DocumentWorkspaceError("unsupported_export_format", "Unsupported text export format.")
        suffix = ".md" if format_name == "md" else ".txt"
        title = str(document["title"])
        safe_slug = re.sub(r"[^A-Za-z0-9._-]+", "-", title).strip("-.")[:80] or "document"
        content = str(document.get("content") or "")
        if format_name == "md":
            content = f"# {title}\n\n> Review required. Not filing-ready.\n\n{content}\n"
        filename = f"{safe_slug}-{document['current_revision_id'][:8]}{suffix}"
        target = _safe_child(paths.exports, filename)
        _atomic_write(target, content.encode("utf-8"))
        _append_audit(paths, "document_exported", document_id=document_id, revision_id=str(document["current_revision_id"]), details={"format": format_name, "artifact_sha256": _sha256_bytes(target.read_bytes())})
        return target


def workspace_status(case_root: Path) -> dict[str, Any]:
    with _LOCK:
        paths = workspace_paths(case_root)
        index = _load_index(paths)
        documents = list(index["documents"].values())
        audit = verify_audit_chain(case_root)
        return {
            "schema_version": SCHEMA_VERSION,
            "document_count": sum(1 for item in documents if item.get("status") != "deleted"),
            "deleted_count": sum(1 for item in documents if item.get("status") == "deleted"),
            "pending_revision_count": sum(len(item.get("pending_revision_ids") or []) for item in documents),
            "audit": audit,
            "local_only": True,
            "originals_preserved": True,
            "destructive_actions_approval_gated": True,
            "review_required_default": True,
        }


def find_preserved_source(case_root: Path, document_id: str, *, extension: str = "") -> Path:
    """Return one immutable preserved source without exposing it to the client."""
    with _LOCK:
        paths = workspace_paths(case_root)
        document_id = _validate_id(document_id, "document_id")
        folder = _safe_child(paths.sources, document_id)
        if not folder.exists() or folder.is_symlink():
            raise DocumentWorkspaceError("preserved_source_not_found", "No preserved source is available for this document.", status_code=404)
        wanted = str(extension or "").lower()
        candidates: list[Path] = []
        for candidate in folder.iterdir():
            if candidate.is_symlink() or not candidate.is_file():
                continue
            if wanted and candidate.suffix.lower() != wanted:
                continue
            candidates.append(candidate)
        if not candidates:
            raise DocumentWorkspaceError("preserved_source_not_found", "No preserved source is available for this document.", status_code=404)
        candidates.sort(key=lambda path: path.name)
        return candidates[0]


def record_artifact_event(
    case_root: Path,
    *,
    document_id: str,
    revision_id: str,
    format_name: str,
    artifact_sha256: str,
    size_bytes: int,
    tracked_changes: bool = False,
) -> dict[str, Any]:
    with _LOCK:
        paths = workspace_paths(case_root)
        return _append_audit(
            paths,
            "document_artifact_created",
            document_id=_validate_id(document_id, "document_id"),
            revision_id=_validate_id(revision_id, "revision_id"),
            details={
                "format": str(format_name)[:32],
                "artifact_sha256": str(artifact_sha256)[:64],
                "size_bytes": max(0, int(size_bytes)),
                "tracked_changes": bool(tracked_changes),
                "original_preserved": True,
            },
        )
