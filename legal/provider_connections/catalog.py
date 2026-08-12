from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


CATALOG_PATH = Path(__file__).resolve().parents[2] / "configs" / "maine_provider_catalog.json"


@dataclass(frozen=True)
class ProviderCatalogEntry:
    provider_id: str
    api_class: str
    endpoint_class: str
    requested_retention_mode: str
    region_data_controls: str
    cost_estimate_basis: str
    tool_support: tuple[str, ...]
    compatibility_profile_version: str
    last_successful_contract_test: str
    admission_status: str
    structured_output: bool
    streaming: bool
    cancellation: bool
    requires_manual_endpoint_configuration: bool
    retention_summary: str
    default_model_policy: str = "operator_selected"
    notes: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProviderCatalogEntry":
        return cls(
            provider_id=str(payload.get("provider_id") or ""),
            api_class=str(payload.get("api_class") or "unknown"),
            endpoint_class=str(payload.get("endpoint_class") or "unknown"),
            requested_retention_mode=str(payload.get("requested_retention_mode") or "unknown"),
            region_data_controls=str(payload.get("region_data_controls") or ""),
            cost_estimate_basis=str(payload.get("cost_estimate_basis") or ""),
            tool_support=tuple(str(item) for item in payload.get("tool_support") or []),
            compatibility_profile_version=str(payload.get("compatibility_profile_version") or "unknown"),
            last_successful_contract_test=str(payload.get("last_successful_contract_test") or ""),
            admission_status=str(payload.get("admission_status") or "admitted_with_limits"),
            structured_output=bool(payload.get("structured_output", False)),
            streaming=bool(payload.get("streaming", False)),
            cancellation=bool(payload.get("cancellation", False)),
            requires_manual_endpoint_configuration=bool(payload.get("requires_manual_endpoint_configuration", True)),
            retention_summary=str(payload.get("retention_summary") or ""),
            default_model_policy=str(payload.get("default_model_policy") or "operator_selected"),
            notes=str(payload.get("notes") or ""),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "api_class": self.api_class,
            "endpoint_class": self.endpoint_class,
            "requested_retention_mode": self.requested_retention_mode,
            "region_data_controls": self.region_data_controls,
            "cost_estimate_basis": self.cost_estimate_basis,
            "tool_support": list(self.tool_support),
            "compatibility_profile_version": self.compatibility_profile_version,
            "last_successful_contract_test": self.last_successful_contract_test,
            "admission_status": self.admission_status,
            "structured_output": self.structured_output,
            "streaming": self.streaming,
            "cancellation": self.cancellation,
            "requires_manual_endpoint_configuration": self.requires_manual_endpoint_configuration,
            "retention_summary": self.retention_summary,
            "default_model_policy": self.default_model_policy,
            "notes": self.notes,
        }


@dataclass
class ProviderCatalog:
    entries: dict[str, ProviderCatalogEntry] = field(default_factory=dict)
    source_path: Path = CATALOG_PATH

    @classmethod
    def from_config(cls, path: str | Path = CATALOG_PATH) -> "ProviderCatalog":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        entries = {
            row["provider_id"]: ProviderCatalogEntry.from_dict(row)
            for row in payload.get("providers", [])
            if str(row.get("provider_id") or "").strip()
        }
        return cls(entries=entries, source_path=Path(path))

    def list(self) -> list[ProviderCatalogEntry]:
        return [self.entries[key] for key in sorted(self.entries)]

    def get(self, provider_id: str) -> ProviderCatalogEntry:
        key = str(provider_id or "").strip()
        if key not in self.entries:
            raise KeyError(f"unknown provider: {provider_id}")
        return self.entries[key]

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_path": str(self.source_path),
            "provider_count": len(self.entries),
            "providers": [entry.as_dict() for entry in self.list()],
        }
