from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run-v8-structured-draft-outline-e2e.py"


def _module():
    specification = importlib.util.spec_from_file_location("v8_structured_outline_e2e", SCRIPT)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_authority_provenance_requires_a_hashed_maine_source(tmp_path: Path) -> None:
    module = _module()
    manifest = tmp_path / "official_authority_store" / "source_manifest.json"
    manifest.parent.mkdir()
    manifest.write_text(
        json.dumps(
            [{
                "source_id": "fictional-source",
                "hash": "a" * 64,
                "source_class": "statute_title_index",
                "jurisdiction": "maine",
                "freshness_status": "fixture",
                "retrieved_at": "2026-08-29T00:00:00Z",
            }]
        ),
        encoding="utf-8",
    )
    provenance = module.authority_provenance(tmp_path, "fictional-source")
    assert provenance["source_hash"] == "a" * 64
    assert "source_class" in provenance
    assert str(tmp_path) not in str(provenance)


def test_runtime_pair_rejects_packaged_external_authority_data(tmp_path: Path) -> None:
    module = _module()
    package = tmp_path / "candidate" / "msix" / "MaineFamilyLawLLM_8.0.0.0_x64.msix"
    runtime = tmp_path / "candidate" / "runtime" / "MaineFamilyLawLLM.exe"
    package.parent.mkdir(parents=True)
    runtime.parent.mkdir(parents=True)
    runtime.write_bytes(b"fictional-runtime")
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("MaineFamilyLawLLM.exe", b"fictional-runtime")
        archive.writestr("official_authority_store/source_manifest.json", "[]")
    with pytest.raises(ValueError, match="package_contains_external_authority_data"):
        module.validate_runtime_pair(runtime, package)


def test_safe_outline_state_exposes_only_structural_review_state() -> None:
    module = _module()
    state = module.safe_outline_state(
        {
            "outline_id": "outline_fictional_001",
            "evidence": [{"lane": "private_matter_record", "source_hash": "a" * 64, "title": "private text"}],
            "authority": [{"lane": "official_authority", "source_hash": "b" * 64, "citation": "source text"}],
            "review_required": True,
            "filing_ready": False,
            "draft_prose_created": False,
        }
    )
    assert state["evidence_lane"] == "private_matter_record"
    assert state["authority_lane"] == "official_authority"
    assert "private text" not in str(state)
    assert "source text" not in str(state)
