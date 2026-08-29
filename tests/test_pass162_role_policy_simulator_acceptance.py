from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.production import app as production_app
from legal.governance.role_policy_simulator import RolePolicySimulationError, RolePolicySimulationStore, simulate_role_policy


ROOT = Path(__file__).resolve().parents[1]


def test_pass162_simulates_fictional_role_decisions_with_policy_basis_and_encrypted_receipt(tmp_path: Path) -> None:
    simulation = simulate_role_policy(simulation_id="preview_001", fictional_roles=["reviewer"], permissions=["matter:read", "settings:write"], tenant_id="fictional-tenant")
    decisions = {row["permission"]: row for row in simulation["permission_results"]}
    assert decisions["matter:read"]["decision"] == "allow"
    assert decisions["settings:write"]["decision"] == "deny"
    assert decisions["settings:write"]["denial_reason"] == "permission_not_granted_by_selected_roles"
    assert simulation["fictional_user_only"] is True and simulation["policy_change_applied"] is False
    receipt = RolePolicySimulationStore(tmp_path, encryption_key="0123456789abcdef").record(simulation, tenant_id="fictional-tenant")
    assert receipt["receipt"]["simulation_receipt_id"].startswith("role_sim_")
    encrypted = next(tmp_path.glob("*.json.enc"))
    assert b"preview_001" not in encrypted.read_bytes()
    try:
        simulate_role_policy(simulation_id="preview_002", fictional_roles=["unknown"], permissions=[], tenant_id="fictional-tenant")
    except RolePolicySimulationError as exc:
        assert str(exc) == "role_policy_simulation_roles_invalid"
    else:
        raise AssertionError("unknown role was not refused")


def test_pass162_canonical_production_route_requires_admin_and_shipped_ui_uses_it(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MFL_ROLE_POLICY_SIMULATION_ROOT", str(tmp_path / "receipts"))
    monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "idempotency"))
    client = TestClient(production_app)
    denied = client.post("/api/admin/role-policy-simulations", headers={"X-User-Role": "reviewer", "X-Tenant-Id": "fictional-tenant"}, json={"simulation_id": "preview_001", "fictional_roles": ["reviewer"], "permissions": ["matter:read"]})
    assert denied.status_code == 403
    accepted = client.post("/api/admin/role-policy-simulations", headers={"X-User-Role": "admin", "X-Tenant-Id": "fictional-tenant", "X-MFLL-Client-Session": "b" * 32, "X-MFLL-Idempotency-Key": "role-policy-simulation-001"}, json={"simulation_id": "preview_001", "fictional_roles": ["reviewer"], "permissions": ["matter:read", "settings:write"]})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["audit_receipt"]["receipt"]["review_required"] is True
    for relative in ("src/maine_family_law_llm/ui/workbench.html", "maine_family_law_llm/ui/workbench.html", "src/maine_family_law_llm/ui/workbench.js", "maine_family_law_llm/ui/workbench.js"):
        assert "role-policy-simulator" in (ROOT / relative).read_text(encoding="utf-8")
