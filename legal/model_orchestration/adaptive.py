"""Hardware-aware, fail-closed planning for local model work."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .hardware import HardwareProfile
from .registry import ModelAdmissionRecord

GIB = 1024**3
ADMITTED_STATUSES = {
    "admitted_for_dev",
    "admitted_with_limits",
    "admitted_for_production",
}
PROTECTED_TASKS = {
    "authority_validity_certification",
    "citation_validity_certification",
    "filing_ready_certification",
    "quote_validity_certification",
}


@dataclass(frozen=True)
class RuntimeBudget:
    tier: str
    memory_budget_bytes: int
    reserve_bytes: int
    context_tokens: int
    concurrency: int
    accelerator: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "memory_budget_bytes": self.memory_budget_bytes,
            "reserve_bytes": self.reserve_bytes,
            "context_tokens": self.context_tokens,
            "concurrency": self.concurrency,
            "accelerator": self.accelerator,
        }


def runtime_budget(profile: HardwareProfile) -> RuntimeBudget:
    """Reserve RAM for Windows and the workbench before admitting a model."""

    total = max(0, profile.total_memory_bytes)
    available = max(0, profile.available_memory_bytes or total)
    if total and total < 8 * GIB:
        tier, ratio, context, concurrency = "essential", 0.42, 2048, 1
    elif total and total < 16 * GIB:
        tier, ratio, context, concurrency = "efficient", 0.52, 4096, 1
    elif total and total < 32 * GIB:
        tier, ratio, context, concurrency = "standard", 0.62, 8192, 1
    else:
        tier, ratio, context, concurrency = "performance", 0.70, 16384, 2
    reserve = max(2 * GIB, int(total * 0.2)) if total else 2 * GIB
    memory_budget = max(0, min(int(available * ratio), max(0, total - reserve) or available))
    accelerator = "gpu" if profile.vram_bytes else ("hinted" if profile.gpu_hint else "cpu")
    if accelerator == "cpu":
        concurrency = 1
    return RuntimeBudget(
        tier=tier,
        memory_budget_bytes=memory_budget,
        reserve_bytes=reserve,
        context_tokens=min(context, profile.recommended_context_limit or context),
        concurrency=min(concurrency, max(1, profile.recommended_concurrency)),
        accelerator=accelerator,
    )


def estimate_peak_memory(model: ModelAdmissionRecord, context_tokens: int) -> int:
    """Conservative admission estimate including weights, runtime, and KV cache."""

    artifact = max(0, model.artifact_size_bytes)
    declared = max(0, model.min_ram_bytes)
    runtime_overhead = max(768 * 1024**2, int(artifact * 0.35))
    kv_cache = max(256 * 1024**2, max(1, context_tokens) * 128 * 1024)
    return max(declared, artifact + runtime_overhead + kv_cache)


class AdaptiveRuntimePlanner:
    """Select an admitted model only when the current machine has safe headroom."""

    def __init__(self, profile: HardwareProfile):
        self.profile = profile
        self.budget = runtime_budget(profile)

    def plan(
        self,
        *,
        task: str,
        models: Iterable[ModelAdmissionRecord],
        requested_context_tokens: int = 0,
        requested_concurrency: int = 1,
        active_model_jobs: int = 0,
        require_production: bool = False,
    ) -> dict[str, Any]:
        normalized_task = str(task or "general_chat").strip().casefold()
        if normalized_task in PROTECTED_TASKS:
            return self._blocked(
                normalized_task,
                ["models_may_not_certify_legal_or_filing_validity"],
            )
        explicit_context = requested_context_tokens > 0
        context = max(512, requested_context_tokens or self.budget.context_tokens)
        context = min(context, self.budget.context_tokens)
        concurrency = max(1, requested_concurrency)
        blockers: list[str] = []
        if concurrency > self.budget.concurrency:
            blockers.append("requested_concurrency_exceeds_safe_budget")
        if active_model_jobs >= self.budget.concurrency:
            blockers.append("runtime_backpressure_active")

        evaluated: list[dict[str, Any]] = []
        for model in models:
            reasons: list[str] = []
            model_context = context
            if model.admission_status not in ADMITTED_STATUSES:
                reasons.append("model_not_admitted")
            if require_production and model.admission_status != "admitted_for_production":
                reasons.append("production_admission_required")
            if normalized_task in model.prohibited_tasks:
                reasons.append("task_prohibited")
            if model.allowed_tasks and normalized_task not in model.allowed_tasks:
                reasons.append("task_not_allowed")
            if model.network_policy != "loopback_only":
                reasons.append("loopback_only_policy_required")
            if model.context_limit_tokens and context > model.context_limit_tokens:
                if explicit_context:
                    reasons.append("model_context_limit_exceeded")
                else:
                    model_context = model.context_limit_tokens
            if model.min_vram_bytes and model.min_vram_bytes > self.profile.vram_bytes:
                reasons.append("insufficient_vram")
            peak = estimate_peak_memory(model, model_context)
            if peak > self.budget.memory_budget_bytes:
                reasons.append("insufficient_safe_memory_headroom")
            evaluated.append(
                {
                    "model_id": model.model_id,
                    "eligible": not reasons,
                    "estimated_peak_memory_bytes": peak,
                    "reasons": reasons,
                    "supports_streaming": model.supports_streaming,
                    "context_tokens": model_context,
                }
            )

        eligible = [item for item in evaluated if item["eligible"]]
        eligible.sort(
            key=lambda item: (
                not bool(item["supports_streaming"]),
                int(item["estimated_peak_memory_bytes"]),
                str(item["model_id"]),
            )
        )
        if blockers or not eligible:
            return {
                **self._blocked(
                    normalized_task,
                    blockers or ["no_admitted_model_fits_current_hardware"],
                ),
                "candidates": evaluated,
            }
        selected = eligible[0]
        return {
            "schema_version": "adaptive_local_runtime_plan_v1",
            "status": "ready",
            "task": normalized_task,
            "selected_model_id": selected["model_id"],
            "context_tokens": selected["context_tokens"],
            "concurrency": concurrency,
            "streaming_preferred": bool(selected["supports_streaming"]),
            "budget": self.budget.as_dict(),
            "candidates": evaluated,
            "fallback": "deterministic_host_with_human_review",
            "remote_providers_enabled": False,
            "network_scope": "loopback_only",
            "review_required": True,
        }

    def _blocked(self, task: str, blockers: list[str]) -> dict[str, Any]:
        return {
            "schema_version": "adaptive_local_runtime_plan_v1",
            "status": "fallback_review_required",
            "task": task,
            "selected_model_id": None,
            "blockers": blockers,
            "budget": self.budget.as_dict(),
            "fallback": "deterministic_host_with_human_review",
            "remote_providers_enabled": False,
            "network_scope": "none",
            "review_required": True,
        }


__all__ = [
    "AdaptiveRuntimePlanner",
    "RuntimeBudget",
    "estimate_peak_memory",
    "runtime_budget",
]
