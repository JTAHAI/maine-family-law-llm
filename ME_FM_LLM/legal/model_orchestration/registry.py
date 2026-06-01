from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .roles import RoleCatalog

PRODUCTION_STATUSES = {"admitted_for_production"}
SAFE_PRIVACY_STATUSES = {"local_only", "private_cloud_reviewed", "hosted_optional_no_training"}
GENERATOR_ROLES = {"maine_final_generator", "maine_plain_language_explainer"}
CERTIFICATION_TASKS = {
    "citation_validity_certification",
    "quote_validity_certification",
    "authority_validity_certification",
    "filing_ready_certification",
}


@dataclass(frozen=True)
class ModelValidationIssue:
    field: str
    reason: str


@dataclass
class ModelAdmissionRecord:
    model_id: str
    provider: str
    role: str
    version: str
    privacy_status: str
    allowed_tasks: list[str]
    prohibited_tasks: list[str]
    benchmark_scores: dict[str, float] = field(default_factory=dict)
    failure_profile: dict[str, Any] = field(default_factory=dict)
    cost_profile: dict[str, Any] = field(default_factory=dict)
    latency_profile: dict[str, Any] = field(default_factory=dict)
    fallback_behavior: str = "block_and_route_to_rule_based_or_human_review"
    eval_regression_history: list[dict[str, Any]] = field(default_factory=list)
    admission_status: str = "candidate"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelAdmissionRecord":
        return cls(
            model_id=str(data.get("model_id", "")),
            provider=str(data.get("provider", "")),
            role=str(data.get("role", "")),
            version=str(data.get("version", "")),
            privacy_status=str(data.get("privacy_status", "blocked_unknown")),
            allowed_tasks=list(data.get("allowed_tasks", [])),
            prohibited_tasks=list(data.get("prohibited_tasks", [])),
            benchmark_scores=dict(data.get("benchmark_scores", {})),
            failure_profile=dict(data.get("failure_profile", {})),
            cost_profile=dict(data.get("cost_profile", {})),
            latency_profile=dict(data.get("latency_profile", {})),
            fallback_behavior=str(data.get("fallback_behavior", "block_and_route_to_human_review")),
            eval_regression_history=list(data.get("eval_regression_history", [])),
            admission_status=str(data.get("admission_status", "candidate")),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "role": self.role,
            "version": self.version,
            "privacy_status": self.privacy_status,
            "allowed_tasks": list(self.allowed_tasks),
            "prohibited_tasks": list(self.prohibited_tasks),
            "benchmark_scores": dict(self.benchmark_scores),
            "failure_profile": dict(self.failure_profile),
            "cost_profile": dict(self.cost_profile),
            "latency_profile": dict(self.latency_profile),
            "fallback_behavior": self.fallback_behavior,
            "eval_regression_history": list(self.eval_regression_history),
            "admission_status": self.admission_status,
        }


class ModelRegistry:
    def __init__(self, role_catalog: RoleCatalog, admission_policy_path: str | Path):
        self.role_catalog = role_catalog
        self.admission_policy = json.loads(Path(admission_policy_path).read_text(encoding="utf-8"))
        self.records: dict[str, ModelAdmissionRecord] = {}

    def validate(self, record: ModelAdmissionRecord) -> list[ModelValidationIssue]:
        issues: list[ModelValidationIssue] = []
        required_fields = self.admission_policy.get("required_fields", [])
        data = record.as_dict()
        for field_name in required_fields:
            value = data.get(field_name)
            if value in (None, "", [], {}):
                issues.append(ModelValidationIssue(field_name, "missing_or_empty"))

        if record.role not in self.role_catalog.roles:
            issues.append(ModelValidationIssue("role", "unknown_role"))
        else:
            role_policy = self.role_catalog.get(record.role)
            for task in record.allowed_tasks:
                if task not in role_policy.allowed_tasks:
                    issues.append(ModelValidationIssue("allowed_tasks", f"task_not_in_role_policy:{task}"))
            for task in CERTIFICATION_TASKS:
                if task in record.allowed_tasks:
                    issues.append(ModelValidationIssue("allowed_tasks", f"generator_self_certification_blocked:{task}"))

        if record.privacy_status not in self.admission_policy.get("allowed_privacy_statuses", []):
            issues.append(ModelValidationIssue("privacy_status", "unknown_privacy_status"))

        if record.admission_status not in self.admission_policy.get("allowed_admission_statuses", []):
            issues.append(ModelValidationIssue("admission_status", "unknown_admission_status"))

        if record.admission_status in PRODUCTION_STATUSES:
            if record.privacy_status not in SAFE_PRIVACY_STATUSES:
                issues.append(ModelValidationIssue("privacy_status", "not_production_safe"))
            if not record.benchmark_scores:
                issues.append(ModelValidationIssue("benchmark_scores", "required_for_production"))
            if not record.failure_profile:
                issues.append(ModelValidationIssue("failure_profile", "required_for_production"))
            if not record.eval_regression_history:
                issues.append(ModelValidationIssue("eval_regression_history", "required_for_production"))
            if record.role in GENERATOR_ROLES and any(
                task in CERTIFICATION_TASKS for task in record.allowed_tasks
            ):
                issues.append(ModelValidationIssue("allowed_tasks", "generator_cannot_certify"))

        return issues

    def register(self, record: ModelAdmissionRecord) -> list[ModelValidationIssue]:
        issues = self.validate(record)
        if not issues:
            self.records[record.model_id] = record
        return issues

    def select_for_task(
        self, task: str, *, require_production: bool = False
    ) -> list[ModelAdmissionRecord]:
        allowed: list[ModelAdmissionRecord] = []
        for record in self.records.values():
            if task not in record.allowed_tasks or task in record.prohibited_tasks:
                continue
            if require_production and record.admission_status not in PRODUCTION_STATUSES:
                continue
            if self.validate(record):
                continue
            allowed.append(record)
        return sorted(allowed, key=lambda item: item.model_id)
