from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.contracts import EndpointInventory
from app.api.main import app as api_app
from app.web.ui_contracts import UICompletionAuditor
from app.web.ui_inventory import UIViewInventory
from legal.ops.release_pilot_hardening import PrivacySafeObservabilityStore
from maine_family_law_llm import api as api_module
from maine_family_law_llm.version import VERSION as PRODUCT_VERSION


TRAINING = [
    "data_boundaries",
    "source_grounding",
    "citation_quote_verification",
    "review_required_exports",
    "feedback_and_error_reporting",
]


def _headers() -> dict[str, str]:
    return {"X-User-Role": "admin", "X-Tenant-Id": "tenant-maintenance"}


def _registered_routes(app) -> set[tuple[str, str]]:
    registered: set[tuple[str, str]] = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", None) or set()
        for method in methods:
            if method in {"HEAD", "OPTIONS"}:
                continue
            registered.add((method, path))
    return registered


def _seed_pilot_participant(client: TestClient) -> str:
    response = client.post(
        "/api/release-pilot-hardening/pilot/participants",
        json={
            "participant_id": "reviewer-604",
            "role": "attorney_reviewer",
            "bar_status_verified": True,
            "verification_reference_sha256": "a" * 64,
            "terms_accepted": True,
            "training_modules": TRAINING,
        },
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    return "reviewer-604"


def _seed_case_root(case_root: Path) -> None:
    case_root.mkdir(parents=True, exist_ok=True)
    (case_root / "order.pdf").write_bytes(b"synthetic-order")
    (case_root / "notes.txt").write_text("synthetic notes", encoding="utf-8")
    store = PrivacySafeObservabilityStore(case_root)
    store.record("api_request", metrics={"count": 1}, labels={"component": "maintenance", "operation": "seed", "status": "pass"})
    assert store.verify()["status"] == "pass"


def test_release_maintenance_ui_inventory_and_route_contracts_include_the_shipped_workbench() -> None:
    ui_inventory = UIViewInventory("app/web/pages").validate()
    assert ui_inventory["status"] == "pass", ui_inventory
    assert "maintenance-center.tsx" in {view["file"] for view in ui_inventory["views"]}

    ui_audit = UICompletionAuditor("app/web/pages").audit().as_dict()
    assert ui_audit["status"] == "pass", ui_audit

    endpoint_inventory = EndpointInventory().compare_to_registered(_registered_routes(api_app))
    assert endpoint_inventory["status"] == "pass", endpoint_inventory
    required_paths = {item["path"] for item in EndpointInventory().as_dict()["endpoints"]}
    assert "/api/release-pilot-hardening/status" in required_paths
    assert "/api/ga-shipment-readiness/status" in required_paths


def test_release_maintenance_api_surface_drives_the_pilot_and_real_matter_workflows(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    pilot_root = tmp_path / "pilot"
    release_root = tmp_path / "release"
    backup_root = tmp_path / "backup"
    eval_root = tmp_path / "eval"
    _seed_case_root(case_root)

    monkeypatch.setattr(api_module, "active_case_root", lambda: case_root)
    monkeypatch.setenv("MFL_PROJECT_ROOT", str(Path.cwd()))
    monkeypatch.setenv("MAINE_FAMILY_LAW_PILOT_ROOT", str(pilot_root))
    monkeypatch.setenv("MAINE_FAMILY_LAW_RELEASE_ROOT", str(release_root))
    monkeypatch.setenv("MAINE_FAMILY_LAW_BACKUP_ROOT", str(backup_root))

    client = TestClient(api_app)
    participant_id = _seed_pilot_participant(client)

    pilot_session = client.post(
        "/api/release-pilot-hardening/pilot/sessions",
        json={"participant_id": participant_id, "data_classification": "public_authority", "approved": True},
        headers=_headers(),
    )
    assert pilot_session.status_code == 200, pilot_session.text
    session_id = pilot_session.json()["session_id"]

    feedback = client.post(
        "/api/release-pilot-hardening/pilot/feedback",
        json={
            "participant_id": participant_id,
            "session_id": session_id,
            "category": "workflow",
            "severity": "medium",
            "description": "Synthetic feedback for the maintenance center workflow.",
        },
        headers=_headers(),
    )
    assert feedback.status_code == 200, feedback.text
    feedback_id = feedback.json()["feedback_id"]

    drill = client.post("/api/release-pilot-hardening/backup-restore/drill", json={"approved": True}, headers=_headers())
    assert drill.status_code == 200, drill.text
    assert drill.json()["status"] == "pass"

    hardening_status = client.get("/api/release-pilot-hardening/status", headers=_headers())
    assert hardening_status.status_code == 200, hardening_status.text
    assert hardening_status.json()["status"] in {"pass", "blocked"}

    status = client.get("/api/attorney-sandbox-operations/status", headers=_headers())
    assert status.status_code == 200, status.text
    assert status.json()["status"] in {"blocked", "ready_for_external_pass48_gate"}

    program = client.post(
        "/api/attorney-sandbox-operations/programs",
        json={"program_id": "pass48-604", "max_questions": 3, "approved": True},
        headers=_headers(),
    )
    assert program.status_code == 200, program.text
    question_id = program.json()["questions"][0]["question_id"]

    client.post(
        "/api/attorney-sandbox-operations/cohorts",
        json={"program_id": "pass48-604", "cohort_id": "cohort-a", "participant_ids": [participant_id], "approved": True},
        headers=_headers(),
    ).raise_for_status()
    session = client.post(
        "/api/attorney-sandbox-operations/assignments",
        json={
            "program_id": "pass48-604",
            "cohort_id": "cohort-a",
            "participant_id": participant_id,
            "question_ids": [question_id],
            "data_classification": "synthetic",
            "approved": True,
        },
        headers=_headers(),
    )
    assert session.status_code == 200, session.text
    operations_session_id = session.json()["session_id"]

    review = client.post(
        "/api/attorney-sandbox-operations/reviews",
        json={
            "participant_id": participant_id,
            "session_id": operations_session_id,
            "question_id": question_id,
            "disposition": "approved_for_sandbox",
            "source_grounding_rating": 5,
            "legal_accuracy_rating": 5,
            "usefulness_rating": 4,
            "boundary_safety_rating": 5,
            "citation_quality_rating": 4,
            "finding_codes": [],
            "response_artifact_sha256": "b" * 64,
            "verifier_report_sha256": "c" * 64,
            "comment": "Synthetic review only.",
            "approved": True,
        },
        headers=_headers(),
    )
    assert review.status_code == 200, review.text

    completion = client.post(
        "/api/attorney-sandbox-operations/sessions/complete",
        json={"participant_id": participant_id, "session_id": operations_session_id, "approved": True},
        headers=_headers(),
    )
    assert completion.status_code == 200, completion.text

    triage = client.post(
        "/api/attorney-sandbox-operations/feedback/triage",
        json={
            "feedback_id": feedback_id,
            "status": "in_remediation",
            "disposition_note": "Synthetic remediation recorded.",
            "remediation_evidence_sha256": "d" * 64,
            "approved": True,
        },
        headers=_headers(),
    )
    assert triage.status_code == 200, triage.text

    attestation = client.post(
        "/api/attorney-sandbox-operations/attestations",
        json={"attestation_type": "identity_audit", "evidence_sha256": "e" * 64, "approved": True},
        headers=_headers(),
    )
    assert attestation.status_code == 200, attestation.text

    export_bundle = client.post(
        "/api/attorney-sandbox-operations/eval/export",
        json={"eval_root": str(eval_root), "approved": True},
        headers=_headers(),
    )
    assert export_bundle.status_code == 200, export_bundle.text

    evidence = client.post("/api/attorney-sandbox-operations/evidence/build", json={"approved": True}, headers=_headers())
    assert evidence.status_code == 200, evidence.text
    assert evidence.json()["artifacts"]
    download = client.get(evidence.json()["artifacts"][0]["download_url"], headers=_headers())
    assert download.status_code == 200, download.text

    real_program = client.post(
        "/api/limited-real-matter-pilot/programs",
        json={"program_id": "pass49-604", "allowed_tenant_ids": ["tenant-maintenance"], "pass48_evidence_sha256": "f" * 64, "approved": True},
        headers=_headers(),
    )
    assert real_program.status_code == 200, real_program.text

    matter = client.post(
        "/api/limited-real-matter-pilot/matters",
        json={
            "matter_id": "matter-604",
            "tenant_id": "tenant-maintenance",
            "participant_id": participant_id,
            "consent_version": "consent-v1",
            "client_consent_evidence_sha256": "1" * 64,
            "privacy_notice_sha256": "2" * 64,
            "matter_store_sha256": "3" * 64,
            "tenant_isolation_evidence_sha256": "4" * 64,
            "encryption_evidence_sha256": "5" * 64,
            "retention_policy_version": "retention-v1",
            "explicit_real_matter_consent": True,
            "training_use_allowed": False,
            "export_restriction_acknowledged": True,
            "human_review_required": True,
            "approved": True,
        },
        headers=_headers(),
    )
    assert matter.status_code == 200, matter.text

    work_product = client.post(
        "/api/limited-real-matter-pilot/work-products",
        json={
            "matter_id": "matter-604",
            "artifact_hashes": {
                "issue_tree": "6" * 64,
                "posture_summary": "7" * 64,
                "timeline": "8" * 64,
                "evidence_map": "9" * 64,
                "authority_matrix": "a" * 64,
                "red_flag_report": "b" * 64,
            },
            "approved": True,
        },
        headers=_headers(),
    )
    assert work_product.status_code == 200, work_product.text

    daily_review = client.post(
        "/api/limited-real-matter-pilot/daily-reviews",
        json={
            "matter_id": "matter-604",
            "participant_id": participant_id,
            "review_date": "2026-08-08",
            "usefulness": "useful",
            "human_review_completed": True,
            "source_verification_completed": True,
            "export_gate_checked": True,
            "blocker_codes": [],
            "review_evidence_sha256": "c" * 64,
            "approved": True,
        },
        headers=_headers(),
    )
    assert daily_review.status_code == 200, daily_review.text

    export_attempt = client.post(
        "/api/limited-real-matter-pilot/exports",
        json={
            "matter_id": "matter-604",
            "export_type": "draft_review_copy",
            "gate_status": "approved_review_required",
            "filing_ready_claimed": False,
            "export_artifact_sha256": "d" * 64,
            "authorization_evidence_sha256": "e" * 64,
            "approved": True,
        },
        headers=_headers(),
    )
    assert export_attempt.status_code == 200, export_attempt.text

    signoff = client.post(
        "/api/limited-real-matter-pilot/signoffs",
        json={
            "matter_id": "matter-604",
            "participant_id": participant_id,
            "usefulness": "useful",
            "attorney_signoff_complete": True,
            "blocker_codes": [],
            "signoff_evidence_sha256": "f" * 64,
            "approved": True,
        },
        headers=_headers(),
    )
    assert signoff.status_code == 200, signoff.text

    real_status = client.get("/api/limited-real-matter-pilot/status", headers=_headers())
    assert real_status.status_code == 200, real_status.text
    assert real_status.json()["status"] in {"ready_for_external_pass49_gate", "blocked"}

    rc_create = client.post(
        "/api/ga-release-candidate/candidates",
        json={
            "candidate_id": "v6-0-4-rc1",
            "version": "5.18.0",
            "source_repo_zip_sha256": "1" * 64,
            "source_repo_zip_name": "Maine-Family-Law-LLM-v5.18.0-ga-release-candidate-full-source.zip",
            "approved": True,
        },
        headers=_headers(),
    )
    assert rc_create.status_code == 200, rc_create.text
    rc_status = client.get("/api/ga-release-candidate/status", headers=_headers())
    assert rc_status.status_code == 200, rc_status.text

    shipment_create = client.post(
        "/api/ga-shipment-readiness/shipments",
        json={
            "shipment_id": "v6-0-4-ga1",
            "version": PRODUCT_VERSION,
            "source_repo_zip_name": "Maine-Family-Law-LLM-v6.0.4-ga-shipment-readiness-full-source.zip",
            "source_repo_zip_sha256": "2" * 64,
            "release_candidate_id": "v6-0-4-rc1",
            "release_candidate_report_sha256": "3" * 64,
            "release_candidate_inventory_hash": "4" * 64,
            "release_channel": "source_release",
            "approved": True,
        },
        headers=_headers(),
    )
    assert shipment_create.status_code == 200, shipment_create.text
    shipment_status = client.get("/api/ga-shipment-readiness/status", headers=_headers())
    assert shipment_status.status_code == 200, shipment_status.text
