"""Model orchestration primitives for Maine Family Law LLM.

Models are replaceable workers. This package intentionally does not include
weights, private prompts, hosted credentials, or production runtime state.
"""

from .governance import (
    ModelGovernanceAuditor,
    ModelGovernanceReport,
    ModelReplacementEvent,
    ModelReplacementLedger,
)
from .orchestrator import ModelOrchestrator, OrchestrationResult
from .registry import ModelAdmissionRecord, ModelRegistry, ModelValidationIssue
from .roles import ModelRolePolicy, RoleCatalog

__all__ = [
    "ModelAdmissionRecord",
    "ModelGovernanceAuditor",
    "ModelGovernanceReport",
    "ModelOrchestrator",
    "ModelRegistry",
    "ModelReplacementEvent",
    "ModelReplacementLedger",
    "ModelRolePolicy",
    "ModelValidationIssue",
    "OrchestrationResult",
    "RoleCatalog",
]
