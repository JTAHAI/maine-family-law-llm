from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from legal.security.privacy_safe_diagnostics import (
    PrivacySafeDiagnosticsError,
    build_support_bundle,
    support_bundle_preview,
)


def _inputs() -> dict:
    return {
        "application_version": "9.0.0",
        "local_policy": {
            "policy_id": "sensitive_clipboard_v1",
            "sensitive_copy_confirmation_required": True,
            "clipboard_reading": "never",
            "clear_after_seconds": 90,
            "private_text": "must not be included",
        },
        "environment": {
            "os_family": "Windows",
            "python_major_minor": "3.12",
            "frozen_runtime": False,
            "path": "C:/fictional/private/matter",
        },
    }


def test_pass139_preview_has_explicit_inclusion_and_never_accepts_free_text() -> None:
    preview = support_bundle_preview(
        sections=["product", "security_policy", "local_environment", "client_error_codes"],
        client_error_codes=[{"code": "record_open_failed", "component": "record_viewer"}],
        **_inputs(),
    )
    serialized = json.dumps(preview)
    assert preview["status"] == "preview"
    assert preview["bundle"]["contains_matter_content"] is False
    assert "C:/fictional/private/matter" not in serialized
    assert "must not be included" not in serialized
    assert preview["bundle"]["sections"]["client_error_codes"] == [{"code": "record_open_failed", "component": "record_viewer"}]
    assert "raw_logs" in preview["excluded_categories"]
    with pytest.raises(PrivacySafeDiagnosticsError, match="diagnostics_section_not_allowed"):
        support_bundle_preview(sections=["raw_logs"], **_inputs())
    with pytest.raises(PrivacySafeDiagnosticsError, match="diagnostics_event_code_invalid"):
        support_bundle_preview(sections=["client_error_codes"], client_error_codes=[{"code": "private message", "component": "ui"}], **_inputs())


def test_pass139_build_requires_approval_and_is_hash_bound() -> None:
    with pytest.raises(PrivacySafeDiagnosticsError, match="diagnostics_bundle_approval_required"):
        build_support_bundle(approved=False, **_inputs())
    built = build_support_bundle(approved=True, sections=["product"], **_inputs())
    assert built["status"] == "pass"
    assert built["filename"].endswith(".json")
    assert len(built["bundle"]["bundle_sha256"]) == 64
    assert built["bundle"]["contains_prompts_or_record_text"] is False


def test_pass139_canonical_api_and_production_ui_expose_explicit_bundle_flow() -> None:
    client = TestClient(app)
    headers = {"X-User-Role": "reviewer", "X-Tenant-Id": "fictional-tenant"}
    preview = client.post(
        "/api/security/privacy/diagnostics/preview",
        headers=headers,
        json={"sections": ["product", "client_error_codes"], "client_error_codes": [{"code": "ui_timeout", "component": "chat"}]},
    )
    assert preview.status_code == 200
    assert preview.json()["bundle"]["contains_matter_content"] is False
    denied = client.post(
        "/api/security/privacy/diagnostics/build",
        headers=headers,
        json={"sections": ["product"]},
    )
    assert denied.status_code == 409
    built = client.post(
        "/api/security/privacy/diagnostics/build",
        headers=headers,
        json={"approved": True, "sections": ["product"]},
    )
    assert built.status_code == 200
    assert built.json()["bundle"]["contains_paths"] is False

    from maine_family_law_llm.local_workbench_ui import read_workbench_asset, render_local_workbench_html

    html = render_local_workbench_html()
    js = read_workbench_asset("workbench.js")
    assert 'id="preview-support-bundle"' in html
    assert "function buildPrivacySafeSupportBundle" in js
    assert "/api/security/privacy/diagnostics/build" in js
