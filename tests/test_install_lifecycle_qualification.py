from __future__ import annotations

import json
from pathlib import Path

from maine_family_law_llm.install_lifecycle_qualification import (
    _build_prior_profile_fixtures,
    _inventory_fixture,
    _migrate_synthetic_profile,
    _tree_manifest,
    write_json,
)


def test_inventory_fixture_and_tree_manifest_detect_generated_files(tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    case_root.mkdir()
    (case_root / "one.pdf").write_bytes(b"%PDF-1.4 synthetic")
    (case_root / "one.docx").write_bytes(b"PK\x03\x04 synthetic")
    (case_root / "nested").mkdir()
    (case_root / "nested" / "image.png").write_bytes(b"\x89PNG synthetic")

    inventory = _inventory_fixture(case_root)
    manifest = _tree_manifest(case_root)

    assert inventory["pdf_count"] == 1
    assert inventory["docx_count"] == 1
    assert inventory["image_count"] == 1
    assert inventory["file_count"] == 3
    assert manifest["file_count"] == 3
    assert len(manifest["manifest_sha256"]) == 64


def test_migration_helper_preserves_matter_identity_and_records_rollback(tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    case_root.mkdir()
    (case_root / "matter.txt").write_text("synthetic matter", encoding="utf-8")
    localappdata = tmp_path / "localappdata"
    prior = _build_prior_profile_fixtures(case_root, localappdata)
    migrated = _migrate_synthetic_profile(
        prior,
        package_version="6.0.4.0",
        package_sha256="a" * 64,
        package_path=r"C:\\Program Files\\WindowsApps\\MaineFamilyLawLLM.exe",
    )

    assert migrated["schema_version"] == "6.0.4.0"
    assert migrated["migration_passed"] is True
    assert migrated["migrated_fields"]["preserved_matter_id"] == case_root.name
    assert migrated["rollback_preparation"]["rollback_ready"] is True


def test_v700_migration_preserves_v604_profile_and_rollback_metadata(tmp_path: Path) -> None:
    prior = {
        "schema_version": "6.0.4.0",
        "package_sha256": "6" * 64,
        "matter_id": "fictional-v604-matter",
        "settings": {"local_only": True, "authority_root": "external"},
        "drafts": ["draft-1"],
        "revision_history": ["revision-1"],
        "sidecars": {"slice_21_31": "preserved_hidden"},
    }
    migrated = _migrate_synthetic_profile(
        prior,
        package_version="7.0.0.0",
        package_sha256="7" * 64,
        package_path=r"C:\Program Files\WindowsApps\MaineFamilyLawLLM.exe",
    )

    assert migrated["schema_version"] == "7.0.0.0"
    assert migrated["matter_id"] == prior["matter_id"]
    assert migrated["drafts"] == prior["drafts"]
    assert migrated["revision_history"] == prior["revision_history"]
    assert migrated["sidecars"] == prior["sidecars"]
    assert migrated["settings"]["local_only"] is True
    assert migrated["rollback_preparation"]["rollback_package_version"] == "6.0.4.0"
    assert migrated["rollback_preparation"]["rollback_package_sha256"] == "6" * 64


def test_write_json_roundtrips_evidence(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    payload = {"status": "pass", "sha256": "b" * 64}
    write_json(evidence, payload)
    assert json.loads(evidence.read_text(encoding="utf-8")) == payload
