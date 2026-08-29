from __future__ import annotations

import json
from pathlib import Path

import pytest

from legal.evals.longitudinal_matter_metrics import LONGITUDINAL_SCENARIOS, LongitudinalMatterMetricRunner


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _row(scenario: str) -> dict:
    return {
        "scenario": scenario,
        "data_class": "synthetic",
        "fixture_id": "longitudinal-fictional-contract-v1",
        "fixture_manifest_sha256": "a" * 64,
        "scenario_evidence_sha256": "b" * 64,
        "attorney_reviewed": False,
    }


def _fixture(tmp_path: Path) -> Path:
    root = tmp_path / "external_eval_root"
    _write_jsonl(root / "maine_longitudinal_matter_gold.jsonl", [_row(item) for item in sorted(LONGITUDINAL_SCENARIOS)])
    return root


def test_pass187_disposable_longitudinal_contract_exercises_real_components(tmp_path: Path) -> None:
    report = LongitudinalMatterMetricRunner().run(eval_root=_fixture(tmp_path), strict_provenance=True).as_dict()
    assert report["status"] == "pass", report
    assert report["scenario_total"] == len(LONGITUDINAL_SCENARIOS)
    assert report["scenario_passed"] == len(LONGITUDINAL_SCENARIOS)
    assert set(report["scenario_counts"]) == LONGITUDINAL_SCENARIOS
    assert report["encrypted_state_verified"] is True
    assert report["append_only_history_verified"] is True
    assert report["source_drill_down_verified"] is True
    assert report["migration_contract_verified"] is True
    assert report["stale_work_verified"] is True
    assert report["attorney_reviewed"] is False
    assert report["private_matter_data_used"] is False


def test_pass187_missing_manifest_provenance_or_coverage_blocks(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    row = _row("corrected_fact")
    row.pop("scenario_evidence_sha256")
    _write_jsonl(root / "maine_longitudinal_matter_gold.jsonl", [row])
    report = LongitudinalMatterMetricRunner().run(eval_root=root, strict_provenance=True).as_dict()
    assert report["status"] == "blocked"
    assert "longitudinal_scenario_evidence_sha256_invalid" in report["blockers"]
    assert "longitudinal_scenario_coverage_missing:restart_reopen" in report["blockers"]


def test_pass187_production_route_is_tenant_scoped_and_keeps_private_paths_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from app.api.contracts import EndpointInventory
    from app.api.production import app

    root = _fixture(tmp_path)
    monkeypatch.setenv("MFL_LONGITUDINAL_MATTER_EVAL_ROOT", str(root))
    client = TestClient(app)
    denied = client.get("/api/evals/longitudinal-matter/benchmark", headers={"X-User-Role": "reviewer"})
    assert denied.status_code == 403
    response = client.post(
        "/api/evals/longitudinal-matter/benchmark",
        headers={"X-User-Role": "reviewer", "X-Tenant-Id": "fictional_tenant"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pass", payload
    assert payload["matter_scope"] == "not_applicable_external_non_matter_evaluation"
    assert payload["attorney_reviewed"] is False
    assert str(tmp_path) not in json.dumps(payload)
    registered = {
        (method, str(route.path))
        for route in app.routes
        for method in (getattr(route, "methods", None) or set())
        if method not in {"HEAD", "OPTIONS"}
    }
    assert EndpointInventory().compare_to_registered(registered, surface="production")["status"] == "pass"
    root_path = Path(__file__).resolve().parents[1]
    for relative in ("src/maine_family_law_llm/ui/workbench.js", "maine_family_law_llm/ui/workbench.js"):
        text = (root_path / relative).read_text(encoding="utf-8")
        assert "longitudinal-matter-benchmark-control" in text
        assert "/api/evals/longitudinal-matter/benchmark" in text
