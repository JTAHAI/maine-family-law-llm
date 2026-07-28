from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .models import SkillManifest, SkillValidationError

_MAX_MANIFEST_BYTES = 256 * 1024
_MAX_MANIFESTS = 256
_MAX_REGISTRY_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class RegistryValidationReport:
    status: str
    skill_count: int
    skills: tuple[str, ...]
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "skill_count": self.skill_count,
            "skills": list(self.skills),
            "errors": list(self.errors),
        }


class SkillRegistry:
    """Read-only registry for declarative, non-executable legal workflow skills."""

    def __init__(self, manifests: Iterable[SkillManifest] = ()) -> None:
        self._skills: dict[str, SkillManifest] = {}
        for manifest in manifests:
            self.register(manifest)

    def register(self, manifest: SkillManifest) -> None:
        if manifest.name in self._skills:
            raise SkillValidationError(f"duplicate skill: {manifest.name}")
        self._skills[manifest.name] = manifest

    def get(self, name: str) -> SkillManifest | None:
        return self._skills.get(name)

    def list(self) -> tuple[SkillManifest, ...]:
        return tuple(self._skills[name] for name in sorted(self._skills))

    def validate_dependencies(self) -> RegistryValidationReport:
        errors: list[str] = []
        for manifest in self.list():
            for dependency in manifest.dependencies:
                if dependency.optional:
                    continue
                if dependency.name not in self._skills:
                    errors.append(
                        f"{manifest.name}: missing required dependency {dependency.name}"
                    )
        return RegistryValidationReport(
            status="pass" if not errors else "fail",
            skill_count=len(self._skills),
            skills=tuple(sorted(self._skills)),
            errors=tuple(errors),
        )

    @classmethod
    def from_directory(cls, directory: Path) -> "SkillRegistry":
        requested = directory.expanduser()
        if requested.is_symlink():
            raise SkillValidationError(f"symlink registry roots are not allowed: {requested}")
        root = requested.resolve(strict=True)
        if not root.is_dir():
            raise SkillValidationError(f"skill directory is not a directory: {root}")
        paths = sorted(root.glob("*.json"))
        if len(paths) > _MAX_MANIFESTS:
            raise SkillValidationError(
                f"registry contains too many manifests: {len(paths)} > {_MAX_MANIFESTS}"
            )
        total_bytes = 0
        manifests: list[SkillManifest] = []
        for path in paths:
            if path.is_symlink():
                raise SkillValidationError(f"symlink manifests are not allowed: {path}")
            resolved = path.resolve(strict=True)
            if root not in resolved.parents:
                raise SkillValidationError(f"manifest escapes registry root: {path}")
            size = resolved.stat().st_size
            if size > _MAX_MANIFEST_BYTES:
                raise SkillValidationError(f"manifest is too large: {path.name}")
            total_bytes += size
            if total_bytes > _MAX_REGISTRY_BYTES:
                raise SkillValidationError(
                    f"registry is too large: {total_bytes} > {_MAX_REGISTRY_BYTES} bytes"
                )
            try:
                payload = json.loads(resolved.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise SkillValidationError(f"cannot read {path.name}: {exc}") from exc
            if not isinstance(payload, dict):
                raise SkillValidationError(f"manifest must be a JSON object: {path.name}")
            manifests.append(SkillManifest.from_dict(payload))
        return cls(manifests)
