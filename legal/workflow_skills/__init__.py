"""Declarative Maine legal workflow skill contracts.

The contract design is adapted from the MIT-licensed A-market ECM lawyer plugin by
zeweihan and contributors. Skills are data only: loading a manifest never executes code.
"""

from .models import SkillDependency, SkillManifest, SkillValidationError
from .registry import RegistryValidationReport, SkillRegistry

__all__ = [
    "RegistryValidationReport",
    "SkillDependency",
    "SkillManifest",
    "SkillRegistry",
    "SkillValidationError",
]
