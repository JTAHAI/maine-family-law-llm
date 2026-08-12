"""Developer-only external evaluation adapter status and admission controls."""

from __future__ import annotations

import importlib.metadata
import importlib.util
from dataclasses import dataclass
from typing import Any


class ExternalEvalAdapterError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExternalEvalAdapterStatus:
    adapter_id: str
    available: bool
    version: str | None
    runtime_enabled: bool
    developer_ci_only: bool
    can_certify_legal_correctness: bool = False

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _available(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def _version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def external_eval_adapter_status() -> dict[str, Any]:
    return {
        "schema_version": "external_eval_adapters_v1",
        "adapters": [
            ExternalEvalAdapterStatus(
                adapter_id="deepeval",
                available=_available("deepeval"),
                version=_version("deepeval"),
                runtime_enabled=False,
                developer_ci_only=True,
            ).to_dict(),
            ExternalEvalAdapterStatus(
                adapter_id="promptfoo",
                available=False,
                version=None,
                runtime_enabled=False,
                developer_ci_only=True,
            ).to_dict(),
        ],
        "attorney_gold_remains_authoritative": True,
        "automatic_provider_calls": False,
        "private_matter_data_allowed": False,
        "review_required": True,
    }


def admit_deepeval_run(*, developer_ci: bool, dataset_attorney_reviewed: bool, private_matter_data: bool) -> dict[str, Any]:
    blockers: list[str] = []
    if developer_ci is not True:
        blockers.append("developer_ci_mode_required")
    if dataset_attorney_reviewed is not True:
        blockers.append("attorney_reviewed_dataset_required")
    if private_matter_data is True:
        blockers.append("private_matter_data_forbidden")
    if not _available("deepeval"):
        blockers.append("deepeval_not_installed")
    return {
        "status": "admitted" if not blockers else "blocked",
        "blockers": blockers,
        "can_certify_legal_correctness": False,
        "can_override_release_gates": False,
        "developer_ci_only": True,
        "review_required": True,
    }
