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
        fallback_mode: str = "deterministic",
    ) -> OrchestrationResult:
        route = self.route_task(
            task,
            require_production=require_production,
            preferred_model_id=preferred_model_id,
            fallback_mode=fallback_mode,
        )
        if route["status"] == "blocked":
            return OrchestrationResult(
                task=task,
                role=route["role"],
                model_id=None,
                status="blocked",
                output={},
                blockers=list(route["blockers"]),
                audit=self._audit(task, None, route["role"], "blocked"),
            )

        chosen_id = route["selected_model_id"]
        if chosen_id is None:
            fallback = DeterministicFallbackWorker(route["role"])
            output = fallback.run(payload)
            return OrchestrationResult(
                task=task,
                role=route["role"],
                model_id=None,
                status="fallback_review_required",
                output=output,
                blockers=list(route["blockers"]),
                audit=self._audit(task, None, route["role"], "fallback_review_required"),
            )

        chosen = self.registry.get_record(chosen_id)
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

    def route_task(
        self,
        task: str,
        *,
        require_production: bool = False,
        preferred_model_id: str | None = None,
        fallback_mode: str = "deterministic",
    ) -> dict[str, Any]:
        if task in {
            "citation_validity_certification",
            "quote_validity_certification",
            "authority_validity_certification",
            "filing_ready_certification",
        }:
            return {
            "task": task,
            "role": "system_gate",
            "selected_model_id": None,
            "status": "blocked",
            "blockers": ["models_may_not_certify_legal_validity"],
            "candidates": [],
            "fallback_mode": "deterministic_system_gate",
            "available_fallbacks": ["deterministic", "lexical_only", "rules_only"],
        }

        candidates = self.registry.select_for_task(task, require_production=require_production)
        if preferred_model_id:
            candidates = [candidate for candidate in candidates if candidate.model_id == preferred_model_id]

        if not candidates:
            roles = self.registry.role_catalog.roles_for_task(task)
            role_name = roles[0].role if roles else "unassigned"
            return {
                "task": task,
                "role": role_name,
                "selected_model_id": None,
                "status": "fallback_review_required",
                "blockers": ["no_admitted_model_for_task"],
                "candidates": [candidate.model_id for candidate in candidates],
                "fallback_mode": fallback_mode,
                "available_fallbacks": ["deterministic", "lexical_only", "rules_only"],
            }

        chosen = candidates[0]
        return {
            "task": task,
            "role": chosen.role,
            "selected_model_id": chosen.model_id,
            "status": "ready",
            "blockers": [],
            "candidates": [candidate.model_id for candidate in candidates],
            "fallback_mode": "model_worker_or_deterministic_fallback",
            "available_fallbacks": ["deterministic", "lexical_only", "rules_only"],
        }

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
