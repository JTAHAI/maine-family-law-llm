from __future__ import annotations

import json
from pathlib import Path

import pytest

from legal.workflow_skills import SkillRegistry, SkillValidationError


def test_bundled_skill_registry_is_valid() -> None:
    root = Path(__file__).resolve().parents[1]
    registry = SkillRegistry.from_directory(root / "configs" / "workflow_skills")
    report = registry.validate_dependencies()
    assert report.status == "pass"
    assert report.skill_count == 5
    qc = registry.get("maine-qc-independent-review")
    assert qc is not None
    assert qc.user_role == "independent_qc"
    assert qc.network_allowed is False


def test_skill_registry_rejects_network_without_permission(tmp_path: Path) -> None:
    payload = {
        "name": "maine-test-invalid",
        "version": "1.0.0",
        "title": "Invalid network skill",
        "description": "Should be rejected.",
        "module": "test_module",
        "user_role": "matter_worker",
        "phases": ["intake"],
        "categories": ["test"],
        "permissions": ["read_files"],
        "network_allowed": True,
    }
    (tmp_path / "invalid.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SkillValidationError, match="network_allowed"):
        SkillRegistry.from_directory(tmp_path)


def test_skill_registry_rejects_symlink_manifest(tmp_path: Path) -> None:
    target = tmp_path / "outside.json"
    target.write_text("{}", encoding="utf-8")
    directory = tmp_path / "registry"
    directory.mkdir()
    link = directory / "linked.json"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(SkillValidationError, match="symlink"):
        SkillRegistry.from_directory(directory)


def test_skill_registry_rejects_symlink_root(tmp_path: Path) -> None:
    target = tmp_path / "registry-target"
    target.mkdir()
    link = tmp_path / "registry-link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(SkillValidationError, match="symlink registry roots"):
        SkillRegistry.from_directory(link)


def test_skill_registry_caps_manifest_count(tmp_path: Path) -> None:
    for index in range(257):
        (tmp_path / f"skill-{index:03d}.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SkillValidationError, match="too many manifests"):
        SkillRegistry.from_directory(tmp_path)
