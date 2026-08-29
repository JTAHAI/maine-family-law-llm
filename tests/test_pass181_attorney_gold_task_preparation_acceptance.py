from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.contracts.endpoint_inventory import EndpointInventory
from app.api.production import app as production_app


ROOT = Path(__file__).resolve().parents[1]
HASH_A = "a" * 64


def test_pass181_blinded_task_preparation_is_hash_only_and_readiness_stays_blocked(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MFL_HUMAN_EVAL_ROOT", str(tmp_path / "human-evals"))
    client = TestClient(production_app)
    payload = {"case_id": "gold_case_001", "task": "citation_resolution", "artifact_sha256": HASH_A, "data_class": "synthetic"}
    assert client.post("/api/evals/human-grounded/cases", headers={"X-User-Role": "reviewer"}, json=payload).status_code == 403
    created = client.post("/api/evals/human-grounded/cases", headers={"X-User-Role": "admin"}, json=payload)
    assert created.status_code == 200, created.text
    assert created.json()["promotion_status"] == "awaiting_independent_reviews"
    readiness = client.get("/api/evals/human-grounded/readiness", headers={"X-User-Role": "reviewer"})
    assert readiness.status_code == 200
    assert readiness.json()["status"] == "blocked"
    assert readiness.json()["private_content_stored"] is False
    raw = (tmp_path / "human-evals" / "human-eval-ledger.json").read_text(encoding="utf-8")
    assert "citation_resolution" in raw and "gold_case_001" in raw
    assert "Fictional matter" not in raw


def test_pass181_shipped_control_and_canonical_inventory_keep_human_boundary_visible() -> None:
    inventory = EndpointInventory().required_paths()
    assert ("POST", "/api/evals/human-grounded/cases") in inventory
    assert ("GET", "/api/evals/human-grounded/readiness") in inventory
    for relative in ("src/maine_family_law_llm/ui/workbench.js", "maine_family_law_llm/ui/workbench.js"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "attorney-gold-task-control" in text
        assert "/api/evals/human-grounded/cases" in text
        assert "Not attorney reviewed" in text
        assert "cannot verify a license" in text
