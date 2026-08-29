from pathlib import Path

from fastapi.testclient import TestClient

from legal.matter.financial_affidavit import FinancialAffidavitStore
from maine_family_law_llm import api as api_module


def _records():
    return [{"evidence_id": "FIN-001", "source_hash": "a" * 64, "title": "Fictional pay record"}, {"evidence_id": "FIN-002", "source_hash": "b" * 64, "title": "Fictional statement"}]


def _payload():
    return {"workspace_id": "financial_review_001", "reviewer_safe_id": "reviewer_001", "entries": [{"entry_id": "entry_001", "category": "income", "label": "Fictional income", "reported_value": "fictional amount A", "reconciliation_key": "income_001", "source_ref": {"record_id": "FIN-001", "source_hash": "a" * 64}}, {"entry_id": "entry_002", "category": "income", "label": "Fictional income comparison", "reported_value": "fictional amount B", "reconciliation_key": "income_001", "source_ref": {"record_id": "FIN-002", "source_hash": "b" * 64}}, {"entry_id": "entry_003", "category": "debt", "label": "Fictional debt", "reported_value": "under review", "reconciliation_key": "debt_001", "source_ref": {"record_id": "FIN-002", "source_hash": "b" * 64}}], "unknowns": ["Fictional unknown period"], "user_confirmed": True}


def test_pass94_encrypted_source_bound_rows_surface_mismatch(tmp_path: Path):
    root = tmp_path / "fictional-matter"
    root.mkdir()
    store = FinancialAffidavitStore(root, encryption_key="fictional-test-key")
    workspace = store.create(_payload(), records=_records())
    assert workspace["totals"] == "not_calculated" and workspace["affidavit_completion"] == "not_available"
    assert workspace["reconciliation_mismatches"][0]["reconciliation_key"] == "income_001"
    assert store.source("financial_review_001", "entry_002")["source"]["source_hash"] == "b" * 64
    assert "fictional amount A" not in store.path.read_text(encoding="utf-8")


def test_pass94_api_scope_source_drilldown_and_production_assets(monkeypatch, tmp_path: Path):
    matter_a, matter_b = tmp_path / "matter-a", tmp_path / "matter-b"
    matter_a.mkdir()
    matter_b.mkdir()
    active = {"root": matter_a}
    monkeypatch.setattr(api_module, "active_case_root", lambda: active["root"])
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _: _records())
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    client = TestClient(api_module.app)
    assert client.post("/api/financial-affidavit-workspaces", json=_payload()).status_code == 200
    source = client.get("/api/financial-affidavit-workspaces/financial_review_001/entries/entry_001/source")
    assert source.status_code == 200 and len(source.json()["source"]["source_token"]) == 64
    active["root"] = matter_b
    assert client.get("/api/financial-affidavit-workspaces/financial_review_001").status_code == 404
    assert Path("src/maine_family_law_llm/api.py").read_bytes() == Path("maine_family_law_llm/api.py").read_bytes()
    text = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert "Financial affidavit review" in text and "Save review workspace" in text
