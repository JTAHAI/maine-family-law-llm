from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import maine_family_law_llm.api as api_module
from legal.ops.release_pilot_hardening import AttorneySandboxStore
from legal.pilot.real_matter_operations import (
    LimitedRealMatterPilotError,
    LimitedRealMatterPilotOperationsStore,
)

TRAINING = [
    "data_boundaries",
    "source_grounding",
    "citation_quote_verification",
    "review_required_exports",
    "feedback_and_error_reporting",
]
REQUIRED = {
    "issue_tree": "1" * 64,
    "posture_summary": "2" * 64,
    "timeline": "3" * 64,
    "evidence_map": "4" * 64,
    "authority_matrix": "5" * 64,
    "red_flag_report": "6" * 64,
}


def _policy(path: Path) -> Path:
    path.write_text(json.dumps({
        "version": "test-v5.17",
        "minimum_matter_count": 1,
        "minimum_daily_reviews_per_matter": 1,
    }), encoding="utf-8")
    return path


def _eligible(repo: Path, pilot: Path, participant: str = "reviewer-1") -> None:
    AttorneySandboxStore(repo, pilot).register_participant(
        participant_id=participant,
        role="attorney_reviewer",
        bar_status_verified=True,
        verification_reference_sha256="a" * 64,
        terms_accepted=True,
        training_modules=TRAINING,
    )


def _program_and_matter(store: LimitedRealMatterPilotOperationsStore) -> None:
    store.create_program(
        program_id="pass49-2026",
        allowed_tenant_ids=["tenant-1"],
        pass48_evidence_sha256="b" * 64,
        approved=True,
    )
    store.enroll_matter(
        matter_id="matter-1",
        tenant_id="tenant-1",
        participant_id="reviewer-1",
        consent_version="consent-v1",
        client_consent_evidence_sha256="c" * 64,
        privacy_notice_sha256="d" * 64,
        matter_store_sha256="e" * 64,
        tenant_isolation_evidence_sha256="f" * 64,
        encryption_evidence_sha256="0" * 64,
        retention_policy_version="pilot-retention-v1",
        explicit_real_matter_consent=True,
        training_use_allowed=False,
        export_restriction_acknowledged=True,
        human_review_required=True,
        approved=True,
    )


def _complete_matter(store: LimitedRealMatterPilotOperationsStore) -> None:
    _program_and_matter(store)
    store.record_work_product(matter_id="matter-1", artifact_hashes=REQUIRED, approved=True)
    store.record_daily_review(
        matter_id="matter-1",
        participant_id="reviewer-1",
        review_date="2026-07-28",
        usefulness="useful",
        human_review_completed=True,
        source_verification_completed=True,
        export_gate_checked=True,
        blocker_codes=[],
        review_evidence_sha256="7" * 64,
        approved=True,
    )
    store.record_export_attempt(
        matter_id="matter-1",
        export_type="draft_review_copy",
        gate_status="approved_review_required",
        filing_ready_claimed=False,
        export_artifact_sha256="8" * 64,
        authorization_evidence_sha256="9" * 64,
        approved=True,
    )
    store.record_signoff(
        matter_id="matter-1",
        participant_id="reviewer-1",
        usefulness="useful",
        attorney_signoff_complete=True,
        blocker_codes=[],
        signoff_evidence_sha256="a" * 64,
        approved=True,
    )


def test_v517_complete_software_workflow_is_only_ready_for_external_gate(tmp_path: Path):
    repo = Path.cwd()
    pilot = tmp_path / "pilot"
    _eligible(repo, pilot)
    store = LimitedRealMatterPilotOperationsStore(repo, pilot, policy_path=_policy(tmp_path / "policy.json"))
    _complete_matter(store)

    status = store.status()
    assert status["status"] == "ready_for_external_pass49_gate"
    assert status["matter_count"] == 1
    assert status["data_leakage_count"] == 0
    assert status["unsupported_export_attempt_count"] == 0
    assert status["pass49_complete"] is False
    assert status["external_launch_evidence_gate_required"] is True
    assert status["application_independently_verifies_consent_or_legal_signoff"] is False
    assert store.verify()["status"] == "pass"


def test_v517_enrollment_requires_allowlist_consent_and_no_training_use(tmp_path: Path):
    repo = Path.cwd()
    pilot = tmp_path / "pilot"
    _eligible(repo, pilot)
    store = LimitedRealMatterPilotOperationsStore(repo, pilot, policy_path=_policy(tmp_path / "policy.json"))
    store.create_program(
        program_id="pass49",
        allowed_tenant_ids=["tenant-1"],
        pass48_evidence_sha256="b" * 64,
        approved=True,
    )
    common = dict(
        matter_id="matter-1",
        participant_id="reviewer-1",
        consent_version="consent-v1",
        client_consent_evidence_sha256="c" * 64,
        privacy_notice_sha256="d" * 64,
        matter_store_sha256="e" * 64,
        tenant_isolation_evidence_sha256="f" * 64,
        encryption_evidence_sha256="0" * 64,
        retention_policy_version="retention-v1",
        explicit_real_matter_consent=True,
        export_restriction_acknowledged=True,
        human_review_required=True,
        approved=True,
    )
    with pytest.raises(LimitedRealMatterPilotError, match="tenant_not_allowed"):
        store.enroll_matter(tenant_id="tenant-2", training_use_allowed=False, **common)
    with pytest.raises(LimitedRealMatterPilotError, match="training_use_refused"):
        store.enroll_matter(tenant_id="tenant-1", training_use_allowed=True, **common)
    common["explicit_real_matter_consent"] = False
    with pytest.raises(LimitedRealMatterPilotError, match="explicit_consent_required"):
        store.enroll_matter(tenant_id="tenant-1", training_use_allowed=False, **common)


def test_v517_missing_work_product_and_review_stay_blocked(tmp_path: Path):
    repo = Path.cwd()
    pilot = tmp_path / "pilot"
    _eligible(repo, pilot)
    store = LimitedRealMatterPilotOperationsStore(repo, pilot, policy_path=_policy(tmp_path / "policy.json"))
    _program_and_matter(store)
    store.record_work_product(matter_id="matter-1", artifact_hashes={"timeline": "3" * 64}, approved=True)
    status = store.status()
    assert status["status"] == "blocked"
    assert any("required_work_product_incomplete" in item for item in status["blockers"])
    assert any("minimum_daily_reviews_not_met" in item for item in status["blockers"])
    assert any("attorney_signoff_missing" in item for item in status["blockers"])


def test_v517_unsupported_filing_ready_attempt_is_permanent_blocker(tmp_path: Path):
    repo = Path.cwd()
    pilot = tmp_path / "pilot"
    _eligible(repo, pilot)
    store = LimitedRealMatterPilotOperationsStore(repo, pilot, policy_path=_policy(tmp_path / "policy.json"))
    _complete_matter(store)
    event = store.record_export_attempt(
        matter_id="matter-1",
        export_type="reviewed_filing_packet",
        gate_status="blocked",
        filing_ready_claimed=True,
        export_artifact_sha256="f" * 64,
        authorization_evidence_sha256="",
        approved=True,
    )
    assert event["unsupported_filing_ready_export_attempt"] is True
    status = store.status()
    assert status["unsupported_export_attempt_count"] == 1
    assert status["status"] == "blocked"


def test_v517_data_leakage_incident_blocks_even_after_retest(tmp_path: Path):
    repo = Path.cwd()
    pilot = tmp_path / "pilot"
    _eligible(repo, pilot)
    store = LimitedRealMatterPilotOperationsStore(repo, pilot, policy_path=_policy(tmp_path / "policy.json"))
    _complete_matter(store)
    opened = store.open_incident(
        matter_id="matter-1",
        category="data_leakage",
        severity="critical",
        summary_code="synthetic-leak-test",
        incident_evidence_sha256="1" * 64,
        approved=True,
    )
    store.update_incident(
        incident_id=opened["incident_id"], status="contained",
        remediation_evidence_sha256="2" * 64, retest_evidence_sha256="", approved=True,
    )
    store.update_incident(
        incident_id=opened["incident_id"], status="fixed_pending_retest",
        remediation_evidence_sha256="3" * 64, retest_evidence_sha256="", approved=True,
    )
    store.update_incident(
        incident_id=opened["incident_id"], status="closed",
        remediation_evidence_sha256="4" * 64, retest_evidence_sha256="5" * 64, approved=True,
    )
    status = store.status()
    assert status["open_incident_count"] == 0
    assert status["data_leakage_count"] == 1
    assert status["status"] == "blocked"
    assert any("prohibited_incident_recorded" in item for item in status["blockers"])


def test_v517_evidence_packet_is_immutable_and_tamper_detected(tmp_path: Path):
    repo = Path.cwd()
    pilot = tmp_path / "pilot"
    _eligible(repo, pilot)
    store = LimitedRealMatterPilotOperationsStore(repo, pilot, policy_path=_policy(tmp_path / "policy.json"))
    _complete_matter(store)
    first = store.build_evidence_packet(approved=True)
    second = store.build_evidence_packet(approved=True)
    assert first["generation_id"] == second["generation_id"]
    assert store.verify_generation(first["generation_id"])["status"] == "pass"
    packet, media = store.resolve_artifact(first["generation_id"], "limited-real-matter-pilot.json")
    assert media == "application/json"
    payload = json.loads(packet.read_text(encoding="utf-8"))
    assert payload["private_matter_content_included"] is False
    assert payload["identifying_party_names_included"] is False
    packet.write_text("{}", encoding="utf-8")
    with pytest.raises(LimitedRealMatterPilotError, match="generation_verification_failed"):
        store.verify_generation(first["generation_id"])
    with pytest.raises(LimitedRealMatterPilotError, match="generation_collision"):
        store.build_evidence_packet(approved=True)


def test_v517_program_configuration_is_immutable_and_review_date_is_real(tmp_path: Path):
    repo = Path.cwd()
    pilot = tmp_path / "pilot"
    _eligible(repo, pilot)
    store = LimitedRealMatterPilotOperationsStore(repo, pilot, policy_path=_policy(tmp_path / "policy.json"))
    store.create_program(
        program_id="pass49",
        allowed_tenant_ids=["tenant-1"],
        pass48_evidence_sha256="b" * 64,
        approved=True,
    )
    with pytest.raises(LimitedRealMatterPilotError, match="configuration_immutable"):
        store.create_program(
            program_id="pass49",
            allowed_tenant_ids=["tenant-2"],
            pass48_evidence_sha256="b" * 64,
            approved=True,
        )
    _program = store._latest_program()
    assert _program and _program["allowed_tenant_ids"] == ["tenant-1"]
    store.enroll_matter(
        matter_id="matter-1", tenant_id="tenant-1", participant_id="reviewer-1",
        consent_version="consent-v1", client_consent_evidence_sha256="c" * 64,
        privacy_notice_sha256="d" * 64, matter_store_sha256="e" * 64,
        tenant_isolation_evidence_sha256="f" * 64, encryption_evidence_sha256="0" * 64,
        retention_policy_version="retention-v1", explicit_real_matter_consent=True,
        training_use_allowed=False, export_restriction_acknowledged=True,
        human_review_required=True, approved=True,
    )
    with pytest.raises(LimitedRealMatterPilotError, match="review_date_invalid"):
        store.record_daily_review(
            matter_id="matter-1", participant_id="reviewer-1", review_date="2026-99-99",
            usefulness="useful", human_review_completed=True, source_verification_completed=True,
            export_gate_checked=True, blocker_codes=[], review_evidence_sha256="1" * 64, approved=True,
        )


def test_v517_non_attorney_role_cannot_enter_real_matter_pilot(tmp_path: Path):
    repo = Path.cwd()
    pilot = tmp_path / "pilot"
    AttorneySandboxStore(repo, pilot).register_participant(
        participant_id="reviewer-1", role="product_reviewer", bar_status_verified=True,
        verification_reference_sha256="a" * 64, terms_accepted=True, training_modules=TRAINING,
    )
    store = LimitedRealMatterPilotOperationsStore(repo, pilot, policy_path=_policy(tmp_path / "policy.json"))
    store.create_program(
        program_id="pass49", allowed_tenant_ids=["tenant-1"],
        pass48_evidence_sha256="b" * 64, approved=True,
    )
    with pytest.raises(LimitedRealMatterPilotError, match="role_not_eligible"):
        store.enroll_matter(
            matter_id="matter-1", tenant_id="tenant-1", participant_id="reviewer-1",
            consent_version="consent-v1", client_consent_evidence_sha256="c" * 64,
            privacy_notice_sha256="d" * 64, matter_store_sha256="e" * 64,
            tenant_isolation_evidence_sha256="f" * 64, encryption_evidence_sha256="0" * 64,
            retention_policy_version="retention-v1", explicit_real_matter_consent=True,
            training_use_allowed=False, export_restriction_acknowledged=True,
            human_review_required=True, approved=True,
        )


def test_v517_api_ui_and_openapi_contract(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    pilot = tmp_path / "pilot"
    monkeypatch.setenv("MAINE_FAMILY_LAW_PILOT_ROOT", str(pilot))
    client = TestClient(api_module.app)
    participant = client.post("/api/release-pilot-hardening/pilot/participants", json={
        "participant_id": "reviewer-1",
        "role": "attorney_reviewer",
        "bar_status_verified": True,
        "verification_reference_sha256": "a" * 64,
        "terms_accepted": True,
        "training_modules": TRAINING,
    })
    assert participant.status_code == 200
    program = client.post("/api/limited-real-matter-pilot/programs", json={
        "program_id": "pass49-api",
        "allowed_tenant_ids": ["tenant-1"],
        "pass48_evidence_sha256": "b" * 64,
        "approved": True,
    })
    assert program.status_code == 200
    matter = client.post("/api/limited-real-matter-pilot/matters", json={
        "matter_id": "matter-1",
        "tenant_id": "tenant-1",
        "participant_id": "reviewer-1",
        "consent_version": "consent-v1",
        "client_consent_evidence_sha256": "c" * 64,
        "privacy_notice_sha256": "d" * 64,
        "matter_store_sha256": "e" * 64,
        "tenant_isolation_evidence_sha256": "f" * 64,
        "encryption_evidence_sha256": "0" * 64,
        "retention_policy_version": "retention-v1",
        "explicit_real_matter_consent": True,
        "training_use_allowed": False,
        "export_restriction_acknowledged": True,
        "human_review_required": True,
        "approved": True,
    })
    assert matter.status_code == 200
    assert client.post("/api/limited-real-matter-pilot/work-products", json={
        "matter_id": "matter-1", "artifact_hashes": REQUIRED, "approved": True,
    }).status_code == 200
    assert client.post("/api/limited-real-matter-pilot/daily-reviews", json={
        "matter_id": "matter-1", "participant_id": "reviewer-1", "review_date": "2026-07-28",
        "usefulness": "useful", "human_review_completed": True,
        "source_verification_completed": True, "export_gate_checked": True,
        "blocker_codes": [], "review_evidence_sha256": "7" * 64, "approved": True,
    }).status_code == 200
    assert client.post("/api/limited-real-matter-pilot/signoffs", json={
        "matter_id": "matter-1", "participant_id": "reviewer-1", "usefulness": "useful",
        "attorney_signoff_complete": True, "blocker_codes": [],
        "signoff_evidence_sha256": "8" * 64, "approved": True,
    }).status_code == 200
    status = client.get("/api/limited-real-matter-pilot/status")
    assert status.status_code == 200
    assert status.json()["status"] == "ready_for_external_pass49_gate"
    built = client.post("/api/limited-real-matter-pilot/evidence/build", json={"approved": True})
    assert built.status_code == 200
    artifact = built.json()["artifacts"][0]
    assert client.get(artifact["download_url"]).status_code == 200

    html = (Path("src/maine_family_law_llm/ui/workbench.html").read_text(encoding="utf-8"))
    js = (Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8"))
    assert 'id="limited-real-matter-pilot-controls"' in html
    assert "/api/limited-real-matter-pilot/status" in js
    paths = client.get("/openapi.json").json()["paths"]
    for route in (
        "/api/limited-real-matter-pilot/status",
        "/api/limited-real-matter-pilot/programs",
        "/api/limited-real-matter-pilot/matters",
        "/api/limited-real-matter-pilot/work-products",
        "/api/limited-real-matter-pilot/daily-reviews",
        "/api/limited-real-matter-pilot/exports",
        "/api/limited-real-matter-pilot/incidents",
        "/api/limited-real-matter-pilot/incidents/update",
        "/api/limited-real-matter-pilot/signoffs",
        "/api/limited-real-matter-pilot/evidence/build",
        "/api/limited-real-matter-pilot/artifacts/{token}",
    ):
        assert route in paths
