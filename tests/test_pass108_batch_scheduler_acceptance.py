from pathlib import Path

from fastapi.testclient import TestClient

from legal.runtime.batch_scheduler import BatchInferenceScheduler
from maine_family_law_llm import api as api_module


class FakeKernel:
    def __init__(self):
        self.jobs = {}
        self.cancelled = []

    def create_job(self, job_type, payload, *, matter_id, idempotency_key):
        job = {"job_id": f"job_{len(self.jobs)+1}", "job_type": job_type, "payload": payload, "matter_id": matter_id, "idempotency_key": idempotency_key, "status": "queued"}
        self.jobs[job["job_id"]] = job
        return dict(job)

    def request_cancel(self, job_id):
        self.cancelled.append(job_id)
        self.jobs[job_id]["status"] = "cancelled"
        return dict(self.jobs[job_id])


def _payload(batch_id="batch_001"):
    return {"batch_id": batch_id, "user_confirmed": True, "items": [
        {"item_id": "item_001", "job_kind": "extract", "source_ref": {"source_id": "record_001", "content_sha256": "a"*64}, "execution_profile": {"context_budget_id": "budget_001"}},
        {"item_id": "item_002", "job_kind": "extract", "source_ref": {"source_id": "record_002", "content_sha256": "b"*64}, "execution_profile": {"context_budget_id": "budget_001"}},
        {"item_id": "item_003", "job_kind": "classify", "source_ref": {"source_id": "record_003", "content_sha256": "c"*64}, "execution_profile": {"context_budget_id": "budget_001"}},
    ]}


def test_pass108_coalesces_only_compatible_jobs_and_preserves_child_cancellation(tmp_path: Path):
    root = tmp_path / "fictional-matter"; root.mkdir()
    kernel = FakeKernel()
    scheduler = BatchInferenceScheduler(root, kernel=kernel, matter_id="fictional_matter", encryption_key="fictional-test-key")
    created = scheduler.create(_payload())
    batch = created["batch"]
    assert batch["coalesced_group_count"] == 2
    assert len(kernel.jobs) == 2
    assert batch["execution_not_automatic"] is True
    assert "record_001" not in scheduler.path.read_text(encoding="utf-8")
    assert scheduler.source("batch_001", "item_001")["source_ref"]["source_id"] == "record_001"

    first = scheduler.cancel_item("batch_001", "item_001")["batch"]
    assert first["items"][0]["status"] == "cancelled_review_required"
    assert kernel.cancelled == []
    second = scheduler.cancel_item("batch_001", "item_002")["batch"]
    assert len(kernel.cancelled) == 1
    assert second["items"][2]["status"] == "queued_review_required"


def test_pass108_api_is_matter_scoped_and_production_assets_are_mirrored(monkeypatch, tmp_path: Path):
    first, second = tmp_path / "matter-one", tmp_path / "matter-two"; first.mkdir(); second.mkdir()
    active = {"root": first}
    monkeypatch.setattr(api_module, "active_case_root", lambda: active["root"])
    monkeypatch.setattr(api_module, "get_runtime_kernel", lambda: FakeKernel())
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    client = TestClient(api_module.app)
    response = client.post("/api/runtime/batch-inference", json=_payload())
    assert response.status_code == 200
    assert response.json()["batch"]["matter_scope"] == "active_matter_only"
    active["root"] = second
    assert client.get("/api/runtime/batch-inference/batch_001").status_code == 404
    assert Path("src/maine_family_law_llm/api.py").read_bytes() == Path("maine_family_law_llm/api.py").read_bytes()
    assert "Batch inference scheduler" in Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
