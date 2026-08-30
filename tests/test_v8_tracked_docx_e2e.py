from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run-v8-tracked-docx-e2e.py"


def _module():
    specification = importlib.util.spec_from_file_location("v8_tracked_docx_e2e", SCRIPT)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_validate_runtime_pair_rejects_unpaired_runtime(tmp_path: Path) -> None:
    module = _module()
    package = tmp_path / "candidate" / "msix" / "MaineFamilyLawLLM_8.0.0.0_x64.msix"
    runtime = tmp_path / "other" / "MaineFamilyLawLLM.exe"
    package.parent.mkdir(parents=True)
    runtime.parent.mkdir(parents=True)
    package.write_bytes(b"fictional-package")
    runtime.write_bytes(b"fictional-runtime")
    with pytest.raises(ValueError, match="runtime_is_not_paired_with_supplied_msix"):
        module.validate_runtime_pair(runtime, package)


def test_validate_runtime_pair_requires_docx_editor_templates(tmp_path: Path) -> None:
    module = _module()
    package = tmp_path / "candidate" / "msix" / "MaineFamilyLawLLM_8.0.0.0_x64.msix"
    runtime = tmp_path / "candidate" / "runtime" / "MaineFamilyLawLLM.exe"
    package.parent.mkdir(parents=True)
    runtime.parent.mkdir(parents=True)
    runtime.write_bytes(b"fictional-runtime")
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("MaineFamilyLawLLM.exe", b"fictional-runtime")
    with pytest.raises(ValueError, match="package_tracked_docx_assets_missing"):
        module.validate_runtime_pair(runtime, package)


def test_safe_artifact_state_omits_docx_text_and_requires_bound_fields() -> None:
    module = _module()
    payload = {
        "artifact_id": "fictional-artifact",
        "sha256": "a" * 64,
        "source_sha256": "b" * 64,
        "edit_count": 2,
        "tracked_changes": True,
        "original_preserved": True,
        "review_required": True,
        "filing_ready": False,
    }
    import io

    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(
            "word/document.xml",
            (
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:t>Transferred</w:t><w:t> schools</w:t></w:document>"
            ),
        )
        archive.writestr(
            "word/comments.xml",
            '<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:t>private note</w:t></w:comments>",
        )
    state = module.safe_artifact_state(payload, stream.getvalue())
    assert state["comments_part_present"] is True
    assert state["replacement_present"] is True
    assert "private note" not in str(state)
    assert state["filing_ready"] is False
