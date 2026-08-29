from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.production import app as production_app
from legal.governance.organization_readiness import OrganizationReadinessDashboard


ROOT = Path(__file__).resolve().parents[1]


def test_pass170_separates_readiness_lanes_and_encrypts_refresh_receipt(tmp_path: Path) -> None:
    dashboard = OrganizationReadinessDashboard(ROOT, tmp_path, encryption_key="0123456789abcdef")
    report = dashboard.build(tenant_id="fictional-tenant")
    decisions = {row["lane"]: row["decision"] for row in report["lanes"]}
    assert report["overall_decision"] == "not_ready_for_enterprise_ga"
    assert decisions["legal"] == "blocked" and decisions["microsoft_store"] == "not_evaluated"
    assert decisions["engineering"] in {"ready_for_internal_review", "blocked"}
    receipt = dashboard.receipt(report, tenant_id="fictional-tenant")
    assert receipt["receipt"]["receipt_id"].startswith("readiness_")
    encrypted = next(tmp_path.glob("*.json.enc"))
    assert b"fictional-tenant" not in encrypted.read_bytes()


def test_pass170_production_admin_route_and_shipped_ui(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MFL_ORGANIZATION_READINESS_ROOT", str(tmp_path / "readiness")); monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "idempotency"))
    client = TestClient(production_app)
    denied = client.get("/api/admin/organization-readiness", headers={"X-User-Role": "reviewer", "X-Tenant-Id": "fictional-tenant"})
    assert denied.status_code == 403
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "fictional-tenant", "X-MFLL-Client-Session": "f" * 32}
    report = client.get("/api/admin/organization-readiness", headers=headers)
    assert report.status_code == 200 and report.json()["overall_decision"] == "not_ready_for_enterprise_ga"
    refreshed = client.post("/api/admin/organization-readiness/refresh", headers={**headers, "X-MFLL-Idempotency-Key": "organization-readiness-001"})
    assert refreshed.status_code == 200 and refreshed.json()["network_used"] is False
    for relative in ("src/maine_family_law_llm/ui/workbench.html", "maine_family_law_llm/ui/workbench.html", "src/maine_family_law_llm/ui/workbench.js", "maine_family_law_llm/ui/workbench.js"):
        assert "organization-readiness" in (ROOT / relative).read_text(encoding="utf-8")
