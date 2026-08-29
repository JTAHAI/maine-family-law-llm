from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.contracts.endpoint_inventory import EndpointInventory
from app.api.main import app as api_app
from app.web.ui_contracts import UICompletionAuditor
from app.web.ui_inventory import UIViewInventory
from legal.ops import ReleaseControlCenterService
from legal.ops.release_pilot_hardening import AttorneySandboxStore, PrivacySafeObservabilityStore
from maine_family_law_llm import api as api_module


ROOT = Path(__file__).resolve().parents[1]
TRAINING = [
    "data_boundaries",
    "source_grounding",
    "citation_quote_verification",
    "review_required_exports",
    "feedback_and_error_reporting",
]


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _passing_release_evidence(root: Path) -> None:
    _write(root / "sbom.cyclonedx.json", {"bomFormat": "CycloneDX", "components": [{"name": "mfl"}]})
    _write(root / "sbom.spdx.json", {"spdxVersion": "SPDX-2.3", "packages": [{"name": "mfl"}]})
    _write(root / "grype.json", {"matches": []})
    _write(root / "pip-audit.json", [{"name": "pypdf", "version": "6.14.2", "vulns": []}])
    _write(root / "semgrep.json", {"results": [], "errors": []})
    package = root / "MaineFamilyLawLLM_6.0.4.0_x64.msix"
    signature = root / "signature-verification.txt"
    smoke = root / "install-launch-uninstall-smoke.json"
    wack = root / "wack-result.json"
    package.write_bytes(b"signed-msix-fixture")
    signature.write_text("signature verified fixture", encoding="utf-8")
    _write(smoke, {"status": "pass"})
    _write(wack, {"status": "pass"})
    import hashlib

    _write(
        root / "msix-qualification.json",
        {
            "package_filename": package.name,
            "package_sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
            "signature_report_filename": signature.name,
            "signature_report_sha256": hashlib.sha256(signature.read_bytes()).hexdigest(),
            "install_smoke_filename": smoke.name,
            "install_smoke_sha256": hashlib.sha256(smoke.read_bytes()).hexdigest(),
            "wack_report_filename": wack.name,
            "wack_report_sha256": hashlib.sha256(wack.read_bytes()).hexdigest(),
            "package_version": "6.0.4.0",
            "architecture": "x64",
            "signed": True,
            "signature_verified": True,
            "install_passed": True,
            "launch_passed": True,
            "api_health_passed": True,
            "ui_load_passed": True,
            "uninstall_passed": True,
            "reinstall_passed": True,
            "wack_status": "pass",
        },
    )
    _write(
        root / "backup-restore.json",
        {
            "status": "pass",
            "backup_verified": True,
            "restore_rehearsal_verified": True,
            "backup_sha256": "b" * 64,
            "file_count": 2,
        },
    )


def _seed_observability(case_root: Path) -> None:
    store = PrivacySafeObservabilityStore(case_root)
    store.configure(mode="local_metrics", approved=True)
    store.record("api_request", metrics={"count": 1}, labels={"component": "api", "operation": "release_control", "status": "pass"})
    store.record("self_test", metrics={"count": 1}, labels={"status": "pass"})
    assert store.verify()["status"] == "pass"


def _seed_pilot(pilot_root: Path) -> None:
    store = AttorneySandboxStore(ROOT, pilot_root)
    store.register_participant(
        participant_id="reviewer-1",
        role="attorney_reviewer",
        bar_status_verified=True,
        verification_reference_sha256="c" * 64,
        terms_accepted=True,
        training_modules=TRAINING,
    )
    store.start_session(participant_id="reviewer-1", data_classification="public_authority", approved=True)
    assert store.dashboard()["status"] == "operational"


def test_release_control_center_service_reports_truthful_mixed_readiness(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    case_root.mkdir()
    (case_root / "order.pdf").write_text("order", encoding="utf-8")
    backup_root = tmp_path / "backup"
    release_evidence_root = tmp_path / "release-evidence"
    pilot_root = tmp_path / "pilot"
    _seed_observability(case_root)
    _seed_pilot(pilot_root)
    _passing_release_evidence(release_evidence_root)
    monkeypatch.setenv("MAINE_FAMILY_LAW_BACKUP_ROOT", str(backup_root))
    monkeypatch.setenv("MAINE_FAMILY_LAW_RELEASE_EVIDENCE_ROOT", str(release_evidence_root))
    monkeypatch.setenv("MAINE_FAMILY_LAW_PILOT_ROOT", str(pilot_root))
    monkeypatch.setattr(api_module, "active_case_root", lambda: case_root)

    service = ReleaseControlCenterService(ROOT, case_root=case_root)
    report = service.status()

    assert report["status"] == "blocked"
    assert report["sections"]["release_manifest"]["status"] == "pass"
    assert report["sections"]["supply_chain"]["status"] == "pass"
    assert report["sections"]["release_evidence"]["status"] == "pass"
    assert report["sections"]["observability"]["status"] == "pass"
    assert report["sections"]["backup_restore"]["status"] == "pass"
    assert report["sections"]["reliability"]["status"] == "blocked"
    assert report["sections"]["accessibility"]["status"] == "pass"
    assert report["sections"]["red_team"]["status"] == "pass"
    assert report["sections"]["pilot"]["status"] == "pass"
    assert report["sections"]["release_pilot_hardening"]["status"] == "pass"
    assert report["sections"]["msix_audit"]["status"] == "pass"
    assert report["sections"]["vulnerability_evidence"]["status"] == "pass"
    assert report["sections"]["release_candidate"]["status"] == "blocked"
    assert report["sections"]["shipment_readiness"]["status"] == "blocked"
    assert report["eligibility_basis"]["release_candidate_pass"] is False
    assert report["eligibility_basis"]["shipment_ready"] is False
    assert "release_control_center_gate_incomplete" in report["blockers"]


def test_release_control_center_route_and_ui_contracts_are_registered(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    case_root.mkdir()
    (case_root / "order.pdf").write_text("order", encoding="utf-8")
    backup_root = tmp_path / "backup"
    release_evidence_root = tmp_path / "release-evidence"
    pilot_root = tmp_path / "pilot"
    _seed_observability(case_root)
    _seed_pilot(pilot_root)
    _passing_release_evidence(release_evidence_root)
    monkeypatch.setenv("MAINE_FAMILY_LAW_BACKUP_ROOT", str(backup_root))
    monkeypatch.setenv("MAINE_FAMILY_LAW_RELEASE_EVIDENCE_ROOT", str(release_evidence_root))
    monkeypatch.setenv("MAINE_FAMILY_LAW_PILOT_ROOT", str(pilot_root))
    monkeypatch.setenv("MFL_PROJECT_ROOT", str(ROOT))
    monkeypatch.setattr(api_module, "active_case_root", lambda: case_root)

    client = TestClient(api_module.app)
    response = client.get("/api/release-control-center/status", headers={"X-User-Role": "admin", "X-Tenant-Id": "tenant-603"})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["review_required"] is True
    assert payload["sections"]["release_evidence"]["status"] == "pass"
    assert payload["sections"]["accessibility"]["status"] == "pass"
    assert payload["sections"]["red_team"]["status"] == "pass"

    views = UIViewInventory("app/web/pages").validate()
    assert views["status"] == "pass"
    assert "release-control-center.tsx" in {view["file"] for view in views["views"]}

    ui = UICompletionAuditor("app/web/pages").audit().as_dict()
    assert ui["status"] == "pass"


def test_release_control_center_endpoint_inventory_includes_status_route() -> None:
    registered = set()
    for route in api_app.routes:
        methods = getattr(route, "methods", set()) or set()
        path = getattr(route, "path", "")
        for method in methods:
            if method in {"GET", "POST"} and path.startswith("/api"):
                registered.add((method, path))

    inventory = EndpointInventory().compare_to_registered(registered)
    assert inventory["status"] == "pass", inventory
    required = EndpointInventory().as_dict()["endpoints"]
    assert any(item["path"] == "/api/release-control-center/status" for item in required)
