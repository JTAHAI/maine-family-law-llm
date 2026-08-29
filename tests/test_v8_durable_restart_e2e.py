from __future__ import annotations

from pathlib import Path

import pytest
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def _module():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "v8_durable_restart_e2e", ROOT / "scripts" / "run-v8-durable-restart-e2e.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_validate_runtime_pair_rejects_unpaired_runtime(tmp_path: Path) -> None:
    module = _module()
    package = tmp_path / "candidate" / "msix" / "MaineFamilyLawLLM_8.0.0.0_x64.msix"
    runtime = tmp_path / "other" / "MaineFamilyLawLLM.exe"
    package.parent.mkdir(parents=True)
    runtime.parent.mkdir(parents=True)
    package.write_bytes(b"package")
    runtime.write_bytes(b"runtime")
    with pytest.raises(ValueError, match="runtime_is_not_paired_with_supplied_msix"):
        module.validate_runtime_pair(runtime, package)


def test_safe_document_state_redacts_content_and_retains_integrity_fields() -> None:
    module = _module()
    state = module.safe_document_state(
        {
            "document_id": "doc-1",
            "current_revision_id": "rev-2",
            "original_revision_id": "rev-1",
            "status": "review_required",
            "review_required": True,
            "original_preserved": True,
            "content": "fictional confidential text",
        }
    )
    assert state["document_id"] == "doc-1"
    assert state["review_required"] is True
    assert state["original_preserved"] is True
    assert "content" not in state
    assert len(state["content_sha256"]) == 64


@pytest.mark.parametrize("contents", [b"fictional runtime", b"stale runtime", None])
def test_runtime_pair_requires_bytes_in_the_exact_archive(tmp_path, contents):
    module = _module()
    package = tmp_path / "candidate/msix/fictional.msix"
    runtime = tmp_path / "candidate/runtime/MaineFamilyLawLLM.exe"
    package.parent.mkdir(parents=True)
    runtime.parent.mkdir(parents=True)
    runtime.write_bytes(b"fictional runtime")
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("MaineFamilyLawLLM.exe" if contents else "other.exe", contents or b"absent")
    if contents == b"fictional runtime":
        module.validate_runtime_pair(runtime, package)
    else:
        with pytest.raises(ValueError, match="runtime_bytes_differ|package_executable_missing"):
            module.validate_runtime_pair(runtime, package)


def test_restart_evidence_never_claims_installed_or_os_network_proof():
    source = (ROOT / "scripts/run-v8-durable-restart-e2e.py").read_text(encoding="utf-8")
    assert '"local_only_zero_network_proven": False' in source
    assert '"installed_package_tested": False' in source
    assert '"zero_external_connections"' not in source
    assert "helper.verify_runtime_instance(first_base" in source
    assert "helper.verify_runtime_instance(second_base" in source
