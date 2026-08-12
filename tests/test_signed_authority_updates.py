import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from legal.production.signed_authority_updates import (
    AuthorityBundleVerifier,
    AuthorityUpdateChannel,
    AuthorityUpdateError,
    signed_payload,
)


def bundle(root: Path, key: Ed25519PrivateKey, *, sequence: int = 1) -> Path:
    root.mkdir()
    authority = root / "maine-authority.jsonl"
    authority.write_text('{"source_id":"test"}\n', encoding="utf-8")
    now = datetime.now(UTC)
    manifest = {
        "schema_version": "authority_update_bundle_v1",
        "bundle_id": f"maine-authority-{sequence}",
        "bundle_version": f"2026.8.{sequence}",
        "sequence": sequence,
        "created_at": (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(days=30)).isoformat().replace("+00:00", "Z"),
        "key_id": "release-2026",
        "files": [
            {
                "path": authority.name,
                "sha256": hashlib.sha256(authority.read_bytes()).hexdigest(),
                "bytes": authority.stat().st_size,
            }
        ],
    }
    manifest["signature"] = base64.b64encode(key.sign(signed_payload(manifest))).decode()
    (root / "authority-update.json").write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )
    return root


def trust(key: Ed25519PrivateKey) -> dict[str, str]:
    raw = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return {"release-2026": base64.b64encode(raw).decode()}


def test_verifier_accepts_only_hash_bound_ed25519_bundle(tmp_path: Path):
    key = Ed25519PrivateKey.generate()
    source = bundle(tmp_path / "source", key)
    verified = AuthorityBundleVerifier(trust(key)).verify(source)
    assert verified["status"] == "verified"
    assert verified["file_count"] == 1

    (source / "maine-authority.jsonl").write_text("tampered", encoding="utf-8")
    with pytest.raises(AuthorityUpdateError, match="authority_bundle_file_integrity_failed"):
        AuthorityBundleVerifier(trust(key)).verify(source)


def test_channel_activates_atomically_and_refuses_rollback(tmp_path: Path):
    key = Ed25519PrivateKey.generate()
    channel = AuthorityUpdateChannel(tmp_path / "channel", trust(key))
    first = channel.install(bundle(tmp_path / "first", key, sequence=1))
    assert first["sequence"] == 1
    assert channel.status()["active"]["bundle_id"] == "maine-authority-1"

    second = channel.install(bundle(tmp_path / "second", key, sequence=2))
    assert second["sequence"] == 2
    with pytest.raises(AuthorityUpdateError, match="authority_bundle_rollback_refused"):
        channel.install(bundle(tmp_path / "rollback", key, sequence=1))


def test_verifier_refuses_untrusted_key_and_path_traversal(tmp_path: Path):
    key = Ed25519PrivateKey.generate()
    source = bundle(tmp_path / "source", key)
    with pytest.raises(AuthorityUpdateError, match="authority_signing_key_untrusted"):
        AuthorityBundleVerifier({}).verify(source)

    manifest_path = source / "authority-update.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][0]["path"] = "../escape.json"
    manifest["signature"] = base64.b64encode(key.sign(signed_payload(manifest))).decode()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(AuthorityUpdateError, match="authority_manifest_path_invalid"):
        AuthorityBundleVerifier(trust(key)).verify(source)
