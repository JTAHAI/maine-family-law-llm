from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from maine_family_law_llm import api as api_module


def _records() -> list[dict[str, object]]:
    return [
        {
            "evidence_id": "ORDER-ONE",
            "title": "Fictional order",
            "source_type": "order",
            "source_hash": "a" * 64,
            "text": "Fictional order text identifies a review question.",
            "page_number": 1,
        },
        {
            "evidence_id": "EMAIL-ONE",
            "title": "Fictional email",
            "source_type": "email",
            "source_hash": "b" * 64,
            "text": "Fictional email supplies a competing account.",
            "page_number": 2,
        },
    ]


def _client(monkeypatch, case_root: Path, rows: list[dict[str, object]] | None = None) -> TestClient:
    monkeypatch.setattr(api_module, "active_case_root", lambda: case_root)
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _root: rows or _records())
    return TestClient(api_module.app)


def _item(item_id: str, role: str, record_id: str, authority: str = "") -> dict[str, str]:
    return {
        "item_id": item_id,
        "issue_id": "PARENTING-TIME",
        "issue_label": "Fictional parenting-time issue",
        "proof_item_id": f"proof-{item_id}",
        "proof_label": f"Fictional proof item {item_id}",
        "evidence_role": role,
        "source_record_id": record_id,
        "authority_candidate": authority,
    }


def test_issue_proof_matrix_records_support_contradiction_and_missing_proof(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"; case_root.mkdir()
    client = _client(monkeypatch, case_root)
    support = client.post("/api/evidence/issue-proof-matrix/items", json=_item("SUPPORT", "supports", "ORDER-ONE", "19-A M.R.S. § 1653"))
    contradiction = client.post("/api/evidence/issue-proof-matrix/items", json=_item("CONTRADICTION", "contradicts", "EMAIL-ONE"))
    missing = client.post("/api/evidence/issue-proof-matrix/items", json=_item("MISSING", "missing_proof", "ORDER-ONE"))
    assert support.status_code == contradiction.status_code == missing.status_code == 200
    assert support.json()["item"]["authority_candidate_status"] == "unverified_candidate"
    assert support.json()["item"]["authority_current_law_determined"] is False
    matrix = client.get("/api/evidence/issue-proof-matrix")
    assert matrix.status_code == 200
    issue = matrix.json()["issues"][0]
    assert issue["supports"] == issue["contradicts"] == issue["missing_proof"] == 1
    assert matrix.json()["review_required"] is True
    assert "does not determine" in matrix.json()["notice"]
    source = client.get("/api/evidence/issue-proof-matrix/items/SUPPORT/source")
    assert source.status_code == 200 and len(source.json()["source"]["source_token"]) == 64


def test_issue_proof_matrix_rejects_foreign_records_and_bad_roles(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"; case_root.mkdir()
    client = _client(monkeypatch, case_root)
    foreign = client.post("/api/evidence/issue-proof-matrix/items", json=_item("FOREIGN", "supports", "OTHER-MATTER"))
    bad_role = client.post("/api/evidence/issue-proof-matrix/items", json=_item("BAD", "legal_element_satisfied", "ORDER-ONE"))
    assert foreign.status_code == 400 and foreign.json()["detail"] == "source_record_not_found_in_active_matter"
    assert bad_role.status_code == 400 and bad_role.json()["detail"] == "issue_proof_evidence_role_invalid"


def test_issue_proof_matrix_review_is_append_only_and_hash_checked(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"; case_root.mkdir()
    client = _client(monkeypatch, case_root)
    created = client.post("/api/evidence/issue-proof-matrix/items", json=_item("ROW", "qualifies", "ORDER-ONE"))
    assert created.status_code == 200
    reviewed = client.post("/api/evidence/issue-proof-matrix/items/ROW/review", json={"review_state": "reviewed_with_qualification", "reviewer_notes": "Fictional reviewer note."})
    assert reviewed.status_code == 200 and len(reviewed.json()["item"]["history"]) == 2
    changed_rows = _records(); changed_rows[0] = {**changed_rows[0], "source_hash": "c" * 64}
    changed = _client(monkeypatch, case_root, changed_rows).get("/api/evidence/issue-proof-matrix/items/ROW/source")
    assert changed.status_code == 400 and changed.json()["detail"] == "issue_proof_source_hash_mismatch"


def test_issue_proof_matrix_ui_is_in_both_shipped_workbench_copies() -> None:
    root = Path(__file__).resolve().parents[1]
    src_ui = (root / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    mirror_ui = (root / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    assert src_ui == mirror_ui
    assert "installIssueProofMatrixControl" in src_ui
    assert "/api/evidence/issue-proof-matrix/items" in src_ui
    assert "authority candidate unverified" in src_ui
