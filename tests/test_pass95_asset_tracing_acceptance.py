from pathlib import Path

from fastapi.testclient import TestClient

from legal.matter.asset_tracing import AssetTracingStore
from maine_family_law_llm import api as api_module


def _records(): return [{"evidence_id": "ASSET-001", "source_hash": "a" * 64, "title": "Fictional asset record"}]


def _payload():
    return {"ledger_id": "asset_ledger_001", "reviewer_safe_id": "reviewer_001", "assets": [{"asset_id": "asset_001", "label": "Fictional asset", "claimed_source": "Reviewer-entered claimed source", "valuation_date": "2026-01-01", "transfers": [{"transfer_id": "transfer_001", "date_candidate": "2026-02-01", "description": "Reviewer-entered transfer note"}], "characterization_assertion": "Reviewer-entered characterization assertion", "characterization_disputed": True, "supporting_records": [{"record_id": "ASSET-001", "source_hash": "a" * 64}]}], "user_confirmed": True}


def test_pass95_encrypted_disputed_asset_trace(tmp_path: Path):
    root = tmp_path / "fictional-matter"; root.mkdir()
    store = AssetTracingStore(root, encryption_key="fictional-test-key")
    ledger = store.create(_payload(), records=_records())
    assert ledger["characterization"] == "not_determined" and ledger["assets"][0]["characterization_disputed"] is True
    assert store.source("asset_ledger_001", "asset_001", "ASSET-001")["source"]["source_hash"] == "a" * 64
    assert "Reviewer-entered transfer note" not in store.path.read_text(encoding="utf-8")


def test_pass95_api_scope_source_drilldown_and_production_assets(monkeypatch, tmp_path: Path):
    matter_a, matter_b = tmp_path / "matter-a", tmp_path / "matter-b"; matter_a.mkdir(); matter_b.mkdir(); active = {"root": matter_a}
    monkeypatch.setattr(api_module, "active_case_root", lambda: active["root"]); monkeypatch.setattr(api_module, "load_case_search_records", lambda _: _records()); monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    client = TestClient(api_module.app)
    assert client.post("/api/asset-tracing-ledgers", json=_payload()).status_code == 200
    source = client.get("/api/asset-tracing-ledgers/asset_ledger_001/assets/asset_001/sources/ASSET-001")
    assert source.status_code == 200 and len(source.json()["source"]["source_token"]) == 64
    active["root"] = matter_b
    assert client.get("/api/asset-tracing-ledgers/asset_ledger_001").status_code == 404
    assert Path("src/maine_family_law_llm/api.py").read_bytes() == Path("maine_family_law_llm/api.py").read_bytes()
    ui = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert "Asset tracing ledger" in ui and "Create tracing ledger" in ui
