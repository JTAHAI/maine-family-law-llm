from __future__ import annotations

import base64
import json
import zipfile
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from legal.release.msix_upgrade_qualification import read_identity, sha256_file
from legal.release.signed_update_metadata import signed_payload, verify_update_metadata


def _package(path: Path) -> None:
    manifest = '''<?xml version="1.0" encoding="utf-8"?><Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"><Identity Name="TAHAIWebServices.MaineFamilyLawLLM" Publisher="CN=Fictional" Version="8.0.0.0" ProcessorArchitecture="x64"/><Properties/><Resources><Resource Language="en-us"/></Resources><Applications><Application Id="MaineFamilyLawLLM" Executable="MaineFamilyLawLLM.exe" EntryPoint="Windows.FullTrustApplication"/></Applications></Package>'''
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("AppxManifest.xml", manifest)


def _metadata(package: Path, scope: Path, key: Ed25519PrivateKey) -> dict:
    metadata = {"schema_version": "msix_store_update_metadata_v1", "delivery_authority": "windows_store_partner_center", "update_control": "windows_store_partner_center", "key_id": "fictional-release-key", "release_scope_sha256": __import__("hashlib").sha256(scope.read_bytes()).hexdigest(), "package": {"file_name": package.name, "sha256": sha256_file(package), "identity": read_identity(package).as_dict()}}
    metadata["signature"] = base64.b64encode(key.sign(signed_payload(metadata))).decode()
    return metadata


def test_pass160_accepts_signed_hash_bound_metadata_without_update_control(tmp_path: Path) -> None:
    package = tmp_path / "MaineFamilyLawLLM_8.0.0.0_x64.msix"; scope = tmp_path / "scope.json"; metadata_path = tmp_path / "metadata.json"; trust = tmp_path / "trust.json"
    _package(package); scope.write_text('{"accepted_features":[]}', encoding="utf-8")
    key = Ed25519PrivateKey.generate(); metadata_path.write_text(json.dumps(_metadata(package, scope, key)), encoding="utf-8")
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    trust.write_text(json.dumps({"trusted_keys": {"fictional-release-key": base64.b64encode(public).decode()}}), encoding="utf-8")
    report = verify_update_metadata(package=package, metadata_path=metadata_path, trust_config=trust, release_scope=scope)
    assert report["status"] == "pass"
    assert report["delivery_boundary"]["network_used"] is False
    assert report["delivery_boundary"]["partner_center_or_windows_update_controlled"] is True


def test_pass160_blocks_tampering_untrusted_key_and_delivery_override(tmp_path: Path) -> None:
    package = tmp_path / "MaineFamilyLawLLM_8.0.0.0_x64.msix"; scope = tmp_path / "scope.json"; metadata_path = tmp_path / "metadata.json"; trust = tmp_path / "trust.json"
    _package(package); scope.write_text('{"accepted_features":[]}', encoding="utf-8")
    key = Ed25519PrivateKey.generate(); metadata = _metadata(package, scope, key); metadata["download_url"] = "https://example.invalid/package.msix"; metadata["package"]["sha256"] = "0" * 64
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8"); trust.write_text(json.dumps({"trusted_keys": {}}), encoding="utf-8")
    report = verify_update_metadata(package=package, metadata_path=metadata_path, trust_config=trust, release_scope=scope)
    assert report["status"] == "blocked"
    assert "metadata_attempts_to_control_delivery" in report["blockers"]
    assert "metadata_package_hash_mismatch" in report["blockers"]
    assert "metadata_signing_key_untrusted" in report["blockers"]
