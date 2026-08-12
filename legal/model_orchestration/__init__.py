"""Model orchestration primitives for Maine Family Law LLM.

Models are replaceable workers. This package intentionally does not include
weights, private prompts, hosted credentials, or production runtime state.
"""

from .adapters import LocalRuntimeAdapter, RuntimeAdapter
from .adaptive import AdaptiveRuntimePlanner, RuntimeBudget, estimate_peak_memory, runtime_budget
from .control_center import ModelControlCenter, ModelControlCenterSummary
from .governance import (
    ModelGovernanceAuditor,
    ModelGovernanceReport,
    ModelReplacementEvent,
    ModelReplacementLedger,
)
from .hardware import HardwareProfile, profile_hardware
from .orchestrator import ModelOrchestrator, OrchestrationResult
from .registry import ModelAdmissionRecord, ModelRegistry, ModelValidationIssue
from .roles import ModelRolePolicy, RoleCatalog

__all__ = [
    "ModelAdmissionRecord",
    "AdaptiveRuntimePlanner",
    "ModelGovernanceAuditor",
    "ModelGovernanceReport",
    "HardwareProfile",
    "LocalRuntimeAdapter",
    "ModelControlCenter",
    "ModelControlCenterSummary",
    "ModelOrchestrator",
    "ModelRegistry",
    "ModelReplacementEvent",
    "ModelReplacementLedger",
    "ModelRolePolicy",
    "ModelValidationIssue",
    "OrchestrationResult",
    "RoleCatalog",
    "RuntimeAdapter",
    "RuntimeBudget",
    "estimate_peak_memory",
    "profile_hardware",
    "runtime_budget",
]
