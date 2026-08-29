from __future__ import annotations

import pytest


def _headers() -> dict[str, str]:
    return {
        "X-User-Role": "reviewer",
        "X-Tenant-Id": "fictional_tenant",
        "X-MFLL-Client-Session": "a" * 48,
    }


@pytest.mark.parametrize(
    "path",
    (
        "/api/release-pilot-hardening/pilot/dashboard",
        "/api/attorney-sandbox-operations/status",
        "/api/limited-real-matter-pilot/status",
        "/api/ga-release-candidate/status",
        "/api/ga-shipment-readiness/status",
    ),
)
def test_pass188_189_production_gateway_uses_protected_enterprise_routes(path: str) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from app.api.production import app

    client = TestClient(app)
    denied = client.get(path)
    assert denied.status_code == 403
    assert "rbac_role_required" in str(denied.json())

    allowed = client.get(path, headers=_headers())
    assert allowed.status_code == 200
    payload = allowed.json()
    assert payload["review_required"] is True
    assert payload["rbac"]["tenant_scoped"] is True
    assert payload["audit_event"]["audit_status"] == "emitted"


def test_pass188_189_existing_operations_stay_truthful_about_external_evidence() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from app.api.production import app

    client = TestClient(app)
    sandbox = client.get("/api/attorney-sandbox-operations/status", headers=_headers())
    real_matter = client.get("/api/limited-real-matter-pilot/status", headers=_headers())
    assert sandbox.status_code == 200 and real_matter.status_code == 200
    assert sandbox.json()["pass48_complete"] is False
    assert real_matter.json()["pass49_complete"] is False
    assert sandbox.json()["external_launch_evidence_gate_required"] is True
    assert real_matter.json()["external_launch_evidence_gate_required"] is True
