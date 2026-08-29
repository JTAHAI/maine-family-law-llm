from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run-v8-exhibit-workbench-e2e.py"


def _module():
    specification = importlib.util.spec_from_file_location("v8_exhibit_workbench_e2e", SCRIPT)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_exhibit_runner_refuses_runtime_not_paired_with_package(tmp_path: Path) -> None:
    module = _module()
    package = tmp_path / "candidate" / "msix" / "MaineFamilyLawLLM_8.0.0.0_x64.msix"
    runtime = tmp_path / "other" / "MaineFamilyLawLLM.exe"
    package.parent.mkdir(parents=True)
    runtime.parent.mkdir(parents=True)
    package.write_bytes(b"fictional-package")
    runtime.write_bytes(b"fictional-runtime")
    with pytest.raises(ValueError, match="runtime_is_not_paired_with_supplied_msix"):
        module.validate_runtime_pair(runtime, package)


def test_safe_checklist_exposes_states_but_not_prompt_text() -> None:
    module = _module()
    result = module.safe_checklist(
        {
            "checklist_id": "fictional_001",
            "exhibit_id": "fictional_exhibit",
            "categories": {"foundation_questions": [{"state": "unresolved", "review_prompt": "private words"}]},
            "review_required": True,
            "admissibility": "not_determined",
            "authenticity": "not_determined",
            "foundation": "not_determined",
        }
    )
    assert result["unresolved_prompt_count"] == 1
    assert "private words" not in str(result)
