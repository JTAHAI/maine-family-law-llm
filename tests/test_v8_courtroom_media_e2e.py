from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run-v8-courtroom-media-e2e.py"


def _module():
    specification = importlib.util.spec_from_file_location("v8_courtroom_media_e2e", SCRIPT)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_courtroom_media_runner_refuses_an_unpaired_runtime(tmp_path: Path) -> None:
    module = _module()
    package = tmp_path / "candidate" / "msix" / "MaineFamilyLawLLM_8.0.0.0_x64.msix"
    runtime = tmp_path / "other" / "MaineFamilyLawLLM.exe"
    package.parent.mkdir(parents=True)
    runtime.parent.mkdir(parents=True)
    package.write_bytes(b"fictional-package")
    runtime.write_bytes(b"fictional-runtime")
    with pytest.raises(ValueError, match="runtime_is_not_paired_with_supplied_msix"):
        module.validate_runtime_pair(runtime, package)


def test_safe_session_excludes_private_note_text() -> None:
    module = _module()
    state = module.safe_session(
        {
            "session_id": "fictional_session",
            "media_id": "fictional_audio",
            "source_hash": "a" * 64,
            "review_required": True,
            "private_notes_separate": True,
            "private_note": "must not surface",
        }
    )
    assert state["review_required"] is True
    assert "must not surface" not in str(state)
