from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from legal.security.clipboard_controls import ClipboardSafetyPolicy
from maine_family_law_llm import api as api_module


def test_clipboard_policy_has_no_content_collection_or_readback() -> None:
    policy = ClipboardSafetyPolicy().as_dict()
    assert policy["clipboard_reading"] == "never"
    assert policy["clipboard_history_stored"] is False
    assert policy["sensitive_copy_requires_explicit_confirmation"] is True
    assert policy["sensitive_app_originated_clear_seconds"] == 90
    assert policy["review_required"] is True


def test_canonical_clipboard_policy_requires_local_role_scope_and_audits() -> None:
    client = TestClient(api_module.app)
    denied = client.get("/api/security/privacy/clipboard-policy", headers={"host": "testserver"})
    assert denied.status_code == 403
    response = client.get(
        "/api/security/privacy/clipboard-policy",
        headers={"X-User-Role": "reviewer", "X-Tenant-Id": "local-desktop", "host": "testserver"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["clipboard_reading"] == "never"
    assert payload["review_required"] is True
    assert payload["audit_event"]["audit_status"] == "emitted"


def test_shipped_ui_centralizes_writes_and_never_reads_clipboard() -> None:
    root = Path(__file__).resolve().parents[1]
    source_html = (root / "src" / "maine_family_law_llm" / "ui" / "workbench.html").read_text(encoding="utf-8")
    shipped_html = (root / "maine_family_law_llm" / "ui" / "workbench.html").read_text(encoding="utf-8")
    source_js = (root / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    shipped_js = (root / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    assert source_html == shipped_html
    assert source_js == shipped_js
    assert "never reads clipboard contents" in source_html
    assert "SENSITIVE_CLIPBOARD_CLEAR_MS = 90 * 1000" in source_js
    assert "window.confirm(`This ${label} may contain private family-record information" in source_js
    assert "navigator.clipboard.read" not in source_js
    assert source_js.count("navigator.clipboard.writeText(") == 2
    assert source_js.count("writeClipboardText(") >= 10
