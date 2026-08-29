from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.runtime.warm_model_pool import WarmModelPoolStore
from maine_family_law_llm import api as api_module


class FakeWarmWorker:
    supports_explicit_release = True

    def __init__(self) -> None:
        self.warm_calls = 0
        self.release_calls = 0

    def warm(self):
        self.warm_calls += 1
        return {
            "provider_id": "ollama",
            "model_id": "fictional-local-model",
            "endpoint_class": "loopback_http",
        }

    def release(self):
        self.release_calls += 1
        return {"released": True}


def _admitted_model():
    return {
        "model_id": "fictional_local_model",
        "installation_status": "admitted_for_task_review_required",
    }


def test_pass104_warms_only_admitted_explicitly_releasable_workers(monkeypatch, tmp_path: Path):
    # The admission path is independent of the host's momentary free memory.
    # Pin the hardware snapshot so a concurrently running suite cannot turn
    # this contract test into an accidental resource-pressure test.
    from legal.runtime import warm_model_pool as pool_module

    monkeypatch.setattr(
        pool_module,
        "profile_hardware",
        lambda _root: type("Hardware", (), {"as_dict": lambda self: {"available_memory_bytes": 8 * 1024**3}})(),
    )
    root = tmp_path / "fictional-matter"
    root.mkdir()
    store = WarmModelPoolStore(root, encryption_key="fictional-test-key")
    worker = FakeWarmWorker()

    result = store.warm(
        {"task": "summarization", "thermal_state": "normal", "user_confirmed": True},
        model=_admitted_model(),
        worker=worker,
    )

    assert result["status"] == "warm_review_required"
    assert result["worker"]["model_id"] == "fictional_local_model"
    assert result["review_required"] is True
    assert result["network_used"] is False
    assert worker.warm_calls == 1
    assert "fictional_local_model" not in store.path.read_text(encoding="utf-8")

    released = store.release(
        {"model_id": "fictional_local_model", "reason": "thermal_pressure"}, worker=worker
    )
    assert released["status"] == "released_review_required"
    assert released["worker"]["release_reason"] == "thermal_pressure"
    assert worker.release_calls == 1
    assert store.status()["recent_events"][0]["action"] == "worker_released"


def test_pass104_refuses_to_warm_without_admission_or_release_capability(tmp_path: Path):
    root = tmp_path / "fictional-matter"
    root.mkdir()
    store = WarmModelPoolStore(root, encryption_key="fictional-test-key")

    no_admission = store.warm(
        {"task": "summarization", "user_confirmed": True}, model=None, worker=None
    )
    assert no_admission["status"] == "not_warmed_no_task_admission_review_required"

    class NoReleaseWorker:
        supports_explicit_release = False

    no_release = store.warm(
        {"task": "summarization", "user_confirmed": True},
        model=_admitted_model(),
        worker=NoReleaseWorker(),
    )
    assert no_release["status"] == "not_warmed_release_capability_missing_review_required"

    with pytest.raises(IntakeWorkbenchError, match="warm_model_pool_confirmation_required"):
        store.warm({"task": "summarization"}, model=_admitted_model(), worker=FakeWarmWorker())


def test_pass104_api_is_matter_scoped_and_production_assets_are_mirrored(monkeypatch, tmp_path: Path):
    first, second = tmp_path / "matter-one", tmp_path / "matter-two"
    first.mkdir()
    second.mkdir()
    active = {"root": first}
    monkeypatch.setattr(api_module, "active_case_root", lambda: active["root"])
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    client = TestClient(api_module.app)
    response = client.post(
        "/api/runtime/warm-model-pool/warm",
        json={"task": "summarization", "user_confirmed": True},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "not_warmed_no_task_admission_review_required"
    active["root"] = second
    assert client.get("/api/runtime/warm-model-pool").json()["workers"] == []

    source_api = Path("src/maine_family_law_llm/api.py").read_bytes()
    mirror_api = Path("maine_family_law_llm/api.py").read_bytes()
    ui = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")

    assert source_api == mirror_api
    assert b"/api/runtime/warm-model-pool/warm" in source_api
    assert b"/api/runtime/warm-model-pool/release" in source_api
    assert "Warm model pool" in ui
    assert "synthetic loopback warm-up" in ui
