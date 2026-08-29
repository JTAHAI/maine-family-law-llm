from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.contracts import EndpointInventory
from app.api.production import app as production_app
from legal.runtime.power_loss_resilience import (
    PowerLossResilienceError,
    PowerLossResilienceReceiptStore,
    SimulatedPowerLoss,
    run_power_loss_resilience_drill,
)
from legal.security.durable_io import atomic_write_bytes
from maine_family_law_llm import api


def _headers(role: str = "admin") -> dict[str, str]:
    return {
        "X-MFLL-Idempotency-Key": "idem-power-loss-fictional-0001",
        "X-User-Role": role,
        "X-Tenant-Id": "fictional-tenant",
        "X-MFLL-Client-Session": "e" * 48,
    }


def test_pass146_atomic_write_never_leaves_a_partial_generation_at_fault_boundaries(tmp_path: Path) -> None:
    target = tmp_path / "synthetic.state"
    previous = b"previous complete generation"
    next_value = b"next complete generation"
    for point, expected in (
        ("after_write", previous),
        ("after_file_sync_before_replace", previous),
        ("after_replace_before_directory_sync", next_value),
    ):
        atomic_write_bytes(target, previous)

        def inject(current: str, target_point: str = point) -> None:
            if current == target_point:
                raise SimulatedPowerLoss(target_point)

        with pytest.raises(SimulatedPowerLoss):
            atomic_write_bytes(target, next_value, fault_injector=inject)
        assert target.read_bytes() == expected
        assert not list(tmp_path.glob(".synthetic.state.*.tmp"))


def test_pass146_synthetic_drill_covers_required_artifact_classes_without_private_data(tmp_path: Path) -> None:
    report = run_power_loss_resilience_drill(workspace_parent=tmp_path)
    assert report["status"] == "pass"
    assert report["simulation_only"] is True
    assert report["physical_power_cut_verified"] is False
    assert report["private_record_content_used"] is False
    assert report["private_paths_included"] is False
    assert report["network_used"] is False
    assert report["operation_count"] == 18
    assert report["failed_operation_count"] == 0
    assert set(report["covered_artifact_classes"]) == {
        "import_manifest", "review_state_write", "encrypted_state", "index_pointer_swap", "backup_manifest", "export_receipt"
    }
    assert all(row["interrupted"] is True for row in report["operations"])
    assert all(row["outcome"] in {"previous_generation_preserved", "next_generation_committed"} for row in report["operations"])
    assert all(row["orphan_temporary_file_count"] == 0 for row in report["operations"])
    assert "synthetic_private_value" not in str(report)
    assert not list(tmp_path.glob("mfll-power-loss-drill-*"))


def test_pass146_receipts_are_encrypted_hash_linked_and_tenant_bound(tmp_path: Path) -> None:
    matter = tmp_path / "fictional-matter"
    matter.mkdir()
    report = run_power_loss_resilience_drill(workspace_parent=tmp_path)
    store = PowerLossResilienceReceiptStore(matter, encryption_key="fictional-power-loss-key")
    store.record(report, actor_role="admin", tenant_id="fictional-tenant")
    store.record(report, actor_role="admin", tenant_id="fictional-tenant")
    assert store.verify() == {"status": "pass", "receipt_count": 2, "audit_chain_valid": True, "review_required": True}
    assert str(matter).encode("utf-8") not in store.path.read_bytes()
    with pytest.raises(PowerLossResilienceError, match="tenant_mismatch"):
        store.record(report, actor_role="admin", tenant_id="other-fictional-tenant")
    with pytest.raises(PowerLossResilienceError, match="private_path_refused"):
        store.record({**report, "path": r"C:\fictional\private"}, actor_role="admin", tenant_id="fictional-tenant")


def test_pass146_canonical_admin_route_is_matter_scoped_and_shipped_in_ui(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    matter = tmp_path / "fictional-matter"
    matter.mkdir()
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-power-loss-key")
    monkeypatch.setattr(api, "active_case_root", lambda: matter)
    client = TestClient(api.app)

    response = client.post("/api/runtime/power-loss-drill", headers=_headers())
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pass"
    assert payload["simulation_only"] is True
    assert payload["physical_power_cut_verified"] is False
    assert payload["audit_receipt"]["drill_id"].startswith("power_")
    assert response.headers["x-mfll-idempotency-status"] == "recorded"
    assert str(matter) not in response.text

    denied = client.post("/api/runtime/power-loss-drill", headers=_headers("reviewer"))
    assert denied.status_code == 403
    assert denied.json()["detail"] == "admin_role_required"
    monkeypatch.setattr(api, "active_case_root", lambda: None)
    no_matter = client.post("/api/runtime/power-loss-drill", headers={**_headers(), "X-MFLL-Idempotency-Key": "idem-power-loss-fictional-0002"})
    assert no_matter.status_code == 409
    assert no_matter.json()["detail"] == "no_active_matter"

    root = Path(__file__).resolve().parents[1]
    for relative in ("src/maine_family_law_llm/ui", "maine_family_law_llm/ui"):
        directory = root / relative
        assert 'id="power-loss-resilience-run"' in (directory / "workbench.html").read_text(encoding="utf-8")
        assert "/api/runtime/power-loss-drill" in (directory / "workbench.js").read_text(encoding="utf-8")


def test_pass146_production_inventory_has_one_canonical_local_route() -> None:
    registered = {
        (method, str(getattr(route, "path", "")))
        for route in production_app.routes
        for method in (getattr(route, "methods", None) or set())
        if method not in {"HEAD", "OPTIONS"}
    }
    report = EndpointInventory().compare_to_registered(registered, surface="production")
    assert report["status"] == "pass", report
    assert ("POST", "/api/runtime/power-loss-drill") in registered
