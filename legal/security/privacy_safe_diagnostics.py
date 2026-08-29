"""Deterministic, opt-in support-bundle construction without matter content."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any


_SECTION_IDS = frozenset({"product", "security_policy", "local_environment", "client_error_codes"})
_EVENT_CODE = re.compile(r"[a-z][a-z0-9_.-]{0,95}")


class PrivacySafeDiagnosticsError(ValueError):
    pass


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _safe_sections(value: object) -> list[str]:
    if value is None:
        return ["product", "security_policy"]
    if not isinstance(value, list):
        raise PrivacySafeDiagnosticsError("diagnostics_sections_invalid")
    sections = []
    for item in value:
        section = str(item or "").strip()
        if section not in _SECTION_IDS:
            raise PrivacySafeDiagnosticsError("diagnostics_section_not_allowed")
        if section not in sections:
            sections.append(section)
    return sections


def _safe_event_codes(value: object) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise PrivacySafeDiagnosticsError("diagnostics_event_codes_invalid")
    rows: list[dict[str, str]] = []
    for raw in value[:100]:
        if not isinstance(raw, dict):
            raise PrivacySafeDiagnosticsError("diagnostics_event_codes_invalid")
        code = str(raw.get("code") or "").strip().casefold()
        component = str(raw.get("component") or "workbench").strip().casefold()
        if not _EVENT_CODE.fullmatch(code) or not _EVENT_CODE.fullmatch(component):
            raise PrivacySafeDiagnosticsError("diagnostics_event_code_invalid")
        rows.append({"code": code, "component": component})
    return rows


def support_bundle_preview(
    *,
    sections: object = None,
    client_error_codes: object = None,
    application_version: str,
    local_policy: dict[str, Any],
    environment: dict[str, Any],
) -> dict[str, Any]:
    """Preview precisely what an opt-in support bundle can include.

    Free-form logs, prompts, matter labels, record content, paths, identities,
    credentials, and URLs are never accepted as input fields.
    """
    selected = _safe_sections(sections)
    events = _safe_event_codes(client_error_codes)
    bundle: dict[str, Any] = {
        "schema_version": "privacy_safe_support_bundle_v1",
        "generated_at": _now(),
        "review_required": True,
        "local_only": True,
        "contains_matter_content": False,
        "contains_paths": False,
        "contains_credentials": False,
        "contains_prompts_or_record_text": False,
        "sections": {},
    }
    if "product" in selected:
        bundle["sections"]["product"] = {"application_version": str(application_version)[:80], "mode": "local_only"}
    if "security_policy" in selected:
        bundle["sections"]["security_policy"] = {
            key: local_policy.get(key)
            for key in ("policy_id", "sensitive_copy_confirmation_required", "clipboard_reading", "clear_after_seconds")
            if key in local_policy
        }
    if "local_environment" in selected:
        bundle["sections"]["local_environment"] = {
            key: environment.get(key)
            for key in ("os_family", "python_major_minor", "frozen_runtime")
            if key in environment
        }
    if "client_error_codes" in selected:
        bundle["sections"]["client_error_codes"] = events
    bundle["bundle_sha256"] = hashlib.sha256(_canonical(bundle)).hexdigest()
    return {
        "status": "preview",
        "selected_sections": selected,
        "excluded_categories": [
            "matter_content", "record_text", "prompts", "names", "paths", "credentials", "raw_logs", "external_urls"
        ],
        "bundle": bundle,
        "review_required": True,
    }


def build_support_bundle(*, approved: bool, **kwargs: Any) -> dict[str, Any]:
    if approved is not True:
        raise PrivacySafeDiagnosticsError("diagnostics_bundle_approval_required")
    preview = support_bundle_preview(**kwargs)
    bundle = dict(preview["bundle"])
    bundle["status"] = "user_approved_support_bundle"
    bundle["bundle_sha256"] = hashlib.sha256(_canonical({key: value for key, value in bundle.items() if key != "bundle_sha256"})).hexdigest()
    return {
        "status": "pass",
        "filename": f"maine-family-law-llm-support-{bundle['bundle_sha256'][:16]}.json",
        "bundle": bundle,
        "excluded_categories": preview["excluded_categories"],
        "review_required": True,
    }


__all__ = ["PrivacySafeDiagnosticsError", "build_support_bundle", "support_bundle_preview"]
