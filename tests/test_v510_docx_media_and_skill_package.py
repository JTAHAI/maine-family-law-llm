from __future__ import annotations

import importlib.util
import json
import os
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _valid_manifest(name: str) -> dict[str, object]:
    return {
        "name": name,
        "version": "1.0.0",
        "title": "Test skill",
        "description": "Data-only test workflow skill.",
        "module": "records_test",
        "user_role": "matter_worker",
        "phases": ["record_organization"],
        "categories": ["testing"],
        "permissions": ["read_files", "write_derived_files"],
        "dependencies": [],
        "output_contract": "test_v1",
        "review_required": True,
        "network_allowed": False,
        "source_requirements": ["test_input"],
    }


def test_docx_media_extraction_is_bounded_and_uses_safe_basename(tmp_path: Path) -> None:
    module = _load_script("extract-docx-media.py")
    docx = tmp_path / "sample.docx"
    with zipfile.ZipFile(docx, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/media/../../image.png", b"not reached")
        archive.writestr("word/media/logo.png", b"image")
    output = tmp_path / "out"
    items = module.extract_media(docx, output)
    assert len(items) == 2
    assert all(Path(item.output_path).parent == output for item in items)
    assert not (tmp_path / "image.png").exists()


def test_skill_packager_rejects_executables(tmp_path: Path) -> None:
    if os.name == "nt":
        pytest.skip("Windows does not preserve POSIX executable mode bits for data files")
    module = _load_script("package-workflow-skill.py")
    skill = tmp_path / "maine-test-executable"
    skill.mkdir()
    (skill / "manifest.json").write_text(
        json.dumps(_valid_manifest(skill.name)), encoding="utf-8"
    )
    script = skill / "run.txt"
    script.write_text("do not execute", encoding="utf-8")
    script.chmod(0o755)
    with pytest.raises(module.SkillPackageError, match="executable"):
        module.package_skill(skill, tmp_path / "out.skill")


def test_skill_packager_creates_deterministic_data_only_archive(tmp_path: Path) -> None:
    module = _load_script("package-workflow-skill.py")
    skill = tmp_path / "maine-test-skill"
    skill.mkdir()
    (skill / "manifest.json").write_text(
        json.dumps(_valid_manifest(skill.name)), encoding="utf-8"
    )
    (skill / "README.md").write_text("review required", encoding="utf-8")
    first = module.package_skill(skill, tmp_path / "one.skill")
    second = module.package_skill(skill, tmp_path / "two.skill")
    assert first["sha256"] == second["sha256"]


def test_skill_packager_rejects_invalid_manifest(tmp_path: Path) -> None:
    module = _load_script("package-workflow-skill.py")
    skill = tmp_path / "maine-invalid"
    skill.mkdir()
    (skill / "manifest.json").write_text(json.dumps({"name": "x"}), encoding="utf-8")
    with pytest.raises(module.SkillPackageError, match="invalid workflow manifest"):
        module.package_skill(skill, tmp_path / "out.skill")
