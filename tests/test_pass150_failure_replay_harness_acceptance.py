from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.contracts import EndpointInventory
from app.api.production import app as production_app
from legal.runtime.failure_replay import FailureReplayError, FailureReplayReceiptStore, replay_sanitized_failure
from maine_family_law_llm import api


def _headers() -> dict[str, str]:
    return {
        "X-User-Role": "reviewer",
        "X-Tenant-Id": "fictional-tenant",
        "X-MFLL-Client-Session": "a" * 48,
    }


def test_pass150_replays_only_allowlisted_sanitized_envelopes(tmp_path: Path) -> None:
    report = replay_sanitized_failure("storage_reserve_required")
    assert report["status"] == "replayed_sanitized_envelope"
    assert report["simulation_only"] is True
    assert report["original_operation_reexecuted"] is False
    assert report["raw_exception_accepted"] is False
    assert report["private_record_content_included"] is False
    store = FailureReplayReceiptStore(tmp_path, encryption_key="fictional-failure-key")
    saved = store.record(report, actor_role="reviewer", tenant_id="fictional-tenant")
    assert saved["source_drill_down"]["source_id"] == "failure_replay:storage_reserve_required"
    assert store.verify()["audit_chain_valid"] is True
    encrypted = store.path.read_bytes()
    assert b"C:\\" not in encrypted and str(tmp_path).encode() not in encrypted
    with pytest.raises(FailureReplayError, match="not_allowlisted"):
        replay_sanitized_failure("C:/secret/private-log.txt")
    with pytest.raises(FailureReplayError, match="tenant_mismatch"):
        store.record(report, actor_role="reviewer", tenant_id="other-tenant")


def test_pass150_canonical_route_ui_and_inventory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    matter = tmp_path / "fictional-failure-matter"
    matter.mkdir()
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-failure-key")
    monkeypatch.setenv("MFL_RUNTIME_STATE_ROOT", str(tmp_path / "fictional-runtime-state"))
    monkeypatch.setattr(api, "active_case_root", lambda: matter)
    client = TestClient(api.app)
    catalog = client.get("/api/runtime/failure-replay", headers=_headers())
    assert catalog.status_code == 200
    assert catalog.json()["raw_failures_accepted"] is False
    rejected = client.post(
        "/api/runtime/failure-replay",
        headers={**_headers(), "X-MFLL-Idempotency-Key": "failure-replay-fixture-0001"},
        json={"scenario_id": "local_service_unreachable", "confirmed": False},
    )
    assert rejected.status_code == 422
    saved = client.post(
        "/api/runtime/failure-replay",
        headers={**_headers(), "X-MFLL-Idempotency-Key": "failure-replay-fixture-0002"},
        json={"scenario_id": "authority_not_found", "confirmed": True},
    )
    assert saved.status_code == 200
    assert saved.json()["original_operation_reexecuted"] is False
    production = TestClient(production_app).post(
        "/api/runtime/failure-replay",
        headers={**_headers(), "X-MFLL-Idempotency-Key": "failure-replay-fixture-0003"},
        json={"scenario_id": "no_active_matter", "confirmed": True},
    )
    assert production.status_code == 200
    assert production.json()["simulation_only"] is True

    root = Path(__file__).resolve().parents[1]
    for relative in ("src/maine_family_law_llm/ui", "maine_family_law_llm/ui"):
        html = (root / relative / "workbench.html").read_text(encoding="utf-8")
        javascript = (root / relative / "workbench.js").read_text(encoding="utf-8")
        assert 'id="failure-replay-run"' in html
        assert "/api/runtime/failure-replay" in javascript
        assert "does not prove that a real failure is fixed" in html
    registered = {
        (method, str(route.path))
        for route in production_app.routes
        for method in (getattr(route, "methods", None) or set())
        if method not in {"HEAD", "OPTIONS"}
    }
    assert EndpointInventory().compare_to_registered(registered, surface="production")["status"] == "pass"
