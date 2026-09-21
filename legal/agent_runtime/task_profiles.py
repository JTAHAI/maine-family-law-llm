"""Versioned, host-owned execution profiles for optional local reasoning.

Profiles are configuration for a bounded task, not a statement that a model has
been trained for it or admitted to make legal determinations.  They deliberately
separate a model's runtime identity from the task-specific output/verifier
contract so that a changed prompt or schema invalidates a prior approval.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any


# Coverage inventory and the bounded structured-output ceiling alter the exact
# approved task contract. Keep the human-readable revision in step with the
# hash so receipts and support investigations cannot mistake it for v1.
_PROFILE_REVISION = "qwen-task-profile-v2"
_CURATED_MODELS = frozenset({"qwen3:4b", "qwen3:8b"})
_TASK_OUTPUTS = {
    "evidence_review": "selected_spans_with_review_flags",
    "drafting": "selected_spans_with_draft_sections",
    "authority_review": "selected_official_authority_spans",
    "intake_triage": "unverified_review",
    "parenting_plan_review": "unverified_review",
    "financial_disclosure_review": "unverified_review",
    "safety_privacy_review": "unverified_review",
}


def task_profile(*, task: str | None, model_name: str) -> dict[str, Any]:
    """Return a deterministic profile for a permitted local Qwen task.

    ``model_name`` is intentionally a literal allowlist value.  The caller
    still has to establish what is installed locally before it may claim an
    artifact identity or task quality result.
    """

    if model_name not in _CURATED_MODELS:
        raise ValueError("curated_qwen_model_not_allowed")
    clean_task = str(task or "").strip()
    if clean_task not in _TASK_OUTPUTS:
        raise ValueError("curated_qwen_task_invalid")
    output_mode = _TASK_OUTPUTS[clean_task]
    payload = {
        "schema_version": "local_reasoning_task_profile_v1",
        "profile_revision": _PROFILE_REVISION,
        "task": clean_task,
        "model_name": model_name,
        "model_class": "reasoning_4b" if model_name == "qwen3:4b" else "reasoning_8b",
        "output_mode": output_mode,
        # This is the complete rendered prompt budget, including host task
        # instructions and the schema.  It intentionally remains conservative
        # until a pinned tokenizer measurement replaces it.
        "max_prompt_bytes": 5000,
        # This route emits a tightly constrained JSON selection, not a long
        # answer. A bounded output cap keeps the 8B opt-in usable on modest
        # hardware and limits late/partial structured generations. The host
        # renders only rechecked source text after the model finishes.
        "max_output_tokens": 768,
        "context_tokens": 8192,
        "thinking_mode": "disabled_for_bounded_source_tasks",
        "review_required": True,
        "source_references_required": True,
        "production_admitted": False,
        "quality_status": "local_runtime_only_not_legal_qualified",
    }
    digest_input = "|".join(f"{key}={payload[key]}" for key in sorted(payload))
    payload["profile_sha256"] = sha256(digest_input.encode("utf-8")).hexdigest()
    return payload
