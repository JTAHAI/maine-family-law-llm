from __future__ import annotations

import base64
import hashlib
import json
import shutil
import warnings
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

import app.api.production as production
from legal.production.signed_authority_updates import AuthorityBundleVerifier, AuthorityUpdateChannel, signed_payload


ROOT = Path(__file__).resolve().parents[1]


def _trust(key: Ed25519PrivateKey) -> dict[str, str]:
    raw = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return {"test-signing-key": base64.b64encode(raw).decode()}


def _bundle(root: Path, key: Ed25519PrivateKey, *, sequence: int = 1) -> Path:
    root.mkdir()
    authority = root / "maine-authority.jsonl"
    authority.write_text('{"source_id":"fictional-public-authority"}\n', encoding="utf-8")
    now = datetime.now(UTC)
    manifest = {
        "schema_version": "authority_update_bundle_v1",
        "bundle_id": f"portable-authority-{sequence}",
        "bundle_version": f"2026.8.{sequence}",
        "sequence": sequence,
        "created_at": (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(days=30)).isoformat().replace("+00:00", "Z"),
        "key_id": "test-signing-key",
        "files": [{"path": authority.name, "sha256": hashlib.sha256(authority.read_bytes()).hexdigest(), "bytes": authority.stat().st_size}],
    }
    manifest["signature"] = base64.b64encode(key.sign(signed_payload(manifest))).decode()
    (root / "authority-update.json").write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    return root


def test_pass40_signed_bundle_round_trip_is_hash_verified_and_local(tmp_path: Path) -> None:
    key = Ed25519PrivateKey.generate()
    source_channel = AuthorityUpdateChannel(tmp_path / "source-device", _trust(key))
    source_channel.install(_bundle(tmp_path / "signed-source", key))

    exported = source_channel.export_archive()

    assert exported["status"] == "exported"
    assert exported["signature_verified"] is True
    assert exported["hashes_verified"] is True
    assert exported["network_used"] is False
    archive = source_channel.root / "exports" / exported["archive_filename"]
    with zipfile.ZipFile(archive) as contents:
        assert set(contents.namelist()) == {"authority-update.json", "maine-authority.jsonl"}

    receiving_channel = AuthorityUpdateChannel(tmp_path / "receiving-device", _trust(key))
    inbox = receiving_channel.root / "inbox"
    inbox.mkdir(parents=True)
    shutil.copy2(archive, inbox / archive.name)
    imported = receiving_channel.import_archive(archive.name)

    assert imported["status"] == "imported_and_activated"
    assert imported["bundle_id"] == "portable-authority-1"
    assert receiving_channel.status()["active"]["bundle_id"] == "portable-authority-1"
    assert AuthorityBundleVerifier(_trust(key)).verify(receiving_channel.bundles / "portable-authority-1")["status"] == "verified"


def test_pass40_tampered_or_duplicate_archive_member_is_rejected_before_install(tmp_path: Path) -> None:
    key = Ed25519PrivateKey.generate()
    source_channel = AuthorityUpdateChannel(tmp_path / "source-device", _trust(key))
    source_channel.install(_bundle(tmp_path / "signed-source", key))
    exported = source_channel.export_archive()
    archive = source_channel.root / "exports" / exported["archive_filename"]
    receiving_channel = AuthorityUpdateChannel(tmp_path / "receiving-device", _trust(key))
    inbox = receiving_channel.root / "inbox"
    inbox.mkdir(parents=True)
    target = inbox / archive.name
    shutil.copy2(archive, target)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Duplicate name: 'maine-authority.jsonl'")
        with zipfile.ZipFile(target, "a", compression=zipfile.ZIP_DEFLATED) as contents:
            contents.writestr("maine-authority.jsonl", "tampered")

    try:
        receiving_channel.import_archive(target.name)
    except ValueError as exc:
        assert str(exc) == "authority_archive_member_invalid"
    else:
        raise AssertionError("tampered archive unexpectedly installed")
    assert receiving_channel.status()["active"] is None


def test_pass40_production_routes_require_admin_and_use_selected_upload(monkeypatch, tmp_path: Path) -> None:
    key = Ed25519PrivateKey.generate()
    channel = AuthorityUpdateChannel(tmp_path / "device", _trust(key))
    channel.install(_bundle(tmp_path / "signed-source", key))
    monkeypatch.setattr(production, "authority_update_channel", lambda: channel)
    client = TestClient(production.app)

    assert client.post("/api/authority-updates/export", json={}).status_code == 403
    exported = client.post(
        "/api/authority-updates/export",
        json={},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "tenant-portability"},
    )
    assert exported.status_code == 200
    assert exported.json()["signature_verified"] is True
    assert exported.json()["audit_event"]["action"] == "authority_bundle_export"

    archive = channel.root / "exports" / exported.json()["archive_filename"]
    receiving = AuthorityUpdateChannel(tmp_path / "receive", _trust(key))
    monkeypatch.setattr(production, "authority_update_channel", lambda: receiving)
    response = client.post(
        "/api/authority-updates/import-upload",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "tenant-portability"},
        files={"bundle": (archive.name, archive.read_bytes(), "application/zip")},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "imported_and_activated"
    assert response.json()["audit_event"]["action"] == "authority_bundle_upload_import"
    assert receiving.status()["active"]["bundle_id"] == "portable-authority-1"


def test_pass40_production_ui_has_explicit_authorization_and_upload_path() -> None:
    source_ui = (ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes()
    mirrored_ui = (ROOT / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes()
    assert b"installAuthorityBundlePortability" in source_ui
    assert b"/api/authority-updates/export" in source_ui
    assert b"/api/authority-updates/import-upload" in source_ui
    assert b"I am authorized to manage signed authority bundles" in source_ui
    assert b"never creates a signing key, changes the MSIX" in source_ui
    assert source_ui == mirrored_ui
