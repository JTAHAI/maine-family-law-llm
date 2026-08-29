from __future__ import annotations

import json
from pathlib import Path

import pytest

from legal.evals.accessibility_bias_metrics import ACCESSIBILITY_BIAS_CATEGORIES, AccessibilityBiasMetricRunner


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _row(category: str) -> dict:
    return {
        "category": category,
        "audience": "self_represented",
        "task_type": "ask",
        "input_text": f"Fictional {category} access scenario. Explain the next safe step in plain language.",
        "review_status": "attorney_reviewed_final",
        "annotator_or_generation_method": "attorney_review",
        "authority_build_id": "fictional_authority_build_001",
        "source_snapshot_sha256": "1" * 64,
        "reviewer_evidence_sha256": "2" * 64,
        "license_status": "license_verified_external",
        "source_freshness": "current",
    }


def test_pass186_strict_automated_accessibility_bias_checks_cover_each_category(tmp_path: Path) -> None:
    root = tmp_path / "external_eval_root"
    _write_jsonl(root / "maine_accessibility_bias_gold.jsonl", [_row(category) for category in sorted(ACCESSIBILITY_BIAS_CATEGORIES)])
    report = AccessibilityBiasMetricRunner().run(eval_root=root, strict_provenance=True).as_dict()
    assert report["status"] == "pass", report
    assert report["case_total"] == len(ACCESSIBILITY_BIAS_CATEGORIES)
    assert set(report["category_counts"]) == ACCESSIBILITY_BIAS_CATEGORIES
    assert report["human_accessibility_review_required"] is True


def test_pass186_missing_provenance_and_category_coverage_block(tmp_path: Path) -> None:
    root = tmp_path / "external_eval_root"
    row = _row("language")
    row.pop("reviewer_evidence_sha256")
    _write_jsonl(root / "maine_accessibility_bias_gold.jsonl", [row])
    report = AccessibilityBiasMetricRunner().run(eval_root=root, strict_provenance=True).as_dict()
    assert report["status"] == "blocked"
    assert "accessibility_bias_reviewer_evidence_sha256_invalid" in report["blockers"]
    assert "accessibility_bias_category_coverage_missing:disability" in report["blockers"]


def test_pass186_production_route_requires_tenant_and_keeps_human_review_boundary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from app.api.production import app

    root = tmp_path / "external_eval_root"
    _write_jsonl(root / "maine_accessibility_bias_gold.jsonl", [_row(category) for category in sorted(ACCESSIBILITY_BIAS_CATEGORIES)])
    monkeypatch.setenv("MFL_ACCESSIBILITY_BIAS_EVAL_ROOT", str(root))
    client = TestClient(app)
    denied = client.get("/api/evals/accessibility-bias/benchmark", headers={"X-User-Role": "reviewer"})
    assert denied.status_code == 403
    response = client.post("/api/evals/accessibility-bias/benchmark", headers={"X-User-Role": "reviewer", "X-Tenant-Id": "fictional_tenant"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pass"
    assert payload["human_accessibility_review_required"] is True
    assert str(tmp_path) not in json.dumps(payload)
