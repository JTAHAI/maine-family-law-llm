from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PilotStage:
    name: str
    allowed_data: str
    required_controls: tuple[str, ...]
    exit_criteria: tuple[str, ...]
    real_matter_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "allowed_data": self.allowed_data,
            "required_controls": list(self.required_controls),
            "exit_criteria": list(self.exit_criteria),
            "real_matter_allowed": self.real_matter_allowed,
        }


class PilotRunbook:
    def stages(self) -> tuple[PilotStage, ...]:
        return (
            PilotStage(
                name="internal_synthetic_testing",
                allowed_data="synthetic_only",
                required_controls=("release_gates_blocked", "private_data_scan", "audit_logging"),
                exit_criteria=("all_foundation_tests_pass", "no_private_data_packaged"),
            ),
            PilotStage(
                name="attorney_only_sandbox",
                allowed_data="synthetic_or_public_authority_only",
                required_controls=("authentication", "rbac", "source_cards", "human_review_queue"),
                exit_criteria=("attorney_feedback_logged", "critical_failures_triaged"),
            ),
            PilotStage(
                name="limited_real_matter_pilot",
                allowed_data="explicit_opt_in_private_matter_data",
                required_controls=("tenant_isolation", "encryption", "retention_policy", "incident_response"),
                exit_criteria=("privacy_controls_verified", "export_false_pass_zero"),
                real_matter_allowed=True,
            ),
            PilotStage(
                name="law_firm_deployment",
                allowed_data="tenant_isolated_matter_data",
                required_controls=("production_auth", "backup_restore", "vendor_review", "rollback_plan"),
                exit_criteria=("security_review_complete", "attorney_review_sla_met"),
                real_matter_allowed=True,
            ),
            PilotStage(
                name="broader_institutional_deployment",
                allowed_data="approved_tenant_data_only",
                required_controls=("external_audit", "support_process", "source_update_notices"),
                exit_criteria=("legal_security_technical_diligence_passed",),
                real_matter_allowed=True,
            ),
        )

    def as_dict(self) -> dict[str, Any]:
        stages = self.stages()
        return {"stage_count": len(stages), "stages": [stage.as_dict() for stage in stages]}


@dataclass
class CorrectionTicket:
    ticket_id: str
    severity: str
    source: str
    description: str
    status: str = "open"
    blocks_release: bool = True

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class CorrectionWorkflow:
    def open_ticket(self, *, ticket_id: str, severity: str, source: str, description: str) -> CorrectionTicket:
        return CorrectionTicket(
            ticket_id=ticket_id,
            severity=severity,
            source=source,
            description=description,
            blocks_release=severity in {"critical", "high"},
        )

    def triage_summary(self, tickets: list[CorrectionTicket]) -> dict[str, Any]:
        blocking = [ticket for ticket in tickets if ticket.blocks_release and ticket.status != "closed"]
        return {
            "ticket_count": len(tickets),
            "blocking_ticket_count": len(blocking),
            "release_blocked": bool(blocking),
            "tickets": [ticket.as_dict() for ticket in tickets],
        }


class LaunchReadinessAuditor:
    """Honest launch readiness auditor for pilot/enterprise launch controls."""

    REQUIRED_OPERATIONS = {
        "support_process",
        "incident_response",
        "correction_workflow",
        "attorney_reviewer_workflow",
        "eval_set_expansion_policy",
        "release_notes",
        "source_update_notices",
        "model_update_notices",
        "rollback_plan",
        "admin_audit_access",
    }

    def audit(self, implemented: set[str]) -> dict[str, Any]:
        missing = sorted(self.REQUIRED_OPERATIONS - implemented)
        return {
            "status": "pass" if not missing else "incomplete",
            "implemented": sorted(implemented),
            "missing": missing,
            "release_blocked": bool(missing),
            "required_operations": sorted(self.REQUIRED_OPERATIONS),
        }



@dataclass(frozen=True)
class AttorneyPilotParticipant:
    participant_id: str
    role: str
    bar_status_verified: bool
    nda_or_terms_accepted: bool
    training_completed: bool
    allowed_scope: tuple[str, ...] = ("research", "review", "draft_review_required")

    def as_dict(self) -> dict[str, Any]:
        return {
            "participant_id": self.participant_id,
            "role": self.role,
            "bar_status_verified": self.bar_status_verified,
            "nda_or_terms_accepted": self.nda_or_terms_accepted,
            "training_completed": self.training_completed,
            "allowed_scope": list(self.allowed_scope),
        }


@dataclass(frozen=True)
class PilotFeedbackItem:
    feedback_id: str
    participant_id: str
    category: str
    severity: str
    description: str
    creates_eval_candidate: bool = True
    status: str = "open"

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class AttorneySandboxPilot:
    """Pass 48 attorney-only sandbox pilot controls.

    This layer deliberately permits only public authority and synthetic/sample matter
    data. It creates usable pilot artifacts (onboarding, training, feedback triage,
    review queue, and dashboard) without weakening review-required legal gates.
    """

    REQUIRED_TRAINING_MODULES = (
        "data_boundaries",
        "source_grounding",
        "citation_quote_verification",
        "review_required_exports",
        "feedback_and_error_reporting",
    )
    REQUIRED_DASHBOARD_SECTIONS = (
        "active_attorneys",
        "training_completion",
        "feedback_triage",
        "review_queue",
        "critical_safety_issues",
        "eval_candidates_created",
        "release_blockers",
    )

    def build_onboarding_packet(self, participants: list[AttorneyPilotParticipant]) -> dict[str, Any]:
        blocked = [
            p.participant_id
            for p in participants
            if not (p.bar_status_verified and p.nda_or_terms_accepted and p.training_completed)
        ]
        return {
            "stage": "attorney_only_sandbox",
            "allowed_data": "synthetic_or_public_authority_only",
            "real_matter_allowed": False,
            "participants": [p.as_dict() for p in participants],
            "training_modules": list(self.REQUIRED_TRAINING_MODULES),
            "blocked_participant_ids": blocked,
            "status": "pass" if not blocked and participants else "blocked",
        }

    def build_review_queue(self, items: list[PilotFeedbackItem]) -> dict[str, Any]:
        queue_rows = []
        for item in items:
            review_type = "eval_candidate_review" if item.creates_eval_candidate else "product_triage"
            queue_rows.append({
                **item.as_dict(),
                "review_type": review_type,
                "requires_attorney_review": True,
                "may_be_counted_as_gold": False,
                "private_data_allowed_for_training": False,
            })
        return {
            "queue_count": len(queue_rows),
            "rows": queue_rows,
            "status": "pass" if queue_rows else "blocked",
        }

    def build_dashboard(self, onboarding: dict[str, Any], feedback_items: list[PilotFeedbackItem], review_queue: dict[str, Any]) -> dict[str, Any]:
        critical_open = [
            item.feedback_id for item in feedback_items if item.severity == "critical" and item.status != "closed"
        ]
        high_open = [item.feedback_id for item in feedback_items if item.severity == "high" and item.status != "closed"]
        eval_candidates = [item.feedback_id for item in feedback_items if item.creates_eval_candidate]
        release_blockers = [*critical_open]
        return {
            "stage": "attorney_only_sandbox",
            "sections": list(self.REQUIRED_DASHBOARD_SECTIONS),
            "active_attorneys": len(onboarding.get("participants", [])) - len(onboarding.get("blocked_participant_ids", [])),
            "training_completion": onboarding.get("status") == "pass",
            "feedback_count": len(feedback_items),
            "review_queue_count": review_queue.get("queue_count", 0),
            "critical_safety_issues": critical_open,
            "high_safety_issues": high_open,
            "eval_candidates_created": eval_candidates,
            "release_blockers": release_blockers,
            "attorney_can_use_for_research_review": onboarding.get("status") == "pass" and not release_blockers,
            "status": "pass" if onboarding.get("status") == "pass" and review_queue.get("status") == "pass" and not release_blockers else "blocked",
        }


@dataclass(frozen=True)
class PrivacyConsentRecord:
    matter_id: str
    tenant_id: str
    participant_id: str
    consent_version: str
    explicit_real_matter_consent: bool
    training_use_allowed: bool = False
    export_restriction_acknowledged: bool = True
    human_review_required: bool = True

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class RealMatterPilotMatter:
    matter_id: str
    tenant_id: str
    participant_id: str
    artifacts_generated: tuple[str, ...]
    tenant_isolation_verified: bool
    encrypted_storage_verified: bool
    data_leakage_detected: bool = False
    unsupported_filing_ready_export_attempts: int = 0
    attorney_signed_off: bool = False
    daily_review_completed: bool = False
    incident_open: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "matter_id": self.matter_id,
            "tenant_id": self.tenant_id,
            "participant_id": self.participant_id,
            "artifacts_generated": list(self.artifacts_generated),
            "tenant_isolation_verified": self.tenant_isolation_verified,
            "encrypted_storage_verified": self.encrypted_storage_verified,
            "data_leakage_detected": self.data_leakage_detected,
            "unsupported_filing_ready_export_attempts": self.unsupported_filing_ready_export_attempts,
            "attorney_signed_off": self.attorney_signed_off,
            "daily_review_completed": self.daily_review_completed,
            "incident_open": self.incident_open,
        }


class LimitedRealMatterPilot:
    """Pass 49 limited real-matter pilot controls.

    The pilot is intentionally narrow: explicit consent, tenant allowlist, matter
    isolation, human review, export restrictions, incident process, and daily
    review are all mandatory before the stage can pass.
    """

    REQUIRED_ARTIFACTS = {
        "issue_tree",
        "posture_summary",
        "timeline",
        "evidence_map",
        "authority_matrix",
        "red_flag_report",
    }

    def audit(
        self,
        *,
        allowed_tenant_ids: set[str],
        consent_records: list[PrivacyConsentRecord],
        matters: list[RealMatterPilotMatter],
    ) -> dict[str, Any]:
        consent_by_matter = {record.matter_id: record for record in consent_records}
        blockers: list[str] = []
        matter_reports = []
        for matter in matters:
            record = consent_by_matter.get(matter.matter_id)
            missing_artifacts = sorted(self.REQUIRED_ARTIFACTS - set(matter.artifacts_generated))
            matter_blockers = []
            if matter.tenant_id not in allowed_tenant_ids:
                matter_blockers.append("tenant_not_in_limited_pilot_group")
            if record is None or not record.explicit_real_matter_consent:
                matter_blockers.append("missing_explicit_privacy_consent")
            if record is not None and record.training_use_allowed:
                matter_blockers.append("private_training_use_must_remain_false")
            if record is not None and not record.human_review_required:
                matter_blockers.append("human_review_not_required")
            if record is not None and not record.export_restriction_acknowledged:
                matter_blockers.append("export_restriction_not_acknowledged")
            if not matter.tenant_isolation_verified:
                matter_blockers.append("tenant_isolation_not_verified")
            if not matter.encrypted_storage_verified:
                matter_blockers.append("encrypted_storage_not_verified")
            if matter.data_leakage_detected:
                matter_blockers.append("data_leakage_detected")
            if matter.unsupported_filing_ready_export_attempts:
                matter_blockers.append("unsupported_filing_ready_export_attempt")
            if missing_artifacts:
                matter_blockers.append("missing_work_product_artifacts:" + ",".join(missing_artifacts))
            if not matter.daily_review_completed:
                matter_blockers.append("daily_pilot_review_missing")
            if matter.incident_open:
                matter_blockers.append("open_incident")
            if not matter.attorney_signed_off:
                matter_blockers.append("attorney_signoff_missing")
            matter_reports.append({
                **matter.as_dict(),
                "consent": record.as_dict() if record else None,
                "missing_artifacts": missing_artifacts,
                "blockers": matter_blockers,
                "status": "pass" if not matter_blockers else "blocked",
            })
            blockers.extend([f"{matter.matter_id}:{blocker}" for blocker in matter_blockers])
        return {
            "stage": "limited_real_matter_pilot",
            "allowed_tenant_ids": sorted(allowed_tenant_ids),
            "matter_count": len(matters),
            "matters": matter_reports,
            "human_review_required": True,
            "export_restrictions_enforced": True,
            "incident_process_required": True,
            "daily_pilot_review_required": True,
            "blockers": blockers,
            "status": "pass" if matters and not blockers else "blocked",
        }
