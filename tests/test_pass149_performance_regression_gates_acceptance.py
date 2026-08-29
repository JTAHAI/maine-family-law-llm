from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.contracts import EndpointInventory
from app.api.production import app as production_app
from legal.runtime.performance_regression import (
    PerformanceGateError,
    PerformanceGateReceiptStore,
    evaluate_performance_gates,
)
from maine_family_law_llm import api


def _headers() -> dict[str, str]:
    return {
        "X-User-Role": "reviewer",
        "X-Tenant-Id": "fictional-tenant",
        "X-MFLL-Client-Session": "a" * 48,
    }


def test_pass149_budget_gate_keeps_missing_and_operator_evidence_honest(tmp_path: Path) -> None:
    report = evaluate_performance_gates(
        {"launch_ms": 1_200, "search_ms": 5_000, "peak_memory_mib": 512},
        evidence_kind="operator_supplied_unverified",
    )
    assert report["status"] == "blocked"
    assert report["over_budget_metric_count"] == 1
    assert report["missing_metric_count"] == 6
    assert report["release_eligible"] is False
    assert report["release_evidence_claimed"] is False
    metrics = {row["metric_id"]: row for row in report["metrics"]}
    assert metrics["search_ms"]["status"] == "over_budget"
    assert metrics["packet_ms"]["status"] == "not_measured"

    store = PerformanceGateReceiptStore(tmp_path, encryption_key="fictional-performance-key")
    saved = store.record(report, actor_role="reviewer", tenant_id="fictional-tenant")
    assert saved["audit_receipt"]["review_required"] is True
    assert store.verify()["audit_chain_valid"] is True
    assert str(tmp_path).encode() not in store.path.read_bytes()
    with pytest.raises(PerformanceGateError, match="tenant_mismatch"):
        store.record(report, actor_role="reviewer", tenant_id="other-tenant")
    with pytest.raises(PerformanceGateError, match="not_allowlisted"):
        evaluate_performance_gates({"prompt_text": 1})


def test_pass149_canonical_route_ui_and_inventory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    matter = tmp_path / "fictional-performance-matter"
    matter.mkdir()
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-performance-key")
    monkeypatch.setenv("MFL_RUNTIME_STATE_ROOT", str(tmp_path / "fictional-runtime-state"))
    monkeypatch.setattr(api, "active_case_root", lambda: matter)
    client = TestClient(api.app)
    catalog = client.get("/api/runtime/performance-gates", headers=_headers())
    assert catalog.status_code == 200
    assert catalog.json()["release_evidence_claimed"] is False
    saved = client.post(
        "/api/runtime/performance-gates",
        headers={**_headers(), "X-MFLL-Idempotency-Key": "performance-gate-fixture-0001"},
        json={"observations": {"launch_ms": 1_000, "search_ms": 500}, "evidence_kind": "operator_supplied_unverified"},
    )
    assert saved.status_code == 200
    assert saved.json()["status"] == "incomplete"
    assert saved.json()["audit_receipt"]["review_required"] is True
    production = TestClient(production_app).post(
        "/api/runtime/performance-gates",
        headers={**_headers(), "X-MFLL-Idempotency-Key": "performance-gate-fixture-0003"},
        json={"observations": {"launch_ms": 1_000}, "evidence_kind": "synthetic_local_test"},
    )
    assert production.status_code == 200
    assert production.json()["release_eligible"] is False
    rejected = client.post(
        "/api/runtime/performance-gates",
        headers={**_headers(), "X-MFLL-Idempotency-Key": "performance-gate-fixture-0002"},
        json={"observations": {"record_text": 1}},
    )
    assert rejected.status_code == 422

    root = Path(__file__).resolve().parents[1]
    for relative in ("src/maine_family_law_llm/ui", "maine_family_law_llm/ui"):
        html = (root / relative / "workbench.html").read_text(encoding="utf-8")
        javascript = (root / relative / "workbench.js").read_text(encoding="utf-8")
        assert 'id="performance-gates-save"' in html
        assert "/api/runtime/performance-gates" in javascript
        assert "not release certification" in html
    registered = {
        (method, str(route.path))
        for route in production_app.routes
        for method in (getattr(route, "methods", None) or set())
        if method not in {"HEAD", "OPTIONS"}
    }
    assert EndpointInventory().compare_to_registered(registered, surface="production")["status"] == "pass"
