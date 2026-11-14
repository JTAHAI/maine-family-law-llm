from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.contracts.endpoint_inventory import EndpointInventory
from app.api.production import app as production_app


ROOT = Path(__file__).resolve().parents[1]
HASH_A = "a" * 64


def test_pass181_blinded_task_preparation_is_hash_only_and_readiness_stays_blocked(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MFL_HUMAN_EVAL_ROOT", str(tmp_path / "human-evals"))
    digest = lambda token: hashlib.sha256(token.encode()).hexdigest()
    tenant_headers = {"X-Tenant-Id": "fictional-tenant"}
    operator = {**tenant_headers, "X-User-Role": "admin", "Authorization": "Bearer " + "a" * 64}
    monkeypatch.setenv("MFL_EVAL_OPERATOR_TENANT", "fictional-tenant")
    monkeypatch.setenv("MFL_EVAL_OPERATOR_BEARER_SHA256", digest("a" * 64))
    monkeypatch.setenv("MFL_EVAL_REVIEWERS_SHA256_JSON", json.dumps({"reviewer-b": digest("b" * 64), "reviewer-c": digest("c" * 64)}))
    client = TestClient(production_app)
    payload = {"case_id": "gold_case_001", "task": "citation_resolution", "artifact_sha256": HASH_A, "data_class": "synthetic"}
    assert client.post("/api/evals/human-grounded/cases", headers={"X-User-Role": "reviewer"}, json=payload).status_code == 403
    assert client.post("/api/evals/human-grounded/cases", headers={**tenant_headers, "X-User-Role": "admin"}, json=payload).status_code == 403
    created = client.post("/api/evals/human-grounded/cases", headers=operator, json=payload)
    assert created.status_code == 200, created.text
    assert created.json()["promotion_status"] == "awaiting_independent_reviews"
    route = "/api/evals/human-grounded/cases/gold_case_001/reviews"
    review = {"reviewer_id": "spoofed", "reviewer_role": "attorney", "disposition": "approved",
              "ratings": dict.fromkeys(("legal_accuracy", "grounding", "usefulness", "boundary_safety"), 5),
              "review_artifact_sha256": HASH_A}
    assert client.post(route, headers={**tenant_headers, "X-User-Role": "attorney"}, json=review).status_code == 403
    assert client.post(route, headers=operator, json=review).status_code == 403
    for char in "bc":
        response = client.post(route, headers={**tenant_headers, "Authorization": "Bearer " + char * 64}, json=review)
        assert response.status_code == 200, response.text
        assert response.json()["reviews"][-1]["reviewer_id"] == "reviewer-" + char
        assert response.json()["reviews"][-1]["reviewer_role"] == "subject_matter_reviewer"
    readiness = client.get("/api/evals/human-grounded/readiness", headers={"X-User-Role": "reviewer"})
    assert readiness.status_code == 200
    assert readiness.json()["status"] == "blocked"
    assert readiness.json()["promotion_eligible_count"] == 0
    assert readiness.json()["practice_or_unauthenticated_candidate_count"] == 1
    assert readiness.json()["private_content_stored"] is False
    raw = (tmp_path / "human-evals" / "human-eval-ledger.json").read_text(encoding="utf-8")
    assert "human_eval_encrypted" in raw and "gold_case_001" not in raw
    assert "citation_resolution" not in raw
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
