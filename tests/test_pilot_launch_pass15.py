from legal.pilot import CorrectionWorkflow, LaunchReadinessAuditor, PilotRunbook


def test_pass15_pilot_runbook_stages_are_ordered_and_conservative():
    stages = PilotRunbook().stages()

    assert [stage.name for stage in stages][:2] == [
        "internal_synthetic_testing",
        "attorney_only_sandbox",
    ]
    assert all(not stage.real_matter_allowed for stage in stages[:2])
    assert all(stage.real_matter_allowed for stage in stages[2:])


def test_pass15_correction_workflow_blocks_on_critical_ticket():
    workflow = CorrectionWorkflow()
    ticket = workflow.open_ticket(
        ticket_id="PILOT-001",
        severity="critical",
        source="release_gate",
        description="Gold evaluation data missing.",
    )
    summary = workflow.triage_summary([ticket])

    assert summary["release_blocked"] is True
    assert summary["blocking_ticket_count"] == 1


def test_pass15_launch_auditor_honestly_reports_incomplete_controls():
    auditor = LaunchReadinessAuditor()
    partial = auditor.audit({"correction_workflow", "rollback_plan"})
    complete = auditor.audit(LaunchReadinessAuditor.REQUIRED_OPERATIONS)

    assert partial["status"] == "incomplete"
    assert partial["release_blocked"] is True
    assert complete["status"] == "pass"
    assert complete["release_blocked"] is False
