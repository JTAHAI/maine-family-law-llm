from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from legal.matter.exhibit_workbench import ExhibitWorkbenchStore
from maine_family_law_llm import api as api_module


def _candidate_payload(exhibit_id: str = "exhibit_001") -> dict[str, object]:
    return {
        "candidates": [
            {
                "exhibit_id": exhibit_id,
                "original_record_id": "fictional_record_001",
                "original_hash": "a" * 64,
                "description": "Fictional school attendance record.",
                "page_count": 2,
            }
        ]
    }


def test_pass68_creates_encrypted_source_bound_review_prompts_without_legal_conclusions(tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"
    case_root.mkdir()
    store = ExhibitWorkbenchStore(case_root, encryption_key="fictional-test-key")
    store.add_candidates(_candidate_payload())
    checklist = store.create_admission_checklist(
        {
            "checklist_id": "admission_001",
            "exhibit_id": "exhibit_001",
            "reviewer_safe_id": "reviewer_001",
            "reviewer_note": "Fictional reviewer context only.",
        }
    )
    assert set(checklist["categories"]) == {
        "foundation_questions",
        "authenticity_materials",
        "objection_candidates",
        "missing_proof",
    }
    assert all(row[0]["state"] == "unresolved" for row in checklist["categories"].values())
    assert checklist["admissibility"] == "not_determined"
    source = store.admission_checklist_source("admission_001")
    assert source["source"] == {
        "record_id": "fictional_record_001",
        "source_hash": "a" * 64,
        "description": "Fictional school attendance record.",
    }
    assert "Fictional reviewer context only." not in store.path.read_text(encoding="utf-8")
    assert len(store.receipt()["admission_checklists_hash"]) == 64


def test_pass68_api_enforces_active_matter_scope_and_exposes_only_review_required_source(monkeypatch, tmp_path: Path) -> None:
    matter_a = tmp_path / "fictional-matter-a"
    matter_b = tmp_path / "fictional-matter-b"
    matter_a.mkdir()
    matter_b.mkdir()
    active = {"root": matter_a}
    monkeypatch.setattr(api_module, "active_case_root", lambda: active["root"])
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    client = TestClient(api_module.app)
    assert client.post("/api/exhibits/candidates", json=_candidate_payload()).status_code == 200
    created = client.post(
        "/api/exhibits/admission-checklists",
        json={
            "checklist_id": "admission_001",
            "exhibit_id": "exhibit_001",
            "reviewer_safe_id": "reviewer_001",
        },
    )
    assert created.status_code == 200
    assert created.json()["review_required"] is True and created.json()["local_only"] is True
    source = client.get("/api/exhibits/admission-checklists/admission_001/source")
    assert source.status_code == 200
    assert source.json()["source_hash"] == "a" * 64
    assert source.json()["admissibility"] == "not_determined"
    active["root"] = matter_b
    assert client.get("/api/exhibits/admission-checklists/admission_001").status_code == 404


def test_pass68_ships_mirrored_production_ui_with_source_drilldown() -> None:
    src = Path("src/maine_family_law_llm/ui/workbench.js")
    mirror = Path("maine_family_law_llm/ui/workbench.js")
    assert src.read_bytes() == mirror.read_bytes()
    source = src.read_text(encoding="utf-8")
    assert "Exhibit admission-preparation checklist" in source
    assert "/api/exhibits/admission-checklists" in source
    assert "Inspect selected checklist source" in source
    assert "id:'open_exhibits_workspace'" in source
    assert "run:()=>openExhibitsWorkspace()" in source
