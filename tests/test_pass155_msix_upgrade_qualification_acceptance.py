from __future__ import annotations

import zipfile
from pathlib import Path

from legal.release.msix_upgrade_qualification import build_upgrade_execution_contract, validate_runner_result


def _package(path: Path, *, version: str, name: str = "TAHAIWebServices.MaineFamilyLawLLM", publisher: str = "CN=Fictional") -> None:
    manifest = f'''<?xml version="1.0" encoding="utf-8"?><Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"><Identity Name="{name}" Publisher="{publisher}" Version="{version}" ProcessorArchitecture="x64"/><Properties/><Resources><Resource Language="en-us"/></Resources><Applications><Application Id="MaineFamilyLawLLM" Executable="MaineFamilyLawLLM.exe" EntryPoint="Windows.FullTrustApplication"/></Applications></Package>'''
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("AppxManifest.xml", manifest)


def test_pass155_hash_binds_compatible_prior_and_candidate_to_isolated_contract(tmp_path: Path) -> None:
    prior = tmp_path / "MaineFamilyLawLLM_7.0.1.0_x64.msix"; candidate = tmp_path / "MaineFamilyLawLLM_8.0.0.0_x64.msix"
    _package(prior, version="7.0.1.0"); _package(candidate, version="8.0.0.0")
    contract = build_upgrade_execution_contract(prior, candidate)
    assert contract["status"] == "ready_for_isolated_execution"
    assert contract["prior"]["sha256"] != contract["candidate"]["sha256"]
    assert contract["candidate"]["identity"]["language"] == "en-us"
    assert contract["safety_boundary"]["modifies_user_store_package"] is False
    result = validate_runner_result(contract, {"prior_sha256": contract["prior"]["sha256"], "candidate_sha256": contract["candidate"]["sha256"], "steps": [{"id": identifier, "status": "pass"} for identifier in contract["required_isolated_steps"]]})
    assert result["status"] == "pass"


def test_pass155_refuses_identity_substitution_and_incomplete_runner_evidence(tmp_path: Path) -> None:
    prior = tmp_path / "MaineFamilyLawLLM_7.0.1.0_x64.msix"; candidate = tmp_path / "MaineFamilyLawLLM_8.0.0.0_x64.msix"
    _package(prior, version="7.0.1.0"); _package(candidate, version="8.0.0.0", publisher="CN=Different")
    contract = build_upgrade_execution_contract(prior, candidate)
    assert contract["status"] == "blocked" and "package_identity_publisher_changed" in contract["blockers"]
    incomplete = validate_runner_result(contract, {"prior_sha256": "0" * 64, "candidate_sha256": "1" * 64, "steps": []})
    assert incomplete["status"] == "blocked"
    assert "runner_required_steps_incomplete" in incomplete["blockers"]
