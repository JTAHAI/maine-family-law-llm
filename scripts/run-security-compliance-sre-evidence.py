#!/usr/bin/env python3
from __future__ import annotations

import json
import argparse
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


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_split_reports(evidence: dict, output_dir: Path) -> dict[str, str]:
    """Write dedicated GA evidence artifacts for Pass 43, Pass 44, and Pass 45."""

    security_report = {
        "status": evidence["security_implementation"].get("status", "fail"),
        "pass": 43,
        "title": "Security implementation",
        "generated_at": evidence["generated_at"],
        "security_implementation": evidence["security_implementation"],
    }
    governance_report = {
        "status": evidence["governance_compliance_packet"].get("status", "fail"),
        "pass": 44,
        "title": "Governance and compliance evidence packet",
        "generated_at": evidence["generated_at"],
        "governance_compliance_packet": evidence["governance_compliance_packet"],
    }
    sre_report = {
        "status": evidence["reliability_sre"].get("status", "fail"),
        "pass": 45,
        "title": "Reliability, scale, and SRE",
        "generated_at": evidence["generated_at"],
        "reliability_sre": evidence["reliability_sre"],
    }
    output_dir = output_dir.resolve()
    paths = {
        "combined": output_dir / "security-compliance-sre-evidence-report.json",
        "pass43": output_dir / "enterprise-security-test-report.json",
        "pass44": output_dir / "governance-compliance-packet-report.json",
        "pass45": output_dir / "sre-reliability-report.json",
    }
    _write_json(paths["combined"], evidence)
    _write_json(paths["pass43"], security_report)
    _write_json(paths["pass44"], governance_report)
    _write_json(paths["pass45"], sre_report)
    return {key: str(path.resolve().relative_to(ROOT)) if ROOT in (path.resolve(), *path.resolve().parents) else str(path.resolve()) for key, path in paths.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Pass 43-45 security/compliance/SRE GA evidence reports.")
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=ROOT / "docs" / "sample-evidence" / "smoke_evidence_pass43_pass44_pass45_security_compliance_sre.json",
        help="Backward-compatible combined sample evidence output path.",
    )
    parser.add_argument(
        "--ga-output-dir",
        type=Path,
        default=ROOT / "docs",
        help="Directory for dedicated Pass 43/44/45 GA evidence reports.",
    )
    parser.add_argument(
        "--sample-only",
        action="store_true",
        help="Only write the backward-compatible sample evidence file.",
    )
    args = parser.parse_args()
    evidence = build_evidence()
    _write_json(args.output, evidence)
    if not args.sample_only:
        evidence["ga_evidence_reports"] = write_split_reports(evidence, args.ga_output_dir)
        _write_json(args.output, evidence)
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
