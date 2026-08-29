"""Verify signed Store update metadata without downloading or installing an update.

Windows and Partner Center remain the only delivery authorities. This verifier
recognizes a hash-bound signed metadata document, but never fetches a package,
contacts a Store service, modifies update settings, or creates signing keys.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from legal.release.msix_upgrade_qualification import MsixUpgradeQualificationError, read_identity, sha256_file

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9._-]{1,180}\.msix$", re.IGNORECASE)
_DELIVERY_AUTHORITY = "windows_store_partner_center"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def signed_payload(metadata: dict[str, Any]) -> bytes:
    payload = dict(metadata)
    payload.pop("signature", None)
    return _canonical(payload)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_object(path: str | Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        raw = json.loads(Path(path).resolve().read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def verify_update_metadata(
    *,
    package: str | Path,
    metadata_path: str | Path | None,
    trust_config: str | Path,
    release_scope: str | Path | None = None,
) -> dict[str, Any]:
    """Verify only an explicit signed update record against an exact MSIX."""

    package_path = Path(package).resolve()
    metadata = _load_object(metadata_path)
    trust = _load_object(trust_config)
    scope_path = Path(release_scope).resolve() if release_scope else None
    blockers: list[str] = []
    try:
        identity = read_identity(package_path)
    except MsixUpgradeQualificationError as exc:
        return {"schema_version": "store_update_metadata_verification_v1", "generated_at": _now(), "status": "blocked", "blockers": [str(exc)], "review_required": True, "network_used": False, "update_control": _DELIVERY_AUTHORITY}
    package_sha256 = sha256_file(package_path)
    if metadata is None:
        blockers.append("metadata_manifest_unavailable")
        metadata = {}
    trusted_keys = trust.get("trusted_keys") if isinstance(trust, dict) else None
    if not isinstance(trusted_keys, dict):
        blockers.append("update_trust_config_invalid")
        trusted_keys = {}
    if metadata.get("schema_version") != "msix_store_update_metadata_v1":
        blockers.append("metadata_schema_unsupported")
    if metadata.get("delivery_authority") != _DELIVERY_AUTHORITY or metadata.get("update_control") != _DELIVERY_AUTHORITY:
        blockers.append("update_delivery_authority_invalid")
    if any(key in metadata for key in ("download_url", "installer_command", "auto_install", "provider_endpoint")):
        blockers.append("metadata_attempts_to_control_delivery")
    package_block = metadata.get("package") if isinstance(metadata.get("package"), dict) else {}
    if package_block.get("file_name") != package_path.name or not _SAFE_FILENAME.fullmatch(str(package_block.get("file_name") or "")):
        blockers.append("metadata_package_filename_mismatch")
    if str(package_block.get("sha256") or "").casefold() != package_sha256:
        blockers.append("metadata_package_hash_mismatch")
    metadata_identity = package_block.get("identity") if isinstance(package_block.get("identity"), dict) else {}
    for field, expected in identity.as_dict().items():
        if metadata_identity.get(field) != expected:
            blockers.append(f"metadata_package_{field}_mismatch")
    expected_scope_sha = _sha256(scope_path) if scope_path and scope_path.is_file() else ""
    if scope_path and not expected_scope_sha:
        blockers.append("release_scope_unavailable")
    if expected_scope_sha and str(metadata.get("release_scope_sha256") or "").casefold() != expected_scope_sha:
        blockers.append("metadata_release_scope_hash_mismatch")
    key_id = str(metadata.get("key_id") or "")
    encoded_key = trusted_keys.get(key_id) if isinstance(trusted_keys, dict) else None
    if not isinstance(encoded_key, str) or not encoded_key:
        blockers.append("metadata_signing_key_untrusted")
    else:
        try:
            public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(encoded_key, validate=True))
            signature = base64.b64decode(str(metadata.get("signature") or ""), validate=True)
            public_key.verify(signature, signed_payload(metadata))
        except (ValueError, InvalidSignature):
            blockers.append("metadata_signature_invalid")
    return {
        "schema_version": "store_update_metadata_verification_v1",
        "generated_at": _now(),
        "status": "pass" if not blockers else "blocked",
        "blockers": sorted(set(blockers)),
        "package": {"file_name": package_path.name, "sha256": package_sha256, "identity": identity.as_dict()},
        "metadata": {"key_id": key_id[:100], "release_scope_sha256": str(metadata.get("release_scope_sha256") or "").casefold(), "signature_present": bool(metadata.get("signature")), "manifest_sha256": _sha256(Path(metadata_path).resolve()) if metadata_path and Path(metadata_path).is_file() else ""},
        "delivery_boundary": {"delivery_authority": _DELIVERY_AUTHORITY, "network_used": False, "package_downloaded": False, "package_installed": False, "partner_center_or_windows_update_controlled": True},
        "review_required": True,
        "store_or_enterprise_claim": "not_made",
    }


__all__ = ["signed_payload", "verify_update_metadata"]
