from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import maine_family_law_llm.api as api_module

from legal.ops.release_pilot_hardening import AttorneySandboxStore
from legal.pilot.sandbox_operations import (
    AttorneySandboxOperationsError,
    AttorneySandboxOperationsStore,
)

TRAINING = [
    "data_boundaries",
    "source_grounding",
    "citation_quote_verification",
    "review_required_exports",
    "feedback_and_error_reporting",
]


def _policy(path: Path, *, minimum_reviewers: int = 1, minimum_sessions: int = 1, minimum_reviews: int = 1) -> Path:
    payload = {
        "version": "test-v5.16",
        "minimum_eligible_reviewers": minimum_reviewers,
        "minimum_completed_sessions": minimum_sessions,
        "minimum_completed_reviews": minimum_reviews,
        "maximum_review_questions": 8,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _eligible(repo_root: Path, pilot_root: Path, participant_id: str = "reviewer-1") -> None:
    AttorneySandboxStore(repo_root, pilot_root).register_participant(
        participant_id=participant_id,
        role="attorney_reviewer",
        bar_status_verified=True,
        verification_reference_sha256="a" * 64,
        terms_accepted=True,
        training_modules=TRAINING,
    )


def _assignment(store: AttorneySandboxOperationsStore, participant_id: str = "reviewer-1") -> tuple[str, str]:
    program = store.create_program(program_id="pass48-2026", max_questions=3, approved=True)
    question_id = program["questions"][0]["question_id"]
    store.create_cohort(
        program_id="pass48-2026",
        cohort_id="cohort-a",
        participant_ids=[participant_id],
        approved=True,
    )
    assignment = store.create_assignment(
        program_id="pass48-2026",
        cohort_id="cohort-a",
        participant_id=participant_id,
        question_ids=[question_id],
        data_classification="synthetic",
        approved=True,
    )
    return assignment["session_id"], question_id


def _review(store: AttorneySandboxOperationsStore, session_id: str, question_id: str, *, disposition: str = "approved_for_sandbox"):
    return store.submit_review(
        participant_id="reviewer-1",
        session_id=session_id,
        question_id=question_id,
        disposition=disposition,
        source_grounding_rating=5,
        legal_accuracy_rating=4,
        usefulness_rating=4,
        boundary_safety_rating=5,
        citation_quality_rating=4,
        finding_codes=[] if disposition == "approved_for_sandbox" else ["unsupported_claim"],
        response_artifact_sha256="b" * 64,
        verifier_report_sha256="c" * 64,
        comment="Public and synthetic review only.",
        approved=True,
    )


def test_v516_program_cohort_assignment_review_and_completion(tmp_path: Path):
    repo_root = Path.cwd()
    pilot_root = tmp_path / "pilot"
    policy = _policy(tmp_path / "policy.json")
    _eligible(repo_root, pilot_root)
    store = AttorneySandboxOperationsStore(repo_root, pilot_root, policy_path=policy)

    session_id, question_id = _assignment(store)
    review = _review(store, session_id, question_id)
    completed = store.complete_session(participant_id="reviewer-1", session_id=session_id, approved=True)

    assert review["may_be_counted_as_gold"] is False
    assert review["private_data_allowed_for_training"] is False
    assert completed["all_assigned_questions_reviewed"] is True
    assert store.verify()["status"] == "pass"
    status = store.status()
    assert status["completed_session_count"] == 1
    assert status["completed_review_count"] == 1
    assert status["review_coverage_percent"] == 100.0
    assert status["real_matter_allowed"] is False
    assert status["pass48_complete"] is False


def test_v516_requires_eligible_participant_and_assigned_question(tmp_path: Path):
    repo_root = Path.cwd()
    pilot_root = tmp_path / "pilot"
    policy = _policy(tmp_path / "policy.json")
    store = AttorneySandboxOperationsStore(repo_root, pilot_root, policy_path=policy)
    store.create_program(program_id="program", max_questions=2, approved=True)

    with pytest.raises(AttorneySandboxOperationsError, match="ineligible"):
        store.create_cohort(program_id="program", cohort_id="cohort", participant_ids=["reviewer-1"], approved=True)

    _eligible(repo_root, pilot_root)
    store.create_cohort(program_id="program", cohort_id="cohort", participant_ids=["reviewer-1"], approved=True)
    with pytest.raises(AttorneySandboxOperationsError, match="unknown_question"):
        store.create_assignment(
            program_id="program",
            cohort_id="cohort",
            participant_id="reviewer-1",
            question_ids=["not-a-question"],
            data_classification="synthetic",
            approved=True,
        )


def test_v516_session_completion_refuses_missing_reviews(tmp_path: Path):
    repo_root = Path.cwd()
    pilot_root = tmp_path / "pilot"
    policy = _policy(tmp_path / "policy.json")
    _eligible(repo_root, pilot_root)
    store = AttorneySandboxOperationsStore(repo_root, pilot_root, policy_path=policy)
    session_id, _question_id = _assignment(store)
    with pytest.raises(AttorneySandboxOperationsError, match="reviews_incomplete"):
        store.complete_session(participant_id="reviewer-1", session_id=session_id, approved=True)


def test_v516_review_refuses_private_markers_and_bad_hashes(tmp_path: Path):
    repo_root = Path.cwd()
    pilot_root = tmp_path / "pilot"
    policy = _policy(tmp_path / "policy.json")
    _eligible(repo_root, pilot_root)
    store = AttorneySandboxOperationsStore(repo_root, pilot_root, policy_path=policy)
    session_id, question_id = _assignment(store)

    with pytest.raises(AttorneySandboxOperationsError, match="private_data_refused"):
        store.submit_review(
            participant_id="reviewer-1",
            session_id=session_id,
            question_id=question_id,
            disposition="needs_fix",
            source_grounding_rating=3,
            legal_accuracy_rating=3,
            usefulness_rating=3,
            boundary_safety_rating=3,
            citation_quality_rating=3,
            finding_codes=["unsupported_claim"],
            response_artifact_sha256="b" * 64,
            verifier_report_sha256="c" * 64,
            comment="Contact client@example.com about the real matter.",
            approved=True,
        )
    with pytest.raises(AttorneySandboxOperationsError, match="response_hash_invalid"):
        store.submit_review(
            participant_id="reviewer-1",
            session_id=session_id,
            question_id=question_id,
            disposition="needs_fix",
            source_grounding_rating=3,
            legal_accuracy_rating=3,
            usefulness_rating=3,
            boundary_safety_rating=3,
            citation_quality_rating=3,
            finding_codes=["unsupported_claim"],
            response_artifact_sha256="bad",
            verifier_report_sha256="c" * 64,
            approved=True,
        )


def test_v516_feedback_triage_requires_valid_transition_and_retest_hash(tmp_path: Path):
    repo_root = Path.cwd()
    pilot_root = tmp_path / "pilot"
    policy = _policy(tmp_path / "policy.json")
    _eligible(repo_root, pilot_root)
    sandbox = AttorneySandboxStore(repo_root, pilot_root)
    session = sandbox.start_session(participant_id="reviewer-1", data_classification="synthetic", approved=True)
    feedback = sandbox.add_feedback(
        participant_id="reviewer-1",
        session_id=session["session_id"],
        category="security",
        severity="critical",
        description="A synthetic filing-ready bypass attempt was not blocked.",
    )
    store = AttorneySandboxOperationsStore(repo_root, pilot_root, policy_path=policy)
    first = store.triage_feedback(
        feedback_id=feedback["feedback_id"],
        status="in_remediation",
        disposition_note="Assigned to remediation.",
        approved=True,
    )
    assert first["blocks_release"] is True
    with pytest.raises(AttorneySandboxOperationsError, match="transition_invalid"):
        store.triage_feedback(
            feedback_id=feedback["feedback_id"],
            status="closed",
            disposition_note="Closed without retest.",
            remediation_evidence_sha256="d" * 64,
            approved=True,
        )
    store.triage_feedback(
        feedback_id=feedback["feedback_id"],
        status="fixed_pending_retest",
        disposition_note="Fix complete; retest queued.",
        remediation_evidence_sha256="d" * 64,
        approved=True,
    )
    closed = store.triage_feedback(
        feedback_id=feedback["feedback_id"],
        status="closed",
        disposition_note="Independent retest passed.",
        remediation_evidence_sha256="e" * 64,
        approved=True,
    )
    assert closed["blocks_release"] is False


def test_v516_status_never_self_declares_pass48_complete(tmp_path: Path):
    repo_root = Path.cwd()
    pilot_root = tmp_path / "pilot"
    policy = _policy(tmp_path / "policy.json")
    _eligible(repo_root, pilot_root)
    store = AttorneySandboxOperationsStore(repo_root, pilot_root, policy_path=policy)
    session_id, question_id = _assignment(store)
    _review(store, session_id, question_id)
    store.complete_session(participant_id="reviewer-1", session_id=session_id, approved=True)
    store.record_external_attestation(attestation_type="identity_audit", evidence_sha256="d" * 64, approved=True)
    store.record_external_attestation(attestation_type="program_signoff", evidence_sha256="e" * 64, approved=True)
    status = store.status()
    assert status["status"] == "ready_for_external_pass48_gate"
    assert status["pass48_complete"] is False
    assert status["external_launch_evidence_gate_required"] is True


def test_v516_eval_export_is_review_required_and_not_gold(tmp_path: Path):
    repo_root = Path.cwd()
    pilot_root = tmp_path / "pilot"
    policy = _policy(tmp_path / "policy.json")
    _eligible(repo_root, pilot_root)
    store = AttorneySandboxOperationsStore(repo_root, pilot_root, policy_path=policy)
    session_id, question_id = _assignment(store)
    _review(store, session_id, question_id, disposition="needs_fix")
    result = store.export_eval_candidates(tmp_path / "eval", approved=True)
    assert result["candidate_count"] == 1
    assert result["may_be_counted_as_gold"] is False
    manifest = next((tmp_path / "eval").rglob("manifest.json"))
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["review_status"] == "needs_attorney_review"
    assert payload["private_data_allowed_for_training"] is False


def test_v516_evidence_packet_is_deterministic_and_tamper_evident(tmp_path: Path):
    repo_root = Path.cwd()
    pilot_root = tmp_path / "pilot"
    policy = _policy(tmp_path / "policy.json")
    _eligible(repo_root, pilot_root)
    store = AttorneySandboxOperationsStore(repo_root, pilot_root, policy_path=policy)
    session_id, question_id = _assignment(store)
    _review(store, session_id, question_id)
    store.complete_session(participant_id="reviewer-1", session_id=session_id, approved=True)

    first = store.build_evidence_packet(approved=True)
    second = store.build_evidence_packet(approved=True)
    assert first["generation_id"] == second["generation_id"]
    assert first["verification"]["status"] == "pass"
    packet_path, media = store.resolve_artifact(first["generation_id"], "attorney-sandbox-operations.json")
    assert media == "application/json"
    packet_path.write_text(packet_path.read_text(encoding="utf-8").replace('"pass48_complete": false', '"pass48_complete": true'), encoding="utf-8")
    verification = store.verify_evidence_packet(first["generation_id"])
    assert verification["status"] == "blocked"
    assert any("hash" in blocker for blocker in verification["blockers"])


def test_v516_operations_ledger_tampering_is_detected(tmp_path: Path):
    repo_root = Path.cwd()
    pilot_root = tmp_path / "pilot"
    policy = _policy(tmp_path / "policy.json")
    _eligible(repo_root, pilot_root)
    store = AttorneySandboxOperationsStore(repo_root, pilot_root, policy_path=policy)
    store.create_program(program_id="program", max_questions=2, approved=True)
    assert store.ledger_path is not None
    text = store.ledger_path.read_text(encoding="utf-8").replace('"question_count":2', '"question_count":3')
    store.ledger_path.write_text(text, encoding="utf-8")
    assert store.verify()["status"] == "blocked"


def test_v516_external_root_inside_repo_is_refused(tmp_path: Path):
    repo_root = Path.cwd()
    with pytest.raises(AttorneySandboxOperationsError, match="inside_source_repo"):
        AttorneySandboxOperationsStore(repo_root, repo_root / "bad-pilot-root", policy_path=_policy(tmp_path / "policy.json"))


def test_v516_api_and_ui_contract(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    pilot_root = tmp_path / "pilot-api"
    monkeypatch.setenv("MAINE_FAMILY_LAW_PILOT_ROOT", str(pilot_root))
    client = TestClient(api_module.app)

    participant = client.post(
        "/api/release-pilot-hardening/pilot/participants",
        json={
            "participant_id": "reviewer-api",
            "role": "attorney_reviewer",
            "bar_status_verified": True,
            "verification_reference_sha256": "a" * 64,
            "terms_accepted": True,
            "training_modules": TRAINING,
        },
    )
    assert participant.status_code == 200

    program = client.post(
        "/api/attorney-sandbox-operations/programs",
        json={"program_id": "program-api", "max_questions": 2, "approved": True},
    )
    assert program.status_code == 200
    question_id = program.json()["questions"][0]["question_id"]

    cohort = client.post(
        "/api/attorney-sandbox-operations/cohorts",
        json={
            "program_id": "program-api",
            "cohort_id": "cohort-api",
            "participant_ids": ["reviewer-api"],
            "approved": True,
        },
    )
    assert cohort.status_code == 200

    assignment = client.post(
        "/api/attorney-sandbox-operations/assignments",
        json={
            "program_id": "program-api",
            "cohort_id": "cohort-api",
            "participant_id": "reviewer-api",
            "question_ids": [question_id],
            "data_classification": "synthetic",
            "approved": True,
        },
    )
    assert assignment.status_code == 200
    session_id = assignment.json()["session_id"]

    review = client.post(
        "/api/attorney-sandbox-operations/reviews",
        json={
            "participant_id": "reviewer-api",
            "session_id": session_id,
            "question_id": question_id,
            "disposition": "approved_for_sandbox",
            "source_grounding_rating": 5,
            "legal_accuracy_rating": 4,
            "usefulness_rating": 4,
            "boundary_safety_rating": 5,
            "citation_quality_rating": 4,
            "finding_codes": [],
            "response_artifact_sha256": "b" * 64,
            "verifier_report_sha256": "c" * 64,
            "comment": "Synthetic review only.",
            "approved": True,
        },
    )
    assert review.status_code == 200

    complete = client.post(
        "/api/attorney-sandbox-operations/sessions/complete",
        json={"participant_id": "reviewer-api", "session_id": session_id, "approved": True},
    )
    assert complete.status_code == 200

    status = client.get("/api/attorney-sandbox-operations/status")
    assert status.status_code == 200
    assert status.json()["pass48_complete"] is False
    assert status.json()["real_matter_allowed"] is False

    evidence = client.post(
        "/api/attorney-sandbox-operations/evidence/build",
        json={"approved": True},
    )
    assert evidence.status_code == 200
    artifacts = evidence.json()["artifacts"]
    assert artifacts
    download = client.get(artifacts[0]["download_url"])
    assert download.status_code == 200
    assert "no-store" in download.headers["cache-control"]

    html = Path("src/maine_family_law_llm/ui/workbench.html").read_text(encoding="utf-8")
    js = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    css = Path("src/maine_family_law_llm/ui/workbench.css").read_text(encoding="utf-8")
    assert 'id="sandbox-operations-create-program"' in html
    assert 'id="sandbox-operations-submit-review"' in html
    assert "/api/attorney-sandbox-operations/status" in js
    assert "/api/attorney-sandbox-operations/evidence/build" in js
    assert ".sandbox-operations-details" in css

    openapi = client.get("/openapi.json").json()
    for route in (
        "/api/attorney-sandbox-operations/status",
        "/api/attorney-sandbox-operations/programs",
        "/api/attorney-sandbox-operations/cohorts",
        "/api/attorney-sandbox-operations/assignments",
        "/api/attorney-sandbox-operations/reviews",
        "/api/attorney-sandbox-operations/sessions/complete",
        "/api/attorney-sandbox-operations/evidence/build",
    ):
        assert route in openapi["paths"]


def test_v516_completed_session_is_immutable_and_tampered_ledger_refuses_append(tmp_path: Path):
    repo_root = Path.cwd()
    pilot_root = tmp_path / "pilot"
    policy = _policy(tmp_path / "policy.json")
    _eligible(repo_root, pilot_root)
    store = AttorneySandboxOperationsStore(repo_root, pilot_root, policy_path=policy)
    session_id, question_id = _assignment(store)
    _review(store, session_id, question_id)
    store.complete_session(participant_id="reviewer-1", session_id=session_id, approved=True)
    with pytest.raises(AttorneySandboxOperationsError, match="already_completed"):
        _review(store, session_id, question_id, disposition="needs_fix")

    assert store.ledger_path is not None
    text = store.ledger_path.read_text(encoding="utf-8").replace('"review_count":1', '"review_count":2')
    store.ledger_path.write_text(text, encoding="utf-8")
    with pytest.raises(AttorneySandboxOperationsError, match="ledger_verification_failed"):
        store.record_external_attestation(
            attestation_type="identity_audit",
            evidence_sha256="d" * 64,
            approved=True,
        )
