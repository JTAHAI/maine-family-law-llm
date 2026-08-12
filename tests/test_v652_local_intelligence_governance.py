from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from legal.model_orchestration import LocalRuntimeAdapter, ModelAdmissionRecord, ModelControlCenter, ModelRegistry, RoleCatalog


ROOT = Path(__file__).resolve().parents[1]


def _headers() -> dict[str, str]:
    return {"X-User-Role": "admin", "X-Tenant-Id": "tenant-652"}


def _make_record(**overrides):
    values = {
        "model_id": "local-governance-001",
        "provider": "local-test",
        "role": "maine_final_generator",
        "version": "1.0.0",
        "privacy_status": "local_only",
        "allowed_tasks": ["draft_generation", "answer_generation"],
        "prohibited_tasks": ["filing_ready_certification"],
        "benchmark_scores": {"smoke": 1.0},
        "benchmark_evidence": {"dataset": "smoke", "evidence_hash": "governance-smoke"},
        "failure_profile": {"known_limits": ["review required"]},
        "cost_profile": {"unit_cost_usd": 0, "billing_unit": "local_call"},
        "latency_profile": {"p95_ms": 20},
        "fallback_behavior": "route_to_deterministic_reviewer",
        "eval_regression_history": [{"suite": "smoke", "status": "pass"}],
        "admission_status": "admitted_for_dev",
        "license_status": "approved",
    }
    values.update(overrides)
    return ModelAdmissionRecord(**values)


def test_registry_rejects_unknown_license_hash_mismatch_and_shell_injection(tmp_path):
    artifact = tmp_path / "model.bin"
    artifact.write_bytes(b"local-artifact")
    catalog = RoleCatalog.from_config(ROOT / "configs" / "maine_model_roles.json")
    registry = ModelRegistry(catalog, ROOT / "configs" / "maine_model_admission_policy.json")
    record = _make_record(
        artifact_path=str(artifact),
        artifact_sha256="0" * 64,
        runtime_executable="cmd.exe && calc.exe",
        license_status="unknown",
    )

    issues = registry.validate(record)
    reasons = {(issue.field, issue.reason) for issue in issues}

    assert ("license_status", "unknown_or_unapproved_license") in reasons
    assert ("runtime_executable", "shell_injection_refused") in reasons
    assert ("runtime_executable", "arbitrary_executable_refused") in reasons
    assert ("artifact_sha256", "hash_mismatch") in reasons


def test_runtime_adapter_reports_contract_and_refuses_unsafe_configuration():
    adapter = LocalRuntimeAdapter(
        provider_id="deterministic_local",
        model_id="local-governance-001",
        metadata={"license": "Apache-2.0", "license_status": "approved", "runtime_executable": "cmd.exe && calc.exe"},
    )

    validation = adapter.validate_configuration({"runtime_executable": "cmd.exe && calc.exe", "license_status": "approved"})
    availability = adapter.availability()
    version = adapter.version()
    license_report = adapter.license_report()
    capability_report = adapter.capability_report()
    estimate = adapter.estimate_resources({"estimated_tokens": 1024})
    stream = adapter.stream_turn({"question": "draft"})
    provenance = adapter.emit_provenance({"turn": "draft"})
    normalized = adapter.normalize_error(RuntimeError("runtime_executable refused"))

    assert validation["status"] == "fail"
    assert "shell_injection_refused" in validation["issues"]
    assert availability["available"] is True
    assert version["version"] == "unknown"
    assert license_report["license_status"] == "approved"
    assert capability_report["model_id"] == "local-governance-001"
    assert estimate["supported"] is True
    assert stream[-1]["status"] == "completed_review_required"
    assert len(provenance["provenance_sha256"]) == 64
    assert "runtime_executable" in normalized["message"]
    assert adapter.no_network_mode() is True
    assert adapter.cleanup()["status"] == "cleaned_up"
    expected = sha256(
        json.dumps(
            {
                "provider_id": "deterministic_local",
                "model_id": "local-governance-001",
                "payload": {"turn": "draft"},
                "metadata": {"license": "Apache-2.0", "license_status": "approved", "runtime_executable": "cmd.exe && calc.exe"},
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    assert provenance["provenance_sha256"] == expected


def test_control_center_dashboard_surfaces_registry_storage_history_and_runtime_contract(tmp_path):
    center = ModelControlCenter(
        project_root=ROOT,
        role_catalog_path=ROOT / "configs" / "maine_model_roles.json",
        admission_policy_path=ROOT / "configs" / "maine_model_admission_policy.json",
        registry_seed_path=ROOT / "configs" / "maine_model_registry.seed.json",
        store_root=tmp_path / "model-store",
    )

    dashboard = center.dashboard()
    runtime_contract = center.runtime_contract("issue-rules-001")

    assert dashboard["registry"]["model_count"] >= 2
    assert dashboard["roles"]["version"] == "1.0.0-pass11"
    assert "registry" in dashboard["storage"]
    assert isinstance(dashboard["admission_history"], list)
    assert runtime_contract["availability"]["available"] is True
    assert runtime_contract["license_report"]["status"] == "pass"
    assert runtime_contract["no_network_mode"] is True


def test_control_center_benchmark_quarantine_and_api_surface(tmp_path, monkeypatch):
    monkeypatch.setenv("MFL_PROJECT_ROOT", str(ROOT))
    monkeypatch.setenv("MFL_MODEL_STORE_ROOT", str(tmp_path / "model-store"))
    center = ModelControlCenter(
        project_root=ROOT,
        role_catalog_path=ROOT / "configs" / "maine_model_roles.json",
        admission_policy_path=ROOT / "configs" / "maine_model_admission_policy.json",
        registry_seed_path=ROOT / "configs" / "maine_model_registry.seed.json",
        store_root=tmp_path / "model-store",
    )
    record = _make_record(
        model_id="local-governance-bench-001",
        role="maine_document_structure_assistant",
        allowed_tasks=["document_structure_analysis"],
        prohibited_tasks=["filing_ready_certification"],
        source_project="local-governance",
        source_url="https://example.invalid/model",
        artifact_filename="model.bin",
        runtime_executable="MaineFamilyLawLLM.exe",
    )
    assert center.registry.register(record) == []

    benchmark = center.benchmark_model(
        "local-governance-bench-001",
        {
            "scores": {"smoke_f1": 1.0},
            "evidence": {"dataset": "smoke", "evidence_hash": "benchmark-001"},
        },
    )
    quarantined = center.quarantine_model("local-governance-bench-001", {"reason": "synthetic regression"})

    client = TestClient(app)
    response = client.get("/api/models/local-governance-bench-001", headers=_headers())
    health = client.get("/api/models/local-governance-bench-001/health", headers=_headers())
    api_benchmark = client.post(
        "/api/models/local-governance-bench-001/benchmark",
        headers=_headers(),
        json={"scores": {"smoke_f1": 1.0}, "evidence": {"dataset": "smoke", "evidence_hash": "benchmark-002"}},
    )

    assert benchmark["benchmark_evidence"]["evidence_hash"] == "benchmark-001"
    assert quarantined["model"]["admission_status"] == "quarantined"
    assert response.status_code == 200, response.text
    assert response.json()["runtime_contract"]["license_report"]["status"] == "pass"
    assert health.status_code == 200, health.text
    assert api_benchmark.status_code == 200, api_benchmark.text
    assert api_benchmark.json()["model"]["benchmark_evidence"]["evidence_hash"] == "benchmark-002"
    assert center.registry.admission_history()
    assert api_benchmark.json()["runtime_contract"]["license_report"]["status"] == "pass"


def test_control_center_routing_supports_explicit_fallback_modes(tmp_path):
    center = ModelControlCenter(
        project_root=ROOT,
        role_catalog_path=ROOT / "configs" / "maine_model_roles.json",
        admission_policy_path=ROOT / "configs" / "maine_model_admission_policy.json",
        registry_seed_path=ROOT / "configs" / "maine_model_registry.seed.json",
        store_root=tmp_path / "model-store",
    )
    deterministic = center.routing_status(task="draft_review", fallback_mode="deterministic")
    lexical = center.routing_status(task="draft_review", fallback_mode="lexical_only")
    rules = center.routing_status(task="draft_review", fallback_mode="rules_only")

    assert deterministic["fallback_selection"] == "deterministic"
    assert lexical["fallback_selection"] == "lexical_only"
    assert rules["fallback_selection"] == "rules_only"
    assert "available_fallbacks" in deterministic
    assert deterministic["available_fallbacks"] == ["deterministic", "lexical_only", "rules_only"]


def test_orchestrator_no_model_mode_and_lexical_only_mode_are_visible():
    catalog = RoleCatalog.from_config(ROOT / "configs" / "maine_model_roles.json")
    registry = ModelRegistry(catalog, ROOT / "configs" / "maine_model_admission_policy.json")
    from legal.model_orchestration.orchestrator import ModelOrchestrator

    route = ModelOrchestrator(registry).route_task("draft_review", fallback_mode="lexical_only")
    blocked = ModelOrchestrator(registry).route_task("draft_review", fallback_mode="rules_only")

    assert route["status"] == "fallback_review_required"
    assert route["fallback_mode"] == "lexical_only"
    assert blocked["fallback_mode"] == "rules_only"
    assert "available_fallbacks" in route


def test_registry_retains_unknown_license_and_worker_type_defaults(tmp_path):
    catalog = RoleCatalog.from_config(ROOT / "configs" / "maine_model_roles.json")
    registry = ModelRegistry(catalog, ROOT / "configs" / "maine_model_admission_policy.json")
    record = _make_record(license_status="unknown", worker_type="")

    assert record.license_status == "unknown"
    assert record.worker_type == ""
    assert ("license_status", "unknown_or_unapproved_license") in {(issue.field, issue.reason) for issue in registry.validate(record)}


def test_local_intelligence_ui_and_workbench_surface_the_control_center():
    page = (ROOT / "app" / "web" / "pages" / "local-intelligence-control-center.tsx").read_text(encoding="utf-8")
    ui_contracts = (ROOT / "app" / "web" / "ui_contracts.py").read_text(encoding="utf-8")
    workbench = (ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")

    assert "data-local-intelligence-control-center" in page
    assert "data-hardware-profile" in page
    assert "data-model-registry" in page
    assert "data-role-permissions" in page
    assert "data-benchmark-runner" in page
    assert "data-routing-fallbacks" in page
    assert "data-health-failures" in page
    assert "data-storage-cache" in page
    assert "data-quarantine-removal" in page
    assert "data-degraded-modes" in page
    assert "data-admission-history" in page
    assert "local_intelligence_control_center" in ui_contracts
    assert "open_local_intelligence_center" not in workbench
    assert "/admin/models" not in workbench
