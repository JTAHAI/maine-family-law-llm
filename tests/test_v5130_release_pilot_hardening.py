from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from legal.ops.release_pilot_hardening import (
    AttorneySandboxStore,
    MatterBackupRestoreDrill,
    PrivacySafeObservabilityStore,
    ReleaseEvidenceAuditor,
    ReleasePilotHardeningError,
)
from maine_family_law_llm import api as api_module


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


def test_release_evidence_audit_passes_complete_external_evidence_but_not_legal_ga(tmp_path: Path):
    evidence = tmp_path / "release-evidence"
    _passing_release_evidence(evidence)
    report = ReleaseEvidenceAuditor(Path.cwd(), evidence).audit()
    assert report["status"] == "pass"
    assert report["store_package_qualified"] is True
    assert report["legal_ga_ready"] is False
    assert "limited_real_matter_pilot_evidence_required" in report["legal_ga_blockers"]


def test_release_evidence_missing_unsigned_wack_and_vulnerabilities_fail_closed(tmp_path: Path):
    evidence = tmp_path / "release-evidence"
    _passing_release_evidence(evidence)
    _write(evidence / "grype.json", {"matches": [{"vulnerability": {"severity": "Critical"}}]})
    msix = json.loads((evidence / "msix-qualification.json").read_text())
    msix.update({"signed": False, "signature_verified": False, "wack_status": "not_run"})
    _write(evidence / "msix-qualification.json", msix)
    report = ReleaseEvidenceAuditor(Path.cwd(), evidence).audit()
    assert report["status"] == "blocked"
    assert "grype_critical_findings" in report["blockers"]
    assert "msix_signed_required" in report["blockers"]
    assert "wack_pass_required" in report["blockers"]


def test_msix_qualification_is_bound_to_actual_external_files(tmp_path: Path):
    evidence = tmp_path / "release-evidence"
    _passing_release_evidence(evidence)
    package = evidence / "MaineFamilyLawLLM_6.0.4.0_x64.msix"
    package.write_bytes(b"tampered-package")
    report = ReleaseEvidenceAuditor(Path.cwd(), evidence).audit()
    assert report["status"] == "blocked"
    assert "msix_package_hash_mismatch" in report["blockers"]


def test_release_evidence_root_inside_repo_is_refused():
    with pytest.raises(ReleasePilotHardeningError, match="external_root_inside_source_repo"):
        ReleaseEvidenceAuditor(Path.cwd(), Path.cwd() / "dist" / "evidence")


def test_privacy_safe_observability_is_hash_chained_and_refuses_paths_and_private_labels(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    store = PrivacySafeObservabilityStore(case)
    store.configure(mode="local_metrics", approved=True)
    first = store.record("retrieval", metrics={"duration_ms": 12, "result_count": 4}, labels={"component": "hybrid_retrieval", "status": "pass"})
    second = store.record("verifier", metrics={"duration_ms": 3}, labels={"component": "citation_verifier", "status": "pass"})
    assert second["previous_sha256"] == first["record_sha256"]
    assert store.verify()["status"] == "pass"
    with pytest.raises(ReleasePilotHardeningError, match="private_or_path"):
        store.record("error", labels={"error_class": r"C:\private\matter.pdf"})
    with pytest.raises(ReleasePilotHardeningError, match="private_or_path"):
        store.record("error", labels={"error_class": "client@example.com"})


def test_observability_concurrent_writes_preserve_one_chain(tmp_path: Path):
    from concurrent.futures import ThreadPoolExecutor

    case = tmp_path / "case"
    case.mkdir()
    store = PrivacySafeObservabilityStore(case)
    store.configure(mode="local_metrics", approved=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda value: store.record("api_request", metrics={"count": 1}, labels={"component": "api", "operation": f"op{value}", "status": "pass"}), range(32)))
    verification = store.verify()
    assert verification["status"] == "pass"
    assert verification["row_count"] == 33  # explicit opt-in receipt plus 32 metrics
    assert verification["opentelemetry"]["remote_exporters_enabled"] is False
    assert verification["opentelemetry"]["private_attributes_allowed"] is False


def test_observability_tampering_is_detected(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    store = PrivacySafeObservabilityStore(case)
    store.configure(mode="local_metrics", approved=True)
    store.record("self_test", metrics={"count": 1}, labels={"status": "pass"})
    text = store.path.read_text(encoding="utf-8").replace('"count":1', '"count":2')
    store.path.write_text(text, encoding="utf-8")
    assert store.verify()["status"] == "blocked"
    assert any("hash_mismatch" in item for item in store.verify()["blockers"])


def test_backup_restore_drill_is_external_deterministic_and_non_destructive(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    (case / "order.pdf").write_bytes(b"immutable-order")
    (case / "notes.txt").write_text("review notes", encoding="utf-8")
    backup_root = tmp_path / "backups"
    drill = MatterBackupRestoreDrill(case, repo_root=Path.cwd(), backup_root=backup_root)
    first = drill.run(approved=True)
    second = drill.run(approved=True)
    assert first["status"] == "pass"
    assert first["backup_sha256"] == second["backup_sha256"]
    assert first["backup_verified"] is True
    assert first["restore_rehearsal_verified"] is True
    assert first["original_matter_modified"] is False
    assert (case / "order.pdf").read_bytes() == b"immutable-order"


def test_backup_restore_refuses_unapproved_symlink_and_tampered_archive(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    (case / "source.txt").write_text("source", encoding="utf-8")
    drill = MatterBackupRestoreDrill(case, repo_root=Path.cwd(), backup_root=tmp_path / "backups")
    with pytest.raises(ReleasePilotHardeningError, match="approval_required"):
        drill.run(approved=False)
    if hasattr(os, "symlink"):
        try:
            os.symlink(case / "source.txt", case / "linked.txt")
        except OSError:
            pass
        else:
            with pytest.raises(ReleasePilotHardeningError, match="symlink_refused"):
                drill.run(approved=True)
            (case / "linked.txt").unlink()
    result = drill.run(approved=True)
    archive = next((tmp_path / "backups").rglob("*.zip"))
    with zipfile.ZipFile(archive, "a") as output:
        output.writestr("matter/unexpected.txt", b"tampered")
    verification = drill.verify_archive(archive)
    assert verification["status"] == "blocked"
    assert verification["blockers"]
    assert result["status"] == "pass"


def test_backup_root_inside_or_containing_active_matter_is_refused(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    with pytest.raises(ReleasePilotHardeningError, match="forbidden_root"):
        MatterBackupRestoreDrill(case, repo_root=Path.cwd(), backup_root=case / "backup")
    with pytest.raises(ReleasePilotHardeningError, match="contains_forbidden_root"):
        MatterBackupRestoreDrill(case, repo_root=Path.cwd(), backup_root=tmp_path)


def test_attorney_sandbox_requires_evidence_terms_training_and_public_or_synthetic_data(tmp_path: Path):
    pilot = AttorneySandboxStore(Path.cwd(), tmp_path / "pilot")
    incomplete = pilot.register_participant(
        participant_id="reviewer-1",
        role="attorney_reviewer",
        bar_status_verified=False,
        verification_reference_sha256="",
        terms_accepted=False,
        training_modules=[],
    )
    assert incomplete["sandbox_eligible"] is False
    with pytest.raises(ReleasePilotHardeningError, match="not_eligible"):
        pilot.start_session(participant_id="reviewer-1", data_classification="synthetic", approved=True)
    with pytest.raises(ReleasePilotHardeningError, match="verification_reference_required"):
        pilot.register_participant(
            participant_id="reviewer-1",
            role="attorney_reviewer",
            bar_status_verified=True,
            verification_reference_sha256="",
            terms_accepted=True,
            training_modules=TRAINING,
        )
    eligible = pilot.register_participant(
        participant_id="reviewer-1",
        role="attorney_reviewer",
        bar_status_verified=True,
        verification_reference_sha256="c" * 64,
        terms_accepted=True,
        training_modules=TRAINING,
    )
    assert eligible["sandbox_eligible"] is True
    session = pilot.start_session(participant_id="reviewer-1", data_classification="public_authority", approved=True)
    assert session["real_matter_allowed"] is False
    with pytest.raises(ReleasePilotHardeningError, match="private_or_unsupported"):
        pilot.start_session(participant_id="reviewer-1", data_classification="private_matter", approved=True)


def test_attorney_sandbox_feedback_is_review_required_not_gold_and_refuses_private_identifiers(tmp_path: Path):
    pilot = AttorneySandboxStore(Path.cwd(), tmp_path / "pilot")
    pilot.register_participant(
        participant_id="reviewer-2",
        role="attorney_reviewer",
        bar_status_verified=True,
        verification_reference_sha256="d" * 64,
        terms_accepted=True,
        training_modules=TRAINING,
    )
    session = pilot.start_session(participant_id="reviewer-2", data_classification="synthetic", approved=True)
    with pytest.raises(ReleasePilotHardeningError, match="private_data_refused"):
        pilot.add_feedback(
            participant_id="reviewer-2",
            session_id=session["session_id"],
            category="privacy",
            severity="high",
            description="Contact client@example.com about C:\\matter\\file.pdf",
        )
    feedback = pilot.add_feedback(
        participant_id="reviewer-2",
        session_id=session["session_id"],
        category="citation",
        severity="high",
        description="The source card did not expose the expected pinpoint span.",
    )
    assert feedback["may_be_counted_as_gold"] is False
    dashboard = pilot.dashboard()
    assert dashboard["status"] == "operational"
    assert dashboard["may_be_counted_as_ga_attorney_pilot_evidence"] is False
    assert feedback["feedback_id"] in dashboard["open_release_blockers"]


def test_attorney_sandbox_ledger_tampering_is_detected(tmp_path: Path):
    pilot = AttorneySandboxStore(Path.cwd(), tmp_path / "pilot")
    pilot.register_participant(
        participant_id="reviewer-3",
        role="attorney_reviewer",
        bar_status_verified=True,
        verification_reference_sha256="e" * 64,
        terms_accepted=True,
        training_modules=TRAINING,
    )
    assert pilot.verify()["status"] == "pass"
    assert pilot.ledger_path is not None
    text = pilot.ledger_path.read_text(encoding="utf-8").replace('"sandbox_eligible":true', '"sandbox_eligible":false')
    pilot.ledger_path.write_text(text, encoding="utf-8")
    assert pilot.verify()["status"] == "blocked"


def test_v513_api_and_ui_contract(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    (case / "source.txt").write_text("public synthetic test", encoding="utf-8")
    evidence = tmp_path / "release-evidence"
    backup = tmp_path / "backup-root"
    pilot = tmp_path / "pilot-root"
    _passing_release_evidence(evidence)
    monkeypatch.setenv("MAINE_FAMILY_LAW_RELEASE_EVIDENCE_ROOT", str(evidence))
    monkeypatch.setenv("MAINE_FAMILY_LAW_BACKUP_ROOT", str(backup))
    monkeypatch.setenv("MAINE_FAMILY_LAW_PILOT_ROOT", str(pilot))
    monkeypatch.setattr(api_module, "active_case_root", lambda: case)
    client = TestClient(api_module.app)

    status = client.get("/api/release-pilot-hardening/status")
    assert status.status_code == 200
    assert status.json()["supply_chain_and_msix"]["status"] == "pass"
    assert status.json()["legal_ga_ready"] is False

    metrics = client.post("/api/release-pilot-hardening/observability/self-test", json={"approved": True})
    assert metrics.status_code == 200
    assert metrics.json()["verification"]["status"] == "pass"

    drill = client.post("/api/release-pilot-hardening/backup-restore/drill", json={"approved": True})
    assert drill.status_code == 200
    assert drill.json()["status"] == "pass"

    participant = client.post(
        "/api/release-pilot-hardening/pilot/participants",
        json={
            "participant_id": "reviewer-api",
            "role": "attorney_reviewer",
            "bar_status_verified": True,
            "verification_reference_sha256": "f" * 64,
            "terms_accepted": True,
            "training_modules": TRAINING,
        },
    )
    assert participant.status_code == 200
    session = client.post(
        "/api/release-pilot-hardening/pilot/sessions",
        json={"participant_id": "reviewer-api", "data_classification": "synthetic", "approved": True},
    )
    assert session.status_code == 200
    feedback = client.post(
        "/api/release-pilot-hardening/pilot/feedback",
        json={
            "participant_id": "reviewer-api",
            "session_id": session.json()["session_id"],
            "category": "workflow",
            "severity": "medium",
            "description": "The reviewer queue needs a clearer blocked-state label.",
        },
    )
    assert feedback.status_code == 200
    dashboard = client.get("/api/release-pilot-hardening/pilot/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["session_count"] == 1

    html = Path("maine_family_law_llm/ui/workbench.html").read_text(encoding="utf-8")
    js = Path("maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    css = Path("maine_family_law_llm/ui/workbench.css").read_text(encoding="utf-8")
    assert 'id="record-inspector-release-pilot-hardening"' in html
    assert 'id="release-pilot-hardening-modal"' in html
    assert "/api/release-pilot-hardening/status" in js
    assert "registerReleasePilotParticipant" in js
    assert ".release-pilot-hardening-modal" in css


def test_v513_scripts_config_and_semgrep_policy_exist():
    assert Path("configs/maine_release_pilot_hardening_policy.json").is_file()
    assert Path(".semgrep/maine-family-law-llm.yml").is_file()
    assert Path("scripts/build-v513-release-evidence.ps1").is_file()
    assert Path("scripts/run-v513-release-hardening-audit.py").is_file()
    assert Path("scripts/run-v513-backup-restore-drill.py").is_file()
