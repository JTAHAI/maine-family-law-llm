from legal.pilot import (
    AttorneyPilotParticipant,
    AttorneySandboxPilot,
    LimitedRealMatterPilot,
    PilotFeedbackItem,
    PrivacyConsentRecord,
    RealMatterPilotMatter,
)


def test_pass48_attorney_sandbox_requires_onboarding_and_blocks_real_matter():
    pilot = AttorneySandboxPilot()
    approved = AttorneyPilotParticipant(
        participant_id="attorney-1",
        role="maine_family_law_attorney",
        bar_status_verified=True,
        nda_or_terms_accepted=True,
        training_completed=True,
    )
    blocked = AttorneyPilotParticipant(
        participant_id="attorney-2",
        role="observer",
        bar_status_verified=True,
        nda_or_terms_accepted=False,
        training_completed=True,
    )

    mixed = pilot.build_onboarding_packet([approved, blocked])
    clean = pilot.build_onboarding_packet([approved])

    assert mixed["status"] == "blocked"
    assert mixed["blocked_participant_ids"] == ["attorney-2"]
    assert clean["status"] == "pass"
    assert clean["real_matter_allowed"] is False
    assert clean["allowed_data"] == "synthetic_or_public_authority_only"


def test_pass48_feedback_creates_attorney_review_queue_and_dashboard():
    pilot = AttorneySandboxPilot()
    participant = AttorneyPilotParticipant(
        participant_id="attorney-1",
        role="maine_family_law_attorney",
        bar_status_verified=True,
        nda_or_terms_accepted=True,
        training_completed=True,
    )
    onboarding = pilot.build_onboarding_packet([participant])
    feedback = [
        PilotFeedbackItem(
            feedback_id="FB-001",
            participant_id="attorney-1",
            category="retrieval_miss",
            severity="medium",
            description="Missing support-form authority.",
        )
    ]

    queue = pilot.build_review_queue(feedback)
    dashboard = pilot.build_dashboard(onboarding, feedback, queue)

    assert queue["status"] == "pass"
    assert queue["rows"][0]["requires_attorney_review"] is True
    assert queue["rows"][0]["may_be_counted_as_gold"] is False
    assert queue["rows"][0]["private_data_allowed_for_training"] is False
    assert dashboard["status"] == "pass"
    assert dashboard["attorney_can_use_for_research_review"] is True
    assert dashboard["eval_candidates_created"] == ["FB-001"]


def test_pass48_open_critical_safety_issue_blocks_dashboard():
    pilot = AttorneySandboxPilot()
    participant = AttorneyPilotParticipant(
        participant_id="attorney-1",
        role="maine_family_law_attorney",
        bar_status_verified=True,
        nda_or_terms_accepted=True,
        training_completed=True,
    )
    onboarding = pilot.build_onboarding_packet([participant])
    feedback = [
        PilotFeedbackItem(
            feedback_id="FB-CRIT",
            participant_id="attorney-1",
            category="filing_ready_bypass",
            severity="critical",
            description="Attempted unsupported export.",
        )
    ]
    queue = pilot.build_review_queue(feedback)
    dashboard = pilot.build_dashboard(onboarding, feedback, queue)

    assert dashboard["status"] == "blocked"
    assert dashboard["critical_safety_issues"] == ["FB-CRIT"]
    assert dashboard["attorney_can_use_for_research_review"] is False


def _good_consent() -> PrivacyConsentRecord:
    return PrivacyConsentRecord(
        matter_id="matter-1",
        tenant_id="tenant-a",
        participant_id="attorney-1",
        consent_version="2026-05-pass49",
        explicit_real_matter_consent=True,
        training_use_allowed=False,
        export_restriction_acknowledged=True,
        human_review_required=True,
    )


def _good_matter() -> RealMatterPilotMatter:
    return RealMatterPilotMatter(
        matter_id="matter-1",
        tenant_id="tenant-a",
        participant_id="attorney-1",
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


def test_pass49_limited_real_matter_pilot_passes_only_with_consent_isolation_artifacts_and_signoff():
    audit = LimitedRealMatterPilot().audit(
        allowed_tenant_ids={"tenant-a"},
        consent_records=[_good_consent()],
        matters=[_good_matter()],
    )

    assert audit["status"] == "pass"
    assert audit["human_review_required"] is True
    assert audit["export_restrictions_enforced"] is True
    assert audit["matters"][0]["status"] == "pass"
    assert audit["blockers"] == []


def test_pass49_blocks_data_leakage_private_training_and_unsupported_exports():
    bad_consent = PrivacyConsentRecord(
        matter_id="matter-1",
        tenant_id="tenant-a",
        participant_id="attorney-1",
        consent_version="2026-05-pass49",
        explicit_real_matter_consent=True,
        training_use_allowed=True,
        export_restriction_acknowledged=False,
        human_review_required=False,
    )
    bad_matter = RealMatterPilotMatter(
        matter_id="matter-1",
        tenant_id="tenant-b",
        participant_id="attorney-1",
        artifacts_generated=("issue_tree",),
        tenant_isolation_verified=False,
        encrypted_storage_verified=False,
        data_leakage_detected=True,
        unsupported_filing_ready_export_attempts=1,
        attorney_signed_off=False,
        daily_review_completed=False,
        incident_open=True,
    )

    audit = LimitedRealMatterPilot().audit(
        allowed_tenant_ids={"tenant-a"},
        consent_records=[bad_consent],
        matters=[bad_matter],
    )
    blockers = "\n".join(audit["blockers"])

    assert audit["status"] == "blocked"
    assert "tenant_not_in_limited_pilot_group" in blockers
    assert "private_training_use_must_remain_false" in blockers
    assert "human_review_not_required" in blockers
    assert "export_restriction_not_acknowledged" in blockers
    assert "data_leakage_detected" in blockers
    assert "unsupported_filing_ready_export_attempt" in blockers
    assert "missing_work_product_artifacts" in blockers
    assert "daily_pilot_review_missing" in blockers
    assert "open_incident" in blockers
    assert "attorney_signoff_missing" in blockers
