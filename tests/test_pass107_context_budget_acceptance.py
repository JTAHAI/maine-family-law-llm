from pathlib import Path

from fastapi.testclient import TestClient

from legal.runtime.context_budget import ContextBudgetStore
from maine_family_law_llm import api as api_module


def _payload(budget_id: str = "budget_001"):
    return {
        "budget_id": budget_id,
        "task": "research",
        "source_refs": [
            {"source_id": "official_statute", "content_sha256": "a" * 64, "char_count": 8_000, "lane": "legal_authority"},
            {"source_id": "private_record", "content_sha256": "b" * 64, "char_count": 4_000, "lane": "private_record"},
        ],
        "verifier_requirements": {"citation": True, "quote": True, "claim": True},
        "requested_context_tokens": 99_999,
    }


def test_pass107_budgets_task_sources_hardware_and_verifiers_in_encrypted_state(tmp_path: Path):
    root = tmp_path / "fictional-matter"
    root.mkdir()
    store = ContextBudgetStore(root, encryption_key="fictional-test-key")
    result = store.create(_payload())
    budget = result["budget"]

    assert budget["status"] == "allocated_with_limits_review_required"
    assert budget["allocation"]["verifier_reserve_tokens"] == 1920
    assert budget["allocation"]["context_tokens"] <= budget["hardware"]["recommended_context_limit"]
    assert budget["review_required"] is True
    assert budget["network_used"] is False
    assert store.source("budget_001", "official_statute")["source_ref"]["lane"] == "legal_authority"
    assert "official_statute" not in store.path.read_text(encoding="utf-8")


def test_pass107_api_is_matter_scoped_and_production_assets_are_mirrored(monkeypatch, tmp_path: Path):
    first, second = tmp_path / "matter-one", tmp_path / "matter-two"
    first.mkdir()
    second.mkdir()
    active = {"root": first}
    monkeypatch.setattr(api_module, "active_case_root", lambda: active["root"])
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    client = TestClient(api_module.app)
    response = client.post("/api/runtime/context-budgets", json=_payload())
    assert response.status_code == 200
    assert response.json()["budget"]["review_required"] is True
    active["root"] = second
    assert client.get("/api/runtime/context-budgets/budget_001").status_code == 404
    assert Path("src/maine_family_law_llm/api.py").read_bytes() == Path("maine_family_law_llm/api.py").read_bytes()
    ui = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert "Adaptive context budget" in ui
    assert "/api/runtime/context-budgets" in ui
