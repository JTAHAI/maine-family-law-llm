#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.pilot import (
    AttorneyPilotParticipant,
    AttorneySandboxPilot,
    LimitedRealMatterPilot,
    PilotFeedbackItem,
    PrivacyConsentRecord,
    RealMatterPilotMatter,
)


def build_pass48() -> dict:
    pilot = AttorneySandboxPilot()
    participants = [
        AttorneyPilotParticipant(
            participant_id="attorney-reviewer-001",
            role="maine_family_law_attorney",
            bar_status_verified=True,
            nda_or_terms_accepted=True,
            training_completed=True,
        ),
        AttorneyPilotParticipant(
            participant_id="attorney-reviewer-002",
            role="supervised_attorney_reviewer",
            bar_status_verified=True,
            nda_or_terms_accepted=True,
            training_completed=True,
        ),
    ]
    feedback = [
        PilotFeedbackItem(
            feedback_id="PILOT-FB-001",
            participant_id="attorney-reviewer-001",
            category="retrieval_miss",
            severity="medium",
            description="Add eval candidate for contested primary residence query expansion.",
        ),
        PilotFeedbackItem(
            feedback_id="PILOT-FB-002",
            participant_id="attorney-reviewer-002",
            category="citation_ui_clarity",
            severity="low",
            description="Expose source-card freshness badge earlier in answer drilldown.",
            creates_eval_candidate=False,
        ),
    ]
    onboarding = pilot.build_onboarding_packet(participants)
    queue = pilot.build_review_queue(feedback)
    dashboard = pilot.build_dashboard(onboarding, feedback, queue)
    return {
        "stage": "pass48_attorney_only_sandbox_pilot",
        "onboarding": onboarding,
        "review_queue": queue,
        "dashboard": dashboard,
        "status": "pass" if onboarding["status"] == "pass" and queue["status"] == "pass" and dashboard["status"] == "pass" else "fail",
        "readiness": "Attorney-only sandbox operations are runnable with public/synthetic data only; all outputs remain review_required.",
    }


def build_pass49() -> dict:
    pilot = LimitedRealMatterPilot()
    consent = [
        PrivacyConsentRecord(
            matter_id="pilot-matter-001",
            tenant_id="tenant-maine-pilot-a",
            participant_id="attorney-reviewer-001",
            consent_version="2026-05-pass49",
            explicit_real_matter_consent=True,
            training_use_allowed=False,
            export_restriction_acknowledged=True,
            human_review_required=True,
        )
    ]
    matters = [
        RealMatterPilotMatter(
            matter_id="pilot-matter-001",
            tenant_id="tenant-maine-pilot-a",
            participant_id="attorney-reviewer-001",
            artifacts_generated=(
                "issue_tree",
                "posture_summary",
                "timeline",
                "evidence_map",
                "authority_matrix",
                "red_flag_report",
            ),
            tenant_isolation_verified=True,
            encrypted_storage_verified=True,
            data_leakage_detected=False,
            unsupported_filing_ready_export_attempts=0,
            attorney_signed_off=True,
            daily_review_completed=True,
            incident_open=False,
        )
    ]
    audit = pilot.audit(
        allowed_tenant_ids={"tenant-maine-pilot-a"},
        consent_records=consent,
        matters=matters,
    )
    return {
        "stage": "pass49_limited_real_matter_pilot",
        "audit": audit,
        "status": "pass" if audit["status"] == "pass" else "fail",
        "readiness": "Limited real-matter pilot controls are implemented and auditable; this fixture proves the control path, not real pilot completion.",
    }


def main() -> int:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "sample-evidence" / "smoke_evidence_pass48_pass49_pilot_operations.json"
    pass48 = build_pass48()
    pass49 = build_pass49()
    evidence = {
        "stage": "enterprise_pass_48_49_pilot_operations",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "pass48_attorney_only_sandbox_pilot": pass48,
            "pass49_limited_real_matter_pilot": pass49,
        },
        "completed_passes": [48, 49],
        "status": "pass" if pass48["status"] == "pass" and pass49["status"] == "pass" else "fail",
        "legal_readiness": (
            "Pass 48 and Pass 49 pilot-operation controls are implemented. Real-world GA still requires actual attorney-only sandbox evidence, limited real-matter pilot evidence, and signoffs captured outside the source repo."
        ),
    }
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
