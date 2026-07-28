from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_SKILL_NAME_RE = re.compile(r"maine-[a-z0-9]+(?:-[a-z0-9]+)*")
_VERSION_RE = re.compile(r"\d+\.\d+\.\d+")
_ALLOWED_ROLES = {"matter_worker", "research_worker", "draft_worker", "independent_qc", "human_reviewer"}
_ALLOWED_PHASES = {
    "intake",
    "record_organization",
    "research",
    "evidence_review",
    "drafting",
    "quality_control",
    "human_review",
    "release",
}
_ALLOWED_PERMISSIONS = {"read_files", "write_derived_files", "read_official_sources", "network_official_only"}


class SkillValidationError(ValueError):
    """Raised when a workflow skill manifest violates the safe contract."""


@dataclass(frozen=True)
class SkillDependency:
    name: str
    optional: bool = False

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SkillDependency":
        name = str(value.get("name", "")).strip()
        if not _SKILL_NAME_RE.fullmatch(name):
            raise SkillValidationError(f"invalid dependency name: {name!r}")
        return cls(name=name, optional=bool(value.get("optional", False)))


@dataclass(frozen=True)
class SkillManifest:
    name: str
    version: str
    title: str
    description: str
    module: str
    user_role: str
    phases: tuple[str, ...]
    categories: tuple[str, ...]
    permissions: tuple[str, ...] = ()
    dependencies: tuple[SkillDependency, ...] = ()
    output_contract: str = "structured_json"
    review_required: bool = True
    network_allowed: bool = False
    source_requirements: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SkillManifest":
        name = str(value.get("name", "")).strip()
        version = str(value.get("version", "")).strip()
        title = str(value.get("title", "")).strip()
        description = str(value.get("description", "")).strip()
        module = str(value.get("module", "")).strip()
        user_role = str(value.get("user_role", "")).strip()
        phases = tuple(str(item).strip() for item in value.get("phases", []))
        categories = tuple(str(item).strip() for item in value.get("categories", []))
        permissions = tuple(str(item).strip() for item in value.get("permissions", []))
        source_requirements = tuple(
            str(item).strip() for item in value.get("source_requirements", [])
        )
        dependencies = tuple(
            SkillDependency.from_dict(item) for item in value.get("dependencies", [])
        )

        if not _SKILL_NAME_RE.fullmatch(name):
            raise SkillValidationError(f"invalid skill name: {name!r}")
        if not _VERSION_RE.fullmatch(version):
            raise SkillValidationError(f"invalid semantic version: {version!r}")
        if not title or len(title) > 120:
            raise SkillValidationError("title must be 1-120 characters")
        if not description or len(description) > 2000:
            raise SkillValidationError("description must be 1-2000 characters")
        if not module or not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", module):
            raise SkillValidationError(f"invalid module: {module!r}")
        if user_role not in _ALLOWED_ROLES:
            raise SkillValidationError(f"unsupported user_role: {user_role!r}")
        if not phases or any(phase not in _ALLOWED_PHASES for phase in phases):
            raise SkillValidationError(f"unsupported phases: {phases!r}")
        if not categories or any(not category for category in categories):
            raise SkillValidationError("at least one non-empty category is required")
        if any(permission not in _ALLOWED_PERMISSIONS for permission in permissions):
            raise SkillValidationError(f"unsupported permissions: {permissions!r}")
        network_allowed = bool(value.get("network_allowed", False))
        if network_allowed and "network_official_only" not in permissions:
            raise SkillValidationError(
                "network_allowed requires the network_official_only permission"
            )
        if user_role == "independent_qc" and module.startswith("draft"):
            raise SkillValidationError("independent QC skills cannot be drafting modules")
        if user_role == "draft_worker" and module.startswith("qc"):
            raise SkillValidationError("draft workers cannot be independent QC modules")

        metadata = value.get("metadata", {})
        if not isinstance(metadata, dict):
            raise SkillValidationError("metadata must be an object")

        return cls(
            name=name,
            version=version,
            title=title,
            description=description,
            module=module,
            user_role=user_role,
            phases=phases,
            categories=categories,
            permissions=permissions,
            dependencies=dependencies,
            output_contract=str(value.get("output_contract", "structured_json")),
            review_required=bool(value.get("review_required", True)),
            network_allowed=network_allowed,
            source_requirements=source_requirements,
            metadata=dict(metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "title": self.title,
            "description": self.description,
            "module": self.module,
            "user_role": self.user_role,
            "phases": list(self.phases),
            "categories": list(self.categories),
            "permissions": list(self.permissions),
            "dependencies": [
                {"name": item.name, "optional": item.optional} for item in self.dependencies
            ],
            "output_contract": self.output_contract,
            "review_required": self.review_required,
            "network_allowed": self.network_allowed,
            "source_requirements": list(self.source_requirements),
            "metadata": dict(self.metadata),
        }
