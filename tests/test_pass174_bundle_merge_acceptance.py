from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.production import app as production_app
from legal.matter.bundle_merge import BundleMergeStore
from legal.matter.intake_workbench import IntakeWorkbenchError
from maine_family_law_llm import api as local_api

HASH_A = "a" * 64; HASH_B = "b" * 64; HASH_C = "c" * 64
ROOT = Path(__file__).resolve().parents[1]

def _payload() -> dict:
    return {"merge_id":"merge_001","left_bundle":{"bundle_id":"bundle_left","bundle_hash":HASH_A,"items":[{"item_id":"item_001","kind":"record","base_hash":HASH_B,"value_hash":HASH_A}]},"right_bundle":{"bundle_id":"bundle_right","bundle_hash":HASH_C,"items":[{"item_id":"item_001","kind":"record","base_hash":HASH_B,"value_hash":HASH_C}]}}

def test_pass174_conflicts_require_explicit_resolution_and_never_apply(tmp_path: Path) -> None:
    store=BundleMergeStore(tmp_path,encryption_key="0123456789abcdef")
    plan=store.create(_payload());assert plan["status"]=="conflicts_review_required" and plan["automatic_merge"] is False
    with pytest.raises(IntakeWorkbenchError,match="bundle_merge_conflicts_unresolved"):store.finalize("merge_001",{"reviewer_safe_id":"reviewer_001","confirmed":True})
    resolved=store.resolve("merge_001",{"conflict_id":"conflict_item_001","choice":"left","resolver_safe_id":"reviewer_001"});assert resolved["status"]=="ready_to_merge_review_required"
    final=store.finalize("merge_001",{"reviewer_safe_id":"reviewer_001","confirmed":True});assert final["status"]=="merged_review_required" and final["matter_modified"] is False and final["merged_bundle"]["automatic_apply"] is False
    encrypted=next((tmp_path/"47_BUNDLE_MERGES").glob("*.enc"));assert b"bundle_left" not in encrypted.read_bytes()

def test_pass174_production_routes_deny_viewer_and_shipped_controls(tmp_path: Path,monkeypatch) -> None:
    matter=tmp_path/"fictional-matter";matter.mkdir();monkeypatch.setattr(local_api,"active_case_root",lambda:matter);monkeypatch.setenv("MAINE_MATTER_STORE_KEY","fictional-passphrase");monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT",str(tmp_path/"idempotency"))
    client=TestClient(production_app);headers={"X-User-Role":"reviewer","X-Tenant-Id":"fictional-tenant","X-MFLL-Client-Session":"c"*32}
    assert client.post("/api/bundle-merges",headers={**headers,"X-User-Role":"viewer","X-MFLL-Idempotency-Key":"pass174-denied"},json=_payload()).status_code==403
    created=client.post("/api/bundle-merges",headers={**headers,"X-MFLL-Idempotency-Key":"pass174-create"},json=_payload());assert created.status_code==200,created.text
    assert client.post("/api/bundle-merges/merge_001/resolve",headers={**headers,"X-MFLL-Idempotency-Key":"pass174-resolve"},json={"conflict_id":"conflict_item_001","choice":"right","resolver_safe_id":"reviewer_001"}).status_code==200
    final=client.post("/api/bundle-merges/merge_001/finalize",headers={**headers,"X-MFLL-Idempotency-Key":"pass174-finalize"},json={"reviewer_safe_id":"reviewer_001","confirmed":True});assert final.status_code==200 and final.json()["matter_modified"] is False
    for rel in ("src/maine_family_law_llm/ui/workbench.js","maine_family_law_llm/ui/workbench.js"):
        text=(ROOT/rel).read_text(encoding="utf-8");assert "bundle-merge-controls" in text and "/api/bundle-merges" in text
