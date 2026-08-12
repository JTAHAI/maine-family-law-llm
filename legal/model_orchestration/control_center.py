from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .adapters import LocalRuntimeAdapter
from .hardware import HardwareProfile, profile_hardware
from .orchestrator import ModelOrchestrator
from .registry import ModelAdmissionRecord, ModelRegistry
from .roles import RoleCatalog
from .store import ModelStoreLayout, external_model_store_layout


@dataclass(frozen=True)
class ModelControlCenterSummary:
    store_root: str
    hardware: dict[str, Any]
    registry: dict[str, Any]
    routing: dict[str, Any]
    roles: dict[str, Any] = None  # type: ignore[assignment]
    admission_history: list[dict[str, Any]] = None  # type: ignore[assignment]
    storage: dict[str, Any] = None  # type: ignore[assignment]

    def as_dict(self) -> dict[str, Any]:
        return {
            "store_root": self.store_root,
            "hardware": dict(self.hardware),
            "registry": dict(self.registry),
            "routing": dict(self.routing),
            "roles": dict(self.roles or {}),
            "admission_history": list(self.admission_history or []),
            "storage": dict(self.storage or {}),
        }


class ModelControlCenter:
    def __init__(
        self,
        *,
        project_root: str | Path,
        role_catalog_path: str | Path,
        admission_policy_path: str | Path,
        registry_seed_path: str | Path | None = None,
        store_root: str | Path | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.role_catalog = RoleCatalog.from_config(role_catalog_path)
        self.layout: ModelStoreLayout = external_model_store_layout(store_root, project_root=self.project_root, create=True)
        self.registry = ModelRegistry(
            self.role_catalog,
            admission_policy_path,
            storage_root=self.layout.root,
            project_root=self.project_root,
        )
        self.registry_seed_path = Path(registry_seed_path) if registry_seed_path else None
        self._bootstrap_seed_records()
        self.hardware_profile: HardwareProfile = profile_hardware(self.layout.root)
        self.runtime_adapter = LocalRuntimeAdapter(
            provider_id="deterministic_local_governance",
            model_id="governance-control-center",
            capabilities={
                "validate_configuration": True,
                "availability": True,
                "license_report": True,
                "capability_report": True,
                "estimate_resources": True,
                "run_turn": True,
                "stream_turn": True,
                "cancel": True,
                "normalize_error": True,
                "healthcheck": True,
                "supports": True,
                "no_network_mode": True,
                "cleanup": True,
                "emit_provenance": True,
            },
            metadata={"license_status": "approved", "runtime_mode": "loopback_only"},
        )

    def _bootstrap_seed_records(self) -> None:
        if self.registry.records or self.registry_seed_path is None or not self.registry_seed_path.exists():
            return
        data = json.loads(self.registry_seed_path.read_text(encoding="utf-8"))
        for payload in data.get("records", []):
            record = ModelAdmissionRecord.from_dict(payload)
            self.registry.records[record.model_id] = record
        self.registry._persist(action="bootstrap_seed", record=next(iter(self.registry.records.values()))) if self.registry.records else None

    def refresh_hardware(self) -> dict[str, Any]:
        self.hardware_profile = profile_hardware(self.layout.root)
        return self.hardware_profile.as_dict()

    def list_models(self) -> dict[str, Any]:
        models = [record.as_dict() for record in self.registry.list_records()]
        return {
            "status": "pass" if models else "degraded",
            "store_root": str(self.layout.root),
            "model_count": len(models),
            "models": models,
            "hardware": self.hardware_profile.as_dict(),
            "roles": self.role_catalog.as_dict(),
            "admission_history": self.registry.admission_history(),
            "storage": {
                "root": str(self.layout.root),
                "registry": str(self.layout.registry),
                "artifacts": str(self.layout.artifacts),
                "runtime_profiles": str(self.layout.runtime_profiles),
                "benchmark_runs": str(self.layout.benchmark_runs),
                "health": str(self.layout.health),
                "logs": str(self.layout.logs),
                "cache": str(self.layout.cache),
                "quarantine": str(self.layout.quarantine),
                "routing": str(self.layout.routing),
            },
            "degraded_modes": [
                mode
                for mode in (
                    "no_model_admitted" if not models else "",
                    "low_memory" if "low_available_memory" in self.hardware_profile.warnings else "",
                    "low_disk" if "low_disk_space" in self.hardware_profile.warnings else "",
                )
                if mode
            ]
            or ["healthy"],
        }

    def get_model(self, model_id: str) -> dict[str, Any]:
        record = self.registry.get_record(model_id)
        return {
            "status": "pass",
            "model": record.as_dict(),
            "health": self.registry.health(model_id),
            "hardware": self.hardware_profile.as_dict(),
            "runtime_contract": self.runtime_contract(model_id),
        }

    def import_model(self, payload: dict[str, Any]) -> dict[str, Any]:
        record = ModelAdmissionRecord.from_dict(payload)
        issues = self.registry.import_record(record)
        return {
            "status": "fail" if issues else "pass",
            "model": record.as_dict(),
            "issues": [issue.__dict__ for issue in issues],
            "hardware": self.hardware_profile.as_dict(),
        }

    def validate_model(self, model_id: str) -> dict[str, Any]:
        record = self.registry.get_record(model_id)
        issues = self.registry.validate(record)
        return {
            "status": "pass" if not issues else "fail",
            "model_id": model_id,
            "issues": [issue.__dict__ for issue in issues],
            "model": record.as_dict(),
            "runtime_contract": self.runtime_contract(model_id),
        }

    def benchmark_model(self, model_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        record = self.registry.benchmark(model_id, payload)
        return {
            "status": "pass",
            "model": record.as_dict(),
            "hardware": self.hardware_profile.as_dict(),
            "benchmark_evidence": record.benchmark_evidence,
            "runtime_contract": self.runtime_contract(model_id),
        }

    def admit_model(self, model_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        record = self.registry.mark_admitted(
            model_id,
            reviewer=str(payload.get("reviewer") or payload.get("admission_reviewer") or ""),
            reason=str(payload.get("reason") or payload.get("admission_reason") or ""),
            production=bool(payload.get("production", False)),
        )
        return {"status": "pass", "model": record.as_dict()}

    def reject_model(self, model_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        record = self.registry.mark_rejected(
            model_id,
            reviewer=str(payload.get("reviewer") or ""),
            reason=str(payload.get("reason") or ""),
        )
        return {"status": "pass", "model": record.as_dict()}

    def quarantine_model(self, model_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        record = self.registry.mark_quarantined(
            model_id,
            reviewer=str(payload.get("reviewer") or ""),
            reason=str(payload.get("reason") or ""),
        )
        return {"status": "pass", "model": record.as_dict()}

    def cancel_model(self, model_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        record = self.registry.update_record(
            model_id,
            health_status="cancelled",
            admission_reason=str(payload.get("reason") or "cancelled_by_operator"),
        )
        return {"status": "pass", "model": record.as_dict()}

    def health(self, model_id: str) -> dict[str, Any]:
        return self.registry.health(model_id)

    def runtime_contract(self, model_id: str) -> dict[str, Any]:
        record = self.registry.get_record(model_id)
        adapter = LocalRuntimeAdapter(
            provider_id=record.runtime_provider or record.provider,
            model_id=record.model_id,
            loopback_only=record.network_policy == "loopback_only",
            remote_providers_enabled=False,
            capabilities={
                "supports_streaming": record.supports_streaming,
                "supports_structured_output": record.supports_structured_output,
                "supports_cancellation": record.supports_cancellation,
            },
            metadata={
                "license": record.license,
                "license_status": record.license_status,
                "runtime_executable": record.runtime_executable,
                "runtime_executable_hash": record.runtime_executable_hash,
                "runtime_version": record.runtime_version,
                "artifact_filename": record.artifact_filename,
            },
        )
        configuration = adapter.validate_configuration(
            {
                "runtime_executable": record.runtime_executable,
                "artifact_sha256": record.artifact_sha256,
                "license_status": record.license_status,
            }
        )
        return {
            "model_id": record.model_id,
            "availability": adapter.availability(),
            "version": adapter.version(),
            "license_report": adapter.license_report(),
            "capability_report": adapter.capability_report(),
            "estimate_resources": adapter.estimate_resources(
                {
                    "estimated_tokens": record.context_limit_tokens,
                    "artifact_size_bytes": record.artifact_size_bytes,
                    "estimated_disk_bytes": record.min_disk_bytes,
                }
            ),
            "configuration": configuration,
            "healthcheck": adapter.healthcheck(),
            "no_network_mode": adapter.no_network_mode(),
            "supports": {
                "streaming": adapter.supports("supports_streaming"),
                "structured_output": adapter.supports("supports_structured_output"),
                "cancellation": adapter.supports("supports_cancellation"),
            },
        }

    def estimate(self, payload: dict[str, Any]) -> dict[str, Any]:
        model_id = str(payload.get("model_id") or payload.get("id") or "")
        artifact_size_bytes = int(payload.get("artifact_size_bytes", 0) or 0)
        context_limit_tokens = int(payload.get("context_limit_tokens", 0) or 0)
        supports_streaming = bool(payload.get("supports_streaming", False))
        estimate = {
            "model_id": model_id,
            "artifact_size_bytes": artifact_size_bytes,
            "estimated_peak_memory_bytes": max(artifact_size_bytes * 3, context_limit_tokens * 1024),
            "recommended_context_limit": min(
                self.hardware_profile.recommended_context_limit,
                context_limit_tokens or self.hardware_profile.recommended_context_limit,
            ),
            "recommended_concurrency": self.hardware_profile.recommended_concurrency,
            "supports_streaming": supports_streaming,
            "hardware": self.hardware_profile.as_dict(),
        }
        if self.hardware_profile.available_memory_bytes and estimate["estimated_peak_memory_bytes"] > self.hardware_profile.available_memory_bytes:
            estimate["status"] = "constrained"
            estimate["warnings"] = ["estimated_peak_memory_exceeds_available_memory"]
        else:
            estimate["status"] = "pass"
            estimate["warnings"] = list(self.hardware_profile.warnings)
        return estimate

    def routing_status(
        self,
        *,
        task: str,
        preferred_model_id: str | None = None,
        require_production: bool = False,
        fallback_mode: str = "deterministic",
    ) -> dict[str, Any]:
        orchestrator = ModelOrchestrator(self.registry)
        route = orchestrator.route_task(
            task,
            require_production=require_production,
            preferred_model_id=preferred_model_id,
            fallback_mode=fallback_mode,
        )
        route["hardware"] = self.hardware_profile.as_dict()
        route["store_root"] = str(self.layout.root)
        route["model_count"] = len(self.registry.records)
        route["admitted_model_ids"] = [record.model_id for record in self.registry.list_records() if record.admission_status in {"admitted_for_dev", "admitted_with_limits", "admitted_for_production"}]
        route["fallback_selection"] = fallback_mode
        return route

    def summary(
        self,
        *,
        task: str = "draft_review",
        preferred_model_id: str | None = None,
        fallback_mode: str = "deterministic",
    ) -> ModelControlCenterSummary:
        return ModelControlCenterSummary(
            store_root=str(self.layout.root),
            hardware=self.hardware_profile.as_dict(),
            registry=self.list_models(),
            routing=self.routing_status(task=task, preferred_model_id=preferred_model_id, fallback_mode=fallback_mode),
            roles=self.role_catalog.as_dict(),
            admission_history=self.registry.admission_history(),
            storage={
                "root": str(self.layout.root),
                "registry": str(self.layout.registry),
                "quarantine": str(self.layout.quarantine),
                "benchmark_runs": str(self.layout.benchmark_runs),
            },
        )

    def dashboard(
        self,
        *,
        task: str = "draft_review",
        preferred_model_id: str | None = None,
        fallback_mode: str = "deterministic",
    ) -> dict[str, Any]:
        summary = self.summary(task=task, preferred_model_id=preferred_model_id, fallback_mode=fallback_mode).as_dict()
        summary["runtime_contracts"] = {
            record.model_id: self.runtime_contract(record.model_id)
            for record in self.registry.list_records()
        }
        return summary
