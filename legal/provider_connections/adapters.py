from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class ProviderAdapter(Protocol):
    provider_id: str
    api_class: str
    pinned_model_id: str
    endpoint_class: str

    def validate_config(self) -> dict[str, Any]: ...
    def capability_report(self) -> dict[str, Any]: ...
    def healthcheck(self) -> dict[str, Any]: ...
    def estimate(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def run_turn(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def stream_turn(self, payload: dict[str, Any]) -> Any: ...
    def cancel(self, run_id: str) -> dict[str, Any]: ...
    def normalize_error(self, error: Exception) -> dict[str, Any]: ...
    def supports(self, capability: str) -> bool: ...
    def retention_summary(self) -> str: ...
    def usage_summary(self) -> dict[str, Any]: ...
    def disconnect(self) -> dict[str, Any]: ...
    def revoke(self) -> dict[str, Any]: ...


@dataclass
class ExternalProviderAdapter:
    provider_id: str
    api_class: str
    pinned_model_id: str
    endpoint_class: str
    request_path: str
    supports_structured_output: bool = False
    supports_streaming: bool = False
    supports_cancellation: bool = False
    requested_retention_mode: str = ""
    region_data_controls: str = ""
    cost_estimate_basis: str = ""
    documented_data_controls: str = ""
    tool_support: list[str] = field(default_factory=list)
    compatibility_profile_version: str = ""
    last_successful_contract_test: str = ""
    last_contract_test: str = ""
    retention_text: str = ""
    actual_usage: dict[str, Any] = field(default_factory=dict)
    transport: Any = None

    def validate_config(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "api_class": self.api_class,
            "pinned_model_id": self.pinned_model_id,
            "endpoint_class": self.endpoint_class,
            "request_path": self.request_path,
            "supports_structured_output": self.supports_structured_output,
            "supports_streaming": self.supports_streaming,
            "supports_cancellation": self.supports_cancellation,
            "requested_retention_mode": self.requested_retention_mode,
            "region_data_controls": self.region_data_controls,
            "cost_estimate_basis": self.cost_estimate_basis,
            "documented_data_controls": self.documented_data_controls,
            "tool_support": list(self.tool_support),
            "compatibility_profile_version": self.compatibility_profile_version,
            "last_successful_contract_test": self.last_successful_contract_test,
            "last_contract_test": self.last_contract_test or self.last_successful_contract_test,
        }

    def capability_report(self) -> dict[str, Any]:
        return {
            **self.validate_config(),
            "retention_summary": self.retention_summary(),
            "official_api_class": self.api_class,
            "pinned_model_id": self.pinned_model_id,
            "endpoint_class": self.endpoint_class,
            "structured_output": self.supports_structured_output,
            "streaming": self.supports_streaming,
            "cancellation": self.supports_cancellation,
            "tools": list(self.tool_support),
            "requested_retention_mode": self.requested_retention_mode,
            "documented_data_controls": self.documented_data_controls or self.retention_text,
            "region": self.region_data_controls,
            "estimated_cost_basis": self.cost_estimate_basis,
            "actual_usage": dict(self.actual_usage),
            "contract_status": "admitted_with_limits" if self.supports_cancellation and self.supports_structured_output else "admitted_with_limits",
        }

    def healthcheck(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "pinned_model_id": self.pinned_model_id,
            "status": "not_probed",
            "transport_configured": self.transport is not None,
            "request_path": self.request_path,
        }

    def estimate(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "estimated_tokens": int(payload.get("estimated_tokens") or 0),
            "estimated_cost_usd": payload.get("estimated_cost_usd"),
            "cost_estimate_basis": self.cost_estimate_basis,
        }

    def run_turn(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.transport is None:
            raise RuntimeError("provider_transport_unavailable")
        body = payload.get("body")
        if not isinstance(body, (bytes, bytearray)):
            raise ValueError("provider_payload_bytes_required")
        headers = dict(payload.get("headers") or {})
        timeout_seconds = int(payload.get("timeout_seconds") or 120)
        endpoint_url = str(payload.get("endpoint_url") or "")
        status_code, response_text, response_headers = self.transport(endpoint_url, self.request_path, headers, bytes(body), timeout_seconds)
        return {
            "provider_id": self.provider_id,
            "status_code": status_code,
            "response_text": response_text,
            "response_headers": response_headers,
        }

    def stream_turn(self, payload: dict[str, Any]) -> Any:
        return self.run_turn(payload)

    def cancel(self, run_id: str) -> dict[str, Any]:
        return {"provider_id": self.provider_id, "run_id": run_id, "cancelled": self.supports_cancellation}

    def normalize_error(self, error: Exception) -> dict[str, Any]:
        return {"provider_id": self.provider_id, "error_type": type(error).__name__, "message": str(error)}

    def supports(self, capability: str) -> bool:
        lookup = {
            "structured_output": self.supports_structured_output,
            "streaming": self.supports_streaming,
            "cancellation": self.supports_cancellation,
        }
        return bool(lookup.get(capability, False))

    def retention_summary(self) -> str:
        return self.retention_text

    def usage_summary(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "cost_estimate_basis": self.cost_estimate_basis,
            "request_path": self.request_path,
            "tool_support": list(self.tool_support),
            "actual_usage": dict(self.actual_usage),
        }

    def disconnect(self) -> dict[str, Any]:
        return {"provider_id": self.provider_id, "status": "disconnected"}

    def revoke(self) -> dict[str, Any]:
        return {"provider_id": self.provider_id, "status": "revoked"}

    def contract_report(self) -> dict[str, Any]:
        return {
            "provider": self.provider_id,
            "official_api_class": self.api_class,
            "pinned_model_id": self.pinned_model_id,
            "endpoint_class": self.endpoint_class,
            "structured_output": self.supports_structured_output,
            "streaming": self.supports_streaming,
            "cancellation": self.supports_cancellation,
            "tools": list(self.tool_support),
            "requested_retention_mode": self.requested_retention_mode,
            "documented_data_controls": self.documented_data_controls or self.retention_text,
            "region": self.region_data_controls,
            "estimated_cost_basis": self.cost_estimate_basis,
            "actual_usage": dict(self.actual_usage),
            "compatibility_profile_version": self.compatibility_profile_version,
            "last_contract_test": self.last_contract_test or self.last_successful_contract_test,
        }
