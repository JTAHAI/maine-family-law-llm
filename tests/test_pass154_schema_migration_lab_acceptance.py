from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.contracts import EndpointInventory
from app.api.production import app as production_app
from legal.runtime.schema_migration_lab import SchemaMigrationLab, SchemaMigrationLabError, SUPPORTED_SOURCE_SCHEMAS
from maine_family_law_llm import api


def _headers(tenant: str = "fictional-tenant") -> dict[str, str]:
    return {"X-User-Role": "reviewer", "X-Tenant-Id": tenant, "X-MFLL-Client-Session": "a" * 48}


def test_pass154_runs_every_declared_profile_and_interruption_contract_without_touching_matter(monkeypatch, tmp_path: Path) -> None:
    matter = tmp_path / "fictional-migration-matter"; matter.mkdir()
    record = matter / "fictional-record.txt"; record.write_text("fictional record must remain unchanged", encoding="utf-8")
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-migration-key")
    lab = SchemaMigrationLab(matter)
    report = lab.run(source_schema="all", scenario="full_suite", actor_role="reviewer", tenant_id="fictional-tenant")
    assert report["status"] == "pass_review_required"
    assert report["check_count"] == len(SUPPORTED_SOURCE_SCHEMAS) * 3
    assert all(check["status"] == "pass" for check in report["checks"])
    assert record.read_text(encoding="utf-8") == "fictional record must remain unchanged"
    body = (matter / "40_RUNTIME" / "schema-migration-lab" / "state.json.enc").read_bytes()
    assert b"fictional record must remain unchanged" not in body
    status = lab.status(tenant_id="fictional-tenant")
    assert status["runs"][0]["run_id"] == report["run_id"] and status["live_matter_changed"] is False
    with pytest.raises(SchemaMigrationLabError, match="migration_lab_tenant_mismatch"):
        lab.status(tenant_id="other-fictional-tenant")


def test_pass154_canonical_api_ui_and_inventory(monkeypatch, tmp_path: Path) -> None:
    matter = tmp_path / "fictional-api-migration-matter"; matter.mkdir(); (matter / "fixture.txt").write_text("fictional", encoding="utf-8")
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-migration-key")
    monkeypatch.setenv("MFL_RUNTIME_STATE_ROOT", str(tmp_path / "runtime-state"))
    monkeypatch.setattr(api, "active_case_root", lambda: matter)
    client = TestClient(production_app)
    created = client.post("/api/runtime/schema-migration-lab/run", headers={**_headers(), "X-MFLL-Idempotency-Key": "migration-lab-fixture-0001"}, json={"source_schema": "6.0.4.0", "scenario": "interrupt_after_commit", "confirmed": True})
    assert created.status_code == 200 and created.json()["live_matter_changed"] is False
    listed = client.get("/api/runtime/schema-migration-lab", headers=_headers())
    assert listed.status_code == 200 and listed.json()["runs"][0]["check_count"] == 1
    root = Path(__file__).resolve().parents[1]
    for relative in ("src/maine_family_law_llm/ui", "maine_family_law_llm/ui"):
        assert 'id="schema-migration-lab-run"' in (root / relative / "workbench.html").read_text(encoding="utf-8")
        assert "/api/runtime/schema-migration-lab/run" in (root / relative / "workbench.js").read_text(encoding="utf-8")
    registered = {(method, str(route.path)) for route in production_app.routes for method in (getattr(route, "methods", None) or set()) if method not in {"HEAD", "OPTIONS"}}
    assert EndpointInventory().compare_to_registered(registered, surface="production")["status"] == "pass"
