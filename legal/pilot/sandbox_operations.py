"""Pass 48 attorney-sandbox operations and immutable evidence packets.

The operational store coordinates real external attorney review without treating an
application event as proof of licensure, legal approval, or GA readiness.  Only
public-authority and synthetic review work is permitted.  Matter files and private
client content are refused.
"""

from __future__ import annotations

import html
import json
import os
import threading
from pathlib import Path
from typing import Any, Iterable

from legal.security.durable_io import (
    DurableIOError,
    durable_append_text,
    exclusive_file_lock,
    read_bounded_regular_file,
)
from legal.security.strict_json import StrictJSONError, strict_json_load_path, strict_json_loads

from legal.ops.release_pilot_hardening import (
    AttorneySandboxStore,
    ReleasePilotHardeningError,
    _EMAIL_RE,
    _HASH_RE,
    _SAFE_ID_RE,
    _SSN_RE,
    _WINDOWS_ABS_RE,
    _canonical_json,
    _now_iso,
    _safe_external_root,
    _sha_bytes,
    _sha_file,
    _write_json,
    find_source_root,
)
from legal.pilot.attorney_review_kit import AttorneySandboxReviewKitBuilder

MAX_OPERATIONS_ROWS = 50_000
MAX_REVIEW_COMMENT_CHARS = 2_000
MAX_QUESTION_ASSIGNMENTS = 250
MAX_PARTICIPANTS_PER_COHORT = 100
_OPERATIONS_LOCK = threading.RLock()


class AttorneySandboxOperationsError(ReleasePilotHardeningError):
    """Fail-closed operational error with an API-safe code."""


class AttorneySandboxOperationsStore:
    """Durable Pass 48 operations over the existing attorney-sandbox ledger.

    The participant and feedback ledger from :class:`AttorneySandboxStore` remains
    authoritative for basic eligibility and feedback capture.  This store adds the
    program, cohort, assignment, structured review, triage, eval-candidate, and
    immutable evidence-packet layers needed to run a bounded sandbox.
    """

    DISPOSITIONS = {
        "approved_for_sandbox",
        "needs_fix",
        "needs_more_authority",
        "unsafe_blocker",
        "not_in_scope",
    }
    FINDING_CODES = {
        "unsupported_claim",
        "partially_supported_claim",
        "fake_or_unresolved_citation",
        "quote_mismatch",
        "stale_or_unknown_authority",
        "jurisdiction_mismatch",
        "retrieval_miss",
        "missing_contrary_authority",
        "unsafe_filing_ready_boundary",
        "privacy_or_confidentiality_risk",
        "accessibility_issue",
        "workflow_confusion",
        "positive_review",
        "other_review_required",
    }
    TRIAGE_STATUSES = {
        "open",
        "acknowledged",
        "in_remediation",
        "fixed_pending_retest",
        "closed",
        "wont_fix_blocker",
    }
    ATTESTATION_TYPES = {"identity_audit", "program_signoff"}
    ARTIFACT_FILENAMES = {
        "attorney-sandbox-operations.json",
        "attorney-sandbox-operations.html",
        "attorney-sandbox-operations-receipt.json",
        "artifact-manifest.json",
    }

    def __init__(
        self,
        repo_root: str | Path,
        pilot_root: str | Path | None = None,
        *,
        policy_path: str | Path | None = None,
    ) -> None:
        self.repo_root = find_source_root(repo_root)
        configured = pilot_root or os.environ.get("MAINE_FAMILY_LAW_PILOT_ROOT")
        try:
            self.root = _safe_external_root(configured, repo_root=self.repo_root, create=bool(configured))
        except ReleasePilotHardeningError as exc:
            raise AttorneySandboxOperationsError(exc.code, status_code=exc.status_code) from exc
        self.ledger_path = self.root / "attorney-sandbox-operations-ledger.jsonl" if self.root else None
        self.evidence_root = self.root / "attorney-sandbox-evidence" if self.root else None
        self.policy_path = Path(policy_path) if policy_path else self.repo_root / "configs" / "maine_attorney_sandbox_operations_policy.json"
        self.policy = self._load_policy()
        self.sandbox = AttorneySandboxStore(self.repo_root, self.root)

    def _load_policy(self) -> dict[str, Any]:
        try:
            payload = strict_json_load_path(self.policy_path, max_bytes=2 * 1024 * 1024, require_object=True)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, StrictJSONError) as exc:
            raise AttorneySandboxOperationsError("sandbox_operations_policy_unavailable", status_code=409) from exc
        if not isinstance(payload, dict):
            raise AttorneySandboxOperationsError("sandbox_operations_policy_invalid", status_code=409)
        return payload

    @staticmethod
    def _safe_id(value: Any, code: str) -> str:
        text = str(value or "").strip()
        if not _SAFE_ID_RE.fullmatch(text):
            raise AttorneySandboxOperationsError(code, status_code=409)
        return text

    @staticmethod
    def _safe_hash(value: Any, code: str, *, required: bool = True) -> str:
        text = str(value or "").strip().casefold()
        if not text and not required:
            return ""
        if not _HASH_RE.fullmatch(text):
            raise AttorneySandboxOperationsError(code, status_code=409)
        return text

    @staticmethod
    def _safe_comment(value: Any) -> str:
        text = str(value or "").strip()[:MAX_REVIEW_COMMENT_CHARS]
        if not text:
            return ""
        if _EMAIL_RE.search(text) or _SSN_RE.search(text) or _WINDOWS_ABS_RE.search(text):
            raise AttorneySandboxOperationsError("sandbox_review_private_data_refused", status_code=409)
        lowered = text.casefold()
        forbidden_markers = (
            "client confidential",
            "sealed record",
            "juvenile record",
            "real matter",
            "social security number",
            "date of birth",
        )
        if any(marker in lowered for marker in forbidden_markers):
            raise AttorneySandboxOperationsError("sandbox_review_private_data_refused", status_code=409)
        return text

    def _rows(self, *, lock_held: bool = False) -> list[dict[str, Any]]:
        if self.ledger_path is None:
            return []
        if not lock_held:
            lock_path = self.ledger_path.with_name(self.ledger_path.name + ".lock")
            with exclusive_file_lock(lock_path):
                return self._rows(lock_held=True)
        if not self.ledger_path.exists():
            return []
        try:
            ledger_text = read_bounded_regular_file(
                self.ledger_path, max_bytes=50 * 1024 * 1024
            ).decode("utf-8")
        except (DurableIOError, UnicodeDecodeError) as exc:
            raise AttorneySandboxOperationsError("sandbox_operations_ledger_invalid", status_code=409) from exc
        rows: list[dict[str, Any]] = []
        for line in ledger_text.splitlines():
            if not line.strip():
                continue
            try:
                row = strict_json_loads(line, max_bytes=1024 * 1024, require_object=True)
            except (json.JSONDecodeError, StrictJSONError) as exc:
                raise AttorneySandboxOperationsError("sandbox_operations_ledger_invalid_json", status_code=409) from exc
            if not isinstance(row, dict):
                raise AttorneySandboxOperationsError("sandbox_operations_ledger_invalid_row", status_code=409)
            rows.append(row)
            if len(rows) > MAX_OPERATIONS_ROWS:
                raise AttorneySandboxOperationsError("sandbox_operations_ledger_row_limit_exceeded", status_code=409)
        return rows

    @staticmethod
    def _verify_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
        previous = "0" * 64
        blockers: list[str] = []
        for index, row in enumerate(rows, start=1):
            if int(row.get("sequence") or 0) != index:
                blockers.append(f"sequence_mismatch:{index}")
            if row.get("previous_sha256") != previous:
                blockers.append(f"chain_mismatch:{index}")
            supplied = str(row.get("record_sha256") or "")
            body = dict(row)
            body.pop("record_sha256", None)
            if supplied != _sha_bytes(_canonical_json(body)):
                blockers.append(f"hash_mismatch:{index}")
            previous = supplied
        return {
            "status": "pass" if not blockers else "blocked",
            "row_count": len(rows),
            "blockers": blockers,
            "latest_record_sha256": previous if rows else "",
        }

    def _append(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self.root is None or self.ledger_path is None:
            raise AttorneySandboxOperationsError("pilot_root_not_configured", status_code=409)
        lock_path = self.ledger_path.with_name(self.ledger_path.name + ".lock")
        with _OPERATIONS_LOCK, exclusive_file_lock(lock_path):
            rows = self._rows(lock_held=True)
            verification = self._verify_rows(rows)
            if verification["status"] != "pass":
                raise AttorneySandboxOperationsError("sandbox_operations_ledger_verification_failed", status_code=409)
            previous = str(rows[-1].get("record_sha256") or "") if rows else "0" * 64
            body = {
                "schema_version": "attorney_sandbox_operations_event_v1",
                "sequence": len(rows) + 1,
                "event_type": event_type,
                "recorded_at": _now_iso(),
                "previous_sha256": previous,
                **payload,
            }
            body["record_sha256"] = _sha_bytes(_canonical_json(body))
            self.root.mkdir(parents=True, exist_ok=True)
            try:
                durable_append_text(
                    self.ledger_path,
                    json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n",
                )
            except DurableIOError as exc:
                raise AttorneySandboxOperationsError("sandbox_operations_ledger_invalid", status_code=409) from exc
            return body

    def verify(self) -> dict[str, Any]:
        return self._verify_rows(self._rows())

    def _question_catalog(self, max_questions: int | None = None) -> list[dict[str, Any]]:
        policy_max = int(self.policy.get("maximum_review_questions") or 48)
        requested = policy_max if max_questions is None else int(max_questions)
        bounded = max(1, min(requested, policy_max, MAX_QUESTION_ASSIGNMENTS))
        queue = AttorneySandboxReviewKitBuilder().build_question_queue(max_questions=bounded)
        catalog: list[dict[str, Any]] = []
        for row in queue:
            prompt = str(row.get("prompt") or "")
            catalog.append({
                "question_id": self._safe_id(row.get("question_id"), "sandbox_question_id_invalid"),
                "topic": str(row.get("topic") or "")[:128],
                "audience": str(row.get("audience") or "")[:128],
                "title": str(row.get("title") or "")[:256],
                "prompt_sha256": _sha_bytes(prompt.encode("utf-8")),
                "expected_source_terms": sorted({str(item)[:128] for item in row.get("expected_source_terms", []) if str(item).strip()}),
                "review_focus": sorted({str(item)[:128] for item in row.get("review_focus", []) if str(item).strip()}),
                "real_matter_allowed": False,
            })
        return catalog

    def create_program(self, *, program_id: str, max_questions: int = 48, approved: bool) -> dict[str, Any]:
        if approved is not True:
            raise AttorneySandboxOperationsError("sandbox_program_approval_required", status_code=409)
        program_id = self._safe_id(program_id, "sandbox_program_id_invalid")
        rows = self._rows()
        if any(row.get("event_type") == "program_created" and row.get("program_id") == program_id for row in rows):
            raise AttorneySandboxOperationsError("sandbox_program_already_exists", status_code=409)
        catalog = self._question_catalog(max_questions)
        queue_sha256 = _sha_bytes(_canonical_json(catalog))
        return self._append("program_created", {
            "program_id": program_id,
            "policy_version": str(self.policy.get("version") or "unknown"),
            "question_count": len(catalog),
            "question_queue_sha256": queue_sha256,
            "questions": catalog,
            "allowed_data": ["synthetic", "public_authority"],
            "real_matter_allowed": False,
            "outputs_review_required": True,
            "application_does_not_verify_licensure": True,
        })

    def _latest_program(self, program_id: str) -> dict[str, Any] | None:
        matches = [row for row in self._rows() if row.get("event_type") == "program_created" and row.get("program_id") == program_id]
        return matches[-1] if matches else None

    def _eligible_participants(self) -> dict[str, dict[str, Any]]:
        verification = self.sandbox.verify()
        if verification["status"] != "pass":
            raise AttorneySandboxOperationsError("participant_ledger_verification_failed", status_code=409)
        rows = self.sandbox._rows()
        latest: dict[str, dict[str, Any]] = {}
        for row in rows:
            if row.get("event_type") == "participant_registered":
                latest[str(row.get("participant_id") or "")] = row
        return {key: row for key, row in latest.items() if row.get("sandbox_eligible") is True}

    def create_cohort(
        self,
        *,
        program_id: str,
        cohort_id: str,
        participant_ids: Iterable[str],
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise AttorneySandboxOperationsError("sandbox_cohort_approval_required", status_code=409)
        program_id = self._safe_id(program_id, "sandbox_program_id_invalid")
        cohort_id = self._safe_id(cohort_id, "sandbox_cohort_id_invalid")
        if self._latest_program(program_id) is None:
            raise AttorneySandboxOperationsError("sandbox_program_not_available", status_code=404)
        participants = sorted({self._safe_id(value, "pilot_participant_id_invalid") for value in participant_ids})
        if not participants or len(participants) > MAX_PARTICIPANTS_PER_COHORT:
            raise AttorneySandboxOperationsError("sandbox_cohort_participant_count_invalid", status_code=409)
        eligible = self._eligible_participants()
        ineligible = [participant_id for participant_id in participants if participant_id not in eligible]
        if ineligible:
            raise AttorneySandboxOperationsError("sandbox_cohort_contains_ineligible_participant", status_code=409)
        if any(row.get("event_type") == "cohort_created" and row.get("cohort_id") == cohort_id for row in self._rows()):
            raise AttorneySandboxOperationsError("sandbox_cohort_already_exists", status_code=409)
        return self._append("cohort_created", {
            "program_id": program_id,
            "cohort_id": cohort_id,
            "participant_ids": participants,
            "participant_count": len(participants),
            "real_matter_allowed": False,
        })

    def _latest_cohort(self, cohort_id: str) -> dict[str, Any] | None:
        matches = [row for row in self._rows() if row.get("event_type") == "cohort_created" and row.get("cohort_id") == cohort_id]
        return matches[-1] if matches else None

    def create_assignment(
        self,
        *,
        program_id: str,
        cohort_id: str,
        participant_id: str,
        question_ids: Iterable[str],
        data_classification: str,
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise AttorneySandboxOperationsError("sandbox_assignment_approval_required", status_code=409)
        program_id = self._safe_id(program_id, "sandbox_program_id_invalid")
        cohort_id = self._safe_id(cohort_id, "sandbox_cohort_id_invalid")
        participant_id = self._safe_id(participant_id, "pilot_participant_id_invalid")
        program = self._latest_program(program_id)
        cohort = self._latest_cohort(cohort_id)
        if program is None or cohort is None or cohort.get("program_id") != program_id:
            raise AttorneySandboxOperationsError("sandbox_program_or_cohort_not_available", status_code=404)
        if participant_id not in set(cohort.get("participant_ids") or []):
            raise AttorneySandboxOperationsError("sandbox_participant_not_in_cohort", status_code=409)
        requested = sorted({self._safe_id(value, "sandbox_question_id_invalid") for value in question_ids})
        if not requested or len(requested) > MAX_QUESTION_ASSIGNMENTS:
            raise AttorneySandboxOperationsError("sandbox_assignment_question_count_invalid", status_code=409)
        catalog = {str(row.get("question_id")): row for row in program.get("questions", []) if isinstance(row, dict)}
        unknown = [question_id for question_id in requested if question_id not in catalog]
        if unknown:
            raise AttorneySandboxOperationsError("sandbox_assignment_unknown_question", status_code=409)
        session = self.sandbox.start_session(
            participant_id=participant_id,
            data_classification=data_classification,
            approved=True,
        )
        return self._append("assignment_created", {
            "program_id": program_id,
            "cohort_id": cohort_id,
            "session_id": str(session.get("session_id") or ""),
            "participant_id": participant_id,
            "data_classification": str(session.get("data_classification") or ""),
            "question_ids": requested,
            "question_count": len(requested),
            "question_queue_sha256": str(program.get("question_queue_sha256") or ""),
            "real_matter_allowed": False,
            "exports_review_required": True,
        })

    def _assignment(self, session_id: str) -> dict[str, Any] | None:
        matches = [row for row in self._rows() if row.get("event_type") == "assignment_created" and row.get("session_id") == session_id]
        return matches[-1] if matches else None

    @staticmethod
    def _rating(value: Any, name: str) -> int:
        try:
            rating = int(value)
        except (TypeError, ValueError) as exc:
            raise AttorneySandboxOperationsError(f"sandbox_review_{name}_rating_invalid", status_code=409) from exc
        if rating < 1 or rating > 5:
            raise AttorneySandboxOperationsError(f"sandbox_review_{name}_rating_invalid", status_code=409)
        return rating

    def submit_review(
        self,
        *,
        participant_id: str,
        session_id: str,
        question_id: str,
        disposition: str,
        source_grounding_rating: int,
        legal_accuracy_rating: int,
        usefulness_rating: int,
        boundary_safety_rating: int,
        citation_quality_rating: int,
        finding_codes: Iterable[str],
        response_artifact_sha256: str,
        verifier_report_sha256: str,
        comment: str = "",
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise AttorneySandboxOperationsError("sandbox_review_approval_required", status_code=409)
        participant_id = self._safe_id(participant_id, "pilot_participant_id_invalid")
        session_id = self._safe_id(session_id, "pilot_session_id_invalid")
        question_id = self._safe_id(question_id, "sandbox_question_id_invalid")
        disposition = str(disposition or "").strip().casefold()
        if disposition not in self.DISPOSITIONS:
            raise AttorneySandboxOperationsError("sandbox_review_disposition_invalid", status_code=409)
        assignment = self._assignment(session_id)
        if assignment is None or assignment.get("participant_id") != participant_id:
            raise AttorneySandboxOperationsError("sandbox_assignment_not_available", status_code=404)
        if any(row.get("event_type") == "session_completed" and row.get("session_id") == session_id for row in self._rows()):
            raise AttorneySandboxOperationsError("sandbox_session_already_completed", status_code=409)
        if question_id not in set(assignment.get("question_ids") or []):
            raise AttorneySandboxOperationsError("sandbox_question_not_assigned", status_code=409)
        findings = sorted({str(item or "").strip().casefold() for item in finding_codes if str(item or "").strip()})
        if any(item not in self.FINDING_CODES for item in findings):
            raise AttorneySandboxOperationsError("sandbox_review_finding_code_invalid", status_code=409)
        ratings = {
            "source_grounding": self._rating(source_grounding_rating, "source_grounding"),
            "legal_accuracy": self._rating(legal_accuracy_rating, "legal_accuracy"),
            "usefulness": self._rating(usefulness_rating, "usefulness"),
            "boundary_safety": self._rating(boundary_safety_rating, "boundary_safety"),
            "citation_quality": self._rating(citation_quality_rating, "citation_quality"),
        }
        return self._append("review_submitted", {
            "participant_id": participant_id,
            "session_id": session_id,
            "program_id": str(assignment.get("program_id") or ""),
            "cohort_id": str(assignment.get("cohort_id") or ""),
            "question_id": question_id,
            "disposition": disposition,
            "ratings": ratings,
            "finding_codes": findings,
            "response_artifact_sha256": self._safe_hash(response_artifact_sha256, "sandbox_review_response_hash_invalid"),
            "verifier_report_sha256": self._safe_hash(verifier_report_sha256, "sandbox_review_verifier_hash_invalid"),
            "comment": self._safe_comment(comment),
            "requires_attorney_review": True,
            "may_be_counted_as_gold": False,
            "private_data_allowed_for_training": False,
            "blocks_release": disposition == "unsafe_blocker" or "unsafe_filing_ready_boundary" in findings or "privacy_or_confidentiality_risk" in findings,
        })

    def complete_session(self, *, participant_id: str, session_id: str, approved: bool) -> dict[str, Any]:
        if approved is not True:
            raise AttorneySandboxOperationsError("sandbox_session_completion_approval_required", status_code=409)
        participant_id = self._safe_id(participant_id, "pilot_participant_id_invalid")
        session_id = self._safe_id(session_id, "pilot_session_id_invalid")
        assignment = self._assignment(session_id)
        if assignment is None or assignment.get("participant_id") != participant_id:
            raise AttorneySandboxOperationsError("sandbox_assignment_not_available", status_code=404)
        latest_reviews: dict[str, dict[str, Any]] = {}
        for row in self._rows():
            if row.get("event_type") == "review_submitted" and row.get("session_id") == session_id:
                latest_reviews[str(row.get("question_id") or "")] = row
        assigned = set(assignment.get("question_ids") or [])
        missing = sorted(assigned - set(latest_reviews))
        if missing:
            raise AttorneySandboxOperationsError("sandbox_session_reviews_incomplete", status_code=409)
        if any(row.get("event_type") == "session_completed" and row.get("session_id") == session_id for row in self._rows()):
            raise AttorneySandboxOperationsError("sandbox_session_already_completed", status_code=409)
        dispositions: dict[str, int] = {}
        for row in latest_reviews.values():
            value = str(row.get("disposition") or "unknown")
            dispositions[value] = dispositions.get(value, 0) + 1
        return self._append("session_completed", {
            "participant_id": participant_id,
            "session_id": session_id,
            "program_id": str(assignment.get("program_id") or ""),
            "cohort_id": str(assignment.get("cohort_id") or ""),
            "review_count": len(latest_reviews),
            "disposition_counts": dict(sorted(dispositions.items())),
            "all_assigned_questions_reviewed": True,
            "real_matter_used": False,
            "outputs_remain_review_required": True,
        })

    def triage_feedback(
        self,
        *,
        feedback_id: str,
        status: str,
        disposition_note: str,
        remediation_evidence_sha256: str = "",
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise AttorneySandboxOperationsError("sandbox_feedback_triage_approval_required", status_code=409)
        feedback_id = self._safe_id(feedback_id, "pilot_feedback_id_invalid")
        status = str(status or "").strip().casefold()
        if status not in self.TRIAGE_STATUSES:
            raise AttorneySandboxOperationsError("sandbox_feedback_triage_status_invalid", status_code=409)
        if self.sandbox.verify()["status"] != "pass":
            raise AttorneySandboxOperationsError("participant_ledger_verification_failed", status_code=409)
        feedback_rows = [row for row in self.sandbox._rows() if row.get("event_type") == "feedback_recorded" and row.get("feedback_id") == feedback_id]
        if not feedback_rows:
            raise AttorneySandboxOperationsError("sandbox_feedback_not_available", status_code=404)
        feedback = feedback_rows[-1]
        prior_rows = [row for row in self._rows() if row.get("event_type") == "feedback_triaged" and row.get("feedback_id") == feedback_id]
        prior = str(prior_rows[-1].get("status") or "open") if prior_rows else "open"
        transitions = {
            "open": {"acknowledged", "in_remediation", "wont_fix_blocker"},
            "acknowledged": {"in_remediation", "wont_fix_blocker"},
            "in_remediation": {"fixed_pending_retest", "wont_fix_blocker"},
            "fixed_pending_retest": {"closed", "in_remediation", "wont_fix_blocker"},
            "closed": set(),
            "wont_fix_blocker": {"in_remediation"},
        }
        if status not in transitions.get(prior, set()):
            raise AttorneySandboxOperationsError("sandbox_feedback_triage_transition_invalid", status_code=409)
        evidence_hash = self._safe_hash(
            remediation_evidence_sha256,
            "sandbox_feedback_remediation_hash_invalid",
            required=status in {"fixed_pending_retest", "closed"} or str(feedback.get("severity")) in {"high", "critical"} and status == "closed",
        )
        return self._append("feedback_triaged", {
            "feedback_id": feedback_id,
            "severity": str(feedback.get("severity") or ""),
            "prior_status": prior,
            "status": status,
            "disposition_note": self._safe_comment(disposition_note),
            "remediation_evidence_sha256": evidence_hash,
            "blocks_release": status != "closed" and (feedback.get("blocks_release") is True or status == "wont_fix_blocker"),
        })

    def record_external_attestation(
        self,
        *,
        attestation_type: str,
        evidence_sha256: str,
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise AttorneySandboxOperationsError("sandbox_attestation_approval_required", status_code=409)
        attestation_type = str(attestation_type or "").strip().casefold()
        if attestation_type not in self.ATTESTATION_TYPES:
            raise AttorneySandboxOperationsError("sandbox_attestation_type_invalid", status_code=409)
        return self._append("external_attestation_recorded", {
            "attestation_type": attestation_type,
            "evidence_sha256": self._safe_hash(evidence_sha256, "sandbox_attestation_hash_invalid"),
            "application_verified_underlying_evidence": False,
            "external_gate_review_required": True,
        })

    def _latest_reviews(self) -> dict[tuple[str, str], dict[str, Any]]:
        latest: dict[tuple[str, str], dict[str, Any]] = {}
        for row in self._rows():
            if row.get("event_type") == "review_submitted":
                latest[(str(row.get("session_id") or ""), str(row.get("question_id") or ""))] = row
        return latest

    def _triage_by_feedback(self) -> dict[str, dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        for row in self._rows():
            if row.get("event_type") == "feedback_triaged":
                latest[str(row.get("feedback_id") or "")] = row
        return latest

    def status(self) -> dict[str, Any]:
        rows = self._rows()
        verification = self.verify()
        participant_verification = self.sandbox.verify()
        eligible = self._eligible_participants()
        programs = [row for row in rows if row.get("event_type") == "program_created"]
        cohorts = [row for row in rows if row.get("event_type") == "cohort_created"]
        assignments = [row for row in rows if row.get("event_type") == "assignment_created"]
        completions = [row for row in rows if row.get("event_type") == "session_completed"]
        latest_reviews = self._latest_reviews()
        triage = self._triage_by_feedback()
        feedback = [row for row in self.sandbox._rows() if row.get("event_type") == "feedback_recorded"]
        open_feedback_blockers: list[str] = []
        for row in feedback:
            feedback_id = str(row.get("feedback_id") or "")
            current = str((triage.get(feedback_id) or {}).get("status") or row.get("status") or "open")
            if row.get("blocks_release") is True and current != "closed":
                open_feedback_blockers.append(feedback_id)
        unsafe_reviews = sorted({
            f"{row.get('session_id')}:{row.get('question_id')}"
            for row in latest_reviews.values()
            if row.get("blocks_release") is True
        })
        attestation_types = {
            str(row.get("attestation_type") or "")
            for row in rows
            if row.get("event_type") == "external_attestation_recorded"
        }
        assigned_question_count = sum(int(row.get("question_count") or 0) for row in assignments)
        review_count = len(latest_reviews)
        coverage = round((review_count / assigned_question_count) * 100.0, 2) if assigned_question_count else 0.0
        minimum_reviewers = int(self.policy.get("minimum_eligible_reviewers") or 2)
        minimum_sessions = int(self.policy.get("minimum_completed_sessions") or 2)
        minimum_reviews = int(self.policy.get("minimum_completed_reviews") or 12)
        blockers: list[str] = []
        if self.root is None:
            blockers.append("pilot_root_not_configured")
        if verification["status"] != "pass":
            blockers.append("operations_ledger_verification_failed")
        if participant_verification["status"] != "pass":
            blockers.append("participant_ledger_verification_failed")
        if not programs:
            blockers.append("sandbox_program_not_created")
        if len(eligible) < minimum_reviewers:
            blockers.append("minimum_eligible_reviewers_not_met")
        if not cohorts:
            blockers.append("sandbox_cohort_not_created")
        if len(completions) < minimum_sessions:
            blockers.append("minimum_completed_sessions_not_met")
        if review_count < minimum_reviews:
            blockers.append("minimum_completed_reviews_not_met")
        if assigned_question_count and coverage < 100.0:
            blockers.append("assigned_review_coverage_incomplete")
        blockers.extend(f"open_feedback_blocker:{item}" for item in sorted(open_feedback_blockers))
        blockers.extend(f"unsafe_review_blocker:{item}" for item in unsafe_reviews)
        if "identity_audit" not in attestation_types:
            blockers.append("external_identity_audit_missing")
        if "program_signoff" not in attestation_types:
            blockers.append("external_program_signoff_missing")
        return {
            "schema_version": "attorney_sandbox_operations_status_v1",
            "status": "ready_for_external_pass48_gate" if not blockers else "blocked",
            "stage": "attorney_only_sandbox_operations",
            "policy_version": str(self.policy.get("version") or "unknown"),
            "root_configured": self.root is not None,
            "program_count": len(programs),
            "cohort_count": len(cohorts),
            "eligible_participant_count": len(eligible),
            "assignment_count": len(assignments),
            "completed_session_count": len(completions),
            "assigned_question_count": assigned_question_count,
            "completed_review_count": review_count,
            "review_coverage_percent": coverage,
            "feedback_count": len(feedback),
            "open_feedback_blockers": sorted(open_feedback_blockers),
            "unsafe_review_blockers": unsafe_reviews,
            "external_attestations": sorted(attestation_types),
            "minimums": {
                "eligible_reviewers": minimum_reviewers,
                "completed_sessions": minimum_sessions,
                "completed_reviews": minimum_reviews,
            },
            "blockers": blockers,
            "operations_ledger": verification,
            "participant_ledger": participant_verification,
            "real_matter_allowed": False,
            "private_data_allowed_for_training": False,
            "all_outputs_review_required": True,
            "application_independently_verifies_attorney_identity": False,
            "pass48_complete": False,
            "external_launch_evidence_gate_required": True,
        }

    def export_eval_candidates(self, eval_root: str | Path, *, approved: bool) -> dict[str, Any]:
        if approved is not True:
            raise AttorneySandboxOperationsError("sandbox_eval_export_approval_required", status_code=409)
        if self.root is None:
            raise AttorneySandboxOperationsError("pilot_root_not_configured", status_code=409)
        try:
            target = _safe_external_root(eval_root, repo_root=self.repo_root, create=True)
        except ReleasePilotHardeningError as exc:
            raise AttorneySandboxOperationsError(exc.code, status_code=exc.status_code) from exc
        if target is None:
            raise AttorneySandboxOperationsError("sandbox_eval_root_not_configured", status_code=409)
        latest_reviews = self._latest_reviews()
        candidates: list[dict[str, Any]] = []
        for row in latest_reviews.values():
            if row.get("disposition") in {"needs_fix", "needs_more_authority", "unsafe_blocker"} or row.get("finding_codes"):
                candidates.append({
                    "candidate_id": f"sandbox-review-{row.get('record_sha256')}",
                    "source": "attorney_sandbox_review",
                    "program_id": row.get("program_id"),
                    "session_id": row.get("session_id"),
                    "question_id": row.get("question_id"),
                    "disposition": row.get("disposition"),
                    "finding_codes": row.get("finding_codes") or [],
                    "response_artifact_sha256": row.get("response_artifact_sha256"),
                    "verifier_report_sha256": row.get("verifier_report_sha256"),
                    "review_status": "needs_attorney_review",
                    "may_be_counted_as_gold": False,
                    "private_data_allowed_for_training": False,
                })
        candidates.sort(key=lambda row: str(row.get("candidate_id") or ""))
        payload_bytes = b"".join(_canonical_json(row) + b"\n" for row in candidates)
        generation_id = _sha_bytes(payload_bytes or b"empty-attorney-sandbox-eval-candidates")
        parent = target / "attorney_sandbox_eval_candidates"
        if parent.exists() and parent.is_symlink():
            raise AttorneySandboxOperationsError("sandbox_eval_artifact_symlink_refused", status_code=409)
        generation = parent / generation_id
        if generation.exists() and generation.is_symlink():
            raise AttorneySandboxOperationsError("sandbox_eval_artifact_symlink_refused", status_code=409)
        generation.mkdir(parents=True, exist_ok=True)
        data_path = generation / "candidates.jsonl"
        if data_path.exists() and data_path.is_symlink():
            raise AttorneySandboxOperationsError("sandbox_eval_artifact_symlink_refused", status_code=409)
        if data_path.exists() and data_path.read_bytes() != payload_bytes:
            raise AttorneySandboxOperationsError("sandbox_eval_generation_collision", status_code=409)
        data_path.write_bytes(payload_bytes)
        manifest = {
            "schema_version": "attorney_sandbox_eval_candidate_manifest_v1",
            "generation_id": generation_id,
            "candidate_count": len(candidates),
            "candidates_sha256": _sha_bytes(payload_bytes),
            "review_status": "needs_attorney_review",
            "may_be_counted_as_gold": False,
            "private_data_allowed_for_training": False,
        }
        _write_json(generation / "manifest.json", manifest)
        event = self._append("eval_candidates_exported", {
            "generation_id": generation_id,
            "candidate_count": len(candidates),
            "candidates_sha256": manifest["candidates_sha256"],
            "may_be_counted_as_gold": False,
        })
        return {**manifest, "event_record_sha256": event["record_sha256"]}

    def _evidence_snapshot(self) -> dict[str, Any]:
        status = self.status()
        rows = self._rows()
        latest_review_rows = list(self._latest_reviews().values())
        snapshot = {
            "schema_version": "attorney_sandbox_operations_evidence_v1",
            "stage": "attorney_only_sandbox_operations",
            "policy_version": str(self.policy.get("version") or "unknown"),
            "status": status,
            "programs": [
                {
                    "program_id": row.get("program_id"),
                    "question_count": row.get("question_count"),
                    "question_queue_sha256": row.get("question_queue_sha256"),
                    "record_sha256": row.get("record_sha256"),
                }
                for row in rows if row.get("event_type") == "program_created"
            ],
            "cohorts": [
                {
                    "cohort_id": row.get("cohort_id"),
                    "program_id": row.get("program_id"),
                    "participant_count": row.get("participant_count"),
                    "record_sha256": row.get("record_sha256"),
                }
                for row in rows if row.get("event_type") == "cohort_created"
            ],
            "assignments": [
                {
                    "session_id": row.get("session_id"),
                    "program_id": row.get("program_id"),
                    "cohort_id": row.get("cohort_id"),
                    "participant_id_hash": _sha_bytes(str(row.get("participant_id") or "").encode("utf-8")),
                    "question_count": row.get("question_count"),
                    "record_sha256": row.get("record_sha256"),
                }
                for row in rows if row.get("event_type") == "assignment_created"
            ],
            "reviews": [
                {
                    "session_id": row.get("session_id"),
                    "question_id": row.get("question_id"),
                    "disposition": row.get("disposition"),
                    "ratings": row.get("ratings"),
                    "finding_codes": row.get("finding_codes"),
                    "response_artifact_sha256": row.get("response_artifact_sha256"),
                    "verifier_report_sha256": row.get("verifier_report_sha256"),
                    "record_sha256": row.get("record_sha256"),
                }
                for row in sorted(latest_review_rows, key=lambda item: (str(item.get("session_id")), str(item.get("question_id"))))
            ],
            "completed_sessions": [
                {
                    "session_id": row.get("session_id"),
                    "review_count": row.get("review_count"),
                    "disposition_counts": row.get("disposition_counts"),
                    "record_sha256": row.get("record_sha256"),
                }
                for row in rows if row.get("event_type") == "session_completed"
            ],
            "attestations": [
                {
                    "attestation_type": row.get("attestation_type"),
                    "evidence_sha256": row.get("evidence_sha256"),
                    "record_sha256": row.get("record_sha256"),
                }
                for row in rows if row.get("event_type") == "external_attestation_recorded"
            ],
            "operations_ledger_head_sha256": self.verify().get("latest_record_sha256") or "",
            "participant_ledger_head_sha256": self.sandbox.verify().get("latest_record_sha256") or "",
            "honesty_boundary": {
                "pass48_complete": False,
                "real_matter_allowed": False,
                "attorney_identity_independently_verified_by_application": False,
                "external_launch_evidence_gate_required": True,
            },
        }
        return snapshot

    @staticmethod
    def _render_html(snapshot: dict[str, Any]) -> str:
        status = snapshot.get("status") or {}
        blockers = status.get("blockers") or []
        rows = "".join(f"<li>{html.escape(str(item))}</li>" for item in blockers) or "<li>None reported by the operational store.</li>"
        return (
            "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Attorney Sandbox Operations Evidence</title>"
            "<style>body{font:16px/1.5 system-ui;margin:2rem;max-width:72rem}code{overflow-wrap:anywhere}"
            "table{border-collapse:collapse;width:100%}th,td{border:1px solid #bbb;padding:.5rem;text-align:left}"
            ".warn{border-left:.35rem solid #9b4d00;padding:1rem;background:#fff7ed}</style></head><body>"
            "<h1>Attorney Sandbox Operations Evidence</h1>"
            "<div class=\"warn\"><strong>External review required.</strong> This packet does not prove attorney identity, "
            "complete Pass 48, permit real matters, or make any output filing-ready.</div>"
            f"<p>Status: <strong>{html.escape(str(status.get('status') or 'blocked'))}</strong></p>"
            "<table><tbody>"
            f"<tr><th>Eligible reviewers</th><td>{int(status.get('eligible_participant_count') or 0)}</td></tr>"
            f"<tr><th>Completed sessions</th><td>{int(status.get('completed_session_count') or 0)}</td></tr>"
            f"<tr><th>Completed reviews</th><td>{int(status.get('completed_review_count') or 0)}</td></tr>"
            f"<tr><th>Review coverage</th><td>{html.escape(str(status.get('review_coverage_percent') or 0))}%</td></tr>"
            "</tbody></table><h2>Blockers</h2><ul>" + rows + "</ul>"
            f"<p>Operations ledger head: <code>{html.escape(str(snapshot.get('operations_ledger_head_sha256') or ''))}</code></p>"
            f"<p>Participant ledger head: <code>{html.escape(str(snapshot.get('participant_ledger_head_sha256') or ''))}</code></p>"
            "</body></html>"
        )

    def build_evidence_packet(self, *, approved: bool) -> dict[str, Any]:
        if approved is not True:
            raise AttorneySandboxOperationsError("sandbox_evidence_build_approval_required", status_code=409)
        if self.evidence_root is None:
            raise AttorneySandboxOperationsError("pilot_root_not_configured", status_code=409)
        if self.evidence_root.exists() and self.evidence_root.is_symlink():
            raise AttorneySandboxOperationsError("sandbox_evidence_root_symlink_refused", status_code=409)
        snapshot = self._evidence_snapshot()
        packet_bytes = json.dumps(snapshot, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
        html_bytes = self._render_html(snapshot).encode("utf-8")
        state_hash = _sha_bytes(_canonical_json(snapshot))
        generation_id = state_hash
        generation = self.evidence_root / generation_id
        if generation.exists() and generation.is_symlink():
            raise AttorneySandboxOperationsError("sandbox_evidence_generation_symlink_refused", status_code=409)
        generation.mkdir(parents=True, exist_ok=True)
        packet_name = "attorney-sandbox-operations.json"
        html_name = "attorney-sandbox-operations.html"
        receipt_name = "attorney-sandbox-operations-receipt.json"
        packet_path = generation / packet_name
        html_path = generation / html_name
        for path, data in ((packet_path, packet_bytes), (html_path, html_bytes)):
            if path.exists() and path.is_symlink():
                raise AttorneySandboxOperationsError("sandbox_evidence_artifact_symlink_refused", status_code=409)
            if path.exists() and path.read_bytes() != data:
                raise AttorneySandboxOperationsError("sandbox_evidence_generation_collision", status_code=409)
            path.write_bytes(data)
        receipt = {
            "schema_version": "attorney_sandbox_operations_receipt_v1",
            "generation_id": generation_id,
            "state_sha256": state_hash,
            "packet_sha256": _sha_bytes(packet_bytes),
            "html_sha256": _sha_bytes(html_bytes),
            "operations_ledger_head_sha256": snapshot.get("operations_ledger_head_sha256"),
            "participant_ledger_head_sha256": snapshot.get("participant_ledger_head_sha256"),
            "pass48_complete": False,
            "external_launch_evidence_gate_required": True,
        }
        receipt_path = generation / receipt_name
        _write_json(receipt_path, receipt)
        manifest_rows = []
        for name in (packet_name, html_name, receipt_name):
            path = generation / name
            manifest_rows.append({"filename": name, "sha256": _sha_file(path), "size_bytes": path.stat().st_size})
        manifest = {
            "schema_version": "attorney_sandbox_operations_artifact_manifest_v1",
            "generation_id": generation_id,
            "artifacts": manifest_rows,
        }
        manifest_path = generation / "artifact-manifest.json"
        _write_json(manifest_path, manifest)
        verification = self.verify_evidence_packet(generation_id)
        return {
            "schema_version": "attorney_sandbox_operations_build_result_v1",
            "generation_id": generation_id,
            "status": verification["status"],
            "verification": verification,
            "artifacts": [*manifest_rows, {"filename": "artifact-manifest.json", "sha256": _sha_file(manifest_path), "size_bytes": manifest_path.stat().st_size}],
            "artifact_manifest_sha256": _sha_file(manifest_path),
            "pass48_complete": False,
            "external_launch_evidence_gate_required": True,
        }

    def verify_evidence_packet(self, generation_id: str) -> dict[str, Any]:
        generation_id = self._safe_hash(generation_id, "sandbox_evidence_generation_id_invalid")
        if self.evidence_root is None:
            raise AttorneySandboxOperationsError("pilot_root_not_configured", status_code=409)
        generation = self.evidence_root / generation_id
        if not generation.is_dir() or generation.is_symlink():
            raise AttorneySandboxOperationsError("sandbox_evidence_generation_not_available", status_code=404)
        manifest_path = generation / "artifact-manifest.json"
        if not manifest_path.is_file() or manifest_path.is_symlink():
            raise AttorneySandboxOperationsError("sandbox_evidence_manifest_not_available", status_code=404)
        try:
            manifest = strict_json_loads(manifest_path.read_bytes(), max_bytes=8 * 1024 * 1024, require_object=True)
        except (UnicodeDecodeError, json.JSONDecodeError, StrictJSONError) as exc:
            raise AttorneySandboxOperationsError("sandbox_evidence_manifest_invalid", status_code=409) from exc
        blockers: list[str] = []
        if str((manifest or {}).get("generation_id") or "") != generation_id:
            blockers.append("artifact_manifest_generation_mismatch")
        entries = manifest.get("artifacts") if isinstance(manifest, dict) else None
        if not isinstance(entries, list):
            entries = []
            blockers.append("artifact_manifest_rows_missing")
        expected = self.ARTIFACT_FILENAMES - {"artifact-manifest.json"}
        seen: set[str] = set()
        for row in entries:
            if not isinstance(row, dict):
                blockers.append("artifact_manifest_row_invalid")
                continue
            name = str(row.get("filename") or "")
            if name in seen:
                blockers.append(f"artifact_manifest_duplicate:{name}")
                continue
            seen.add(name)
            if name not in expected:
                blockers.append(f"artifact_manifest_unexpected:{name}")
                continue
            path = generation / name
            if not path.is_file() or path.is_symlink():
                blockers.append(f"artifact_missing_or_symlink:{name}")
                continue
            if path.stat().st_size != int(row.get("size_bytes") or -1):
                blockers.append(f"artifact_size_mismatch:{name}")
            if _sha_file(path) != str(row.get("sha256") or ""):
                blockers.append(f"artifact_hash_mismatch:{name}")
        if seen != expected:
            blockers.append("artifact_manifest_set_mismatch")
        try:
            receipt = strict_json_loads((generation / "attorney-sandbox-operations-receipt.json").read_bytes(), max_bytes=16 * 1024 * 1024, require_object=True)
            packet = strict_json_loads((generation / "attorney-sandbox-operations.json").read_bytes(), max_bytes=16 * 1024 * 1024, require_object=True)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, StrictJSONError) as exc:
            raise AttorneySandboxOperationsError("sandbox_evidence_payload_invalid", status_code=409) from exc
        packet_state_sha256 = _sha_bytes(_canonical_json(packet))
        if str(receipt.get("generation_id") or "") != generation_id:
            blockers.append("receipt_generation_mismatch")
        if packet_state_sha256 != generation_id:
            blockers.append("packet_generation_mismatch")
        if str(receipt.get("state_sha256") or "") != packet_state_sha256:
            blockers.append("packet_state_hash_mismatch")
        if str(receipt.get("packet_sha256") or "") != _sha_file(generation / "attorney-sandbox-operations.json"):
            blockers.append("receipt_packet_hash_mismatch")
        html_path = generation / "attorney-sandbox-operations.html"
        if str(receipt.get("html_sha256") or "") != _sha_file(html_path):
            blockers.append("receipt_html_hash_mismatch")
        expected_html = self._render_html(packet).encode("utf-8")
        if html_path.read_bytes() != expected_html:
            blockers.append("html_not_deterministic_from_packet")
        return {
            "status": "pass" if not blockers else "blocked",
            "generation_id": generation_id,
            "blockers": blockers,
            "artifact_count": len(seen),
            "pass48_complete": False,
        }

    def resolve_artifact(self, generation_id: str, filename: str) -> tuple[Path, str]:
        verification = self.verify_evidence_packet(generation_id)
        if verification["status"] != "pass":
            raise AttorneySandboxOperationsError("sandbox_evidence_verification_failed", status_code=409)
        filename = str(filename or "").strip()
        if filename not in self.ARTIFACT_FILENAMES:
            raise AttorneySandboxOperationsError("sandbox_evidence_artifact_not_available", status_code=404)
        assert self.evidence_root is not None
        path = self.evidence_root / generation_id / filename
        if not path.is_file() or path.is_symlink():
            raise AttorneySandboxOperationsError("sandbox_evidence_artifact_not_available", status_code=404)
        media = "text/html" if filename.endswith(".html") else "application/json"
        return path, media


__all__ = ["AttorneySandboxOperationsError", "AttorneySandboxOperationsStore"]
