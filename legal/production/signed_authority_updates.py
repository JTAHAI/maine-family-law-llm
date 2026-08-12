"""Ed25519-verified, rollback-resistant offline authority bundle updates."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock

_SAFE_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._-]{2,99}\Z")
_MANIFEST = "authority-update.json"


class AuthorityUpdateError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def signed_payload(manifest: dict[str, Any]) -> bytes:
    payload = dict(manifest)
    payload.pop("signature", None)
    return _canonical(payload)


class AuthorityBundleVerifier:
    def __init__(self, trusted_keys: dict[str, str]):
        self.trusted_keys = dict(trusted_keys)

    def verify(self, bundle_root: str | Path, *, minimum_sequence: int = 0) -> dict[str, Any]:
        unresolved_root = Path(bundle_root).expanduser()
        if unresolved_root.is_symlink():
            raise AuthorityUpdateError("authority_bundle_unavailable")
        root = unresolved_root.resolve()
        if not root.is_dir():
            raise AuthorityUpdateError("authority_bundle_unavailable")
        manifest_path = root / _MANIFEST
        if not manifest_path.is_file() or manifest_path.is_symlink():
            raise AuthorityUpdateError("authority_manifest_missing")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AuthorityUpdateError("authority_manifest_invalid") from exc
        if manifest.get("schema_version") != "authority_update_bundle_v1":
            raise AuthorityUpdateError("authority_manifest_schema_unsupported")
        bundle_id = str(manifest.get("bundle_id") or "")
        if not _SAFE_ID.fullmatch(bundle_id):
            raise AuthorityUpdateError("authority_bundle_id_invalid")
        sequence = int(manifest.get("sequence") or 0)
        if sequence <= minimum_sequence:
            raise AuthorityUpdateError("authority_bundle_rollback_refused")
        self._verify_time(manifest)
        self._verify_signature(manifest)
        files = manifest.get("files")
        if not isinstance(files, list) or not files:
            raise AuthorityUpdateError("authority_manifest_files_required")
        verified_files: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in files:
            if not isinstance(raw, dict):
                raise AuthorityUpdateError("authority_manifest_file_invalid")
            relative = self._safe_relative(str(raw.get("path") or ""))
            if relative in seen:
                raise AuthorityUpdateError("authority_manifest_file_duplicate")
            seen.add(relative)
            unresolved_path = root
            for part in PurePosixPath(relative).parts:
                unresolved_path /= part
                if unresolved_path.is_symlink():
                    raise AuthorityUpdateError("authority_bundle_file_unavailable")
            path = unresolved_path.resolve()
            if root not in path.parents or not path.is_file():
                raise AuthorityUpdateError("authority_bundle_file_unavailable")
            expected_hash = str(raw.get("sha256") or "").casefold()
            expected_bytes = int(raw.get("bytes") or -1)
            if _sha256(path) != expected_hash or path.stat().st_size != expected_bytes:
                raise AuthorityUpdateError("authority_bundle_file_integrity_failed")
            verified_files.append(
                {"path": relative, "sha256": expected_hash, "bytes": expected_bytes}
            )
        return {
            "status": "verified",
            "bundle_id": bundle_id,
            "bundle_version": str(manifest.get("bundle_version") or ""),
            "sequence": sequence,
            "key_id": str(manifest.get("key_id") or ""),
            "file_count": len(verified_files),
            "files": verified_files,
            "manifest_sha256": _sha256(manifest_path),
            "network_used": False,
            "review_required": True,
        }

    def _verify_signature(self, manifest: dict[str, Any]) -> None:
        key_id = str(manifest.get("key_id") or "")
        encoded_key = self.trusted_keys.get(key_id, "")
        if not encoded_key:
            raise AuthorityUpdateError("authority_signing_key_untrusted")
        try:
            public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(encoded_key))
            signature = base64.b64decode(str(manifest.get("signature") or ""), validate=True)
            public_key.verify(signature, signed_payload(manifest))
        except (ValueError, InvalidSignature) as exc:
            raise AuthorityUpdateError("authority_manifest_signature_invalid") from exc

    @staticmethod
    def _verify_time(manifest: dict[str, Any]) -> None:
        now = datetime.now(UTC)
        try:
            created = datetime.fromisoformat(str(manifest["created_at"]).replace("Z", "+00:00"))
            expires = datetime.fromisoformat(str(manifest["expires_at"]).replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthorityUpdateError("authority_manifest_time_invalid") from exc
        if created.tzinfo is None or expires.tzinfo is None:
            raise AuthorityUpdateError("authority_manifest_time_invalid")
        if created > now or expires <= now or expires <= created:
            raise AuthorityUpdateError("authority_manifest_outside_validity_window")

    @staticmethod
    def _safe_relative(value: str) -> str:
        candidate = PurePosixPath(value)
        if (
            not value
            or value.startswith(("/", "\\"))
            or "\\" in value
            or candidate.is_absolute()
            or ":" in candidate.parts[0]
            or any(part in {"", ".", ".."} for part in candidate.parts)
        ):
            raise AuthorityUpdateError("authority_manifest_path_invalid")
        return candidate.as_posix()


class AuthorityUpdateChannel:
    """Stage, verify again, and atomically activate a signed offline bundle."""

    def __init__(self, root: str | Path, trusted_keys: dict[str, str]):
        self.root = Path(root).expanduser().resolve()
        self.bundles = self.root / "bundles"
        self.staging = self.root / "staging"
        self.active_path = self.root / "active-authority-bundle.json"
        self.lock_path = self.root / ".authority-update.lock"
        self.bundles.mkdir(parents=True, exist_ok=True)
        self.staging.mkdir(parents=True, exist_ok=True)
        self.verifier = AuthorityBundleVerifier(trusted_keys)

    def status(self) -> dict[str, Any]:
        active = self._active()
        return {
            "schema_version": "authority_update_channel_status_v1",
            "status": "active" if active else "awaiting_signed_bundle",
            "active": active,
            "trusted_key_count": len(self.verifier.trusted_keys),
            "network_used": False,
            "automatic_downloads": False,
            "review_required": True,
        }

    def install(self, source_root: str | Path) -> dict[str, Any]:
        with exclusive_file_lock(self.lock_path):
            active = self._active()
            minimum_sequence = int((active or {}).get("sequence") or 0)
            verified = self.verifier.verify(source_root, minimum_sequence=minimum_sequence)
            destination = self.bundles / verified["bundle_id"]
            if destination.exists():
                raise AuthorityUpdateError("authority_bundle_already_installed")
            stage = self.staging / f"{verified['bundle_id']}-{uuid.uuid4().hex}"
            stage.mkdir()
            source = Path(source_root).resolve()
            shutil.copy2(source / _MANIFEST, stage / _MANIFEST)
            for item in verified["files"]:
                relative = PurePosixPath(item["path"])
                target = stage / Path(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / Path(*relative.parts), target)
            staged = self.verifier.verify(stage, minimum_sequence=minimum_sequence)
            os.replace(stage, destination)
            pointer = {
                **staged,
                "activated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            }
            atomic_write_bytes(self.active_path, _canonical(pointer), mode=0o600)
            return pointer

    def _active(self) -> dict[str, Any] | None:
        if not self.active_path.is_file():
            return None
        try:
            value = json.loads(self.active_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AuthorityUpdateError("authority_active_pointer_invalid") from exc
        if not isinstance(value, dict):
            raise AuthorityUpdateError("authority_active_pointer_invalid")
        return value


__all__ = [
    "AuthorityBundleVerifier",
    "AuthorityUpdateChannel",
    "AuthorityUpdateError",
    "signed_payload",
]
