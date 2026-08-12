from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from maine_family_law_llm.runtime_kernel import DurableJobKernel


def test_job_kernel_is_idempotent_durable_and_audited(tmp_path) -> None:
    path = tmp_path / "runtime.sqlite3"
    first = DurableJobKernel(path)
    job = first.create_job(
        "document_analysis",
        {"source_id": "source-1"},
        matter_id="matter-1",
        idempotency_key="request-1",
    )
    duplicate = first.create_job(
        "document_analysis",
        {"source_id": "different"},
        matter_id="matter-1",
        idempotency_key="request-1",
    )
    assert duplicate["job_id"] == job["job_id"]

    second = DurableJobKernel(path)
    persisted = second.get_job(job["job_id"])
    assert persisted is not None
    assert persisted["payload"] == {"source_id": "source-1"}
    assert [event["event_type"] for event in second.events(job["job_id"])] == ["job_created"]
    assert second.health()["integrity"] == "ok"


def test_job_claim_progress_completion_and_ownership(tmp_path) -> None:
    kernel = DurableJobKernel(tmp_path / "runtime.sqlite3")
    job = kernel.create_job("ocr", {"page": 1})
    claimed = kernel.claim_job(job["job_id"], "worker-a")
    assert claimed["status"] == "running"
    assert claimed["attempt"] == 1

    progress = kernel.heartbeat(job["job_id"], "worker-a", 0.4)
    assert progress["progress"] == 0.4
    with pytest.raises(RuntimeError, match="job_lease_not_owned"):
        kernel.heartbeat(job["job_id"], "worker-b", 0.5)

    completed = kernel.finish_job(job["job_id"], "worker-a", result={"pages": 1})
    assert completed["status"] == "completed"
    assert completed["progress"] == 1.0
    assert completed["result"] == {"pages": 1}


def test_cancel_and_expired_lease_recovery(tmp_path) -> None:
    kernel = DurableJobKernel(tmp_path / "runtime.sqlite3")
    queued = kernel.create_job("index", {})
    assert kernel.request_cancel(queued["job_id"])["status"] == "cancelled"

    running = kernel.create_job("docling", {})
    kernel.claim_job(running["job_id"], "worker-a", lease_seconds=15)
    future = datetime.now(UTC) + timedelta(minutes=1)
    recovered = kernel.recover_expired(now=future)
    assert [item["job_id"] for item in recovered] == [running["job_id"]]
    assert recovered[0]["status"] == "queued"


def test_runtime_job_api_uses_configured_external_state_root(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MFL_RUNTIME_STATE_ROOT", str(tmp_path))
    import app.api.production as production

    production._runtime_kernel = None
    client = production.runtime_kernel()
    job = client.create_job("test", {"ok": True}, matter_id="matter-api")
    assert client.get_job(job["job_id"])["matter_id"] == "matter-api"
    assert client.path.parent == tmp_path.resolve()
