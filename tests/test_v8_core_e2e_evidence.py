from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "assemble-v8-core-e2e-evidence.py"


def _qualification() -> dict[str, object]:
    checks = {
        name: {"status": "pass"}
        for name in (
            "runtime_health", "workbench_root", "retrieval_status", "retrieval_search",
            "grounded_school_answer", "grounded_private_answer", "no_automatic_install",
            "no_document_network", "presidio_available", "deterministic_fallback",
            "docling_or_fallback", "privacy_worker", "redacted_copy", "ocr_status",
            "original_immutable", "duplicate_detection", "record_comparison",
            "changed_copy", "docling_engine", "redaction_receipt", "original_hash_unchanged",
        )
    }
    return {
        "schema_version": "installed_offline_qualification_v2",
        "qualification_status": "blocked",
        "feature_check_status": "pass",
        "feature_blockers": [],
        "execution_level": "frozen_runtime_canonical_http",
        "runtime_instance_verified": True,
        "fictional_only": True,
        "installed_msix": False,
        "request_events": [{"method": method, "path": route, "http_status": 200,
                            "request_id": "fictional-request-id",
                            "service_instance": "fictional-validator-unit-test"}
                           for method, route in [
                               ("POST", "/api/records/REC-DOCX/parse"),
                               ("POST", "/api/records/REC-PII-TXT/privacy-scan"),
                               ("POST", "/api/records/REC-PII-TXT/redacted-copy"),
                               ("POST", "/api/records/REC-OCR/ocr"),
                               ("GET", "/api/records/REC-DUP-A/duplicates"),
                               ("POST", "/api/records/compare"),
                           ]],
        "blockers": ["os_level_zero_network_proof_not_executed", "installed_msix_not_tested"],
        "qualification_checks": checks,
        "runtime_resolution": {},
        "inventory_result": {"records": 8},
        "offline_boundary": {"runtime_network_observation": {"sample_count": 5, "external_connection_count": 0}},
    }


def _run(
    tmp_path: Path,
    *,
    mutate: str = "",
    durable_restart: bool = False,
    ui_navigation: bool = False,
) -> subprocess.CompletedProcess[str]:
    package_root = tmp_path / "candidate"
    package = package_root / "msix" / "MaineFamilyLawLLM_8.0.0.0_x64.msix"
    runtime = package_root / "runtime" / "MaineFamilyLawLLM.exe"
    package.parent.mkdir(parents=True)
    runtime.parent.mkdir(parents=True)
    # ZIP bytes exercise validator logic only; these are not executed models/apps.
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("MaineFamilyLawLLM.exe", b"other" if mutate == "wrong_package_bytes" else b"fictional-runtime")
    runtime.write_bytes(b"fictional-runtime")
    qualification = _qualification()
    qualification["runtime_resolution"] = {"executable_path": str(runtime.resolve())}
    qualification["runtime_sha256"] = hashlib.sha256(runtime.read_bytes()).hexdigest()
    if mutate == "failed_check":
        qualification["qualification_checks"]["ocr_status"] = {"status": "fail"}  # type: ignore[index]
    elif mutate == "legacy_driver":
        qualification["schema_version"] = "installed_offline_qualification_v1"
    elif mutate == "missing_action":
        qualification["request_events"] = []
    elif mutate == "missing_hash":
        qualification.pop("runtime_sha256")
    elif mutate == "wrong_instance":
        qualification["runtime_instance_verified"] = False
    elif mutate == "changed_runtime":
        runtime.write_bytes(b"changed-since-qualification")
    elif mutate == "unobserved_network":
        qualification["offline_boundary"]["runtime_network_observation"]["errors"] = ["process_connections_access_denied"]
    qualification_path = tmp_path / "qualification.json"
    qualification_path.write_text(json.dumps(qualification), encoding="utf-8")
    evidence = {
        "candidate": {"package_sha256": hashlib.sha256(package.read_bytes()).hexdigest()},
        "installed_offline_qualification": {"status": "pass"},
        "production_ui_browser_smoke": {"status": "pass"},
    }
    evidence_path = tmp_path / "package-evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    output = tmp_path / "matrix.json"
    summary = tmp_path / "summary.txt"
    command = [sys.executable, str(SCRIPT), "--qualification-json", str(qualification_path), "--package", str(package), "--package-evidence-json", str(evidence_path), "--output-json", str(output), "--output-text", str(summary)]
    if durable_restart:
        restart = {
            "schema_version": "mfl_v8_durable_restart_e2e_v2",
            "decision": "PASS",
            "blockers": [],
            "package_sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
            "runtime_sha256": hashlib.sha256(runtime.read_bytes()).hexdigest(),
            "fictional_data_only": True,
            "execution_level": "frozen_runtime_canonical_api",
            "checks": {name: "pass" for name in (
                "first_runtime_instance_bound", "second_runtime_instance_bound", "first_health",
                "first_activation", "draft_created_review_required", "revision_committed",
                "original_preserved", "audit_before_valid", "second_health", "second_activation",
                "same_document_reopened", "same_revision_reopened", "same_content_reopened",
                "review_required_after_restart", "audit_after_valid", "document_list_contains_reopened",
            )},
        }
        if mutate == "empty_restart_checks":
            restart["checks"] = {}
        elif mutate == "legacy_restart":
            restart["schema_version"] = "mfl_v8_durable_restart_e2e_v1"
        elif mutate == "restart_missing_provenance":
            restart.pop("fictional_data_only")
        restart_path = tmp_path / "restart.json"
        restart_path.write_text(json.dumps(restart), encoding="utf-8")
        command.extend(["--durable-restart-json", str(restart_path)])
    if ui_navigation:
        navigation = {
            "schema_version": "mfl_v8_isolated_ui_navigation_v1",
            "decision": "ISOLATED_FROZEN_UI_NAVIGATION_VERIFIED",
            "candidate": {"package_sha256": hashlib.sha256(package.read_bytes()).hexdigest()},
            "environment": {"existing_profile_data_used": False},
            "actions": [
                {"action": "Open frozen workbench", "result": "pass"},
                {"action": "Open full workbench", "result": "pass"},
            ],
        }
        navigation_path = tmp_path / "navigation.json"
        navigation_path.write_text(json.dumps(navigation), encoding="utf-8")
        command.extend(["--ui-navigation-json", str(navigation_path)])
    return subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_core_e2e_matrix_is_hash_bound_and_marks_out_of_scope_journeys(tmp_path: Path) -> None:
    result = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    matrix = json.loads(Path(output["matrix"]).read_text(encoding="utf-8"))
    assert matrix["decision"] == "CORE_API_VERIFIED_WITH_LIMITATIONS"
    assert matrix["journey_summary"] == {"not_evaluated": 5, "total": 14, "verified": 9}
    assert matrix["candidate"]["package_sha256"]
    assert all(row["review_required"] for row in matrix["journeys"])
    assert {row["journey_id"] for row in matrix["journeys"] if not row["pass"]} == {"core-10", "core-11", "scope-01", "scope-02", "scope-03"}
    assert matrix["candidate"]["installed_msix"] is False


def test_core_e2e_matrix_refuses_failed_qualification(tmp_path: Path) -> None:
    result = _run(tmp_path, mutate="failed_check")
    assert result.returncode == 2
    assert "qualification check is not passed: ocr_status" in result.stderr


def test_core_e2e_matrix_promotes_hash_bound_durable_restart_evidence(tmp_path: Path) -> None:
    result = _run(tmp_path, durable_restart=True)
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    matrix = json.loads(Path(output["matrix"]).read_text(encoding="utf-8"))
    assert matrix["journey_summary"] == {"not_evaluated": 4, "total": 14, "verified": 10}
    restart = next(row for row in matrix["journeys"] if row["journey_id"] == "scope-03")
    assert restart["status"] == "verified"
    assert len(matrix["artifact_hashes"]) == 4


def test_core_e2e_matrix_promotes_isolated_hash_bound_navigation_evidence(tmp_path: Path) -> None:
    result = _run(tmp_path, durable_restart=True, ui_navigation=True)
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    matrix = json.loads(Path(output["matrix"]).read_text(encoding="utf-8"))
    assert matrix["journey_summary"] == {"not_evaluated": 3, "total": 14, "verified": 11}
    navigation = next(row for row in matrix["journeys"] if row["journey_id"] == "core-11")
    assert navigation["status"] == "verified"
    assert "specialized feature controls" in navigation["limitation"]
    assert len(matrix["artifact_hashes"]) == 5


@pytest.mark.parametrize("mutate", ["legacy_driver", "missing_action", "missing_hash",
                                  "wrong_instance", "changed_runtime", "wrong_package_bytes",
                                  "unobserved_network"])
def test_core_evidence_rejects_unproven_or_mismatched_runtime(tmp_path, mutate):
    result = _run(tmp_path, mutate=mutate)
    assert result.returncode == 2
    assert "Evidence assembly blocked:" in result.stderr
    assert not (tmp_path / "matrix.json").exists()


@pytest.mark.parametrize("mutate", ["empty_restart_checks", "legacy_restart", "restart_missing_provenance"])
def test_core_evidence_rejects_incomplete_restart_proof(tmp_path, mutate):
    result = _run(tmp_path, durable_restart=True, mutate=mutate)
    assert result.returncode == 2
    assert "Evidence assembly blocked:" in result.stderr
    assert not (tmp_path / "matrix.json").exists()
