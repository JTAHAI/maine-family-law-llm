from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from legal.model_orchestration import ModelAdmissionRecord, ModelControlCenter, ModelRegistry, RoleCatalog
from legal.model_orchestration.store import ModelStoreRootError, external_model_store_layout, resolve_external_model_root


ROOT = Path(__file__).resolve().parents[1]


def _headers() -> dict[str, str]:
    return {"X-User-Role": "admin", "X-Tenant-Id": "tenant-650"}


def test_external_model_store_layout_is_outside_repo_and_creates_control_center_root(tmp_path):
    layout = external_model_store_layout(tmp_path / "model-store", project_root=ROOT, create=True)
    assert layout.root == (tmp_path / "model-store").resolve()
    assert layout.registry.is_dir()
    assert layout.artifacts.is_dir()
    assert layout.quarantine.is_dir()


def test_model_registry_supports_rich_metadata_and_file_backed_admission(tmp_path):
    catalog = RoleCatalog.from_config(ROOT / "configs" / "maine_model_roles.json")
    registry = ModelRegistry(
        catalog,
        ROOT / "configs" / "maine_model_admission_policy.json",
        storage_root=tmp_path / "model-store",
        project_root=ROOT,
    )
    record = ModelAdmissionRecord(
        model_id="local-draft-002",
        provider="local-test",
        role="maine_final_generator",
        version="0.2.0",
        privacy_status="local_only",
        allowed_tasks=["draft_generation", "answer_generation"],
        prohibited_tasks=["filing_ready_certification"],
        benchmark_scores={"draft_review_required_contract": 1.0},
        failure_profile={"known_limits": ["cannot certify legal correctness"]},
        cost_profile={"unit_cost_usd": 0, "billing_unit": "local_call"},
        latency_profile={"p95_ms": 23},
        eval_regression_history=[{"suite": "smoke", "status": "pass"}],
        admission_status="admitted_for_dev",
        display_name="Local Draft Generator",
        source="local-test",
        upstream_project="mock-local",
        upstream_version="0.2",
        license="Apache-2.0",
        license_status="approved",
        artifact_sha256="a" * 64,
        artifact_size_bytes=12345,
        context_limit_tokens=8192,
        supports_streaming=True,
        supports_structured_output=True,
        supports_cancellation=True,
    )

    assert registry.register(record) == []
    assert (tmp_path / "model-store" / "registry" / "registry.json").exists()
    loaded = ModelRegistry(
        catalog,
        ROOT / "configs" / "maine_model_admission_policy.json",
        storage_root=tmp_path / "model-store",
        project_root=ROOT,
    )
    assert loaded.get_record("local-draft-002").display_name == "Local Draft Generator"
    assert loaded.get_record("local-draft-002").supports_cancellation is True


def test_model_control_center_reports_hardware_and_safe_fallback(tmp_path):
    center = ModelControlCenter(
        project_root=ROOT,
        role_catalog_path=ROOT / "configs" / "maine_model_roles.json",
        admission_policy_path=ROOT / "configs" / "maine_model_admission_policy.json",
        registry_seed_path=ROOT / "configs" / "maine_model_registry.seed.json",
        store_root=tmp_path / "model-store",
    )

    routing = center.routing_status(task="draft_review")
    assert routing["status"] == "fallback_review_required"
    assert routing["fallback_mode"] == "deterministic"
    assert "no_admitted_model_for_task" in routing["blockers"] or routing["candidates"]

    summary = center.summary()
    assert summary.hardware["logical_cpu_count"] >= 1
    assert summary.registry["model_count"] >= 1


def test_model_control_center_routes_and_api_surface_are_registered(monkeypatch, tmp_path):
    monkeypatch.setenv("MFL_PROJECT_ROOT", str(ROOT))
    monkeypatch.setenv("MFL_MODEL_STORE_ROOT", str(tmp_path / "model-store"))
    client = TestClient(app)

    models = client.get("/api/models", headers=_headers())
    hardware = client.get("/api/hardware/profile", headers=_headers())
    routing = client.get("/api/model-routing/status", params={"task": "draft_review"}, headers=_headers())
    estimate = client.post(
        "/api/models/estimate",
        headers=_headers(),
        json={"model_id": "local-draft-002", "artifact_size_bytes": 1024, "context_limit_tokens": 4096},
    )

    assert models.status_code == 200, models.text
    assert hardware.status_code == 200, hardware.text
    assert routing.status_code == 200, routing.text
    assert estimate.status_code == 200, estimate.text
    assert models.json()["review_required"] is True
    assert hardware.json()["logical_cpu_count"] >= 1
    assert "fallback_mode" in routing.json()
    assert estimate.json()["review_required"] is True


def test_model_store_root_rejects_repo_internal_paths():
    candidate = ROOT / "model_store"
    try:
        resolve_external_model_root(candidate, project_root=ROOT, create=False)
    except ModelStoreRootError as exc:
        assert exc.code in {"external_root_inside_source_repo", "model_store_inside_forbidden_root"}
    else:  # pragma: no cover - defensive
        raise AssertionError("repo-internal model store paths must be refused")
