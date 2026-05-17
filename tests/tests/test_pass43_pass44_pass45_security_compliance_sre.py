from __future__ import annotations

from pathlib import Path

from legal.governance import GovernanceCompliancePacketBuilder
from legal.ops import BackupRestoreRunbook, ReliabilitySREAuditor, SLOMeasurement
from legal.security import (
    AnswerProvenanceTrail,
    ExportEvent,
    ImmutableExportLog,
    KeyRotationLedger,
    MatterAccessPolicy,
    MatterReference,
    SecurityImplementationAuditor,
    UserContext,
)

ROOT = Path(__file__).resolve().parents[1]


def _provenance_record():
    return AnswerProvenanceTrail().build_record(
        user_id="user-1",
        tenant_id="tenant-a",
        matter_id="matter-1",
        source_id="statute-19a-1653",
        model_id="generator-001",
        prompt="prompt",
        retrieved_context="source context",
        output="review_required output",
        verifier_status="pass",
        export_status="blocked_review_required",
    )


def test_pass43_security_controls_cover_auth_rbac_tenant_encryption_audit_and_export_logs():
    key_ledger = KeyRotationLedger()
    key_ledger.append(key_id="key-1", action="rotate", actor="admin", reason="test")
    export_log = ImmutableExportLog()
    export_log.append(
        ExportEvent(
            export_id="export-1",
            user_id="user-1",
            tenant_id="tenant-a",
            matter_id="matter-1",
            export_status="blocked_review_required",
            verifier_status="review_required",
            filing_ready_gate_hash="hash",
        )
    )

    report = SecurityImplementationAuditor(ROOT / "configs/maine_enterprise_security_controls.json").audit(
        provenance_record=_provenance_record(),
        key_rotation_ledger=key_ledger,
        export_log=export_log,
    )

    assert report["status"] == "pass", report
    assert not report["missing_controls"]
    assert report["audit_trail"]["admin_explanation_available"] is True
    assert report["key_rotation_ledger"]["verified"] is True
    assert report["immutable_export_log"]["verified"] is True


def test_pass43_tenant_matter_access_blocks_cross_tenant_reads():
    policy = MatterAccessPolicy()
    user = UserContext(user_id="u1", tenant_id="tenant-a", roles=("attorney",), matter_ids=("matter-1",))
    same = MatterReference(matter_id="matter-1", tenant_id="tenant-a")
    other_tenant = MatterReference(matter_id="matter-1", tenant_id="tenant-b")

    assert policy.can_access(user, same, "matter:read") is True
    assert policy.can_access(user, other_tenant, "matter:read") is False


def test_pass43_immutable_export_log_rejects_false_filing_ready_pass():
    export_log = ImmutableExportLog()
    try:
        export_log.append(
            ExportEvent(
                export_id="bad-export",
                user_id="user-1",
                tenant_id="tenant-a",
                matter_id="matter-1",
                export_status="filing_ready",
                verifier_status="failed",
                filing_ready_gate_hash="hash",
            )
        )
    except ValueError as exc:
        assert "verifier_status=pass" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("false filing-ready export was not rejected")


def test_pass44_governance_compliance_packet_has_framework_mappings_and_runbooks():
    report = GovernanceCompliancePacketBuilder(
        policy_path=ROOT / "configs/maine_governance_compliance_packet.json",
        repo_root=ROOT,
    ).build().as_dict()

    assert report["status"] == "pass", report
    assert len(report["packet_items"]) >= 10
    assert "govern" in report["nist_ai_rmf_mapping"]
    assert "confabulation_controls" in report["nist_ai_600_1_mapping"]
    assert "LLM01_prompt_injection" in report["owasp_llm_mapping"]
    assert report["owner_signoff_slots"]["legal_owner"] == "required_before_ga"


def test_pass45_sre_policy_tracks_slos_restore_drill_degraded_modes_and_missing_controls():
    auditor = ReliabilitySREAuditor(ROOT / "configs/maine_sre_reliability_policy.json")
    restore = BackupRestoreRunbook().run_drill(
        backup_id="backup-1",
        restore_target="restore-target",
        checksum_before="same",
        checksum_after="same",
    )
    report = auditor.audit(
        implemented_controls=set(auditor.policy["required_operational_controls"]),
        measurements=[SLOMeasurement("api_p95_latency_ms", 10, 100)],
        restore_drill=restore,
    )

    assert report["status"] == "pass", report
    assert report["restore_drill"]["status"] == "pass"
    assert "vector_index_down" in report["degraded_modes"]

    blocked = auditor.audit(implemented_controls=set(), measurements=[], restore_drill=restore)
    assert blocked["status"] == "fail"
    assert any(item.startswith("missing_operational_control:") for item in blocked["blockers"])
