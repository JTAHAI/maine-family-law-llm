from __future__ import annotations

import json
from pathlib import Path

import pytest

from legal.api_stability import ApiStabilityProgram


def _baseline(root: Path, snapshot: dict) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "public_api_contract_baseline.json").write_text(
        json.dumps({"schema_version": "public_api_contract_baseline_v1", "endpoints": snapshot["endpoints"], "deprecated_endpoints": ["GET /api/legacy-example [local]"]}),
        encoding="utf-8",
    )


def test_pass195_external_frozen_contract_detects_breaking_changes(tmp_path: Path) -> None:
    program = ApiStabilityProgram(project_root=Path(__file__).resolve().parents[1])
    snapshot = program.snapshot(); root = tmp_path / "external-api-contract"; _baseline(root, snapshot)
    compatible = program.compare(baseline_root=root).as_dict()
    assert compatible["status"] == "pass", compatible
    assert compatible["deprecation_warnings"]
    payload = json.loads((root / "public_api_contract_baseline.json").read_text(encoding="utf-8"))
    payload["endpoints"].append({"method": "GET", "path": "/api/removed-legacy-endpoint", "review_required": True, "surface": "local"})
    (root / "public_api_contract_baseline.json").write_text(json.dumps(payload), encoding="utf-8")
    broken = program.compare(baseline_root=root).as_dict()
    assert broken["status"] == "blocked"
    assert "public_api_endpoint_removed" in broken["blockers"]
    assert broken["migration_actions"]


def test_pass195_production_route_requires_tenant_and_redacts_baseline_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from app.api.contracts import EndpointInventory
    from app.api.production import app

    program = ApiStabilityProgram(project_root=Path(__file__).resolve().parents[1]); root = tmp_path / "external-api-contract"; _baseline(root, program.snapshot())
    monkeypatch.setenv("MFL_PUBLIC_API_CONTRACT_ROOT", str(root))
    client = TestClient(app)
    assert client.get("/api/api-stability/status", headers={"X-User-Role": "reviewer"}).status_code == 403
    headers = {"X-User-Role": "reviewer", "X-Tenant-Id": "fictional_tenant"}
    response = client.post("/api/api-stability/compare", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pass", payload
    assert payload["review_required"] is True
    assert str(tmp_path) not in json.dumps(payload)
    registered = {(method, str(route.path)) for route in app.routes for method in (getattr(route, "methods", None) or set()) if method not in {"HEAD", "OPTIONS"}}
    assert EndpointInventory().compare_to_registered(registered, surface="production")["status"] == "pass"
    root_path = Path(__file__).resolve().parents[1]
    for relative in ("src/maine_family_law_llm/ui/workbench.js", "maine_family_law_llm/ui/workbench.js"):
        text = (root_path / relative).read_text(encoding="utf-8")
        assert "api-stability-control" in text
        assert "/api/api-stability/compare" in text
