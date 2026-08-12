from __future__ import annotations

import json
from hashlib import sha256
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .roles import RoleCatalog
from .store import ModelStoreLayout, external_model_store_layout

PRODUCTION_STATUSES = {"admitted_for_production", "admitted_with_limits"}
SAFE_PRIVACY_STATUSES = {"local_only", "private_cloud_reviewed", "hosted_optional_no_training"}
GENERATOR_ROLES = {"maine_final_generator", "maine_plain_language_explainer"}
CERTIFICATION_TASKS = {
    "citation_validity_certification",
    "quote_validity_certification",
    "authority_validity_certification",
    "filing_ready_certification",
}
DEFAULT_STATUS_VALUES = {
    "candidate",
    "testing",
    "admitted_for_dev",
    "admitted_with_limits",
    "admitted_for_production",
    "rejected",
    "quarantined",
    "superseded",
    "unavailable",
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
    display_name: str = ""
    source: str = ""
    upstream_project: str = ""
    upstream_version: str = ""
    license: str = ""
    artifact_path: str = ""
    artifact_sha256: str = ""
    artifact_size_bytes: int = 0
    quantization: str = ""
    architecture: str = ""
    context_limit_tokens: int = 0
    supported_output_schema: dict[str, Any] = field(default_factory=dict)
    runtime_identity: dict[str, Any] = field(default_factory=dict)
    allowed_roles: list[str] = field(default_factory=list)
    prohibited_roles: list[str] = field(default_factory=list)
    network_policy: str = "loopback_only"
    benchmark_runs: list[dict[str, Any]] = field(default_factory=list)
    min_ram_bytes: int = 0
    min_vram_bytes: int = 0
    estimated_disk_bytes: int = 0
    latency_class: str = ""
    supports_streaming: bool = False
    supports_structured_output: bool = False
    supports_cancellation: bool = False
    requires_human_review: bool = True
    verifier_role: str = ""
    admission_reviewer: str = ""
    admission_reason: str = ""
    admitted_at: str = ""
    updated_at: str = ""
    admission_source: str = ""
    health_status: str = ""
    source_project: str = ""
    source_url: str = ""
    license_status: str = "unknown"
    artifact_filename: str = ""
    runtime_provider: str = ""
    runtime_executable: str = ""
    runtime_executable_hash: str = ""
    runtime_version: str = ""
    benchmark_evidence: dict[str, Any] = field(default_factory=dict)
    min_disk_bytes: int = 0
    last_healthcheck_at: str = ""
    last_run_at: str = ""
    created_at: str = ""
    worker_type: str = ""

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
            display_name=str(data.get("display_name", "")),
            source=str(data.get("source", "")),
            upstream_project=str(data.get("upstream_project", "")),
            upstream_version=str(data.get("upstream_version", "")),
            license=str(data.get("license", "")),
            artifact_path=str(data.get("artifact_path", "")),
            artifact_sha256=str(data.get("artifact_sha256", "")),
            artifact_size_bytes=int(data.get("artifact_size_bytes", 0) or 0),
            quantization=str(data.get("quantization", "")),
            architecture=str(data.get("architecture", "")),
            context_limit_tokens=int(data.get("context_limit_tokens", 0) or 0),
            supported_output_schema=dict(data.get("supported_output_schema", {})),
            runtime_identity=dict(data.get("runtime_identity", {})),
            allowed_roles=list(data.get("allowed_roles", [])),
            prohibited_roles=list(data.get("prohibited_roles", [])),
            network_policy=str(data.get("network_policy", "loopback_only")),
            benchmark_runs=list(data.get("benchmark_runs", [])),
            min_ram_bytes=int(data.get("min_ram_bytes", 0) or 0),
            min_vram_bytes=int(data.get("min_vram_bytes", 0) or 0),
            estimated_disk_bytes=int(data.get("estimated_disk_bytes", 0) or 0),
            latency_class=str(data.get("latency_class", "")),
            supports_streaming=bool(data.get("supports_streaming", False)),
            supports_structured_output=bool(data.get("supports_structured_output", False)),
            supports_cancellation=bool(data.get("supports_cancellation", False)),
            requires_human_review=bool(data.get("requires_human_review", True)),
            verifier_role=str(data.get("verifier_role", "")),
            admission_reviewer=str(data.get("admission_reviewer", "")),
            admission_reason=str(data.get("admission_reason", "")),
            admitted_at=str(data.get("admitted_at", "")),
            updated_at=str(data.get("updated_at", "")),
            admission_source=str(data.get("admission_source", "")),
            health_status=str(data.get("health_status", "")),
            source_project=str(data.get("source_project", data.get("upstream_project", ""))),
            source_url=str(data.get("source_url", "")),
            license_status=str(data.get("license_status", "unknown")),
            artifact_filename=str(data.get("artifact_filename", "")),
            runtime_provider=str(data.get("runtime_provider", "unknown")),
            runtime_executable=str(data.get("runtime_executable", "")),
            runtime_executable_hash=str(data.get("runtime_executable_hash", "")),
            runtime_version=str(data.get("runtime_version", data.get("version", ""))),
            benchmark_evidence=dict(data.get("benchmark_evidence", {})),
            min_disk_bytes=int(data.get("min_disk_bytes", 0) or 0),
            last_healthcheck_at=str(data.get("last_healthcheck_at", "")),
            last_run_at=str(data.get("last_run_at", "")),
            created_at=str(data.get("created_at", "")),
            worker_type=str(data.get("worker_type", "")),
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
            "display_name": self.display_name,
            "source": self.source,
            "upstream_project": self.upstream_project,
            "upstream_version": self.upstream_version,
            "license": self.license,
            "artifact_path": self.artifact_path,
            "artifact_sha256": self.artifact_sha256,
            "artifact_size_bytes": self.artifact_size_bytes,
            "quantization": self.quantization,
            "architecture": self.architecture,
            "context_limit_tokens": self.context_limit_tokens,
            "supported_output_schema": dict(self.supported_output_schema),
            "runtime_identity": dict(self.runtime_identity),
            "allowed_roles": list(self.allowed_roles),
            "prohibited_roles": list(self.prohibited_roles),
            "network_policy": self.network_policy,
            "benchmark_runs": list(self.benchmark_runs),
            "min_ram_bytes": self.min_ram_bytes,
            "min_vram_bytes": self.min_vram_bytes,
            "estimated_disk_bytes": self.estimated_disk_bytes,
            "latency_class": self.latency_class,
            "supports_streaming": self.supports_streaming,
            "supports_structured_output": self.supports_structured_output,
            "supports_cancellation": self.supports_cancellation,
            "requires_human_review": self.requires_human_review,
            "verifier_role": self.verifier_role,
            "admission_reviewer": self.admission_reviewer,
            "admission_reason": self.admission_reason,
            "admitted_at": self.admitted_at,
            "updated_at": self.updated_at,
            "admission_source": self.admission_source,
            "health_status": self.health_status,
            "source_project": self.source_project,
            "source_url": self.source_url,
            "license_status": self.license_status,
            "artifact_filename": self.artifact_filename,
            "runtime_provider": self.runtime_provider,
            "runtime_executable": self.runtime_executable,
            "runtime_executable_hash": self.runtime_executable_hash,
            "runtime_version": self.runtime_version,
            "benchmark_evidence": dict(self.benchmark_evidence),
            "min_disk_bytes": self.min_disk_bytes,
            "last_healthcheck_at": self.last_healthcheck_at,
            "last_run_at": self.last_run_at,
            "created_at": self.created_at,
            "worker_type": self.worker_type,
        }


class ModelRegistry:
    def __init__(
        self,
        role_catalog: RoleCatalog,
        admission_policy_path: str | Path,
        *,
        storage_root: str | Path | None = None,
        project_root: str | Path = ".",
    ):
        self.role_catalog = role_catalog
        self.admission_policy = json.loads(Path(admission_policy_path).read_text(encoding="utf-8"))
        self.project_root = Path(project_root).resolve()
        self.storage_layout: ModelStoreLayout | None = None
        self.records: dict[str, ModelAdmissionRecord] = {}
        if storage_root is not None:
            self.storage_layout = external_model_store_layout(storage_root, project_root=self.project_root, create=True)
            self._load_persisted_records()

    def _records_path(self) -> Path | None:
        if self.storage_layout is None:
            return None
        return self.storage_layout.registry / "registry.json"

    def _history_path(self) -> Path | None:
        if self.storage_layout is None:
            return None
        return self.storage_layout.registry / "registry.jsonl"

    def _touch_storage_dirs(self) -> None:
        if self.storage_layout is not None:
            self.storage_layout.ensure()

    def _load_persisted_records(self) -> None:
        self._touch_storage_dirs()
        snapshot = self._records_path()
        history = self._history_path()
        payload: list[dict[str, Any]] = []
        if snapshot is not None and snapshot.exists():
            data = json.loads(snapshot.read_text(encoding="utf-8"))
            payload = list(data.get("records", []))
        elif history is not None and history.exists():
            for line in history.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                payload.append(json.loads(line).get("record", {}))
        for row in payload:
            record = ModelAdmissionRecord.from_dict(row)
            if record.model_id:
                self.records[record.model_id] = record

    def _persist(self, *, action: str, record: ModelAdmissionRecord) -> None:
        if self.storage_layout is None:
            return
        self._touch_storage_dirs()
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        history_path = self._history_path()
        if history_path is not None:
            history_path.parent.mkdir(parents=True, exist_ok=True)
            with history_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {
                            "timestamp": now,
                            "action": action,
                            "model_id": record.model_id,
                            "record": record.as_dict(),
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
        snapshot_path = self._records_path()
        if snapshot_path is not None:
            snapshot_path.write_text(
                json.dumps(
                    {
                        "schema_version": "maine_model_registry_v2",
                        "generated_at": now,
                        "records": [self.records[key].as_dict() for key in sorted(self.records)],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

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
            if role_policy.required_privacy_statuses and record.privacy_status not in role_policy.required_privacy_statuses:
                issues.append(ModelValidationIssue("privacy_status", "role_privacy_policy_mismatch"))
            if role_policy.requires_cancellation_support and not record.supports_cancellation:
                issues.append(ModelValidationIssue("supports_cancellation", "required_by_role"))

        if record.allowed_roles and record.role not in record.allowed_roles:
            issues.append(ModelValidationIssue("allowed_roles", "role_not_in_allowed_roles"))
        if record.prohibited_roles and record.role in record.prohibited_roles:
            issues.append(ModelValidationIssue("prohibited_roles", "role_in_prohibited_roles"))

        if record.privacy_status not in self.admission_policy.get("allowed_privacy_statuses", []):
            issues.append(ModelValidationIssue("privacy_status", "unknown_privacy_status"))
        if record.license_status not in self.admission_policy.get("allowed_license_statuses", ["approved"]):
            issues.append(ModelValidationIssue("license_status", "unknown_or_unapproved_license"))

        if record.admission_status not in self.admission_policy.get("allowed_admission_statuses", list(DEFAULT_STATUS_VALUES)):
            issues.append(ModelValidationIssue("admission_status", "unknown_admission_status"))

        if record.admission_status in PRODUCTION_STATUSES:
            if record.privacy_status not in SAFE_PRIVACY_STATUSES:
                issues.append(ModelValidationIssue("privacy_status", "not_production_safe"))
            if not record.benchmark_scores:
                issues.append(ModelValidationIssue("benchmark_scores", "required_for_production"))
            if not record.benchmark_evidence:
                issues.append(ModelValidationIssue("benchmark_evidence", "required_for_production"))
            if not record.failure_profile:
                issues.append(ModelValidationIssue("failure_profile", "required_for_production"))
            if not record.eval_regression_history:
                issues.append(ModelValidationIssue("eval_regression_history", "required_for_production"))
            if record.role in GENERATOR_ROLES and any(task in CERTIFICATION_TASKS for task in record.allowed_tasks):
                issues.append(ModelValidationIssue("allowed_tasks", "generator_cannot_certify"))
            if record.network_policy not in {"loopback_only", "offline_only", "airgapped"}:
                issues.append(ModelValidationIssue("network_policy", "not_production_safe"))
        if record.runtime_executable and any(token in record.runtime_executable for token in ("&&", "||", ";", "|", "`", "$(", ">", "<")):
            issues.append(ModelValidationIssue("runtime_executable", "shell_injection_refused"))
        if record.runtime_executable and any(part in record.runtime_executable.lower() for part in ("cmd.exe", "powershell.exe", "pwsh.exe")):
            issues.append(ModelValidationIssue("runtime_executable", "arbitrary_executable_refused"))
        if record.artifact_sha256 and len(record.artifact_sha256) != 64:
            issues.append(ModelValidationIssue("artifact_sha256", "invalid_sha256_length"))
        if record.artifact_path:
            artifact_path = Path(record.artifact_path)
            if artifact_path.exists() and artifact_path.is_file():
                digest = sha256(artifact_path.read_bytes()).hexdigest()
                if record.artifact_sha256 and digest != record.artifact_sha256:
                    issues.append(ModelValidationIssue("artifact_sha256", "hash_mismatch"))

        return issues

    def register(self, record: ModelAdmissionRecord) -> list[ModelValidationIssue]:
        issues = self.validate(record)
        if not issues:
            if not record.updated_at:
                record.updated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            self.records[record.model_id] = record
            self._persist(action="register", record=record)
        return issues

    def import_record(self, record: ModelAdmissionRecord) -> list[ModelValidationIssue]:
        return self.register(record)

    def list_records(self) -> list[ModelAdmissionRecord]:
        return sorted(self.records.values(), key=lambda item: item.model_id)

    def get_record(self, model_id: str) -> ModelAdmissionRecord:
        if model_id not in self.records:
            raise KeyError(f"unknown model_id: {model_id}")
        return self.records[model_id]

    def update_record(self, model_id: str, **changes: Any) -> ModelAdmissionRecord:
        record = self.get_record(model_id)
        payload = record.as_dict()
        payload.update(changes)
        updated = ModelAdmissionRecord.from_dict(payload)
        updated.updated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        self.records[model_id] = updated
        self._persist(action="update", record=updated)
        return updated

    def mark_admitted(self, model_id: str, *, reviewer: str = "", reason: str = "", production: bool = False) -> ModelAdmissionRecord:
        status = "admitted_for_production" if production else "admitted_for_dev"
        return self.update_record(
            model_id,
            admission_status=status,
            admission_reviewer=reviewer,
            admission_reason=reason,
            admitted_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            health_status="admitted",
        )

    def mark_rejected(self, model_id: str, *, reviewer: str = "", reason: str = "") -> ModelAdmissionRecord:
        return self.update_record(
            model_id,
            admission_status="rejected",
            admission_reviewer=reviewer,
            admission_reason=reason,
            health_status="rejected",
        )

    def mark_quarantined(self, model_id: str, *, reviewer: str = "", reason: str = "") -> ModelAdmissionRecord:
        return self.update_record(
            model_id,
            admission_status="quarantined",
            admission_reviewer=reviewer,
            admission_reason=reason,
            health_status="quarantined",
        )

    def benchmark(self, model_id: str, benchmark_payload: dict[str, Any]) -> ModelAdmissionRecord:
        record = self.get_record(model_id)
        benchmark_runs = list(record.benchmark_runs)
        benchmark_runs.append(
            {
                "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                **benchmark_payload,
            }
        )
        benchmark_scores = dict(record.benchmark_scores)
        for key, value in benchmark_payload.get("scores", {}).items():
            try:
                benchmark_scores[str(key)] = float(value)
            except (TypeError, ValueError):
                continue
        benchmark_evidence = dict(record.benchmark_evidence)
        if benchmark_payload.get("evidence"):
            benchmark_evidence.update(dict(benchmark_payload["evidence"]))
        return self.update_record(
            model_id,
            benchmark_runs=benchmark_runs,
            benchmark_scores=benchmark_scores,
            benchmark_evidence=benchmark_evidence or dict(record.benchmark_evidence),
            last_run_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            health_status="benchmarked",
        )

    def health(self, model_id: str) -> dict[str, Any]:
        record = self.get_record(model_id)
        issues = self.validate(record)
        return {
            "model_id": model_id,
            "status": "healthy" if not issues else "degraded",
            "issues": [issue.__dict__ for issue in issues],
            "record": record.as_dict(),
            "last_healthcheck_at": record.last_healthcheck_at,
            "last_run_at": record.last_run_at,
        }

    def select_for_task(self, task: str, *, require_production: bool = False) -> list[ModelAdmissionRecord]:
        allowed: list[ModelAdmissionRecord] = []
        for record in self.records.values():
            if task not in record.allowed_tasks or task in record.prohibited_tasks:
                continue
            if require_production and record.admission_status not in PRODUCTION_STATUSES:
                continue
            if self.validate(record):
                continue
            allowed.append(record)
        return sorted(allowed, key=lambda item: (item.admission_status != "admitted_for_production", item.model_id))

    def admission_history(self) -> list[dict[str, Any]]:
        history_path = self._history_path()
        if history_path is None or not history_path.exists():
            return []
        entries: list[dict[str, Any]] = []
        for line in history_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries
