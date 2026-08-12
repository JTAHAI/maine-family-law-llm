from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModelRolePolicy:
    role: str
    allowed_tasks: tuple[str, ...]
    prohibited_tasks: tuple[str, ...]
    requires_grounding: bool
    may_generate_legal_prose: bool
    permitted_input_lanes: tuple[str, ...] = ()
    output_schema: dict[str, Any] = field(default_factory=dict)
    required_evidence: tuple[str, ...] = ()
    prohibited_actions: tuple[str, ...] = ()
    max_context_tokens: int = 0
    required_privacy_statuses: tuple[str, ...] = ()
    requires_cancellation_support: bool = False
    requires_human_review: bool = True
    fallback_behavior: str = "deterministic_fallback"
    verifier_role: str = ""

    def allows(self, task: str) -> bool:
        return task in self.allowed_tasks and task not in self.prohibited_tasks


class RoleCatalog:
    def __init__(self, roles: dict[str, ModelRolePolicy], version: str):
        self.roles = roles
        self.version = version

    @classmethod
    def from_config(cls, path: str | Path) -> "RoleCatalog":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        roles = {
            name: ModelRolePolicy(
                role=name,
                allowed_tasks=tuple(value.get("allowed_tasks", [])),
                prohibited_tasks=tuple(value.get("prohibited_tasks", [])),
                requires_grounding=bool(value.get("requires_grounding", True)),
                may_generate_legal_prose=bool(value.get("may_generate_legal_prose", False)),
                permitted_input_lanes=tuple(value.get("permitted_input_lanes", [])),
                output_schema=dict(value.get("output_schema", {})),
                required_evidence=tuple(value.get("required_evidence", [])),
                prohibited_actions=tuple(value.get("prohibited_actions", [])),
                max_context_tokens=int(value.get("max_context_tokens", 0) or 0),
                required_privacy_statuses=tuple(value.get("required_privacy_statuses", [])),
                requires_cancellation_support=bool(value.get("requires_cancellation_support", False)),
                requires_human_review=bool(value.get("requires_human_review", True)),
                fallback_behavior=str(value.get("fallback_behavior", "deterministic_fallback")),
                verifier_role=str(value.get("verifier_role", "")),
            )
            for name, value in data.get("roles", {}).items()
        }
        return cls(roles=roles, version=str(data.get("version", "unknown")))

    def get(self, role: str) -> ModelRolePolicy:
        if role not in self.roles:
            raise KeyError(f"unknown model role: {role}")
        return self.roles[role]

    def roles_for_task(self, task: str) -> list[ModelRolePolicy]:
        return [role for role in self.roles.values() if role.allows(task)]

    def validate_task(self, role: str, task: str) -> list[str]:
        policy = self.get(role)
        issues: list[str] = []
        if task not in policy.allowed_tasks:
            issues.append(f"task_not_allowed:{task}")
        if task in policy.prohibited_tasks:
            issues.append(f"task_prohibited:{task}")
        return issues

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "roles": {
                name: {
                    "allowed_tasks": list(policy.allowed_tasks),
                    "prohibited_tasks": list(policy.prohibited_tasks),
                    "requires_grounding": policy.requires_grounding,
                    "may_generate_legal_prose": policy.may_generate_legal_prose,
                    "permitted_input_lanes": list(policy.permitted_input_lanes),
                    "output_schema": dict(policy.output_schema),
                    "required_evidence": list(policy.required_evidence),
                    "prohibited_actions": list(policy.prohibited_actions),
                    "max_context_tokens": policy.max_context_tokens,
                    "required_privacy_statuses": list(policy.required_privacy_statuses),
                    "requires_cancellation_support": policy.requires_cancellation_support,
                    "requires_human_review": policy.requires_human_review,
                    "fallback_behavior": policy.fallback_behavior,
                    "verifier_role": policy.verifier_role,
                }
                for name, policy in sorted(self.roles.items())
            },
        }
