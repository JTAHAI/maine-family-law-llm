"""Authenticated workspace JSON; legacy reads never rewrite historical files.

The non-secret workspace identity travels with a complete backup. Encrypted
documents require the original user's protected vault (or configured secret).
Individual ciphertext files cannot be substituted across workspaces or paths.
This layer does not encrypt intentional exports or imported binary originals.
"""

from __future__ import annotations

import base64
import json
import os
import re
import uuid
from pathlib import Path

from legal.security.durable_io import (
    atomic_write_bytes,
    exclusive_file_lock,
    read_bounded_regular_file,
)
from legal.security.local_encryption import LocalEnvelopeEncryptor

FORMAT = "document_workspace_encrypted_json_v1"
IDENTITY = ".storage-identity"
MAX_PLAINTEXT = 6_000_000
MAX_ENVELOPE = MAX_PLAINTEXT * 2 + 4096


def policy(root: Path | None = None) -> dict:
    legacy = bool(
        root and (root / "document_index.json").exists() and not (root / IDENTITY).exists()
    )
    migrated = False
    if root and (root / ".migration-receipt.json").exists():
        from legal.documents.migration import RECEIPT, _journal

        receipt = _journal(root, RECEIPT)
        if receipt["identity"] != _identity(root, create=False):
            raise ValueError("workspace_migration_identity_mismatch")
        migrated = True
    return {
        "schema_version": FORMAT,
        "new_json_writes_encrypted": True,
        "legacy_reads_supported": True,
        "legacy_migration_performed": migrated,
        "all_workspace_files_encrypted": False,
        "legacy_read_only": legacy,
        "notice": (
            "New draft text, revision notes and index writes are encrypted with your local key. "
            "Legacy workspaces remain read-only until a reviewed migration; imported originals "
            "and exported copies are not encrypted by this layer. "
            "Keep the complete workspace and its original protected key for recovery. "
            "Older app versions cannot open new encrypted revisions."
        ),
    }


def _location(path: Path) -> tuple[Path, str]:
    # Callers already obtained paths from workspace_paths. Check all components
    # again so standalone use cannot follow a reparse redirect inside the store.
    root = next((p for p in path.parents if p.name == "19_DOCUMENT_WORKSPACE"), None)
    if root is None:
        raise ValueError("workspace_storage_location_invalid")
    for component in (path, *path.parents):
        if component.is_symlink() or (
            component.exists() and getattr(component.lstat(), "st_file_attributes", 0) & 0x400
        ):
            raise ValueError("workspace_storage_redirect_refused")
        if component == root:
            break
    return root, path.relative_to(root).as_posix()


def _identity(root: Path, *, create: bool) -> str:
    path = root / IDENTITY
    if create:
        with exclusive_file_lock(root / ".storage-identity.lock"):
            if not path.exists():
                # Never silently replace a legacy index or strand its original
                # revisions. A lost identity is likewise not an empty store.
                if (root / "document_index.json").exists() or next(
                    (root / "documents").glob("*/revisions/*.json"), None
                ) is not None:
                    raise ValueError("workspace_legacy_storage_migration_required")
                atomic_write_bytes(path, uuid.uuid4().hex.encode("ascii"))
    raw = read_bounded_regular_file(path, max_bytes=32).decode("ascii")
    if not re.fullmatch(r"[a-f0-9]{32}", raw):
        raise ValueError("workspace_storage_identity_invalid")
    return raw


def _encryptor() -> LocalEnvelopeEncryptor:
    # The historical default is resolved by LocalEnvelopeEncryptor to the
    # OS-protected random per-user secret, never used as a literal fixed key.
    return LocalEnvelopeEncryptor(
        os.environ.get("MAINE_MATTER_STORE_KEY") or LocalEnvelopeEncryptor.development_default
    )


def encode(path: Path, payload: dict) -> bytes:
    root, relative = _location(path)
    if not isinstance(payload, dict):
        raise ValueError("workspace_storage_payload_invalid")
    identity = _identity(root, create=True)
    return encode_bound(identity, relative, payload)


def encode_bound(identity: str, relative: str, payload: dict) -> bytes:
    """Internal staging codec; does not install an identity or permit a live write."""
    if not re.fullmatch(r"[a-f0-9]{32}", identity) or not isinstance(payload, dict):
        raise ValueError("workspace_storage_binding_invalid")
    bound = {"workspace_id": identity, "relative_path": relative, "payload": payload}
    plain = json.dumps(bound, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(plain) > MAX_PLAINTEXT:
        raise ValueError("workspace_storage_payload_too_large")
    return json.dumps(
        {"storage_format": FORMAT, "envelope": _encryptor().encrypt(plain).as_dict()},
        separators=(",", ":"),
    ).encode("utf-8")


def decode(path: Path, raw: bytes):
    root, relative = _location(path)
    if len(raw) > MAX_ENVELOPE:
        raise ValueError("workspace_storage_payload_too_large")
    value = json.loads(raw.decode("utf-8"))
    if isinstance(value, dict) and "storage_format" in value:
        if set(value) != {"storage_format", "envelope"} or value["storage_format"] != FORMAT:
            raise ValueError("workspace_storage_format_invalid")
        envelope = value["envelope"]
        # This is a new format, not a migration of historical demo envelopes.
        # Do not inherit the shared decryptor's legacy/fixed-key compatibility.
        if (
            not isinstance(envelope, dict)
            or set(envelope) != {"algorithm", "kdf", "salt", "nonce", "ciphertext", "mac"}
            or not all(isinstance(field, str) for field in envelope.values())
            or envelope["algorithm"] != LocalEnvelopeEncryptor.algorithm
            or envelope["kdf"] != LocalEnvelopeEncryptor.kdf
            or envelope["mac"] != ""
        ):
            raise ValueError("workspace_storage_envelope_invalid")
        if (
            len(base64.b64decode(envelope["salt"], validate=True)) != 16
            or len(base64.b64decode(envelope["nonce"], validate=True)) != 12
            or len(base64.b64decode(envelope["ciphertext"], validate=True)) < 16
        ):
            raise ValueError("workspace_storage_envelope_invalid")
        identity = _identity(root, create=False)
        bound = _encryptor().decrypt_json(envelope)
        if (
            not isinstance(bound, dict)
            or set(bound) != {"workspace_id", "relative_path", "payload"}
            or bound["workspace_id"] != identity
            or bound["relative_path"] != relative
            or not isinstance(bound["payload"], dict)
        ):
            raise ValueError("workspace_storage_binding_invalid")
        return bound["payload"]
    if len(raw) > MAX_PLAINTEXT:
        raise ValueError("workspace_storage_payload_too_large")
    if (root / IDENTITY).exists():
        raise ValueError("workspace_storage_plaintext_downgrade_refused")
    return value  # Legacy reads are deliberately non-mutating.
