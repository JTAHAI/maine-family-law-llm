from legal.model_orchestration.adaptive import AdaptiveRuntimePlanner, runtime_budget
from legal.model_orchestration.hardware import HardwareProfile
from legal.model_orchestration.registry import ModelAdmissionRecord

GIB = 1024**3


def profile(*, total: int, available: int, vram: int = 0) -> HardwareProfile:
    return HardwareProfile(
        os_name="Windows",
        os_version="11",
        machine="AMD64",
        architecture="64bit",
        logical_cpu_count=8,
        total_memory_bytes=total,
        available_memory_bytes=available,
        disk_free_bytes=100 * GIB,
        vram_bytes=vram,
        recommended_concurrency=4,
        recommended_context_limit=16384,
    )


def model(**overrides) -> ModelAdmissionRecord:
    values = {
        "model_id": "local-compact",
        "provider": "local",
        "role": "general_assistant",
        "version": "1",
        "privacy_status": "local_only",
        "allowed_tasks": ["general_chat", "legal_research"],
        "prohibited_tasks": [],
        "admission_status": "admitted_for_production",
        "network_policy": "loopback_only",
        "artifact_size_bytes": 2 * GIB,
        "min_ram_bytes": 3 * GIB,
        "context_limit_tokens": 8192,
        "supports_streaming": True,
    }
    values.update(overrides)
    return ModelAdmissionRecord(**values)


def test_budget_preserves_os_headroom_on_low_spec_pc():
    budget = runtime_budget(profile(total=8 * GIB, available=5 * GIB))
    assert budget.tier == "efficient"
    assert budget.concurrency == 1
    assert budget.memory_budget_bytes < 5 * GIB


def test_planner_selects_smallest_streaming_model_that_fits():
    planner = AdaptiveRuntimePlanner(profile(total=32 * GIB, available=24 * GIB))
    plan = planner.plan(
        task="general_chat",
        models=[
            model(model_id="large", artifact_size_bytes=10 * GIB),
            model(model_id="compact", artifact_size_bytes=2 * GIB),
        ],
    )
    assert plan["status"] == "ready"
    assert plan["selected_model_id"] == "compact"
    assert plan["network_scope"] == "loopback_only"


def test_planner_fails_closed_when_machine_lacks_headroom():
    planner = AdaptiveRuntimePlanner(profile(total=6 * GIB, available=3 * GIB))
    plan = planner.plan(task="general_chat", models=[model(artifact_size_bytes=5 * GIB)])
    assert plan["status"] == "fallback_review_required"
    assert plan["selected_model_id"] is None
    assert "insufficient_safe_memory_headroom" in plan["candidates"][0]["reasons"]


def test_planner_never_routes_legal_certification_to_model():
    planner = AdaptiveRuntimePlanner(profile(total=32 * GIB, available=24 * GIB))
    plan = planner.plan(task="filing_ready_certification", models=[model()])
    assert plan["status"] == "fallback_review_required"
    assert "models_may_not_certify_legal_or_filing_validity" in plan["blockers"]


def test_planner_enforces_backpressure_and_production_admission():
    planner = AdaptiveRuntimePlanner(profile(total=32 * GIB, available=24 * GIB))
    plan = planner.plan(
        task="general_chat",
        models=[model(admission_status="admitted_for_dev")],
        active_model_jobs=2,
        require_production=True,
    )
    assert plan["status"] == "fallback_review_required"
    assert "runtime_backpressure_active" in plan["blockers"]
    assert "production_admission_required" in plan["candidates"][0]["reasons"]
