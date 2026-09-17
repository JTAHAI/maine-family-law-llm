"""Confirmed bounded JSON migration with authenticated recovery and exact originals.

Only index/revision files are converted. Originals/exports/review sidecars are
not silently moved, reclassified, or claimed encrypted. No model admission.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import uuid
from pathlib import Path

from legal.documents import migration_review, storage
from legal.documents import workspace as ws
from legal.security.durable_io import (
    atomic_write_bytes,
    ensure_write_capacity,
    exclusive_file_lock,
    read_bounded_regular_file,
)

PENDING = ".migration-pending.json"
PREPARING = ".migration-preparing.json"
RECEIPT = ".migration-receipt.json"
STAGE = ".migration-stage"
HEX = re.compile(r"[a-f0-9]{32}")
RELATIVE = re.compile(r"document_index\.json|documents/[a-f0-9]{32}/revisions/[a-f0-9]{32}\.json")


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read(path: Path, limit=storage.MAX_ENVELOPE) -> bytes:
    storage._location(path)
    return read_bounded_regular_file(path, max_bytes=limit)


def _seal(payload: dict) -> bytes:
    return json.dumps(storage._encryptor().encrypt_json(payload), separators=(",", ":")).encode()


def _open(raw: bytes) -> dict:
    envelope = json.loads(raw)
    cipher = storage._encryptor()
    if envelope.get("algorithm") != cipher.algorithm or envelope.get("kdf") != cipher.kdf:
        raise ValueError("migration_envelope_invalid")
    value = cipher.decrypt_json(envelope)
    if not isinstance(value, dict):
        raise ValueError("migration_state_invalid")
    return value


def _journal(root: Path, name: str) -> dict:
    value = _open(_read(root / name, 1_000_000))
    if (
        value.get("schema_version") != "document_json_migration_v1"
        or (name != RECEIPT and value.get("root_binding") != _hash(str(root.resolve()).encode()))
        or not HEX.fullmatch(str(value.get("transaction_id", "")))
        or not HEX.fullmatch(str(value.get("identity", "")))
    ):
        raise ValueError("migration_binding_invalid")
    rows = value.get("files")
    minimum = 0 if name == PREPARING else 1
    if not isinstance(rows, list) or not minimum <= len(rows) <= migration_review.MAX_FILES:
        raise ValueError("migration_inventory_invalid")
    names = set()
    for row in rows:
        if (
            not isinstance(row, dict)
            or not RELATIVE.fullmatch(str(row.get("path", "")))
            or row["path"] in names
            or not all(
                re.fullmatch(r"[a-f0-9]{64}", str(row.get(k, "")))
                for k in ("original_sha256", "encrypted_sha256")
            )
        ):
            raise ValueError("migration_inventory_invalid")
        names.add(row["path"])
    if rows and "document_index.json" not in names:
        raise ValueError("migration_index_missing")
    if name == RECEIPT and value.get("completed") is not True:
        raise ValueError("migration_receipt_incomplete")
    return value


def _stage(root: Path, journal: dict) -> Path:
    path = root / STAGE / journal["transaction_id"]
    storage._location(path / "probe")
    return path


def _original(root: Path, journal: dict, index: int) -> bytes:
    row = journal["files"][index]
    value = _open(_read(_stage(root, journal) / f"old-{index}.json", 32_000_000))
    if value.get("transaction_id") != journal["transaction_id"] or value.get("path") != row["path"]:
        raise ValueError("migration_backup_binding_invalid")
    raw = base64.b64decode(value["bytes"], validate=True)
    if len(raw) > storage.MAX_PLAINTEXT or _hash(raw) != row["original_sha256"]:
        raise ValueError("migration_backup_integrity_invalid")
    return raw


def _finish(root: Path, journal: dict) -> None:
    # Verify every backup, replacement and live preimage before touching live data.
    stage = _stage(root, journal)
    for index, row in enumerate(journal["files"]):
        _original(root, journal, index)
        candidate = _read(stage / f"new-{index}.json")
        if _hash(candidate) != row["encrypted_sha256"]:
            raise ValueError("migration_candidate_changed")
        if _hash(_read(root / row["path"])) not in {
            row["original_sha256"],
            row["encrypted_sha256"],
        }:
            raise ValueError("migration_live_file_changed")
    identity_path = root / storage.IDENTITY
    if identity_path.exists():
        if _read(identity_path, 32).decode() != journal["identity"]:
            raise ValueError("migration_identity_changed")
    else:
        atomic_write_bytes(identity_path, journal["identity"].encode())
    for index, row in enumerate(journal["files"]):
        path = root / row["path"]
        candidate = _read(stage / f"new-{index}.json")
        payload = storage.decode(path, candidate)
        if payload != json.loads(_original(root, journal, index)):
            raise ValueError("migration_payload_changed")
        live = _hash(_read(path))
        if live == row["original_sha256"]:
            atomic_write_bytes(path, candidate)
        elif live != row["encrypted_sha256"]:
            raise ValueError("migration_live_file_changed")
    for row in journal["files"]:
        if _hash(_read(root / row["path"])) != row["encrypted_sha256"]:
            raise ValueError("migration_reopen_failed")
    # Atomic marker transition: a crash before it causes idempotent revalidation.
    atomic_write_bytes(root / PENDING, _seal({**journal, "completed": True}))
    os.replace(root / PENDING, root / RECEIPT)


def recover_pending(root: Path) -> None:
    """Complete only a previously confirmed, authenticated transaction on open."""
    if not (root / PENDING).exists():
        return
    try:
        with ws._LOCK, exclusive_file_lock(root / ".migration.lock"):
            if (root / PENDING).exists():
                _finish(root, _journal(root, PENDING))
    except Exception as exc:
        raise ws.DocumentWorkspaceError(
            "workspace_migration_recovery_required",
            "An interrupted draft migration could not be verified. Original recovery copies "
            "are retained. Keep the entire workspace and original key; "
            "do not remove migration files.",
            status_code=409,
        ) from exc


def execute(case_root: Path, *, expected_manifest: str, confirmed: bool, guard) -> dict:
    if confirmed is not True:
        raise ws.DocumentWorkspaceError(
            "workspace_migration_confirmation_required",
            "Explicit migration confirmation is required.",
        )
    try:
        with ws._LOCK:
            paths = ws.workspace_paths(case_root)
            with exclusive_file_lock(paths.root / ".migration.lock"):
                current = migration_review.review(case_root)
                if current["manifest_sha256"] != expected_manifest:
                    raise ValueError("migration_preview_changed")
                guard()
                ensure_write_capacity(paths.index, current["json_bytes"] * 8 + 1_000_000)
                if (paths.root / STAGE).exists() and not (paths.root / PREPARING).exists():
                    raise ValueError("migration_preparation_requires_review")
                transaction = uuid.uuid4().hex
                journal = {
                    "schema_version": "document_json_migration_v1",
                    "root_binding": _hash(str(paths.root.resolve()).encode()),
                    "transaction_id": transaction,
                    "identity": uuid.uuid4().hex,
                    "preview_sha256": expected_manifest,
                    "files": [],
                }
                if (paths.root / PREPARING).exists():
                    journal = _journal(paths.root, PREPARING)
                    if journal["preview_sha256"] != expected_manifest:
                        raise ValueError("migration_preparation_changed")
                    journal["files"] = []
                else:
                    atomic_write_bytes(paths.root / PREPARING, _seal(journal))
                stage = _stage(paths.root, journal)
                stage.mkdir(parents=True, mode=0o700, exist_ok=True)
                names = [
                    f"documents/{r['document_id']}/revisions/{r['revision_id']}.json"
                    for r in current["revisions"]
                ] + ["document_index.json"]
                for index, name in enumerate(names):
                    raw = _read(paths.root / name, storage.MAX_PLAINTEXT)
                    encrypted = storage.encode_bound(journal["identity"], name, json.loads(raw))
                    row = {
                        "path": name,
                        "original_sha256": _hash(raw),
                        "encrypted_sha256": _hash(encrypted),
                    }
                    journal["files"].append(row)
                    atomic_write_bytes(
                        stage / f"old-{index}.json",
                        _seal(
                            {
                                "transaction_id": journal["transaction_id"],
                                "path": name,
                                "bytes": base64.b64encode(raw).decode(),
                            }
                        ),
                    )
                    atomic_write_bytes(stage / f"new-{index}.json", encrypted)
                    if _original(paths.root, journal, index) != raw:
                        raise ValueError("migration_backup_verification_failed")
                if migration_review.review(case_root)["manifest_sha256"] != expected_manifest:
                    raise ValueError("migration_preview_changed")
                guard()
                atomic_write_bytes(paths.root / PREPARING, _seal(journal))
                os.replace(paths.root / PREPARING, paths.root / PENDING)
                _finish(paths.root, journal)
                return {
                    "schema_version": "document_json_migration_result_v1",
                    "transaction_id": journal["transaction_id"],
                    "file_count": len(names),
                    "migration_performed": True,
                    "original_bytes_recoverable": True,
                    "review_required": True,
                    "filing_ready": False,
                    "all_workspace_files_encrypted": False,
                    "scope": "draft_index_and_revisions_only",
                }
    except ws.DocumentWorkspaceError:
        raise
    except Exception as exc:
        raise ws.DocumentWorkspaceError(
            "workspace_migration_not_completed",
            "Migration did not finish. Keep all workspace and recovery files and the original key. "
            "Reopen the original matter to verify or resume the confirmed transaction.",
            status_code=409,
        ) from exc


def original_snapshot(case_root: Path) -> dict[str, bytes]:
    """Internal recovery reader for verified backup tools; never restores over live files."""
    root = Path(case_root) / ws.WORKSPACE_FOLDER
    storage._location(root / "probe")
    journal = _journal(root, PENDING if (root / PENDING).exists() else RECEIPT)
    return {
        row["path"]: _original(root, journal, index) for index, row in enumerate(journal["files"])
    }
