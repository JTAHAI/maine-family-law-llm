from pathlib import Path

from fastapi.testclient import TestClient

from legal.matter.debt_reconciliation import DebtReconciliationStore
from maine_family_law_llm import api as api_module


def _records(): return [{"evidence_id": "DEBT-001", "source_hash": "a" * 64, "title": "Fictional statement A"}, {"evidence_id": "DEBT-002", "source_hash": "b" * 64, "title": "Fictional statement B"}]


def _payload():
    return {"workspace_id": "debt_review_001", "reviewer_safe_id": "reviewer_001", "statements": [{"statement_id": "statement_001", "account_key": "account_001", "creditor_label": "Fictional creditor", "period_label": "Fictional period A", "reported_balance": "fictional balance A", "responsibility_assertion": "reviewer-entered assertion", "payment_note": "fictional payment note", "missing_period": False, "source_ref": {"record_id": "DEBT-001", "source_hash": "a" * 64}}, {"statement_id": "statement_002", "account_key": "account_001", "creditor_label": "Fictional creditor", "period_label": "Fictional period B", "reported_balance": "fictional balance B", "responsibility_assertion": "reviewer-entered assertion", "payment_note": "", "missing_period": True, "source_ref": {"record_id": "DEBT-002", "source_hash": "b" * 64}}], "user_confirmed": True}


def test_pass96_encrypted_statement_comparison_surfaces_conflicts(tmp_path: Path):
    root = tmp_path / "fictional-matter"; root.mkdir()
    store = DebtReconciliationStore(root, encryption_key="fictional-test-key")
    workspace = store.create(_payload(), records=_records())
    assert workspace["balance"] == "not_determined" and workspace["responsibility"] == "not_determined"
    assert workspace["conflicts_or_gaps"][0]["missing_period"] is True
    assert store.source("debt_review_001", "statement_002")["source"]["source_hash"] == "b" * 64
    assert "fictional balance A" not in store.path.read_text(encoding="utf-8")


def test_pass96_api_scope_source_drilldown_and_production_assets(monkeypatch, tmp_path: Path):
    matter_a, matter_b = tmp_path / "matter-a", tmp_path / "matter-b"; matter_a.mkdir(); matter_b.mkdir(); active = {"root": matter_a}
    monkeypatch.setattr(api_module, "active_case_root", lambda: active["root"]); monkeypatch.setattr(api_module, "load_case_search_records", lambda _: _records()); monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    client = TestClient(api_module.app)
    assert client.post("/api/debt-reconciliation-workspaces", json=_payload()).status_code == 200
    source = client.get("/api/debt-reconciliation-workspaces/debt_review_001/statements/statement_001/source")
    assert source.status_code == 200 and len(source.json()["source"]["source_token"]) == 64
    active["root"] = matter_b
    assert client.get("/api/debt-reconciliation-workspaces/debt_review_001").status_code == 404
    assert Path("src/maine_family_law_llm/api.py").read_bytes() == Path("maine_family_law_llm/api.py").read_bytes()
    ui = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert "Debt reconciliation" in ui and "Create comparison" in ui
