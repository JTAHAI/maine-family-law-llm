"""External, versioned API-contract comparison for the local workbench."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.evals.external_eval_root import ExternalEvalRootError, resolve_external_eval_root


BASELINE_FILENAME = "public_api_contract_baseline.json"
CONTRACT_VERSION = "v1"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


@dataclass
class ApiContractComparisonReport:
    status: str
    readiness: str
    generated_at: str
    current_contract_version: str
    current_contract_sha256: str
    endpoint_count: int
    added_endpoints: list[str] = field(default_factory=list)
    removed_endpoints: list[str] = field(default_factory=list)
    changed_endpoints: list[str] = field(default_factory=list)
    deprecation_warnings: list[str] = field(default_factory=list)
    migration_actions: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    review_required: bool = True
    network_used: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "api_contract_comparison_report_v1",
            "status": self.status,
            "readiness": self.readiness,
            "generated_at": self.generated_at,
            "current_contract_version": self.current_contract_version,
            "current_contract_sha256": self.current_contract_sha256,
            "endpoint_count": self.endpoint_count,
            "added_endpoints": self.added_endpoints,
            "removed_endpoints": self.removed_endpoints,
            "changed_endpoints": self.changed_endpoints,
            "deprecation_warnings": self.deprecation_warnings,
            "migration_actions": self.migration_actions,
            "blockers": self.blockers,
            "review_required": self.review_required,
            "network_used": self.network_used,
        }


class ApiStabilityProgram:
    """Compare the declared public surface with an external frozen baseline."""

    def __init__(self, *, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()

    def snapshot(self) -> dict[str, Any]:
        from app.api.contracts import EndpointInventory

        endpoints = [
            {
                "method": item["method"],
                "path": item["path"],
                "review_required": bool(item["review_required"]),
                "surface": item["surface"],
            }
            for item in EndpointInventory().as_dict()["endpoints"]
        ]
        endpoints.sort(key=lambda item: (item["path"], item["method"], item["surface"]))
        body = {"contract_version": CONTRACT_VERSION, "endpoints": endpoints}
        return {**body, "contract_sha256": _digest(body)}

    def compare(self, *, baseline_root: str | Path | None) -> ApiContractComparisonReport:
        current = self.snapshot()
        if baseline_root is None or not str(baseline_root).strip():
            return self._report(current, blockers=["external_api_contract_baseline_not_configured"])
        try:
            root = resolve_external_eval_root(baseline_root, project_root=self.project_root, create=False)
        except ExternalEvalRootError as exc:
            return self._report(current, blockers=[exc.code])
        path = root / BASELINE_FILENAME
        try:
            baseline = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return self._report(current, blockers=["external_api_contract_baseline_unavailable"])
        if not isinstance(baseline, dict) or baseline.get("schema_version") != "public_api_contract_baseline_v1":
            return self._report(current, blockers=["external_api_contract_baseline_schema_unsupported"])
        baseline_endpoints = baseline.get("endpoints")
        if not isinstance(baseline_endpoints, list):
            return self._report(current, blockers=["external_api_contract_baseline_malformed"])
        current_rows = {self._key(row): row for row in current["endpoints"]}
        baseline_rows = {self._key(row): row for row in baseline_endpoints if isinstance(row, dict)}
        added = sorted(set(current_rows) - set(baseline_rows))
        removed = sorted(set(baseline_rows) - set(current_rows))
        changed = sorted(key for key in set(current_rows) & set(baseline_rows) if current_rows[key] != self._normalized_row(baseline_rows[key]))
        deprecated = sorted(str(value) for value in baseline.get("deprecated_endpoints") or [] if str(value))
        blockers: list[str] = []
        if removed:
            blockers.append("public_api_endpoint_removed")
        if changed:
            blockers.append("public_api_endpoint_contract_changed")
        migration_actions = [f"publish_deprecation_notice:{item}" for item in deprecated]
        migration_actions.extend(f"major_version_or_compatibility_adapter_required:{item}" for item in [*removed, *changed])
        return ApiContractComparisonReport(
            status="pass" if not blockers else "blocked",
            readiness="public_api_contract_compatible" if not blockers else "public_api_contract_breaking_change_detected",
            generated_at=_now(),
            current_contract_version=CONTRACT_VERSION,
            current_contract_sha256=current["contract_sha256"],
            endpoint_count=len(current_rows),
            added_endpoints=added,
            removed_endpoints=removed,
            changed_endpoints=changed,
            deprecation_warnings=deprecated,
            migration_actions=migration_actions,
            blockers=blockers,
        )

    @staticmethod
    def _normalized_row(value: dict[str, Any]) -> dict[str, Any]:
        return {
            "method": str(value.get("method") or ""),
            "path": str(value.get("path") or ""),
            "review_required": bool(value.get("review_required")),
            "surface": str(value.get("surface") or ""),
        }

    @classmethod
    def _key(cls, value: dict[str, Any]) -> str:
        row = cls._normalized_row(value)
        return f"{row['method']} {row['path']} [{row['surface']}]"

    def _report(self, current: dict[str, Any], *, blockers: list[str]) -> ApiContractComparisonReport:
        return ApiContractComparisonReport(
            status="blocked",
            readiness="public_api_contract_baseline_required",
            generated_at=_now(),
            current_contract_version=CONTRACT_VERSION,
            current_contract_sha256=current["contract_sha256"],
            endpoint_count=len(current["endpoints"]),
            blockers=blockers,
        )


__all__ = ["ApiStabilityProgram", "ApiContractComparisonReport", "BASELINE_FILENAME", "CONTRACT_VERSION"]
