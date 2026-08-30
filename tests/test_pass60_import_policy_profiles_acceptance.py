from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from legal.matter.import_policy import ImportPolicyStore
from maine_family_law_llm import api as api_module
from maine_family_law_llm.case_corpus_builder import build_case_corpus


def test_import_profile_is_encrypted_and_cannot_weaken_global_floor(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "fictional-matter"
    root.mkdir()
    monkeypatch.setattr(api_module, "active_case_root", lambda: root)
    client = TestClient(api_module.app)
    created = client.post(
        "/api/evidence/import-policy/profiles",
        json={
            "profile_id": "strict_docs_001",
            "max_file_bytes": 1024,
            "allowed_extensions": [".txt"],
            "privacy_scan_required": True,
            "quarantine_unknown_extensions": True,
            "local_ocr_review_for_images": True,
        },
    )
    assert created.status_code == 200
    assert created.json()["profile"]["policy"]["allowed_extensions"] == [".txt"]
    encrypted = root / "18_SETTINGS" / "import-policy.json.enc"
    assert json.loads(encrypted.read_text(encoding="utf-8"))["algorithm"] == "aes-256-gcm"
    weakened = client.post(
        "/api/evidence/import-policy/profiles",
        json={"profile_id": "weak_docs_001", "allowed_extensions": [".exe"], "privacy_scan_required": False},
    )
    assert weakened.status_code == 422
    assert "weakens_global_floor" in weakened.json()["detail"]


def test_active_profile_is_enforced_before_canonical_corpus_parsing(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    source = tmp_path / "inputs"
    source.mkdir()
    (source / "allowed.txt").write_text("Fictional allowed evidence.", encoding="utf-8")
    (source / "blocked.exe").write_bytes(b"not executable in this fictional fixture")
    output = tmp_path / "output"
    matter_root = output / "fictional-policy-matter"
    matter_root.mkdir(parents=True)
    ImportPolicyStore(matter_root).create(
        {"profile_id": "txt_only_001", "max_file_bytes": 1024 * 1024, "allowed_extensions": [".txt"], "privacy_scan_required": True, "quarantine_unknown_extensions": True, "local_ocr_review_for_images": True}
    )
    result = build_case_corpus(repo_root=repo, source_roots=[source], output_root=output, case_name="fictional-policy-matter")
    proof = json.loads(result.proof_json_path.read_text(encoding="utf-8"))
    quarantined = json.loads((result.case_root / "14_QUARANTINE_UNREADABLE_UNSUPPORTED" / "problem_files.json").read_text(encoding="utf-8"))
    assert proof["source_files_discovered"] == 2
    assert proof["source_files_hashed"] == 1
    assert proof["import_policy"]["quarantined_candidate_count"] == 1
    # The corpus exposes a stable user-facing quarantine category while
    # retaining the policy reason for a reviewer/audit drill-down.
    assert any(
        item["reason"] == "unsupported" and item.get("policy_reason") == "profile_extension_not_allowed"
        for item in quarantined
    )


def test_import_policy_ui_and_api_assets_are_mirrored() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes() == (root / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes()
    assert (root / "src" / "maine_family_law_llm" / "api.py").read_bytes() == (root / "maine_family_law_llm" / "api.py").read_bytes()
    assert "/api/evidence/import-policy/profiles" in (root / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    assert "importPolicyDelegationBound" in (root / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
