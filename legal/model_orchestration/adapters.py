from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol


class RuntimeAdapter(Protocol):
    provider_id: str
    model_id: str

    def validate_configuration(self, payload: dict[str, Any] | None = None) -> dict[str, Any]: ...

    def availability(self) -> dict[str, Any]: ...

    def version(self) -> dict[str, Any]: ...

    def license_report(self) -> dict[str, Any]: ...

    def healthcheck(self) -> dict[str, Any]: ...

    def capability_report(self) -> dict[str, Any]: ...

    def estimate_resources(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def estimate(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def run_turn(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def stream_turn(self, payload: dict[str, Any]) -> list[dict[str, Any]]: ...

    def cancel(self, run_id: str) -> dict[str, Any]: ...

    def normalize_error(self, error: Exception) -> dict[str, Any]: ...

    def no_network_mode(self) -> bool: ...

    def cleanup(self) -> dict[str, Any]: ...

    def emit_provenance(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def supports(self, capability: str) -> bool: ...


@dataclass
class LocalRuntimeAdapter:
    provider_id: str
    model_id: str
    loopback_only: bool = True
    remote_providers_enabled: bool = False
    capabilities: dict[str, bool] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate_configuration(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = dict(payload or {})
        issues: list[str] = []
        executable = str(payload.get("runtime_executable") or self.metadata.get("runtime_executable") or "")
        if executable and any(token in executable for token in ("&&", "||", ";", "|", "`", "$(", ">", "<")):
            issues.append("shell_injection_refused")
        if executable:
            lower = executable.lower()
            if any(name in lower for name in ("cmd.exe", "powershell.exe", "pwsh.exe")):
                issues.append("arbitrary_executable_refused")
        if payload.get("license_status") in {"unknown", "unreviewed", "blocked"}:
            issues.append("license_status_refused")
        return {
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "status": "pass" if not issues else "fail",
            "issues": issues,
            "runtime_executable": executable,
            "no_network_mode": self.no_network_mode(),
        }

    def availability(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "available": self.loopback_only and not self.remote_providers_enabled,
            "no_network_mode": self.no_network_mode(),
        }

    def version(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "version": str(self.metadata.get("runtime_version") or self.metadata.get("version") or "unknown"),
        }

    def license_report(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "license": str(self.metadata.get("license") or self.metadata.get("source_license") or ""),
            "license_status": str(self.metadata.get("license_status") or "approved"),
            "status": "pass" if str(self.metadata.get("license_status") or "approved") not in {"unknown", "blocked"} else "fail",
        }

    def healthcheck(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "loopback_only": self.loopback_only,
            "remote_providers_enabled": self.remote_providers_enabled,
            "status": "healthy" if self.loopback_only and not self.remote_providers_enabled else "degraded",
            "metadata": dict(self.metadata),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    def capability_report(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "capabilities": dict(self.capabilities),
            "loopback_only": self.loopback_only,
            "remote_providers_enabled": self.remote_providers_enabled,
        }

    def estimate_resources(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "estimated_tokens": int(payload.get("estimated_tokens", 0) or 0),
            "estimated_latency_class": payload.get("estimated_latency_class", "unknown"),
            "supported": True,
        }

    def estimate(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.estimate_resources(payload)

    def run_turn(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "status": "completed_review_required",
            "review_required": True,
            "input_keys": sorted(payload.keys()),
            "no_network_mode": self.no_network_mode(),
        }

    def stream_turn(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        result = self.run_turn(payload)
        return [
            {"event": "start", "provider_id": self.provider_id, "model_id": self.model_id},
            {"event": "chunk", "text": "review_required", "status": result["status"]},
            {"event": "end", **result},
        ]

    def cancel(self, run_id: str) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "run_id": run_id,
            "status": "cancelled",
        }

    def normalize_error(self, error: Exception) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "error_type": type(error).__name__,
            "message": str(error).replace(self.metadata.get("runtime_executable", ""), "[redacted]" if self.metadata.get("runtime_executable") else ""),
        }

    def no_network_mode(self) -> bool:
        return bool(self.loopback_only and not self.remote_providers_enabled)

    def cleanup(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "status": "cleaned_up",
        }

    def emit_provenance(self, payload: dict[str, Any]) -> dict[str, Any]:
        content = json.dumps(
            {
                "provider_id": self.provider_id,
                "model_id": self.model_id,
                "payload": payload,
                "metadata": self.metadata,
            },
            sort_keys=True,
        ).encode("utf-8")
        return {
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "provenance_sha256": hashlib.sha256(content).hexdigest(),
            "no_network_mode": self.no_network_mode(),
        }

    def supports(self, capability: str) -> bool:
        return bool(self.capabilities.get(capability, False))
