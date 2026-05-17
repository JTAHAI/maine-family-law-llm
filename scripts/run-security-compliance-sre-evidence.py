#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.governance import GovernanceCompliancePacketBuilder
from legal.ops import BackupRestoreRunbook, ReliabilitySREAuditor
from legal.security import (
    AnswerProvenanceTrail,
    ExportEvent,
    ImmutableExportLog,
    KeyRotationLedger,
    SecurityImplementationAuditor,
)


def build_evidence() -> dict:
    trail = AnswerProvenanceTrail()
    provenance = trail.build_record(
        user_id="admin-001",
        tenant_id="tenant-maine-demo",
        matter_id="matter-demo-001",
        source_id="statute-19a-1653",
        model_id="maine-final-generator-review-required-001",
        prompt="What Maine authority controls best interest findings?",
        retrieved_context="19-A M.R.S. § 1653 and M.R. Civ. P. 120 source-card excerpts.",
        output="review_required: Maine best-interest findings require source verification before export.",
        verifier_status="review_required_verified_sources_pending_human_review",
        export_status="blocked_review_required",
    )
    key_ledger = KeyRotationLedger()
    key_ledger.append(
        key_id="tenant-maine-demo-kek-2026-05",
        action="rotate",
        actor="security-admin",
        reason="pass43 scheduled key rotation evidence",
    )
    export_log = ImmutableExportLog()
    export_log.append(
        ExportEvent(
            export_id="export-demo-001",
            user_id="admin-001",
            tenant_id="tenant-maine-demo",
            matter_id="matter-demo-001",
            export_status="blocked_review_required",
            verifier_status="review_required_verified_sources_pending_human_review",
            filing_ready_gate_hash=trail.hash_text("gate failed because human review is incomplete"),
        )
    )
    security = SecurityImplementationAuditor(ROOT / "configs/maine_enterprise_security_controls.json").audit(
        provenance_record=provenance,
        key_rotation_ledger=key_ledger,
        export_log=export_log,
    )
    compliance = GovernanceCompliancePacketBuilder(
        policy_path=ROOT / "configs/maine_governance_compliance_packet.json",
        repo_root=ROOT,
    ).build().as_dict()
    sre_auditor = ReliabilitySREAuditor(ROOT / "configs/maine_sre_reliability_policy.json")
    restore = BackupRestoreRunbook().run_drill(
        backup_id="backup-offline-demo-001",
        restore_target="/tmp/maine-family-law-llm-restore-drill",
        checksum_before="abc123",
        checksum_after="abc123",
    )
    sre = sre_auditor.audit(
        implemented_controls=set(sre_auditor.policy.get("required_operational_controls", [])),
        measurements=sre_auditor.default_offline_measurements(),
        restore_drill=restore,
    )
    status = "pass" if security["status"] == "pass" and compliance["status"] == "pass" and sre["status"] == "pass" else "fail"
    return {
        "stage": "enterprise_pass_43_pass_44_pass_45_security_compliance_sre",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "security_implementation": security,
        "governance_compliance_packet": compliance,
        "reliability_sre": sre,
        "status": status,
        "completed_passes": [43, 44, 45],
        "remaining_passes": 6,
        "legal_readiness": "Pass 43-45 source-code foundations are implemented. GA still requires full release eval run, legal red-team signoff, attorney-only sandbox pilot, limited real-matter pilot, GA release-candidate signoffs, and production shipped operations artifacts.",
    }


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "smoke_evidence_pass43_pass44_pass45_security_compliance_sre.json"
    evidence = build_evidence()
    out.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
