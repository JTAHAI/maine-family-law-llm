from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any

from legal.deliberation.schemas import canonical_json, safe_identifier, utc_now


def _redact_text(value: str) -> str:
    text = str(value or "")
    if not text:
        return text
    if len(text) > 2 and text[1:3] == ":\\":
        return "[redacted_path]"
    if text.startswith("\\\\"):
        return "[redacted_path]"
    return text


def _opaque_token(value: str, *, scope: str) -> str:
    return f"{scope}_{sha256(str(value or '').encode('utf-8')).hexdigest()[:10]}"


def sanitize_for_outbound(payload: Any, *, scope: str = "scope") -> Any:
    if isinstance(payload, dict):
        sanitized: dict[str, Any] = {}
        for key, value in payload.items():
            lower = str(key).casefold()
            if lower in {"api_key", "token", "secret", "credential", "authorization", "cookie"}:
                sanitized[key] = "[redacted_secret]"
                continue
            if lower.endswith("_path") or lower in {"path", "filepath", "file_path", "absolute_path"}:
                sanitized[key] = "[redacted_path]"
                continue
            if lower in {"matter_id", "session_id", "tenant_id", "run_id"}:
                sanitized[key] = _opaque_token(str(value), scope=scope)
                continue
            sanitized[key] = sanitize_for_outbound(value, scope=scope)
        return sanitized
    if isinstance(payload, list):
        return [sanitize_for_outbound(item, scope=scope) for item in payload]
    if isinstance(payload, str):
        return _redact_text(payload)
    return payload


def _payload_hash(payload: Any) -> str:
    return sha256(canonical_json(payload)).hexdigest()


@dataclass(frozen=True)
class OutboundManifest:
    run_id: str
    provider_id: str
    pinned_model_id: str
    purpose: str
    question: str
    consent_mode: str
    exact_text_excerpt_ids: list[str]
    exact_payload: dict[str, Any]
    redactions: list[str]
    source_lanes: list[str]
    allowed_tools: list[str]
    estimated_tokens: int
    estimated_cost_usd: float | None
    retention_data_control_summary: str
    approval_timestamp: str = ""
    payload_sha256: str = ""
    approval_actor: str = ""
    expires_at: str = ""
    manifest_id: str = field(default_factory=lambda: safe_identifier("manifest", fallback="manifest"))

    def as_dict(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "run_id": self.run_id,
            "provider_id": self.provider_id,
            "pinned_model_id": self.pinned_model_id,
            "purpose": self.purpose,
            "question": self.question,
            "consent_mode": self.consent_mode,
            "exact_text_excerpt_ids": list(self.exact_text_excerpt_ids),
            "exact_payload": dict(self.exact_payload),
            "redactions": list(self.redactions),
            "source_lanes": list(self.source_lanes),
            "allowed_tools": list(self.allowed_tools),
            "estimated_tokens": self.estimated_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "retention_data_control_summary": self.retention_data_control_summary,
            "approval_timestamp": self.approval_timestamp,
            "payload_sha256": self.payload_sha256,
            "approval_actor": self.approval_actor,
            "expires_at": self.expires_at,
        }


@dataclass(frozen=True)
class OutboundManifestApproval:
    manifest_id: str
    approval_actor: str
    approved_at: str
    expires_at: str
    payload_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "approval_actor": self.approval_actor,
            "approved_at": self.approved_at,
            "expires_at": self.expires_at,
            "payload_sha256": self.payload_sha256,
        }


def _normalize_selection(consent_mode: str, payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    redactions: list[str] = []
    if consent_mode == "question_only":
        return [], redactions
    if consent_mode == "selected_excerpts":
        excerpts = [dict(item) for item in payload.get("selected_excerpts") or [] if isinstance(item, dict)]
        return excerpts, redactions
    if consent_mode == "selected_document":
        if payload.get("selected_document_confirmed") is not True:
            raise ValueError("selected_document_second_confirmation_required")
        document = payload.get("selected_document")
        if not isinstance(document, dict):
            raise ValueError("selected_document_required")
        return [dict(document)], redactions + ["selected_document_second_confirmation"]
    raise ValueError("whole_matter_transmission_prohibited")


def _sanitize_selected_item(item: dict[str, Any], *, scope: str) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in item.items():
        lower = str(key).casefold()
        if lower in {"excerpt_id", "record_id", "source_id"}:
            sanitized[key] = str(value)
            continue
        if lower in {"api_key", "token", "secret", "credential", "authorization", "cookie"}:
            sanitized[key] = "[redacted_secret]"
            continue
        if lower.endswith("_path") or lower in {"path", "filepath", "file_path", "absolute_path"}:
            sanitized[key] = "[redacted_path]"
            continue
        sanitized[key] = sanitize_for_outbound(value, scope=scope)
    return sanitized


def build_outbound_manifest(
    *,
    run_id: str,
    provider_id: str,
    pinned_model_id: str,
    purpose: str,
    question: str,
    consent_mode: str,
    source_lanes: list[str],
    allowed_tools: list[str],
    estimated_tokens: int,
    estimated_cost_usd: float | None,
    retention_data_control_summary: str,
    payload: dict[str, Any],
    budget_controls: dict[str, Any] | None = None,
    approval_actor: str = "",
    approval_timestamp: str = "",
    expires_at: str = "",
) -> OutboundManifest:
    normalized_mode = str(consent_mode or "local_only").strip().lower()
    if normalized_mode == "local_only":
        selected_items, redactions = [], []
    elif normalized_mode in {"question_only", "selected_excerpts", "selected_document"}:
        selected_items, redactions = _normalize_selection(normalized_mode, payload)
    else:
        raise ValueError("unsupported_consent_mode")
    selected_items = [_sanitize_selected_item(item, scope=provider_id) for item in selected_items]

    exact_payload = sanitize_for_outbound(
        {
            "run_id": run_id,
            "provider_id": provider_id,
            "pinned_model_id": pinned_model_id,
            "purpose": purpose,
            "question": question,
            "consent_mode": normalized_mode,
            "selected_items": selected_items,
            "tool_permissions": list(allowed_tools),
            "source_lanes": list(source_lanes),
            "estimated_tokens": estimated_tokens,
            "estimated_cost_usd": estimated_cost_usd,
            "budget_controls": sanitize_for_outbound(budget_controls or payload.get("budget_controls") or {}, scope=provider_id),
            "retention_data_control_summary": retention_data_control_summary,
            "metadata": sanitize_for_outbound(payload.get("metadata") or {}, scope=provider_id),
        },
        scope=provider_id,
    )
    exact_payload["selected_items"] = selected_items
    payload_hash = _payload_hash(exact_payload)
    manifest_id = safe_identifier(f"{run_id}:{provider_id}:{payload_hash}", fallback="manifest")
    if not approval_timestamp:
        approval_timestamp = utc_now()
    if not expires_at:
        expires_at = approval_timestamp
    return OutboundManifest(
        run_id=run_id,
        provider_id=provider_id,
        pinned_model_id=pinned_model_id,
        purpose=purpose,
        question=question,
        consent_mode=normalized_mode,
        exact_text_excerpt_ids=[str(item.get("excerpt_id") or item.get("record_id") or item.get("source_id") or "") for item in selected_items if isinstance(item, dict)],
        exact_payload=exact_payload,
        redactions=redactions,
        source_lanes=list(source_lanes),
        allowed_tools=list(allowed_tools),
        estimated_tokens=int(estimated_tokens),
        estimated_cost_usd=estimated_cost_usd,
        retention_data_control_summary=retention_data_control_summary,
        approval_timestamp=approval_timestamp,
        payload_sha256=payload_hash,
        approval_actor=approval_actor,
        expires_at=expires_at,
        manifest_id=manifest_id,
    )


def validate_manifest_transition(previous: OutboundManifest | None, current: OutboundManifest) -> list[str]:
    if previous is None:
        return []
    blockers: list[str] = []
    if previous.payload_sha256 != current.payload_sha256:
        blockers.append("payload_changed")
    if previous.provider_id != current.provider_id:
        blockers.append("provider_changed")
    if previous.pinned_model_id != current.pinned_model_id:
        blockers.append("model_changed")
    if previous.allowed_tools != current.allowed_tools:
        blockers.append("tool_permissions_changed")
    if previous.exact_text_excerpt_ids != current.exact_text_excerpt_ids:
        blockers.append("source_selection_changed")
    if previous.redactions != current.redactions:
        blockers.append("redactions_changed")
    if previous.expires_at and current.approval_timestamp and previous.expires_at < current.approval_timestamp:
        blockers.append("consent_expired")
    return blockers
