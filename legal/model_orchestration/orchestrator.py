from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from .registry import ModelRegistry


class ModelWorker(Protocol):
    def run(self, payload: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class OrchestrationResult:
    task: str
    role: str
    model_id: str | None
    status: str
    output: dict[str, Any]
    audit: dict[str, Any] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)


class DeterministicFallbackWorker:
    """Safe non-LLM fallback for roles that are not backed by an admitted model."""

    def __init__(self, role: str):
        self.role = role

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "fallback_review_required",
            "role": self.role,
            "summary": "No admitted model worker was available; route to deterministic code or human review.",
            "input_keys": sorted(payload.keys()),
        }


class ModelOrchestrator:
    def __init__(self, registry: ModelRegistry):
        self.registry = registry
        self.workers: dict[str, ModelWorker] = {}

    def register_worker(self, model_id: str, worker: ModelWorker) -> None:
        if model_id not in self.registry.records:
            raise KeyError(f"model is not admitted in registry: {model_id}")
        self.workers[model_id] = worker

    def run_task(
        self,
        task: str,
        payload: dict[str, Any],
        *,
        require_production: bool = False,
        preferred_model_id: str | None = None,
    ) -> OrchestrationResult:
        if task in {
            "citation_validity_certification",
            "quote_validity_certification",
            "authority_validity_certification",
            "filing_ready_certification",
        }:
            return OrchestrationResult(
                task=task,
                role="system_gate",
                model_id=None,
                status="blocked",
                output={},
                blockers=["models_may_not_certify_legal_validity"],
                audit=self._audit(task, None, "system_gate", "blocked"),
            )

        candidates = self.registry.select_for_task(task, require_production=require_production)
        if preferred_model_id:
            candidates = [candidate for candidate in candidates if candidate.model_id == preferred_model_id]

        if not candidates:
            roles = self.registry.role_catalog.roles_for_task(task)
            role_name = roles[0].role if roles else "unassigned"
            fallback = DeterministicFallbackWorker(role_name)
            output = fallback.run(payload)
            return OrchestrationResult(
                task=task,
                role=role_name,
                model_id=None,
                status="fallback_review_required",
                output=output,
                blockers=["no_admitted_model_for_task"],
                audit=self._audit(task, None, role_name, "fallback_review_required"),
            )

        chosen = candidates[0]
        worker = self.workers.get(chosen.model_id, DeterministicFallbackWorker(chosen.role))
        output = worker.run(payload)
        status = str(output.get("status", "completed_review_required"))
        return OrchestrationResult(
            task=task,
            role=chosen.role,
            model_id=chosen.model_id,
            status=status,
            output=output,
            blockers=[] if chosen.model_id in self.workers else ["worker_not_registered_used_fallback"],
            audit=self._audit(task, chosen.model_id, chosen.role, status),
        )

    @staticmethod
    def _audit(task: str, model_id: str | None, role: str, status: str) -> dict[str, Any]:
        return {
            "event_type": "model_orchestration",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task": task,
            "model_id": model_id,
            "role": role,
            "status": status,
            "review_required_by_default": True,
        }
