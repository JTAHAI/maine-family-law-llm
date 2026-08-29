from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.contracts.endpoint_inventory import REQUIRED_API_ENDPOINTS
from app.api.production import app as production_app
from legal.governance.admin_console import AdminConsoleReceiptStore, build_admin_console_summary


ROOT = Path(__file__).resolve().parents[1]


def test_pass161_admin_console_is_tenant_scoped_encrypted_and_never_enumerates_people(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MFL_PROJECT_ROOT", str(ROOT))
    monkeypatch.setenv("MFL_ADMIN_CONSOLE_ROOT", str(tmp_path / "admin-receipts"))
    monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "idempotency"))
    client = TestClient(production_app)
    denied = client.get("/api/admin/console", headers={"X-User-Role": "reviewer", "X-Tenant-Id": "fictional-tenant"})
    assert denied.status_code == 403
    response = client.post("/api/admin/console/refresh", headers={"X-User-Role": "admin", "X-Tenant-Id": "fictional-tenant", "X-MFLL-Client-Session": "a" * 32, "X-MFLL-Idempotency-Key": "admin-console-refresh-001"}, json={})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["tenant_scope"]["tenant_id"] == "fictional-tenant"
    assert payload["users_and_roles"]["account_management_available"] is False
    assert payload["private_record_content_included"] is False
    assert payload["paths_disclosed"] is False
    assert payload["audit_receipt"]["receipt"]["receipt_id"].startswith("admin_")
    assert "C:\\" not in response.text
    encrypted_files = list((tmp_path / "admin-receipts").glob("*.json.enc"))
    assert len(encrypted_files) == 1 and b"fictional-tenant" not in encrypted_files[0].read_bytes()


def test_pass161_production_ui_has_admin_entry_route_inventory_and_safe_summary(tmp_path: Path) -> None:
    summary = build_admin_console_summary(project_root=ROOT, tenant_id="fictional-tenant")
    receipt = AdminConsoleReceiptStore(tmp_path, encryption_key="0123456789abcdef").record(summary, tenant_id="fictional-tenant")
    assert receipt["receipt_count"] == 1
    pairs = {(spec.method, spec.path) for spec in REQUIRED_API_ENDPOINTS}
    assert ("GET", "/api/admin/console") in pairs and ("POST", "/api/admin/console/refresh") in pairs
    for relative in ("src/maine_family_law_llm/ui/workbench.html", "maine_family_law_llm/ui/workbench.html", "src/maine_family_law_llm/ui/workbench.js", "maine_family_law_llm/ui/workbench.js"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "admin-console-refresh" in text
    assert summary["blocked_exports"]["filing_ready"] is False
    assert summary["network_used"] is False
