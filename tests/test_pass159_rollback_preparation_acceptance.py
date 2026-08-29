from __future__ import annotations

import json
import zipfile
from pathlib import Path

from legal.release.msix_upgrade_qualification import sha256_file
from legal.release.rollback_preparation import build_rollback_preparation, validate_rollback_rehearsal


def _package(path: Path, *, version: str, publisher: str = "CN=Fictional") -> None:
    manifest = f'''<?xml version="1.0" encoding="utf-8"?><Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"><Identity Name="TAHAIWebServices.MaineFamilyLawLLM" Publisher="{publisher}" Version="{version}" ProcessorArchitecture="x64"/><Properties/><Resources><Resource Language="en-us"/></Resources><Applications><Application Id="MaineFamilyLawLLM" Executable="MaineFamilyLawLLM.exe" EntryPoint="Windows.FullTrustApplication"/></Applications></Package>'''
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("AppxManifest.xml", manifest)


def test_pass159_prepares_hash_bound_isolated_rollback_with_verified_fictional_backup(tmp_path: Path) -> None:
    rollback = tmp_path / "MaineFamilyLawLLM_7.0.1.0_x64.msix"; candidate = tmp_path / "MaineFamilyLawLLM_8.0.0.0_x64.msix"
    _package(rollback, version="7.0.1.0"); _package(candidate, version="8.0.0.0")
    backup = tmp_path / "backup.json"
    backup.write_text(json.dumps({"status": "pass", "candidate_package_sha256": sha256_file(candidate), "backup_sha256": "a" * 64, "isolated_recovery_restore": "pass", "active_matter_unchanged": True, "synthetic_data_only": True}), encoding="utf-8")
    plan = build_rollback_preparation(candidate_package=candidate, rollback_package=rollback, backup_evidence=backup)
    assert plan["status"] == "prepared_for_isolated_rollback_rehearsal"
    assert plan["safety_boundary"]["automatic_rollback_allowed"] is False
    assert all("\\" not in step["requirement"] for step in plan["required_isolated_steps"])
    result = validate_rollback_rehearsal(
        plan,
        {
            "candidate_sha256": plan["candidate"]["sha256"],
            "rollback_sha256": plan["rollback"]["sha256"],
            "synthetic_data_only": True,
            "active_matter_unchanged": True,
            "steps": [{"id": step["id"], "status": "pass"} for step in plan["required_isolated_steps"]],
        },
    )
    assert result["status"] == "pass"


def test_pass159_blocks_missing_backup_evidence_and_package_identity_change(tmp_path: Path) -> None:
    rollback = tmp_path / "MaineFamilyLawLLM_7.0.1.0_x64.msix"; candidate = tmp_path / "MaineFamilyLawLLM_8.0.0.0_x64.msix"
    _package(rollback, version="7.0.1.0", publisher="CN=Older"); _package(candidate, version="8.0.0.0")
    plan = build_rollback_preparation(candidate_package=candidate, rollback_package=rollback)
    assert plan["status"] == "blocked"
    assert "isolated_backup_recovery_evidence_missing" in plan["blockers"]
    assert "rollback_package_publisher_changed" in plan["blockers"]
