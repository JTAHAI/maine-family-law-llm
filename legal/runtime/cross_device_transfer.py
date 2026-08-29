"""Passphrase-encrypted, user-carried matter transfer bundles.

Bundles are created only in an explicitly configured external location.  Their
single encrypted container includes a deterministic manifest and the selected
matter files; importing verifies every entry and produces a separate recovery
copy.  This module never discovers devices, uses a provider, uploads data, or
merges into an active matter.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock, read_bounded_regular_file
from legal.security.local_encryption import EncryptedBlob, LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path

_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")
_MAX_FILE_BYTES = 2 * 1024 * 1024
_MAX_TOTAL_BYTES = 32 * 1024 * 1024
_MAX_FILES = 1_000
_MAX_BUNDLE_BYTES = 80 * 1024 * 1024
_EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".mfl_encrypted_backups"}


class CrossDeviceTransferError(RuntimeError):
    def __init__(self, code: str, *, status_code: int = 409) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canon(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _hash(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else _canon(value)).hexdigest()


def _safe_id(value: object, code: str) -> str:
    result = str(value or "").strip().lower()
    if not _ID.fullmatch(result):
        raise CrossDeviceTransferError(code, status_code=422)
    return result


def _transfer_encryptor(passphrase: object) -> LocalEnvelopeEncryptor:
    text = str(passphrase or "")
    if len(text) < 16 or len(text) > 512:
        raise CrossDeviceTransferError("transfer_passphrase_invalid", status_code=422)
    return LocalEnvelopeEncryptor(text)


class CrossDeviceTransferStore:
    schema_version = "cross_device_transfer_v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None, transfer_root: str | Path | None = None) -> None:
        self.case_root = Path(case_root).resolve()
        if not self.case_root.is_dir() or self.case_root.is_symlink():
            raise CrossDeviceTransferError("active_matter_unavailable", status_code=404)
        configured = str(transfer_root or os.environ.get("MFL_TRANSFER_ROOT") or "").strip()
        self.transfer_root = Path(configured).expanduser().resolve() if configured else None
        if self.transfer_root is not None and (self.transfer_root == self.case_root or self.case_root in self.transfer_root.parents):
            raise CrossDeviceTransferError("transfer_root_must_be_outside_active_matter")
        self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")
        self.scope = _hash(str(self.case_root))[:24]
        self.receipt_path = self.case_root / "40_RUNTIME" / "cross-device-transfer" / "receipts.json.enc"
        self.lock_path = self.receipt_path.parent / ".receipts.lock"

    def _require_root(self) -> Path:
        if self.transfer_root is None:
            raise CrossDeviceTransferError("transfer_root_not_configured")
        if self.transfer_root.exists() and self.transfer_root.is_symlink():
            raise CrossDeviceTransferError("transfer_root_symlink_refused")
        self.transfer_root.mkdir(parents=True, exist_ok=True)
        return self.transfer_root

    def _files(self) -> list[tuple[str, bytes, str]]:
        rows: list[tuple[str, bytes, str]] = []
        total = 0
        for path in sorted(self.case_root.rglob("*"), key=lambda item: item.as_posix().casefold()):
            relative = path.relative_to(self.case_root)
            if any(part in _EXCLUDED_PARTS for part in relative.parts) or path.is_symlink() or not path.is_file():
                continue
            try:
                raw = read_bounded_regular_file(path, max_bytes=_MAX_FILE_BYTES)
            except Exception as exc:
                raise CrossDeviceTransferError("transfer_source_file_unavailable") from exc
            total += len(raw)
            if len(rows) >= _MAX_FILES or total > _MAX_TOTAL_BYTES:
                raise CrossDeviceTransferError("transfer_bundle_limit_exceeded", status_code=413)
            rows.append((relative.as_posix(), raw, _hash(raw)))
        return rows

    @staticmethod
    def _zip_info(name: str) -> zipfile.ZipInfo:
        info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o600 << 16
        return info

    @staticmethod
    def _safe_zip_name(name: str) -> bool:
        path = PurePosixPath(name)
        return bool(name) and not path.is_absolute() and ".." not in path.parts and "\\" not in name

    def status(self) -> dict[str, Any]:
        root_ready = self.transfer_root is not None and not (self.transfer_root.exists() and self.transfer_root.is_symlink())
        return {"status": "ready" if root_ready else "blocked", "transfer_root_configured": self.transfer_root is not None, "external_location_required": True, "network_used": False, "review_required": True}

    def create_bundle(self, *, transfer_id: object, passphrase: object, actor_role: str, tenant_id: str) -> dict[str, Any]:
        transfer_id = _safe_id(transfer_id, "transfer_id_invalid")
        root = self._require_root()
        crypto = _transfer_encryptor(passphrase)
        files = self._files()
        manifest = {"schema_version": self.schema_version, "transfer_id": transfer_id, "source_scope_hash": self.scope, "created_at": _now(), "files": [{"path": path, "size": len(raw), "sha256": digest} for path, raw, digest in files], "file_count": len(files), "total_bytes": sum(len(raw) for _path, raw, _digest_value in files), "network_used": False, "review_required": True}
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
            output.writestr(self._zip_info("transfer-manifest.json"), _canon(manifest))
            for path, raw, _digest_value in files:
                output.writestr(self._zip_info(f"matter/{path}"), raw)
        bundle_bytes = archive.getvalue()
        if len(bundle_bytes) > _MAX_BUNDLE_BYTES:
            raise CrossDeviceTransferError("transfer_bundle_limit_exceeded", status_code=413)
        target = root / "bundles" / f"{transfer_id}.json.enc"
        if target.exists():
            raise CrossDeviceTransferError("transfer_id_exists")
        atomic_write_bytes(target, _canon(crypto.encrypt(bundle_bytes).as_dict()), mode=0o600)
        self._verify_bundle(target, crypto, expected_transfer_id=transfer_id)
        report = {"schema_version": self.schema_version, "status": "created", "transfer_id": transfer_id, "bundle_sha256": _hash(target.read_bytes()), "file_count": len(files), "total_bytes": manifest["total_bytes"], "user_carried": True, "network_used": False, "paths_disclosed": False, "private_record_content_included": False, "source_drill_down": {"source_type": "encrypted_transfer_manifest", "source_id": f"transfer:{transfer_id}"}, "review_required": True}
        return self._record(report, actor_role=actor_role, tenant_id=tenant_id, event_type="cross_device_transfer_created")

    def list_bundles(self) -> dict[str, Any]:
        root = self._require_root()
        bundles = []
        for path in sorted((root / "bundles").glob("*.json.enc"), key=lambda item: item.stat().st_mtime, reverse=True)[:30] if (root / "bundles").is_dir() else []:
            if not path.is_file() or path.is_symlink():
                continue
            try:
                transfer_id = _safe_id(path.name.removesuffix(".json.enc"), "transfer_id_invalid")
            except CrossDeviceTransferError:
                continue
            bundles.append({"transfer_id": transfer_id, "bundle_sha256": _hash(path.read_bytes()), "user_carried": True, "encrypted": True, "review_required": True})
        return {"schema_version": self.schema_version, "status": "review_required", "bundle_count": len(bundles), "bundles": bundles, "paths_disclosed": False, "network_used": False, "review_required": True}

    def import_bundle(self, *, transfer_id: object, passphrase: object, actor_role: str, tenant_id: str) -> dict[str, Any]:
        transfer_id = _safe_id(transfer_id, "transfer_id_invalid")
        root = self._require_root()
        crypto = _transfer_encryptor(passphrase)
        source = root / "bundles" / f"{transfer_id}.json.enc"
        manifest, entries = self._verify_bundle(source, crypto, expected_transfer_id=transfer_id)
        target = root / "recovery" / transfer_id
        if target.exists():
            raise CrossDeviceTransferError("transfer_recovery_exists")
        for relative, raw in entries:
            destination = (target / PurePosixPath(relative)).resolve()
            if target.resolve() not in destination.parents:
                raise CrossDeviceTransferError("transfer_path_invalid")
            destination.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_bytes(destination, raw, mode=0o600)
        report = {"schema_version": self.schema_version, "status": "imported_to_isolated_recovery_copy", "transfer_id": transfer_id, "file_count": manifest["file_count"], "total_bytes": manifest["total_bytes"], "live_matter_overwritten": False, "active_matter_changed": False, "network_used": False, "paths_disclosed": False, "private_record_content_included": False, "source_drill_down": {"source_type": "encrypted_transfer_manifest", "source_id": f"transfer:{transfer_id}"}, "review_required": True}
        return self._record(report, actor_role=actor_role, tenant_id=tenant_id, event_type="cross_device_transfer_imported")

    def _verify_bundle(self, path: Path, crypto: LocalEnvelopeEncryptor, *, expected_transfer_id: str) -> tuple[dict[str, Any], list[tuple[str, bytes]]]:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > _MAX_BUNDLE_BYTES:
            raise CrossDeviceTransferError("transfer_bundle_unavailable", status_code=404)
        try:
            envelope = strict_json_load_path(path, max_bytes=_MAX_BUNDLE_BYTES, require_object=True)
            archive_bytes = crypto.decrypt(EncryptedBlob.from_dict(envelope))
            archive = zipfile.ZipFile(io.BytesIO(archive_bytes), "r")
            manifest = json.loads(archive.read("transfer-manifest.json").decode("utf-8"))
        except Exception as exc:
            raise CrossDeviceTransferError("transfer_bundle_integrity_failed") from exc
        if not isinstance(manifest, dict) or manifest.get("schema_version") != self.schema_version or manifest.get("transfer_id") != expected_transfer_id:
            raise CrossDeviceTransferError("transfer_manifest_invalid")
        files = manifest.get("files")
        if not isinstance(files, list) or len(files) > _MAX_FILES:
            raise CrossDeviceTransferError("transfer_manifest_invalid")
        names = set(archive.namelist())
        expected = {"transfer-manifest.json"}
        entries: list[tuple[str, bytes]] = []
        total = 0
        for row in files:
            relative = str(row.get("path") or "") if isinstance(row, dict) else ""
            name = f"matter/{relative}"
            if not self._safe_zip_name(name) or name not in names:
                raise CrossDeviceTransferError("transfer_manifest_invalid")
            raw = archive.read(name)
            total += len(raw)
            if len(raw) > _MAX_FILE_BYTES or total > _MAX_TOTAL_BYTES or len(raw) != int(row.get("size") or -1) or _hash(raw) != str(row.get("sha256") or ""):
                raise CrossDeviceTransferError("transfer_bundle_integrity_failed")
            expected.add(name)
            entries.append((relative, raw))
        if names != expected or int(manifest.get("file_count") or -1) != len(entries) or int(manifest.get("total_bytes") or -1) != total:
            raise CrossDeviceTransferError("transfer_manifest_invalid")
        return manifest, entries

    def _record(self, report: dict[str, Any], *, actor_role: str, tenant_id: str, event_type: str) -> dict[str, Any]:
        with exclusive_file_lock(self.lock_path):
            state = {"schema_version": self.schema_version, "tenant_id": "", "audit": []}
            if self.receipt_path.exists():
                try: state = self.encryptor.decrypt_json(strict_json_load_path(self.receipt_path, max_bytes=512 * 1024, require_object=True))
                except Exception as exc: raise CrossDeviceTransferError("transfer_receipt_store_unavailable") from exc
            if state.get("tenant_id") and state["tenant_id"] != tenant_id: raise CrossDeviceTransferError("transfer_tenant_mismatch", status_code=403)
            state["tenant_id"] = tenant_id; previous = str((state.get("audit") or [{}])[-1].get("event_hash") or ""); recorded_at = _now(); basis = {"event_type": event_type, "recorded_at": recorded_at, "report_hash": _hash(report), "previous_hash": previous, "actor_role": actor_role[:40], "tenant_id": tenant_id}; audit = {**basis, "event_hash": _hash(basis)}; state["audit"] = [*list(state.get("audit") or []), audit][-80:]
            atomic_write_bytes(self.receipt_path, _canon(self.encryptor.encrypt_json(state)), mode=0o600)
        return {**report, "audit_receipt": {"transfer_receipt_id": f"transfer_{audit['event_hash'][:24]}", "recorded_at": recorded_at, "review_required": True}, "audit_chain_head": audit["event_hash"]}


__all__ = ["CrossDeviceTransferError", "CrossDeviceTransferStore"]
