from pathlib import Path

from legal.model_orchestration import ModelAdmissionRecord, ModelOrchestrator, ModelRegistry, RoleCatalog

ROOT = Path(__file__).resolve().parents[1]


class EchoWorker:
    def run(self, payload):
        return {"status": "completed_review_required", "echo": payload}


def make_registry():
    catalog = RoleCatalog.from_config(ROOT / "configs" / "maine_model_roles.json")
    return ModelRegistry(catalog, ROOT / "configs" / "maine_model_admission_policy.json")


def test_role_catalog_blocks_generator_self_certification_roles():
    catalog = RoleCatalog.from_config(ROOT / "configs" / "maine_model_roles.json")
    final_generator = catalog.get("maine_final_generator")

    assert "draft_generation" in final_generator.allowed_tasks
    assert "filing_ready_certification" in final_generator.prohibited_tasks
    assert catalog.validate_task("maine_final_generator", "filing_ready_certification")


def test_registry_requires_model_admission_metadata_for_production():
    registry = make_registry()
    record = ModelAdmissionRecord(
        model_id="draft-gen-001",
        provider="local-test",
        role="maine_final_generator",
        version="0.0.1",
        privacy_status="blocked_unknown",
        allowed_tasks=["draft_generation"],
        prohibited_tasks=["filing_ready_certification"],
        admission_status="admitted_for_production",
    )

    issues = registry.validate(record)
    reasons = {(issue.field, issue.reason) for issue in issues}

    assert ("privacy_status", "not_production_safe") in reasons
    assert ("benchmark_scores", "required_for_production") in reasons
    assert ("failure_profile", "required_for_production") in reasons
    assert ("eval_regression_history", "required_for_production") in reasons


def test_registry_admits_dev_model_and_orchestrator_runs_worker():
    registry = make_registry()
    record = ModelAdmissionRecord(
        model_id="issue-rules-001",
        provider="local-rule-engine",
        role="maine_issue_classifier",
        version="1.0",
        privacy_status="local_only",
        allowed_tasks=["issue_classification"],
        prohibited_tasks=["final_legal_answer"],
        benchmark_scores={"smoke_f1": 1.0},
        failure_profile={"known_limits": ["keyword baseline"]},
        cost_profile={"unit": "local"},
        latency_profile={"p95_ms": 1},
        eval_regression_history=[{"suite": "smoke", "status": "pass"}],
        admission_status="admitted_for_dev",
        license_status="approved",
    )

    assert registry.register(record) == []
    orchestrator = ModelOrchestrator(registry)
    orchestrator.register_worker("issue-rules-001", EchoWorker())
    result = orchestrator.run_task("issue_classification", {"text": "child support issue"})

    assert result.status == "completed_review_required"
    assert result.model_id == "issue-rules-001"
    assert result.role == "maine_issue_classifier"
    assert result.audit["review_required_by_default"] is True


def test_orchestrator_blocks_model_filing_ready_certification():
    registry = make_registry()
    result = ModelOrchestrator(registry).run_task("filing_ready_certification", {})

    assert result.status == "blocked"
    assert "models_may_not_certify_legal_validity" in result.blockers


def test_orchestrator_falls_back_when_no_admitted_model_exists():
    registry = make_registry()
    result = ModelOrchestrator(registry).run_task("draft_review", {"draft": "text"})

    assert result.status == "fallback_review_required"
    assert "no_admitted_model_for_task" in result.blockers
    assert result.output["role"] == "maine_draft_reviewer"
