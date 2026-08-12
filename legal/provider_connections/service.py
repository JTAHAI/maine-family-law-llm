from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable

from .catalog import ProviderCatalog
from .credentials import WindowsCredentialStore, WindowsCredentialError
from .manifests import OutboundManifest, OutboundManifestApproval, build_outbound_manifest, validate_manifest_transition
from .store import ProviderStoreLayout, external_provider_store_layout


@dataclass(frozen=True)
class ProviderConnectionRecord:
    provider_id: str
    account_label: str
    status: str
    credential_status: str
    pinned_model_id: str
    endpoint_url: str
    request_path: str
    api_class: str
    endpoint_class: str
    requested_retention_mode: str
    region_data_controls: str
    cost_estimate_basis: str
    tool_support: list[str] = field(default_factory=list)
    compatibility_profile_version: str = ""
    last_successful_contract_test: str = ""
    connected_at: str = ""
    disconnected_at: str = ""
    revoked_at: str = ""
    estimated_charges_warning: str = ""
    data_control_summary: str = ""
    model_policy: str = "operator_selected"
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "account_label": self.account_label,
            "status": self.status,
            "credential_status": self.credential_status,
            "pinned_model_id": self.pinned_model_id,
            "endpoint_url": self.endpoint_url,
            "request_path": self.request_path,
            "api_class": self.api_class,
            "endpoint_class": self.endpoint_class,
            "requested_retention_mode": self.requested_retention_mode,
            "region_data_controls": self.region_data_controls,
            "cost_estimate_basis": self.cost_estimate_basis,
            "tool_support": list(self.tool_support),
            "compatibility_profile_version": self.compatibility_profile_version,
            "last_successful_contract_test": self.last_successful_contract_test,
            "connected_at": self.connected_at,
            "disconnected_at": self.disconnected_at,
            "revoked_at": self.revoked_at,
            "estimated_charges_warning": self.estimated_charges_warning,
            "data_control_summary": self.data_control_summary,
            "model_policy": self.model_policy,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ProviderSessionState:
    session_id: str
    provider_id: str
    run_id: str
    credential_namespace: str
    context_buffer: dict[str, Any]
    budget: dict[str, Any]
    tool_grants: list[str]
    rate_limits: dict[str, Any]
    cancellation_token: str
    audit_records: list[dict[str, Any]] = field(default_factory=list)
    status: str = "active"

    def as_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "provider_id": self.provider_id,
            "run_id": self.run_id,
            "credential_namespace": self.credential_namespace,
            "context_buffer": dict(self.context_buffer),
            "budget": dict(self.budget),
            "tool_grants": list(self.tool_grants),
            "rate_limits": dict(self.rate_limits),
            "cancellation_token": self.cancellation_token,
            "audit_records": [dict(row) for row in self.audit_records],
            "status": self.status,
        }


class ProviderConnectionError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ProviderConnectionService:
    def __init__(
        self,
        *,
        project_root: str | Path,
        store_root: str | Path | None = None,
        catalog: ProviderCatalog | None = None,
        credential_store: WindowsCredentialStore | None = None,
        transport: Callable[[str, str, dict[str, str], bytes, int], tuple[int, str, dict[str, Any]]] | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.layout: ProviderStoreLayout = external_provider_store_layout(store_root, project_root=self.project_root, create=True)
        self.catalog = catalog or ProviderCatalog.from_config()
        self.credential_store = credential_store or WindowsCredentialStore(namespace="maine-family-law-llm")
        self.transport = transport
        self._connections_path = self.layout.connections / "connections.json"
        self._manifests_path = self.layout.manifests / "manifests.jsonl"
        self._approvals_path = self.layout.manifests / "approvals.jsonl"
        self._sessions_path = self.layout.sessions / "sessions.jsonl"
        self._usage_path = self.layout.usage / "usage.json"
        self._connections: dict[str, ProviderConnectionRecord] = self._load_connections()
        self._manifests: dict[str, OutboundManifest] = {}
        self._approvals: dict[str, OutboundManifestApproval] = {}
        self._sessions: dict[tuple[str, str], ProviderSessionState] = {}

    def _load_connections(self) -> dict[str, ProviderConnectionRecord]:
        if not self._connections_path.exists():
            return {}
        payload = json.loads(self._connections_path.read_text(encoding="utf-8"))
        records: dict[str, ProviderConnectionRecord] = {}
        for row in payload.get("connections", []):
            record = ProviderConnectionRecord(
                provider_id=str(row.get("provider_id") or ""),
                account_label=str(row.get("account_label") or "default"),
                status=str(row.get("status") or "disconnected"),
                credential_status=str(row.get("credential_status") or "missing"),
                pinned_model_id=str(row.get("pinned_model_id") or ""),
                endpoint_url=str(row.get("endpoint_url") or ""),
                request_path=str(row.get("request_path") or ""),
                api_class=str(row.get("api_class") or ""),
                endpoint_class=str(row.get("endpoint_class") or ""),
                requested_retention_mode=str(row.get("requested_retention_mode") or ""),
                region_data_controls=str(row.get("region_data_controls") or ""),
                cost_estimate_basis=str(row.get("cost_estimate_basis") or ""),
                tool_support=list(row.get("tool_support") or []),
                compatibility_profile_version=str(row.get("compatibility_profile_version") or ""),
                last_successful_contract_test=str(row.get("last_successful_contract_test") or ""),
                connected_at=str(row.get("connected_at") or ""),
                disconnected_at=str(row.get("disconnected_at") or ""),
                revoked_at=str(row.get("revoked_at") or ""),
                estimated_charges_warning=str(row.get("estimated_charges_warning") or ""),
                data_control_summary=str(row.get("data_control_summary") or ""),
                model_policy=str(row.get("model_policy") or "operator_selected"),
                notes=str(row.get("notes") or ""),
            )
            if record.provider_id:
                records[record.provider_id] = record
        return records

    def _persist_connections(self) -> None:
        self._connections_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "provider_connections_v1",
            "generated_at": datetime.now(UTC).isoformat(),
            "connections": [record.as_dict() for record in self.list_connections()],
        }
        self._connections_path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")

    def _append_jsonl(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, sort_keys=True, ensure_ascii=False))
            handle.write("\n")

    def list_connections(self) -> list[ProviderConnectionRecord]:
        return [self._connections[key] for key in sorted(self._connections)]

    def list_providers(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for entry in self.catalog.list():
            connection = self._connections.get(entry.provider_id)
            credential = self.credential_store.credential_status(entry.provider_id, account_label=(connection.account_label if connection else "default"))
            rows.append(
                {
                    **entry.as_dict(),
                    "connected": connection is not None and connection.status == "connected",
                    "credential_status": credential.credential_status,
                    "pinned_model_id": connection.pinned_model_id if connection else "",
                    "endpoint_url": connection.endpoint_url if connection else "",
                    "request_path": connection.request_path if connection else "",
                    "data_control_summary": connection.data_control_summary if connection else entry.retention_summary,
                    "estimated_charges_warning": connection.estimated_charges_warning if connection else "Connection charges are BYOK and billed by the provider.",
                    "connection": connection.as_dict() if connection else None,
                }
            )
        return rows

    def provider_status(self, provider_id: str) -> dict[str, Any]:
        entry = self.catalog.get(provider_id)
        connection = self._connections.get(entry.provider_id)
        credential = self.credential_store.credential_status(entry.provider_id, account_label=(connection.account_label if connection else "default"))
        return {
            "status": "pass",
            "provider": entry.as_dict(),
            "connection": connection.as_dict() if connection else None,
            "credential": credential.as_dict(),
            "sharing_summary": self.sharing_summary().get("sharing_summary"),
        }

    def _connection_or_raise(self, provider_id: str) -> ProviderConnectionRecord:
        key = str(provider_id or "").strip()
        if key not in self._connections:
            raise ProviderConnectionError("provider_not_connected", "The provider is not connected.", status_code=409)
        return self._connections[key]

    def connect(self, provider_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        entry = self.catalog.get(provider_id)
        account_label = str(payload.get("account_label") or "default").strip() or "default"
        api_key = str(payload.get("api_key") or payload.get("credential") or "").strip()
        if not api_key:
            raise ProviderConnectionError("credential_required", "An API key or credential is required.", status_code=422)
        pinned_model_id = str(payload.get("pinned_model_id") or payload.get("model_id") or "").strip()
        if not pinned_model_id:
            raise ProviderConnectionError("model_required", "A pinned model ID is required.", status_code=422)
        endpoint_url = str(payload.get("endpoint_url") or payload.get("base_url") or "").strip()
        request_path = str(payload.get("request_path") or "").strip()
        if not endpoint_url:
            raise ProviderConnectionError("endpoint_required", "An endpoint URL is required.", status_code=422)
        if not request_path:
            raise ProviderConnectionError("request_path_required", "A request path is required before transmission is enabled.", status_code=422)
        retention_mode = str(payload.get("retention_mode") or entry.requested_retention_mode or "unknown").strip()
        data_control_summary = str(payload.get("data_control_summary") or entry.retention_summary or retention_mode)
        charges_warning = str(payload.get("estimated_charges_warning") or "BYOK charges are billed by the provider and remain separate from the application.")
        try:
            secret_status = self.credential_store.store_secret(
                entry.provider_id,
                "api_key",
                api_key,
                account_label=account_label,
            )
        except WindowsCredentialError as exc:
            raise ProviderConnectionError(
                exc.code,
                exc.message,
                status_code=503,
            ) from exc
        record = ProviderConnectionRecord(
            provider_id=entry.provider_id,
            account_label=account_label,
            status="connected",
            credential_status=secret_status.credential_status,
            pinned_model_id=pinned_model_id,
            endpoint_url=endpoint_url,
            request_path=request_path,
            api_class=entry.api_class,
            endpoint_class=entry.endpoint_class,
            requested_retention_mode=retention_mode,
            region_data_controls=str(payload.get("region_data_controls") or entry.region_data_controls),
            cost_estimate_basis=str(payload.get("cost_estimate_basis") or entry.cost_estimate_basis),
            tool_support=list(entry.tool_support),
            compatibility_profile_version=entry.compatibility_profile_version,
            last_successful_contract_test=entry.last_successful_contract_test,
            connected_at=datetime.now(UTC).isoformat(),
            estimated_charges_warning=charges_warning,
            data_control_summary=data_control_summary,
            model_policy=str(payload.get("model_policy") or entry.default_model_policy),
            notes=str(payload.get("notes") or entry.notes),
        )
        self._connections[entry.provider_id] = record
        self._persist_connections()
        return {
            "status": "connected",
            "provider": entry.as_dict(),
            "connection": record.as_dict(),
            "credential": secret_status.as_dict(),
        }

    def disconnect(self, provider_id: str) -> dict[str, Any]:
        record = self._connection_or_raise(provider_id)
        updated = ProviderConnectionRecord(**{**record.as_dict(), "status": "disconnected", "disconnected_at": datetime.now(UTC).isoformat()})
        self._connections[record.provider_id] = updated
        self._persist_connections()
        return {"status": "disconnected", "connection": updated.as_dict()}

    def revoke(self, provider_id: str, *, account_label: str | None = None) -> dict[str, Any]:
        record = self._connection_or_raise(provider_id)
        label = account_label or record.account_label
        try:
            credential = self.credential_store.delete_secret(
                provider_id,
                "api_key",
                account_label=label,
            )
        except WindowsCredentialError as exc:
            raise ProviderConnectionError(
                exc.code,
                exc.message,
                status_code=503,
            ) from exc
        updated = ProviderConnectionRecord(**{**record.as_dict(), "status": "revoked", "credential_status": credential.credential_status, "revoked_at": datetime.now(UTC).isoformat()})
        self._connections[record.provider_id] = updated
        self._persist_connections()
        return {"status": "revoked", "connection": updated.as_dict(), "credential": credential.as_dict()}

    def disconnect_all(self) -> dict[str, Any]:
        results = []
        for provider_id in list(self._connections):
            results.append(self.disconnect(provider_id))
        return {"status": "disconnected_all", "results": results}

    def revoke_all(self) -> dict[str, Any]:
        results = []
        for provider_id in list(self._connections):
            results.append(self.revoke(provider_id))
        return {"status": "revoked_all", "results": results}

    def return_local_only(self) -> dict[str, Any]:
        disconnected = self.disconnect_all()["results"] if self._connections else []
        self._sessions.clear()
        payload = {
            "status": "local_only",
            "local_only": True,
            "provider_count": len(self._connections),
            "disconnected_provider_count": len(disconnected),
            "provider_sessions_cleared": True,
            "sharing_summary": self.sharing_summary().get("sharing_summary"),
        }
        self._append_jsonl(
            self._sessions_path,
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "event": "returned_local_only",
                "provider_count": len(self._connections),
                "disconnected_provider_count": len(disconnected),
            },
        )
        return payload

    def sharing_summary(self) -> dict[str, Any]:
        providers = self.list_providers()
        connected = [row for row in providers if row.get("connected")]
        return {
            "status": "pass",
            "local_only": not connected,
            "sharing_summary": {
                "provider_count": len(providers),
                "connected_provider_count": len(connected),
                "connected_provider_ids": [row.get("provider_id") for row in connected],
                "consent_modes": ["local_only", "question_only", "selected_excerpts", "selected_document"],
                "budget_controls": {
                    "provider_cap_usd": "operator-approved",
                    "round_cap": "operator-approved",
                    "context_cap": "operator-approved",
                    "output_cap": "operator-approved",
                    "tool_call_cap": "operator-approved",
                    "private_record_tool_cap": "operator-approved",
                    "retry_cap": "operator-approved",
                    "timeout_seconds": "operator-approved",
                    "circuit_breaker": "operator-approved",
                },
                "data_controls": [row.get("data_control_summary") for row in providers],
                "review_required": True,
            },
        }

    def capabilities(self, provider_id: str) -> dict[str, Any]:
        entry = self.catalog.get(provider_id)
        connection = self._connections.get(entry.provider_id)
        return {
            "status": "pass",
            "provider": entry.as_dict(),
            "connection": connection.as_dict() if connection else None,
            "connected": connection is not None and connection.status == "connected",
            "credential_status": self.credential_store.credential_status(entry.provider_id, account_label=(connection.account_label if connection else "default")).credential_status,
        }

    def health(self, provider_id: str, *, local_only: bool = True) -> dict[str, Any]:
        entry = self.catalog.get(provider_id)
        connection = self._connections.get(entry.provider_id)
        credential = self.credential_store.credential_status(entry.provider_id, account_label=(connection.account_label if connection else "default"))
        return {
            "provider_id": entry.provider_id,
            "status": "deferred_local_only" if local_only else ("healthy" if connection and connection.status == "connected" and credential.exists else "degraded"),
            "local_only": local_only,
            "connected": connection is not None and connection.status == "connected",
            "credential_status": credential.credential_status,
            "provider": entry.as_dict(),
            "connection": connection.as_dict() if connection else None,
        }

    def _manifest_path(self, manifest_id: str) -> Path:
        safe_name = str(manifest_id or "").replace(":", "_")
        return self.layout.manifests / f"{safe_name}.json"

    def _approval_path(self, manifest_id: str) -> Path:
        safe_name = str(manifest_id or "").replace(":", "_")
        return self.layout.manifests / f"{safe_name}.approval.json"

    def _save_manifest(self, manifest: OutboundManifest) -> None:
        self._manifests[manifest.manifest_id] = manifest
        self._manifest_path(manifest.manifest_id).write_text(json.dumps(manifest.as_dict(), indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
        self._append_jsonl(self._manifests_path, {"timestamp": datetime.now(UTC).isoformat(), "manifest": manifest.as_dict()})

    def _save_approval(self, approval: OutboundManifestApproval) -> None:
        self._approvals[approval.manifest_id] = approval
        self._approval_path(approval.manifest_id).write_text(json.dumps(approval.as_dict(), indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
        self._append_jsonl(self._approvals_path, {"timestamp": datetime.now(UTC).isoformat(), "approval": approval.as_dict()})

    def get_manifest(self, manifest_id: str) -> OutboundManifest:
        manifest = self._manifests.get(manifest_id)
        if manifest is not None:
            return manifest
        path = self._manifest_path(manifest_id)
        if not path.exists():
            raise ProviderConnectionError("manifest_not_found", "The outbound manifest was not found.", status_code=404)
        manifest = OutboundManifest(**json.loads(path.read_text(encoding="utf-8")))
        self._manifests[manifest_id] = manifest
        return manifest

    def build_manifest(self, *, run_id: str, provider_id: str, payload: dict[str, Any]) -> OutboundManifest:
        entry = self.catalog.get(provider_id)
        connection = self._connections.get(entry.provider_id)
        if not connection or connection.status != "connected":
            raise ProviderConnectionError("provider_not_connected", "The provider must be connected before a manifest can be previewed.", status_code=409)
        consent_mode = str(payload.get("consent_mode") or "local_only").strip().lower()
        if consent_mode == "whole_matter":
            raise ProviderConnectionError("whole_matter_prohibited", "Whole-matter transmission is prohibited.", status_code=409)
        selected_excerpt_ids = [str(item.get("excerpt_id") or item.get("record_id") or item.get("source_id") or "") for item in payload.get("selected_excerpts") or [] if isinstance(item, dict)]
        manifest = build_outbound_manifest(
            run_id=run_id,
            provider_id=entry.provider_id,
            pinned_model_id=connection.pinned_model_id,
            purpose=str(payload.get("purpose") or "deliberation"),
            question=str(payload.get("question") or ""),
            consent_mode=consent_mode,
            source_lanes=[str(item) for item in (payload.get("source_lanes") or []) if str(item).strip()],
            allowed_tools=[str(item) for item in (payload.get("allowed_tools") or []) if str(item).strip()],
            estimated_tokens=int(payload.get("estimated_tokens") or 0),
            estimated_cost_usd=(float(payload["estimated_cost_usd"]) if payload.get("estimated_cost_usd") is not None else None),
            budget_controls=dict(payload.get("budget_controls") or {}),
            retention_data_control_summary=str(payload.get("retention_data_control_summary") or connection.data_control_summary or entry.retention_summary),
            payload=payload,
            approval_actor=str(payload.get("approval_actor") or ""),
            approval_timestamp=str(payload.get("approval_timestamp") or ""),
            expires_at=str(payload.get("expires_at") or ""),
        )
        if selected_excerpt_ids and manifest.exact_text_excerpt_ids != selected_excerpt_ids:
            raise ProviderConnectionError("excerpt_selection_changed", "Selected excerpts changed while building the manifest.", status_code=409)
        self._save_manifest(manifest)
        self._append_jsonl(
            self._sessions_path,
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "event": "manifest_previewed",
                "manifest_id": manifest.manifest_id,
                "run_id": run_id,
                "provider_id": provider_id,
                "payload_sha256": manifest.payload_sha256,
            },
        )
        return manifest

    def approve_manifest(self, manifest_id: str, *, actor: str, run_id: str | None = None) -> OutboundManifestApproval:
        manifest = self.get_manifest(manifest_id)
        if run_id and manifest.run_id != run_id:
            raise ProviderConnectionError("run_mismatch", "The manifest does not belong to this run.", status_code=409)
        approval = OutboundManifestApproval(
            manifest_id=manifest.manifest_id,
            approval_actor=actor,
            approved_at=datetime.now(UTC).isoformat(),
            expires_at=(datetime.now(UTC) + timedelta(minutes=30)).isoformat(),
            payload_sha256=manifest.payload_sha256,
        )
        approved_manifest = OutboundManifest(
            **{**manifest.as_dict(), "approval_actor": actor, "approval_timestamp": approval.approved_at, "expires_at": approval.expires_at}
        )
        self._save_manifest(approved_manifest)
        self._save_approval(approval)
        return approval

    def start_external(self, manifest_id: str, *, run_id: str | None = None) -> dict[str, Any]:
        manifest = self.get_manifest(manifest_id)
        if run_id and manifest.run_id != run_id:
            raise ProviderConnectionError("run_mismatch", "The manifest does not belong to this run.", status_code=409)
        approval = self._approvals.get(manifest.manifest_id)
        if approval is None:
            raise ProviderConnectionError("approval_required", "The outbound manifest must be approved before transmission.", status_code=409)
        blockers = validate_manifest_transition(manifest, manifest)
        if blockers:
            raise ProviderConnectionError("manifest_transition_blocked", ",".join(blockers), status_code=409)
        connection = self._connection_or_raise(manifest.provider_id)
        if connection.pinned_model_id != manifest.pinned_model_id:
            raise ProviderConnectionError("model_changed", "The pinned model changed after approval.", status_code=409)
        if connection.provider_id != manifest.provider_id:
            raise ProviderConnectionError("provider_changed", "The provider changed after approval.", status_code=409)
        if approval.payload_sha256 != manifest.payload_sha256:
            raise ProviderConnectionError("payload_changed", "The outbound payload changed after approval.", status_code=409)
        if datetime.now(UTC).isoformat() > approval.expires_at:
            raise ProviderConnectionError("consent_expired", "The outbound approval expired.", status_code=409)
        if connection.status != "connected":
            raise ProviderConnectionError("provider_not_connected", "The provider is not connected.", status_code=409)
        budget_controls = dict(manifest.exact_payload.get("budget_controls") or {})
        estimated_tokens = int(manifest.estimated_tokens)
        estimated_cost = float(manifest.estimated_cost_usd or 0.0)
        if budget_controls:
            token_cap = int(budget_controls.get("context_cap") or budget_controls.get("provider_cap_tokens") or budget_controls.get("round_cap_tokens") or 0)
            cost_cap = budget_controls.get("provider_cap_usd")
            tool_call_cap = int(budget_controls.get("tool_call_cap") or 0)
            output_cap = int(budget_controls.get("output_cap") or 0)
            private_record_cap = int(budget_controls.get("private_record_tool_cap") or 0)
            retry_cap = int(budget_controls.get("retry_cap") or 0)
            if token_cap and estimated_tokens > token_cap:
                raise ProviderConnectionError("budget_exhausted", "The estimated token usage exceeds the approved context budget.", status_code=409)
            if cost_cap is not None and str(cost_cap).strip():
                try:
                    if estimated_cost > float(cost_cap):
                        raise ProviderConnectionError("budget_exhausted", "The estimated cost exceeds the approved provider budget.", status_code=409)
                except ValueError:
                    pass
            if tool_call_cap and len(manifest.allowed_tools) > tool_call_cap:
                raise ProviderConnectionError("budget_exhausted", "The requested tool budget exceeds the approved cap.", status_code=409)
            if output_cap and len(json.dumps(manifest.exact_payload, sort_keys=True, ensure_ascii=False)) > output_cap:
                raise ProviderConnectionError("budget_exhausted", "The outbound payload exceeds the approved output cap.", status_code=409)
            if private_record_cap and any("private" in lane.casefold() for lane in manifest.source_lanes) and len(manifest.exact_text_excerpt_ids) > private_record_cap:
                raise ProviderConnectionError("budget_exhausted", "The private-record tool budget exceeds the approved cap.", status_code=409)
            if retry_cap and retry_cap < 1:
                raise ProviderConnectionError("budget_exhausted", "The retry budget is exhausted.", status_code=409)
        request_bytes = json.dumps(manifest.exact_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if sha256(request_bytes).hexdigest() != manifest.payload_sha256:  # pragma: no cover - defensive double-check
            raise ProviderConnectionError("payload_hash_mismatch", "The transmitted bytes do not match the approved manifest.", status_code=409)
        if self.transport is None:
            return {
                "status": "approved_and_staged",
                "manifest_id": manifest.manifest_id,
                "provider_id": manifest.provider_id,
                "pinned_model_id": manifest.pinned_model_id,
                "payload_sha256": manifest.payload_sha256,
                "transmitted": False,
                "reason": "transport_unavailable_in_this_slice",
            }
        status_code, response_text, response_headers = self.transport(
            connection.endpoint_url,
            connection.request_path,
            {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-MFL-Provider-Id": manifest.provider_id,
                "X-MFL-Manifest-Id": manifest.manifest_id,
                "X-MFL-Payload-SHA256": manifest.payload_sha256,
            },
            request_bytes,
            120,
        )
        session = self._sessions.get((manifest.provider_id, manifest.run_id)) or ProviderSessionState(
            session_id=f"{manifest.provider_id}:{manifest.run_id}",
            provider_id=manifest.provider_id,
            run_id=manifest.run_id,
            credential_namespace=self.credential_store.namespace,
            context_buffer=manifest.exact_payload,
            budget={
                "estimated_tokens": manifest.estimated_tokens,
                "estimated_cost_usd": manifest.estimated_cost_usd,
                "provider_cap_usd": budget_controls.get("provider_cap_usd"),
                "round_cap": budget_controls.get("round_cap"),
                "context_cap": budget_controls.get("context_cap"),
                "output_cap": budget_controls.get("output_cap"),
                "tool_call_cap": len(manifest.allowed_tools),
                "private_record_tool_cap": budget_controls.get("private_record_tool_cap"),
                "retry_cap": budget_controls.get("retry_cap"),
                "timeout_seconds": budget_controls.get("timeout_seconds", 120),
                "circuit_breaker": budget_controls.get("circuit_breaker", "operator_controlled"),
            },
            tool_grants=list(manifest.allowed_tools),
            rate_limits={"max_requests_per_minute": 10},
            cancellation_token=f"cancel:{manifest.manifest_id}",
            audit_records=[],
        )
        audit_row = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": "provider_run_started",
            "manifest_id": manifest.manifest_id,
            "provider_id": manifest.provider_id,
            "run_id": manifest.run_id,
            "payload_sha256": manifest.payload_sha256,
            "status_code": status_code,
            "response_headers": dict(response_headers),
        }
        session.audit_records.append(audit_row)
        self._sessions[(manifest.provider_id, manifest.run_id)] = session
        self._append_jsonl(self._sessions_path, audit_row)
        return {
            "status": "transmitted" if 200 <= status_code < 300 else "provider_error",
            "manifest_id": manifest.manifest_id,
            "provider_id": manifest.provider_id,
            "pinned_model_id": manifest.pinned_model_id,
            "payload_sha256": manifest.payload_sha256,
            "transmitted": 200 <= status_code < 300,
            "response_text": response_text[:2000],
            "response_headers": response_headers,
            "session": session.as_dict(),
        }

    def usage(self, run_id: str) -> dict[str, Any]:
        rows = [session.as_dict() for key, session in self._sessions.items() if key[1] == run_id]
        return {
            "run_id": run_id,
            "provider_sessions": rows,
            "provider_count": len(rows),
            "usage_summary": {
                "run_id": run_id,
                "provider_count": len(rows),
                "connected_provider_ids": [row.get("provider_id") for row in rows],
                "budget_state": "budget_exhausted" if any(row.get("budget", {}).get("estimated_cost_usd") is not None and row.get("budget", {}).get("estimated_cost_usd") == 0 for row in rows) else "within_budget",
            },
            "budget_state": "budget_exhausted" if any(row.get("budget", {}).get("estimated_cost_usd") is not None and row.get("budget", {}).get("estimated_cost_usd") == 0 for row in rows) else "within_budget",
        }

    def cancel(self, run_id: str) -> dict[str, Any]:
        cancelled = []
        for key, session in list(self._sessions.items()):
            if key[1] != run_id:
                continue
            updated = ProviderSessionState(**{**session.as_dict(), "status": "cancelled"})
            self._sessions[key] = updated
            cancelled.append(updated.as_dict())
            self._append_jsonl(self._sessions_path, {"timestamp": datetime.now(UTC).isoformat(), "event": "provider_run_cancelled", "run_id": run_id, "provider_id": key[0], "session_id": session.session_id})
        return {"status": "cancelled", "run_id": run_id, "provider_sessions": cancelled}
