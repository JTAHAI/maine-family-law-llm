from __future__ import annotations

import json
from pathlib import Path

import pytest

from legal.evals.procedural_safety_metrics import PROCEDURAL_SCENARIOS, ProceduralSafetyMetricRunner


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _row(scenario_type: str, expected: str, payload: dict) -> dict:
    return {
        "scenario_type": scenario_type,
        "expected_blockers": [expected],
        "filing_payload": payload,
        "review_status": "attorney_reviewed_final",
        "annotator_or_generation_method": "attorney_review",
        "authority_build_id": "fictional_authority_build_001",
        "source_snapshot_sha256": "e" * 64,
        "reviewer_evidence_sha256": "f" * 64,
        "license_status": "license_verified_external",
        "source_freshness": "current",
    }


def _fixture(tmp_path: Path) -> Path:
    root = tmp_path / "external_eval_root"
    _write_jsonl(
        root / "maine_procedural_safety_gold.jsonl",
        [
            _row("deadline", "deadline_source_missing", {"procedure_posture_report": {"blockers": ["deadline_source_missing"]}}),
            _row("service", "service_proof_missing", {"procedure_posture_report": {"blockers": ["service_proof_missing"]}}),
            _row("posture", "posture_review_missing", {"procedure_posture_report": {"blockers": ["posture_review_missing"]}}),
            _row("forms", "stale_form:FM-002", {"forms_report": {"stale_forms": ["FM-002"]}}),
            _row("venue", "venue_scope_unresolved", {"procedure_posture_report": {"blockers": ["venue_scope_unresolved"]}}),
            _row("filing", "citation_not_found:fictional", {"verification_report": {"blockers": ["citation_not_found:fictional"]}}),
        ],
    )
    return root


def test_pass185_strict_procedural_safety_scenarios_fail_closed(tmp_path: Path) -> None:
    report = ProceduralSafetyMetricRunner().run(eval_root=_fixture(tmp_path), strict_provenance=True).as_dict()
    assert report["status"] == "pass", report
    assert report["scenario_total"] == len(PROCEDURAL_SCENARIOS)
    assert report["scenario_correct"] == len(PROCEDURAL_SCENARIOS)
    assert set(report["scenario_type_counts"]) == PROCEDURAL_SCENARIOS


def test_pass185_missing_provenance_or_coverage_blocks_metric(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    row = json.loads((root / "maine_procedural_safety_gold.jsonl").read_text(encoding="utf-8").splitlines()[0])
    row.pop("reviewer_evidence_sha256")
    _write_jsonl(root / "maine_procedural_safety_gold.jsonl", [row])
    report = ProceduralSafetyMetricRunner().run(eval_root=root, strict_provenance=True).as_dict()
    assert report["status"] == "blocked"
    assert "procedural_reviewer_evidence_sha256_invalid" in report["blockers"]
    assert "procedural_scenario_coverage_missing:filing" in report["blockers"]


def test_pass185_production_route_is_tenant_scoped_and_ships_controls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from app.api.production import app

    root = _fixture(tmp_path)
    monkeypatch.setenv("MFL_PROCEDURAL_SAFETY_EVAL_ROOT", str(root))
    client = TestClient(app)
    denied = client.post("/api/evals/procedural-safety/benchmark", headers={"X-User-Role": "viewer", "X-Tenant-Id": "fictional_tenant"})
    assert denied.status_code == 403
    response = client.post("/api/evals/procedural-safety/benchmark", headers={"X-User-Role": "reviewer", "X-Tenant-Id": "fictional_tenant"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pass"
    assert payload["scenario_correct"] == len(PROCEDURAL_SCENARIOS)
    assert str(tmp_path) not in json.dumps(payload)
    for path in (Path("src/maine_family_law_llm/ui/workbench.js"), Path("maine_family_law_llm/ui/workbench.js")):
        text = path.read_text(encoding="utf-8")
        assert "procedural-safety-benchmark-control" in text
        assert "/api/evals/procedural-safety/benchmark" in text
