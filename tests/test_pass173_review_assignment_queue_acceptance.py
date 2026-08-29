from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.contracts.endpoint_inventory import EndpointInventory
from app.api.production import app as production_app
from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.matter.review_assignments import ReviewAssignmentStore
from maine_family_law_llm import api as local_api


ROOT = Path(__file__).resolve().parents[1]
HASH = "b" * 64


def _payload() -> dict:
    return {
        "assignment_id": "assignment_001", "assignee_safe_id": "reviewer_001", "required_role": "reviewer", "due_date": "2027-06-15",
        "scope_kind": "record", "scope_id": "record_001", "scope_hash": HASH,
        "required_evidence": [{"evidence_id": "evidence_001", "evidence_hash": HASH, "kind": "record"}],
        "instructions": "Inspect the fictional record and exact provenance before completing this review task.",
    }


def test_pass173_assignment_is_encrypted_scoped_evidence_bound_and_not_approval(tmp_path: Path) -> None:
    store = ReviewAssignmentStore(tmp_path, encryption_key="0123456789abcdef")
    created = store.create(_payload())
    assert created["external_messaging"] is False and created["scope"]["source_drill_down"]["route"] == "/api/records/record_001/integrity"
    with pytest.raises(IntakeWorkbenchError, match="review_assignment_assignee_mismatch"):
        store.claim("assignment_001", {"reviewer_safe_id": "reviewer_002"})
    claimed = store.claim("assignment_001", {"reviewer_safe_id": "reviewer_001"})
    assert claimed["status"] == "claimed_review_required"
    with pytest.raises(IntakeWorkbenchError, match="assignment_required_evidence_unacknowledged"):
        store.complete("assignment_001", {"reviewer_safe_id": "reviewer_001", "acknowledged_evidence_ids": [], "completion_note": "Fictional completion note."})
    completed = store.complete("assignment_001", {"reviewer_safe_id": "reviewer_001", "acknowledged_evidence_ids": ["evidence_001"], "completion_note": "Fictional completion note; not an approval."})
    assert completed["status"] == "completed_review_required" and completed["completion_is_not_approval"] is True
    assert store.inventory()["assignments"] == []
    assert len(store.inventory(include_completed=True)["assignments"]) == 1
    encrypted = next((tmp_path / "46_REVIEW_ASSIGNMENTS").glob("*.enc"))
    assert b"fictional record" not in encrypted.read_bytes().lower()
    history = store._load()["history"]
    assert all(row["previous_hash"] == (history[index - 1]["hash"] if index else "") for index, row in enumerate(history))


def test_pass173_production_assignment_queue_role_boundary_and_shipped_ui(tmp_path: Path, monkeypatch) -> None:
    matter = tmp_path / "fictional-matter"; matter.mkdir()
    monkeypatch.setattr(local_api, "active_case_root", lambda: matter)
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-acceptance-passphrase")
    monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "idempotency"))
    client = TestClient(production_app)
    headers = {"X-User-Role": "reviewer", "X-Tenant-Id": "fictional-tenant", "X-MFLL-Client-Session": "d" * 32}
    denied = client.post("/api/review-assignments", headers={**headers, "X-User-Role": "viewer", "X-MFLL-Idempotency-Key": "pass173-viewer-denied"}, json=_payload())
    assert denied.status_code == 403
    created = client.post("/api/review-assignments", headers={**headers, "X-MFLL-Idempotency-Key": "pass173-create"}, json=_payload())
    assert created.status_code == 200, created.text
    queue = client.get("/api/review-assignments", headers=headers)
    assert queue.status_code == 200 and queue.json()["external_messaging"] is False
    claimed = client.post("/api/review-assignments/assignment_001/claim", headers={**headers, "X-MFLL-Idempotency-Key": "pass173-claim"}, json={"reviewer_safe_id": "reviewer_001"})
    assert claimed.status_code == 200
    completed = client.post("/api/review-assignments/assignment_001/complete", headers={**headers, "X-MFLL-Idempotency-Key": "pass173-complete"}, json={"reviewer_safe_id": "reviewer_001", "acknowledged_evidence_ids": ["evidence_001"], "completion_note": "Fictional completion only."})
    assert completed.status_code == 200 and completed.json()["automatic_approval"] is False
    assert str(matter) not in completed.text
    assert ("POST", "/api/review-assignments/{assignment_id}/complete") in EndpointInventory().required_paths()
    for relative in ("src/maine_family_law_llm/ui/workbench.js", "maine_family_law_llm/ui/workbench.js"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "review-assignment-queue-controls" in text and "/api/review-assignments" in text
