from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from legal.evals.release_measurements import ReleaseMetricMeasurementTemplateBuilder, required_external_metric_names
from legal.evals.release_metric_eligibility import ReleaseMetricEligibilityGate, _signature_payload


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _external_bundle(root: Path) -> None:
    metrics: list[dict] = []
    artifacts: set[str] = set()
    for row in ReleaseMetricMeasurementTemplateBuilder().build()["metrics"]:
        name = row["name"]
        value = 0.0 if name == "filing_gate_false_pass_rate" else 0.99
        if name == "hallucination_rate":
            value = 0.01
        hashes = {field: _sha(f"{name}:{field}") for field in (
            "source_snapshot_sha256",
            "reviewer_evidence_sha256",
            "license_evidence_sha256",
            "input_manifest_sha256",
            "environment_manifest_sha256",
            "output_manifest_sha256",
        )}
        artifacts.update(hashes.values())
        metrics.append(
            {
                **row,
                "value": value,
                "sample_size": int(row["minimum_sample_size"]),
                "basis": f"external_task_specific_attorney_reviewed_evaluator_over_{row['source_dataset']}",
                "attorney_reviewed": True,
                "reviewer_status": "attorney_reviewed_external_evidence",
                "evidence": {
                    "data_class": "external_attorney_reviewed",
                    "license_status": "externally_verified",
                    "authority_build_id": "maine-authority-build-2026.08.27",
                    **hashes,
                    "reproducibility": {"status": "reproduced", "independent_runs": 2},
                },
            }
        )
    measurement_path = root / "release_metric_measurements.json"
    artifact_path = root / "release_metric_artifacts.json"
    _write_json(measurement_path, {"schema_version": "release_metric_measurements_v1", "metrics": metrics})
    _write_json(
        artifact_path,
        {
            "schema_version": "release_metric_artifact_manifest_v1",
            "artifacts": [{"sha256": item} for item in sorted(artifacts)],
        },
    )
    private_key = Ed25519PrivateKey.generate()
    encoded_key = base64.b64encode(
        private_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    ).decode("ascii")
    _write_json(
        root / "release_metric_eligibility_trust.json",
        {"schema_version": "release_metric_eligibility_trust_v1", "trusted_keys": {"external-qa-key": encoded_key}},
    )
    attestation = {
        "schema_version": "release_metric_eligibility_attestation_v1",
        "attestation_id": "external-qa-evidence-20260827",
        "measurement_sha256": hashlib.sha256(measurement_path.read_bytes()).hexdigest(),
        "artifact_manifest_sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
        "metric_names": required_external_metric_names(),
    }
    attestation["signature"] = {
        "key_id": "external-qa-key",
        "signature": base64.b64encode(private_key.sign(_signature_payload(attestation))).decode("ascii"),
    }
    _write_json(root / "release_metric_eligibility_attestation.json", attestation)


def test_pass190_external_license_reproducibility_and_signature_contract_passes(tmp_path: Path) -> None:
    root = tmp_path / "external-release-evidence"
    _external_bundle(root)
    report = ReleaseMetricEligibilityGate(project_root=Path(__file__).resolve().parents[1]).run(eval_root=root).as_dict()

    assert report["status"] == "pass", report
    assert report["measurement_audit_status"] == "pass"
    assert report["artifact_manifest_verified"] is True
    assert report["attestation_verified"] is True
    assert report["signature_verification"] == "verified"
    assert all(row["status"] == "pass" for row in report["metric_statuses"])
    assert report["enterprise_decision_eligible"] is False
    assert report["private_matter_data_used"] is False
    assert report["network_used"] is False


def test_pass190_synthetic_or_unmanifested_evidence_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "external-release-evidence"
    _external_bundle(root)
    measurement_path = root / "release_metric_measurements.json"
    payload = json.loads(measurement_path.read_text(encoding="utf-8"))
    payload["metrics"][0]["evidence"]["data_class"] = "synthetic"
    _write_json(measurement_path, payload)
    report = ReleaseMetricEligibilityGate(project_root=Path(__file__).resolve().parents[1]).run(eval_root=root).as_dict()

    assert report["status"] == "blocked"
    assert any(item.startswith("metric_data_class_not_external_attorney_reviewed:") for item in report["blockers"])
    assert "release_metric_attestation_measurement_hash_mismatch" in report["blockers"]


def test_pass190_production_route_requires_tenant_and_redacts_external_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from app.api.contracts import EndpointInventory
    from app.api.production import app

    root = tmp_path / "external-release-evidence"
    _external_bundle(root)
    monkeypatch.setenv("MFL_RELEASE_METRIC_ELIGIBILITY_ROOT", str(root))
    client = TestClient(app)
    denied = client.get("/api/evals/release-metric-eligibility", headers={"X-User-Role": "reviewer"})
    assert denied.status_code == 403
    response = client.post(
        "/api/evals/release-metric-eligibility",
        headers={"X-User-Role": "reviewer", "X-Tenant-Id": "fictional_tenant"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pass", payload
    assert payload["enterprise_decision_eligible"] is False
    assert payload["matter_scope"] == "not_applicable_external_non_matter_evaluation"
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
        assert "release-metric-eligibility-control" in text
        assert "/api/evals/release-metric-eligibility" in text
