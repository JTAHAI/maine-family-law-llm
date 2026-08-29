from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.contracts.endpoint_inventory import EndpointInventory
from app.api.production import app as production_app
from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.matter.structured_comment_threads import StructuredCommentThreadStore
from maine_family_law_llm import api as local_api


ROOT = Path(__file__).resolve().parents[1]
HASH = "a" * 64


def _payload(kind: str, thread_id: str) -> dict:
    base = {"thread_id": thread_id, "author_safe_id": "reviewer_001", "body": "Fictional review observation; verify before relying on it.", "target_kind": kind}
    if kind == "record_span":
        return {**base, "record_id": "record_001", "source_hash": HASH, "character_start": 4, "character_end": 26}
    if kind == "source_span":
        return {**base, "source_id": "me.rev.stat.title19a", "source_hash": HASH, "character_start": 4, "character_end": 26}
    if kind == "claim":
        return {**base, "claim_id": "claim_001", "claim_hash": HASH}
    if kind == "draft_text":
        return {**base, "document_id": "draft_001", "revision_hash": HASH, "character_start": 4, "character_end": 26}
    return {**base, "artifact_id": "artifact_001", "artifact_hash": HASH}


def test_pass172_all_target_kinds_are_hash_bound_encrypted_and_append_only(tmp_path: Path) -> None:
    store = StructuredCommentThreadStore(tmp_path, encryption_key="0123456789abcdef")
    created = {kind: store.create_thread(_payload(kind, f"thread_{kind}")) for kind in ("record_span", "source_span", "claim", "draft_text", "artifact")}
    assert created["record_span"]["target"]["source_drill_down"]["route"] == "/api/records/record_001/integrity"
    assert created["source_span"]["target"]["source_drill_down"]["exact_span"] == {"start": 4, "end": 26}
    reply = store.add_comment("thread_record_span", {"comment_id": "reply_001", "parent_comment_id": "opening_thread_record_span", "author_safe_id": "reviewer_002", "body": "Fictional reply; retain the question for review."})
    assert len(reply["comments"]) == 2 and reply["automatic_merge"] is False
    resolved = store.resolve("thread_record_span", {"resolver_safe_id": "reviewer_001", "resolution_note": "Resolved only as a review state; exact source remains controlling."})
    assert resolved["state"] == "resolved_review_required"
    with pytest.raises(IntakeWorkbenchError, match="structured_comment_thread_resolved"):
        store.add_comment("thread_record_span", {"comment_id": "reply_002", "author_safe_id": "reviewer_002", "body": "A closed thread cannot be changed."})
    inventory = store.inventory()
    assert len(inventory["threads"]) == 5
    assert "body" not in inventory["threads"][0]["comments"][0]
    encrypted = next((tmp_path / "45_STRUCTURED_COMMENT_THREADS").glob("*.enc"))
    assert b"Fictional review observation" not in encrypted.read_bytes()
    history = store._load()["history"]
    assert all(row["previous_hash"] == (history[index - 1]["hash"] if index else "") for index, row in enumerate(history))


def test_pass172_production_routes_deny_viewer_mutation_and_ship_controls(tmp_path: Path, monkeypatch) -> None:
    matter = tmp_path / "fictional-matter"; matter.mkdir()
    monkeypatch.setattr(local_api, "active_case_root", lambda: matter)
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-acceptance-passphrase")
    monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "idempotency"))
    client = TestClient(production_app)
    headers = {"X-User-Role": "reviewer", "X-Tenant-Id": "fictional-tenant", "X-MFLL-Client-Session": "e" * 32}
    denied = client.post("/api/review-comments/threads", headers={**headers, "X-User-Role": "viewer", "X-MFLL-Idempotency-Key": "pass172-viewer-denied"}, json=_payload("record_span", "thread_001"))
    assert denied.status_code == 403
    created = client.post("/api/review-comments/threads", headers={**headers, "X-MFLL-Idempotency-Key": "pass172-create"}, json=_payload("record_span", "thread_001"))
    assert created.status_code == 200, created.text
    reply = client.post("/api/review-comments/threads/thread_001/comments", headers={**headers, "X-MFLL-Idempotency-Key": "pass172-reply"}, json={"comment_id": "reply_001", "author_safe_id": "reviewer_002", "body": "Fictional reply."})
    assert reply.status_code == 200
    thread = client.get("/api/review-comments/threads/thread_001", headers=headers)
    assert thread.status_code == 200 and thread.json()["target"]["source_drill_down"]["review_required"] is True
    resolved = client.post("/api/review-comments/threads/thread_001/resolve", headers={**headers, "X-MFLL-Idempotency-Key": "pass172-resolve"}, json={"resolver_safe_id": "reviewer_001", "resolution_note": "Fictional review state only."})
    assert resolved.status_code == 200 and resolved.json()["state"] == "resolved_review_required"
    inventory = client.get("/api/review-comments/inventory", headers=headers)
    assert inventory.status_code == 200 and inventory.json()["private_comment_bodies_in_inventory"] is False
    assert str(matter) not in inventory.text
    assert ("POST", "/api/review-comments/threads/{thread_id}/resolve") in EndpointInventory().required_paths()
    for relative in ("src/maine_family_law_llm/ui/workbench.js", "maine_family_law_llm/ui/workbench.js"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "structured-comment-thread-controls" in text and "/api/review-comments/threads" in text
