"""Pass 49 limited real-matter pilot operations and immutable evidence.

The store records only opaque identifiers, hashes, enumerated outcomes, and
control evidence. It never stores client names, matter prose, source excerpts,
credentials, or unrestricted paths. The application can determine that its
software-side controls are ready for an external Pass 49 audit, but it cannot
self-certify attorney participation, consent validity, legal usefulness, or GA.
"""

from __future__ import annotations

import html
import json
import os
import re
import threading
import time
from datetime import date
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
    find_source_root,
)

MAX_LEDGER_ROWS = 50_000
MAX_TENANTS = 25
MAX_MATTERS = 100
MAX_CODES = 50
MAX_ARTIFACTS = 32
_PILOT_LOCK = threading.RLock()
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


class LimitedRealMatterPilotError(ReleasePilotHardeningError):
    """Fail-closed operational error with an API-safe code."""


class LimitedRealMatterPilotOperationsStore:
    """Durable Pass 49 operations over a bounded external pilot root."""

    REQUIRED_ARTIFACTS = {
        "issue_tree",
        "posture_summary",
        "timeline",
        "evidence_map",
        "authority_matrix",
        "red_flag_report",
    }
    OPTIONAL_ARTIFACTS = {
        "citation_report",
        "quote_report",
        "claim_support_report",
        "reviewed_filing_packet",
        "form_freshness_report",
        "missing_record_checklist",
    }
    USEFULNESS = {"useful", "partially_useful", "not_useful", "not_yet_determined"}
    INCIDENT_CATEGORIES = {
        "data_leakage",
        "cross_matter_access",
        "unsupported_export",
        "citation_or_authority",
        "workflow_safety",
        "security",
        "privacy",
        "availability",
        "other",
    }
    INCIDENT_SEVERITIES = {"low", "medium", "high", "critical"}
    INCIDENT_STATUSES = {"open", "contained", "fixed_pending_retest", "closed"}
    EXPORT_TYPES = {
        "research_memo",
        "draft_review_copy",
        "evidence_packet",
        "reviewed_filing_packet",
        "diagnostic_bundle",
    }
    EXPORT_GATE_STATUSES = {"blocked", "approved_review_required"}
    ELIGIBLE_REVIEWER_ROLES = {"attorney_reviewer", "supervised_attorney_reviewer"}
    ARTIFACT_FILENAMES = {
        "limited-real-matter-pilot.json",
        "limited-real-matter-pilot.html",
        "limited-real-matter-pilot-receipt.json",
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
            raise LimitedRealMatterPilotError(exc.code, status_code=exc.status_code) from exc
        self.ledger_path = self.root / "limited-real-matter-pilot-ledger.jsonl" if self.root else None
        self.evidence_root = self.root / "limited-real-matter-pilot-evidence" if self.root else None
        self.policy_path = (
            Path(policy_path)
            if policy_path
            else self.repo_root / "configs" / "maine_limited_real_matter_pilot_policy.json"
        )
        self.policy = self._load_policy()
        self.sandbox = AttorneySandboxStore(self.repo_root, self.root)

    def _load_policy(self) -> dict[str, Any]:
        try:
            payload = strict_json_load_path(self.policy_path, max_bytes=2 * 1024 * 1024, require_object=True)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, StrictJSONError) as exc:
            raise LimitedRealMatterPilotError("real_matter_pilot_policy_unavailable", status_code=409) from exc
        if not isinstance(payload, dict):
            raise LimitedRealMatterPilotError("real_matter_pilot_policy_invalid", status_code=409)
        return payload

    @staticmethod
    def _safe_id(value: Any, code: str) -> str:
        text = str(value or "").strip()
        if not _SAFE_ID_RE.fullmatch(text):
            raise LimitedRealMatterPilotError(code, status_code=409)
        return text

    @staticmethod
    def _safe_hash(value: Any, code: str, *, required: bool = True) -> str:
        text = str(value or "").strip().casefold()
        if not text and not required:
            return ""
        if not _HASH_RE.fullmatch(text):
            raise LimitedRealMatterPilotError(code, status_code=409)
        return text

    @classmethod
    def _safe_codes(cls, values: Iterable[Any], code: str) -> list[str]:
        output: list[str] = []
        for value in values:
            item = cls._safe_id(value, code)
            if item not in output:
                output.append(item)
            if len(output) > MAX_CODES:
                raise LimitedRealMatterPilotError("pilot_code_limit_exceeded", status_code=409)
        return sorted(output)

    @staticmethod
    def _private_text_refused(value: Any) -> None:
        text = str(value or "").strip()
        if not text:
            return
        if _EMAIL_RE.search(text) or _SSN_RE.search(text) or _WINDOWS_ABS_RE.search(text):
            raise LimitedRealMatterPilotError("real_matter_pilot_private_text_refused", status_code=409)
        lowered = text.casefold()
        if any(marker in lowered for marker in ("client name", "date of birth", "street address", "sealed record", "juvenile name")):
            raise LimitedRealMatterPilotError("real_matter_pilot_private_text_refused", status_code=409)

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
            raise LimitedRealMatterPilotError("real_matter_pilot_ledger_invalid", status_code=409) from exc
        rows: list[dict[str, Any]] = []
        for line in ledger_text.splitlines():
            if not line.strip():
                continue
            try:
                row = strict_json_loads(line, max_bytes=1024 * 1024, require_object=True)
            except (json.JSONDecodeError, StrictJSONError) as exc:
                raise LimitedRealMatterPilotError("real_matter_pilot_ledger_invalid_json", status_code=409) from exc
            if not isinstance(row, dict):
                raise LimitedRealMatterPilotError("real_matter_pilot_ledger_invalid_row", status_code=409)
            rows.append(row)
            if len(rows) > MAX_LEDGER_ROWS:
                raise LimitedRealMatterPilotError("real_matter_pilot_ledger_row_limit_exceeded", status_code=409)
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

    def verify(self) -> dict[str, Any]:
        return self._verify_rows(self._rows())

    def _append(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self.root is None or self.ledger_path is None:
            raise LimitedRealMatterPilotError("pilot_root_not_configured", status_code=409)
        lock_path = self.ledger_path.with_name(self.ledger_path.name + ".lock")
        with _PILOT_LOCK, exclusive_file_lock(lock_path):
            rows = self._rows(lock_held=True)
            verification = self._verify_rows(rows)
            if verification["status"] != "pass":
                raise LimitedRealMatterPilotError("real_matter_pilot_ledger_verification_failed", status_code=409)
            previous = str(rows[-1].get("record_sha256") or "") if rows else "0" * 64
            body = {
                "schema_version": "limited_real_matter_pilot_event_v1",
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
                raise LimitedRealMatterPilotError("real_matter_pilot_ledger_invalid", status_code=409) from exc
            return body

    def _latest(self, event_type: str, key: str, value: str) -> dict[str, Any] | None:
        matches = [row for row in self._rows() if row.get("event_type") == event_type and row.get(key) == value]
        return matches[-1] if matches else None

    def _latest_program(self) -> dict[str, Any] | None:
        matches = [row for row in self._rows() if row.get("event_type") == "pilot_program_created"]
        return matches[-1] if matches else None

    def _eligible_participant(self, participant_id: str) -> dict[str, Any]:
        participant = self.sandbox._latest_participant(participant_id)
        if not participant or participant.get("sandbox_eligible") is not True:
            raise LimitedRealMatterPilotError("real_matter_pilot_participant_not_eligible", status_code=409)
        if str(participant.get("role") or "") not in self.ELIGIBLE_REVIEWER_ROLES:
            raise LimitedRealMatterPilotError("real_matter_pilot_participant_role_not_eligible", status_code=409)
        return participant

    def create_program(
        self,
        *,
        program_id: str,
        allowed_tenant_ids: Iterable[str],
        pass48_evidence_sha256: str,
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise LimitedRealMatterPilotError("real_matter_pilot_program_approval_required", status_code=409)
        program_id = self._safe_id(program_id, "real_matter_pilot_program_id_invalid")
        tenants = self._safe_codes(allowed_tenant_ids, "real_matter_pilot_tenant_id_invalid")
        if not tenants:
            raise LimitedRealMatterPilotError("real_matter_pilot_tenant_allowlist_required", status_code=409)
        if len(tenants) > MAX_TENANTS:
            raise LimitedRealMatterPilotError("real_matter_pilot_tenant_limit_exceeded", status_code=409)
        pass48_hash = self._safe_hash(pass48_evidence_sha256, "pass48_evidence_hash_invalid")
        existing = self._latest_program()
        if existing:
            if existing.get("program_id") != program_id:
                raise LimitedRealMatterPilotError("real_matter_pilot_program_already_active", status_code=409)
            if list(existing.get("allowed_tenant_ids") or []) != tenants or existing.get("pass48_evidence_sha256") != pass48_hash:
                raise LimitedRealMatterPilotError("real_matter_pilot_program_configuration_immutable", status_code=409)
            return existing
        return self._append("pilot_program_created", {
            "program_id": program_id,
            "allowed_tenant_ids": tenants,
            "pass48_evidence_sha256": pass48_hash,
            "limited_named_tenant_group_only": True,
            "private_training_use_allowed": False,
            "human_review_required": True,
            "export_restrictions_required": True,
        })

    def enroll_matter(
        self,
        *,
        matter_id: str,
        tenant_id: str,
        participant_id: str,
        consent_version: str,
        client_consent_evidence_sha256: str,
        privacy_notice_sha256: str,
        matter_store_sha256: str,
        tenant_isolation_evidence_sha256: str,
        encryption_evidence_sha256: str,
        retention_policy_version: str,
        explicit_real_matter_consent: bool,
        training_use_allowed: bool,
        export_restriction_acknowledged: bool,
        human_review_required: bool,
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise LimitedRealMatterPilotError("real_matter_pilot_enrollment_approval_required", status_code=409)
        program = self._latest_program()
        if not program:
            raise LimitedRealMatterPilotError("real_matter_pilot_program_not_created", status_code=409)
        matter_id = self._safe_id(matter_id, "real_matter_pilot_matter_id_invalid")
        tenant_id = self._safe_id(tenant_id, "real_matter_pilot_tenant_id_invalid")
        participant_id = self._safe_id(participant_id, "real_matter_pilot_participant_id_invalid")
        consent_version = self._safe_id(consent_version, "real_matter_pilot_consent_version_invalid")
        retention_policy_version = self._safe_id(retention_policy_version, "real_matter_pilot_retention_policy_invalid")
        if tenant_id not in set(program.get("allowed_tenant_ids") or []):
            raise LimitedRealMatterPilotError("real_matter_pilot_tenant_not_allowed", status_code=409)
        self._eligible_participant(participant_id)
        if not explicit_real_matter_consent:
            raise LimitedRealMatterPilotError("real_matter_pilot_explicit_consent_required", status_code=409)
        if training_use_allowed:
            raise LimitedRealMatterPilotError("real_matter_pilot_training_use_refused", status_code=409)
        if not export_restriction_acknowledged:
            raise LimitedRealMatterPilotError("real_matter_pilot_export_restriction_ack_required", status_code=409)
        if not human_review_required:
            raise LimitedRealMatterPilotError("real_matter_pilot_human_review_required", status_code=409)
        if self._latest("matter_enrolled", "matter_id", matter_id):
            raise LimitedRealMatterPilotError("real_matter_pilot_matter_already_enrolled", status_code=409)
        enrolled = [row for row in self._rows() if row.get("event_type") == "matter_enrolled"]
        if len(enrolled) >= MAX_MATTERS:
            raise LimitedRealMatterPilotError("real_matter_pilot_matter_limit_exceeded", status_code=409)
        return self._append("matter_enrolled", {
            "program_id": program.get("program_id"),
            "matter_id": matter_id,
            "tenant_id": tenant_id,
            "participant_id": participant_id,
            "consent_version": consent_version,
            "client_consent_evidence_sha256": self._safe_hash(client_consent_evidence_sha256, "real_matter_pilot_client_consent_hash_invalid"),
            "privacy_notice_sha256": self._safe_hash(privacy_notice_sha256, "real_matter_pilot_privacy_notice_hash_invalid"),
            "matter_store_sha256": self._safe_hash(matter_store_sha256, "real_matter_pilot_matter_store_hash_invalid"),
            "tenant_isolation_evidence_sha256": self._safe_hash(tenant_isolation_evidence_sha256, "real_matter_pilot_isolation_hash_invalid"),
            "encryption_evidence_sha256": self._safe_hash(encryption_evidence_sha256, "real_matter_pilot_encryption_hash_invalid"),
            "retention_policy_version": retention_policy_version,
            "explicit_real_matter_consent": True,
            "training_use_allowed": False,
            "export_restriction_acknowledged": True,
            "human_review_required": True,
            "data_classification": "real_private_matter_limited_pilot",
            "private_content_recorded_in_ledger": False,
        })

    def record_work_product(
        self,
        *,
        matter_id: str,
        artifact_hashes: dict[str, str],
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise LimitedRealMatterPilotError("real_matter_pilot_work_product_approval_required", status_code=409)
        matter_id = self._safe_id(matter_id, "real_matter_pilot_matter_id_invalid")
        if not self._latest("matter_enrolled", "matter_id", matter_id):
            raise LimitedRealMatterPilotError("real_matter_pilot_matter_not_enrolled", status_code=404)
        if not isinstance(artifact_hashes, dict) or len(artifact_hashes) > MAX_ARTIFACTS:
            raise LimitedRealMatterPilotError("real_matter_pilot_artifact_map_invalid", status_code=409)
        allowed = self.REQUIRED_ARTIFACTS | self.OPTIONAL_ARTIFACTS
        normalized: dict[str, str] = {}
        for key, value in artifact_hashes.items():
            artifact_type = self._safe_id(key, "real_matter_pilot_artifact_type_invalid")
            if artifact_type not in allowed:
                raise LimitedRealMatterPilotError("real_matter_pilot_artifact_type_not_allowed", status_code=409)
            normalized[artifact_type] = self._safe_hash(value, "real_matter_pilot_artifact_hash_invalid")
        missing = sorted(self.REQUIRED_ARTIFACTS - set(normalized))
        return self._append("work_product_recorded", {
            "matter_id": matter_id,
            "artifact_hashes": dict(sorted(normalized.items())),
            "artifact_count": len(normalized),
            "missing_required_artifacts": missing,
            "work_product_complete": not missing,
            "artifact_content_recorded_in_ledger": False,
        })

    def record_daily_review(
        self,
        *,
        matter_id: str,
        participant_id: str,
        review_date: str,
        usefulness: str,
        human_review_completed: bool,
        source_verification_completed: bool,
        export_gate_checked: bool,
        blocker_codes: Iterable[str],
        review_evidence_sha256: str,
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise LimitedRealMatterPilotError("real_matter_pilot_daily_review_approval_required", status_code=409)
        matter_id = self._safe_id(matter_id, "real_matter_pilot_matter_id_invalid")
        participant_id = self._safe_id(participant_id, "real_matter_pilot_participant_id_invalid")
        if not self._latest("matter_enrolled", "matter_id", matter_id):
            raise LimitedRealMatterPilotError("real_matter_pilot_matter_not_enrolled", status_code=404)
        self._eligible_participant(participant_id)
        review_date = str(review_date or "").strip()
        if not _DATE_RE.fullmatch(review_date):
            raise LimitedRealMatterPilotError("real_matter_pilot_review_date_invalid", status_code=409)
        try:
            date.fromisoformat(review_date)
        except ValueError as exc:
            raise LimitedRealMatterPilotError("real_matter_pilot_review_date_invalid", status_code=409) from exc
        usefulness = str(usefulness or "").strip().casefold()
        if usefulness not in self.USEFULNESS:
            raise LimitedRealMatterPilotError("real_matter_pilot_usefulness_invalid", status_code=409)
        blockers = self._safe_codes(blocker_codes, "real_matter_pilot_blocker_code_invalid")
        return self._append("daily_review_recorded", {
            "matter_id": matter_id,
            "participant_id": participant_id,
            "review_date": review_date,
            "usefulness": usefulness,
            "human_review_completed": bool(human_review_completed),
            "source_verification_completed": bool(source_verification_completed),
            "export_gate_checked": bool(export_gate_checked),
            "blocker_codes": blockers,
            "review_evidence_sha256": self._safe_hash(review_evidence_sha256, "real_matter_pilot_daily_review_hash_invalid"),
            "private_review_notes_recorded": False,
        })

    def record_export_attempt(
        self,
        *,
        matter_id: str,
        export_type: str,
        gate_status: str,
        filing_ready_claimed: bool,
        export_artifact_sha256: str,
        authorization_evidence_sha256: str,
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise LimitedRealMatterPilotError("real_matter_pilot_export_record_approval_required", status_code=409)
        matter_id = self._safe_id(matter_id, "real_matter_pilot_matter_id_invalid")
        if not self._latest("matter_enrolled", "matter_id", matter_id):
            raise LimitedRealMatterPilotError("real_matter_pilot_matter_not_enrolled", status_code=404)
        export_type = str(export_type or "").strip().casefold()
        gate_status = str(gate_status or "").strip().casefold()
        if export_type not in self.EXPORT_TYPES:
            raise LimitedRealMatterPilotError("real_matter_pilot_export_type_invalid", status_code=409)
        if gate_status not in self.EXPORT_GATE_STATUSES:
            raise LimitedRealMatterPilotError("real_matter_pilot_export_gate_status_invalid", status_code=409)
        unsupported = bool(filing_ready_claimed)
        if gate_status == "approved_review_required" and not authorization_evidence_sha256:
            raise LimitedRealMatterPilotError("real_matter_pilot_export_authorization_hash_required", status_code=409)
        return self._append("export_attempt_recorded", {
            "matter_id": matter_id,
            "export_type": export_type,
            "gate_status": gate_status,
            "filing_ready_claimed": bool(filing_ready_claimed),
            "unsupported_filing_ready_export_attempt": unsupported,
            "export_artifact_sha256": self._safe_hash(export_artifact_sha256, "real_matter_pilot_export_hash_invalid"),
            "authorization_evidence_sha256": self._safe_hash(
                authorization_evidence_sha256,
                "real_matter_pilot_export_authorization_hash_invalid",
                required=gate_status == "approved_review_required",
            ),
            "export_restriction_enforced": True,
            "review_required": True,
        })

    def open_incident(
        self,
        *,
        matter_id: str,
        category: str,
        severity: str,
        summary_code: str,
        incident_evidence_sha256: str,
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise LimitedRealMatterPilotError("real_matter_pilot_incident_approval_required", status_code=409)
        matter_id = self._safe_id(matter_id, "real_matter_pilot_matter_id_invalid")
        if not self._latest("matter_enrolled", "matter_id", matter_id):
            raise LimitedRealMatterPilotError("real_matter_pilot_matter_not_enrolled", status_code=404)
        category = str(category or "").strip().casefold()
        severity = str(severity or "").strip().casefold()
        if category not in self.INCIDENT_CATEGORIES:
            raise LimitedRealMatterPilotError("real_matter_pilot_incident_category_invalid", status_code=409)
        if severity not in self.INCIDENT_SEVERITIES:
            raise LimitedRealMatterPilotError("real_matter_pilot_incident_severity_invalid", status_code=409)
        summary_code = self._safe_id(summary_code, "real_matter_pilot_incident_summary_code_invalid")
        incident_seed = f"{matter_id}\0{category}\0{time.time_ns()}".encode()
        incident_id = f"incident-{_sha_bytes(incident_seed)[:20]}"
        return self._append("incident_opened", {
            "incident_id": incident_id,
            "matter_id": matter_id,
            "category": category,
            "severity": severity,
            "summary_code": summary_code,
            "incident_evidence_sha256": self._safe_hash(incident_evidence_sha256, "real_matter_pilot_incident_hash_invalid"),
            "status": "open",
            "private_incident_narrative_recorded": False,
            "blocks_pilot": severity in {"high", "critical"} or category in {"data_leakage", "cross_matter_access", "unsupported_export"},
        })

    def update_incident(
        self,
        *,
        incident_id: str,
        status: str,
        remediation_evidence_sha256: str,
        retest_evidence_sha256: str,
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise LimitedRealMatterPilotError("real_matter_pilot_incident_update_approval_required", status_code=409)
        incident_id = self._safe_id(incident_id, "real_matter_pilot_incident_id_invalid")
        status = str(status or "").strip().casefold()
        if status not in self.INCIDENT_STATUSES - {"open"}:
            raise LimitedRealMatterPilotError("real_matter_pilot_incident_status_invalid", status_code=409)
        opened = self._latest("incident_opened", "incident_id", incident_id)
        if not opened:
            raise LimitedRealMatterPilotError("real_matter_pilot_incident_not_found", status_code=404)
        updates = [row for row in self._rows() if row.get("event_type") == "incident_updated" and row.get("incident_id") == incident_id]
        current = str(updates[-1].get("status") or "") if updates else "open"
        transitions = {
            "open": {"contained"},
            "contained": {"fixed_pending_retest"},
            "fixed_pending_retest": {"closed"},
            "closed": set(),
        }
        if status not in transitions.get(current, set()):
            raise LimitedRealMatterPilotError("real_matter_pilot_incident_transition_invalid", status_code=409)
        remediation = self._safe_hash(remediation_evidence_sha256, "real_matter_pilot_remediation_hash_invalid")
        retest = self._safe_hash(
            retest_evidence_sha256,
            "real_matter_pilot_retest_hash_invalid",
            required=status == "closed",
        )
        return self._append("incident_updated", {
            "incident_id": incident_id,
            "matter_id": opened.get("matter_id"),
            "prior_status": current,
            "status": status,
            "remediation_evidence_sha256": remediation,
            "retest_evidence_sha256": retest,
            "blocks_pilot": status != "closed",
        })

    def record_signoff(
        self,
        *,
        matter_id: str,
        participant_id: str,
        usefulness: str,
        attorney_signoff_complete: bool,
        blocker_codes: Iterable[str],
        signoff_evidence_sha256: str,
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise LimitedRealMatterPilotError("real_matter_pilot_signoff_approval_required", status_code=409)
        matter_id = self._safe_id(matter_id, "real_matter_pilot_matter_id_invalid")
        participant_id = self._safe_id(participant_id, "real_matter_pilot_participant_id_invalid")
        enrollment = self._latest("matter_enrolled", "matter_id", matter_id)
        if not enrollment:
            raise LimitedRealMatterPilotError("real_matter_pilot_matter_not_enrolled", status_code=404)
        self._eligible_participant(participant_id)
        usefulness = str(usefulness or "").strip().casefold()
        if usefulness not in self.USEFULNESS - {"not_yet_determined"}:
            raise LimitedRealMatterPilotError("real_matter_pilot_usefulness_invalid", status_code=409)
        blockers = self._safe_codes(blocker_codes, "real_matter_pilot_blocker_code_invalid")
        return self._append("matter_signoff_recorded", {
            "matter_id": matter_id,
            "participant_id": participant_id,
            "usefulness": usefulness,
            "attorney_signoff_complete": bool(attorney_signoff_complete),
            "blocker_codes": blockers,
            "signoff_evidence_sha256": self._safe_hash(signoff_evidence_sha256, "real_matter_pilot_signoff_hash_invalid"),
            "application_independently_verifies_signoff": False,
        })

    def _incident_state(self) -> dict[str, dict[str, Any]]:
        states: dict[str, dict[str, Any]] = {}
        for row in self._rows():
            if row.get("event_type") == "incident_opened":
                states[str(row.get("incident_id") or "")] = dict(row)
            elif row.get("event_type") == "incident_updated":
                incident_id = str(row.get("incident_id") or "")
                if incident_id in states:
                    states[incident_id].update(row)
        return states

    def status(self) -> dict[str, Any]:
        rows = self._rows()
        verification = self._verify_rows(rows)
        participant_verification = self.sandbox.verify()
        program = self._latest_program()
        enrollments = [row for row in rows if row.get("event_type") == "matter_enrolled"]
        work_products = {
            str(row.get("matter_id") or ""): row
            for row in rows if row.get("event_type") == "work_product_recorded"
        }
        daily_by_matter: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            if row.get("event_type") == "daily_review_recorded":
                daily_by_matter.setdefault(str(row.get("matter_id") or ""), []).append(row)
        signoffs = {
            str(row.get("matter_id") or ""): row
            for row in rows if row.get("event_type") == "matter_signoff_recorded"
        }
        exports = [row for row in rows if row.get("event_type") == "export_attempt_recorded"]
        incident_states = self._incident_state()
        minimum_matters = int(self.policy.get("minimum_matter_count") or 1)
        minimum_daily = int(self.policy.get("minimum_daily_reviews_per_matter") or 1)
        blockers: list[str] = []
        matter_reports: list[dict[str, Any]] = []
        if self.root is None:
            blockers.append("pilot_root_not_configured")
        if verification["status"] != "pass":
            blockers.append("real_matter_pilot_ledger_verification_failed")
        if participant_verification["status"] != "pass":
            blockers.append("participant_ledger_verification_failed")
        if not program:
            blockers.append("real_matter_pilot_program_not_created")
        if len(enrollments) < minimum_matters:
            blockers.append("minimum_real_matter_count_not_met")

        permanent_incident_blockers = {
            incident_id: row
            for incident_id, row in incident_states.items()
            if str(row.get("category") or "") in {"data_leakage", "cross_matter_access"}
        }
        open_incidents = {
            incident_id: row
            for incident_id, row in incident_states.items()
            if str(row.get("status") or "open") != "closed"
        }
        unsupported_exports = [row for row in exports if row.get("unsupported_filing_ready_export_attempt") is True]
        if permanent_incident_blockers:
            blockers.extend(f"prohibited_incident_recorded:{item}" for item in sorted(permanent_incident_blockers))
        if unsupported_exports:
            blockers.extend(
                f"unsupported_filing_ready_export_attempt:{row.get('matter_id')}:{row.get('record_sha256')}"
                for row in unsupported_exports
            )

        for enrollment in enrollments:
            matter_id = str(enrollment.get("matter_id") or "")
            matter_blockers: list[str] = []
            try:
                self._eligible_participant(str(enrollment.get("participant_id") or ""))
            except LimitedRealMatterPilotError:
                matter_blockers.append("participant_no_longer_eligible")
            if enrollment.get("explicit_real_matter_consent") is not True:
                matter_blockers.append("explicit_real_matter_consent_missing")
            if enrollment.get("training_use_allowed") is not False:
                matter_blockers.append("private_training_use_not_false")
            if enrollment.get("human_review_required") is not True:
                matter_blockers.append("human_review_requirement_missing")
            if enrollment.get("export_restriction_acknowledged") is not True:
                matter_blockers.append("export_restriction_acknowledgement_missing")
            for field in (
                "client_consent_evidence_sha256",
                "privacy_notice_sha256",
                "matter_store_sha256",
                "tenant_isolation_evidence_sha256",
                "encryption_evidence_sha256",
            ):
                if not _HASH_RE.fullmatch(str(enrollment.get(field) or "")):
                    matter_blockers.append(f"control_evidence_missing:{field}")
            work_product = work_products.get(matter_id)
            if not work_product or work_product.get("work_product_complete") is not True:
                matter_blockers.append("required_work_product_incomplete")
            daily_rows = daily_by_matter.get(matter_id, [])
            if len(daily_rows) < minimum_daily:
                matter_blockers.append("minimum_daily_reviews_not_met")
            if daily_rows:
                latest_daily = daily_rows[-1]
                for field in ("human_review_completed", "source_verification_completed", "export_gate_checked"):
                    if latest_daily.get(field) is not True:
                        matter_blockers.append(f"daily_review_control_missing:{field}")
                if latest_daily.get("blocker_codes"):
                    matter_blockers.append("latest_daily_review_has_blockers")
            matter_incidents = {
                incident_id: row
                for incident_id, row in open_incidents.items()
                if row.get("matter_id") == matter_id
            }
            if matter_incidents:
                matter_blockers.extend(f"open_incident:{item}" for item in sorted(matter_incidents))
            signoff = signoffs.get(matter_id)
            if not signoff or signoff.get("attorney_signoff_complete") is not True:
                matter_blockers.append("attorney_signoff_missing")
            elif signoff.get("blocker_codes"):
                matter_blockers.append("attorney_signoff_lists_blockers")
            if signoff and signoff.get("usefulness") == "not_useful":
                matter_blockers.append("matter_workflow_not_useful")
            matter_reports.append({
                "matter_id": matter_id,
                "tenant_id": enrollment.get("tenant_id"),
                "participant_id": enrollment.get("participant_id"),
                "work_product_complete": bool(work_product and work_product.get("work_product_complete") is True),
                "daily_review_count": len(daily_rows),
                "latest_usefulness": (daily_rows[-1].get("usefulness") if daily_rows else "not_yet_determined"),
                "attorney_signoff_complete": bool(signoff and signoff.get("attorney_signoff_complete") is True),
                "open_incident_count": len(matter_incidents),
                "blockers": matter_blockers,
                "status": "pass" if not matter_blockers else "blocked",
            })
            blockers.extend(f"{matter_id}:{item}" for item in matter_blockers)

        status = "ready_for_external_pass49_gate" if not blockers else "blocked"
        return {
            "schema_version": "limited_real_matter_pilot_status_v1",
            "status": status,
            "stage": "limited_real_matter_pilot_operations",
            "policy_version": str(self.policy.get("version") or "unknown"),
            "root_configured": self.root is not None,
            "program_id": str((program or {}).get("program_id") or ""),
            "allowed_tenant_ids": list((program or {}).get("allowed_tenant_ids") or []),
            "matter_count": len(enrollments),
            "matters": matter_reports,
            "daily_review_count": sum(len(rows_) for rows_ in daily_by_matter.values()),
            "incident_count": len(incident_states),
            "open_incident_count": len(open_incidents),
            "data_leakage_count": sum(1 for row in incident_states.values() if row.get("category") == "data_leakage"),
            "unsupported_export_attempt_count": len(unsupported_exports),
            "attorney_signoff_count": sum(1 for row in signoffs.values() if row.get("attorney_signoff_complete") is True),
            "minimums": {"matters": minimum_matters, "daily_reviews_per_matter": minimum_daily},
            "blockers": blockers,
            "pilot_ledger": verification,
            "participant_ledger": participant_verification,
            "training_use_allowed": False,
            "human_review_required": True,
            "export_restrictions_required": True,
            "application_independently_verifies_consent_or_legal_signoff": False,
            "pass49_complete": False,
            "external_launch_evidence_gate_required": True,
        }

    def _evidence_snapshot(self) -> dict[str, Any]:
        rows = self._rows()
        status = self.status()
        allowed_events = {
            "pilot_program_created",
            "matter_enrolled",
            "work_product_recorded",
            "daily_review_recorded",
            "export_attempt_recorded",
            "incident_opened",
            "incident_updated",
            "matter_signoff_recorded",
        }
        events: list[dict[str, Any]] = []
        for row in rows:
            if row.get("event_type") not in allowed_events:
                continue
            safe = {
                key: value
                for key, value in row.items()
                if key not in {"previous_sha256"}
            }
            events.append(safe)
        return {
            "schema_version": "limited_real_matter_pilot_evidence_v1",
            "stage": "limited_real_matter_pilot_operations",
            "policy_version": str(self.policy.get("version") or "unknown"),
            "status": status,
            "events": events,
            "ledger_sha256": _sha_file(self.ledger_path) if self.ledger_path and self.ledger_path.exists() else "",
            "private_matter_content_included": False,
            "identifying_party_names_included": False,
            "absolute_paths_included": False,
            "training_use_allowed": False,
            "pass49_complete": False,
        }

    @staticmethod
    def _render_html(packet: dict[str, Any]) -> str:
        status = packet.get("status") or {}
        rows = []
        for matter in status.get("matters") or []:
            blockers = ", ".join(str(item) for item in matter.get("blockers") or []) or "None"
            rows.append(
                "<tr>"
                f"<td>{html.escape(str(matter.get('matter_id') or ''))}</td>"
                f"<td>{html.escape(str(matter.get('tenant_id') or ''))}</td>"
                f"<td>{html.escape(str(matter.get('status') or ''))}</td>"
                f"<td>{html.escape(str(matter.get('daily_review_count') or 0))}</td>"
                f"<td>{html.escape(blockers)}</td>"
                "</tr>"
            )
        return """<!doctype html><html><head><meta charset=\"utf-8\"><title>Limited Real-Matter Pilot Evidence</title>
<style>body{font-family:system-ui;margin:2rem;line-height:1.45}table{border-collapse:collapse;width:100%}th,td{border:1px solid #bbb;padding:.55rem;text-align:left}code{background:#f3f3f3;padding:.1rem .25rem}.blocked{color:#8b1e1e}.pass{color:#146c2e}</style></head><body>""" + (
            f"<h1>Limited Real-Matter Pilot Evidence</h1><p>Status: <strong class='{html.escape(str(status.get('status') or 'blocked'))}'>{html.escape(str(status.get('status') or 'blocked'))}</strong></p>"
            "<p>This packet contains opaque identifiers, hashes, enumerated outcomes, and control evidence only. It does not contain private matter text and does not complete Pass 49.</p>"
            f"<p>Matters: {int(status.get('matter_count') or 0)} · Daily reviews: {int(status.get('daily_review_count') or 0)} · Open incidents: {int(status.get('open_incident_count') or 0)}</p>"
            "<table><thead><tr><th>Matter ID</th><th>Tenant ID</th><th>Status</th><th>Daily reviews</th><th>Blockers</th></tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table>"
            f"<h2>Global blockers</h2><pre>{html.escape(json.dumps(status.get('blockers') or [], indent=2))}</pre>"
            "</body></html>"
        )

    @staticmethod
    def _write_immutable_json(path: Path, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
        if path.exists() and path.is_symlink():
            raise LimitedRealMatterPilotError("real_matter_pilot_evidence_symlink_refused", status_code=409)
        if path.exists() and path.read_bytes() != data:
            raise LimitedRealMatterPilotError("real_matter_pilot_generation_collision", status_code=409)
        path.write_bytes(data)

    def build_evidence_packet(self, *, approved: bool) -> dict[str, Any]:
        if approved is not True:
            raise LimitedRealMatterPilotError("real_matter_pilot_evidence_approval_required", status_code=409)
        if self.root is None or self.evidence_root is None:
            raise LimitedRealMatterPilotError("pilot_root_not_configured", status_code=409)
        snapshot = self._evidence_snapshot()
        packet_bytes = json.dumps(snapshot, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
        html_bytes = self._render_html(snapshot).encode("utf-8")
        generation_id = _sha_bytes(_canonical_json(snapshot))
        parent = self.evidence_root
        generation = parent / generation_id
        if parent.exists() and parent.is_symlink():
            raise LimitedRealMatterPilotError("real_matter_pilot_evidence_symlink_refused", status_code=409)
        if generation.exists() and generation.is_symlink():
            raise LimitedRealMatterPilotError("real_matter_pilot_evidence_symlink_refused", status_code=409)
        generation.mkdir(parents=True, exist_ok=True)
        packet_name = "limited-real-matter-pilot.json"
        html_name = "limited-real-matter-pilot.html"
        receipt_name = "limited-real-matter-pilot-receipt.json"
        packet_path = generation / packet_name
        html_path = generation / html_name
        receipt_path = generation / receipt_name
        for path, data in ((packet_path, packet_bytes), (html_path, html_bytes)):
            if path.exists() and path.is_symlink():
                raise LimitedRealMatterPilotError("real_matter_pilot_evidence_symlink_refused", status_code=409)
            if path.exists() and path.read_bytes() != data:
                raise LimitedRealMatterPilotError("real_matter_pilot_generation_collision", status_code=409)
            path.write_bytes(data)
        receipt = {
            "schema_version": "limited_real_matter_pilot_receipt_v1",
            "generation_id": generation_id,
            "packet_sha256": _sha_bytes(packet_bytes),
            "html_sha256": _sha_bytes(html_bytes),
            "ledger_sha256": snapshot.get("ledger_sha256"),
            "status": (snapshot.get("status") or {}).get("status"),
            "private_matter_content_included": False,
            "pass49_complete": False,
        }
        self._write_immutable_json(receipt_path, receipt)
        artifacts = []
        for filename in (packet_name, html_name, receipt_name):
            path = generation / filename
            artifacts.append({"filename": filename, "sha256": _sha_file(path), "size_bytes": path.stat().st_size})
        manifest = {
            "schema_version": "limited_real_matter_pilot_artifact_manifest_v1",
            "generation_id": generation_id,
            "artifacts": sorted(artifacts, key=lambda row: row["filename"]),
        }
        self._write_immutable_json(generation / "artifact-manifest.json", manifest)
        self.verify_generation(generation_id)
        return {
            "schema_version": "limited_real_matter_pilot_build_result_v1",
            "status": "pass",
            "generation_id": generation_id,
            "pilot_status": (snapshot.get("status") or {}).get("status"),
            "artifacts": [
                {"filename": filename, "sha256": _sha_file(generation / filename), "size_bytes": (generation / filename).stat().st_size}
                for filename in sorted(self.ARTIFACT_FILENAMES)
            ],
            "pass49_complete": False,
            "external_launch_evidence_gate_required": True,
        }

    def verify_generation(self, generation_id: str) -> dict[str, Any]:
        generation_id = self._safe_hash(generation_id, "real_matter_pilot_generation_id_invalid")
        if self.evidence_root is None:
            raise LimitedRealMatterPilotError("pilot_root_not_configured", status_code=409)
        generation = self.evidence_root / generation_id
        if not generation.is_dir() or generation.is_symlink():
            raise LimitedRealMatterPilotError("real_matter_pilot_generation_not_found", status_code=404)
        manifest_path = generation / "artifact-manifest.json"
        try:
            manifest = strict_json_loads(manifest_path.read_bytes(), max_bytes=8 * 1024 * 1024, require_object=True)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, StrictJSONError) as exc:
            raise LimitedRealMatterPilotError("real_matter_pilot_manifest_invalid", status_code=409) from exc
        if not isinstance(manifest, dict) or manifest.get("generation_id") != generation_id:
            raise LimitedRealMatterPilotError("real_matter_pilot_manifest_invalid", status_code=409)
        rows = manifest.get("artifacts")
        if not isinstance(rows, list):
            raise LimitedRealMatterPilotError("real_matter_pilot_manifest_invalid", status_code=409)
        expected = self.ARTIFACT_FILENAMES - {"artifact-manifest.json"}
        names = {str(row.get("filename") or "") for row in rows if isinstance(row, dict)}
        if names != expected or len(rows) != len(expected):
            raise LimitedRealMatterPilotError("real_matter_pilot_manifest_artifact_set_mismatch", status_code=409)
        blockers: list[str] = []
        for row in rows:
            filename = str(row.get("filename") or "")
            path = generation / filename
            if not path.is_file() or path.is_symlink():
                blockers.append(f"artifact_unavailable:{filename}")
                continue
            if int(row.get("size_bytes") or -1) != path.stat().st_size:
                blockers.append(f"artifact_size_mismatch:{filename}")
            if str(row.get("sha256") or "") != _sha_file(path):
                blockers.append(f"artifact_hash_mismatch:{filename}")
        try:
            packet_payload = strict_json_loads((generation / "limited-real-matter-pilot.json").read_bytes(), max_bytes=16 * 1024 * 1024, require_object=True)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, StrictJSONError):
            blockers.append("packet_invalid")
            packet_payload = {}
        if not isinstance(packet_payload, dict) or _sha_bytes(_canonical_json(packet_payload)) != generation_id:
            blockers.append("generation_content_hash_mismatch")
        try:
            receipt = strict_json_loads((generation / "limited-real-matter-pilot-receipt.json").read_bytes(), max_bytes=16 * 1024 * 1024, require_object=True)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, StrictJSONError):
            blockers.append("receipt_invalid")
            receipt = {}
        if str(receipt.get("generation_id") or "") != generation_id:
            blockers.append("receipt_generation_id_mismatch")
        if str(receipt.get("packet_sha256") or "") != _sha_file(generation / "limited-real-matter-pilot.json"):
            blockers.append("receipt_packet_hash_mismatch")
        if str(receipt.get("html_sha256") or "") != _sha_file(generation / "limited-real-matter-pilot.html"):
            blockers.append("receipt_html_hash_mismatch")
        if blockers:
            raise LimitedRealMatterPilotError("real_matter_pilot_generation_verification_failed", status_code=409)
        return {"status": "pass", "generation_id": generation_id, "blockers": []}

    def resolve_artifact(self, generation_id: str, filename: str) -> tuple[Path, str]:
        generation_id = self._safe_hash(generation_id, "real_matter_pilot_generation_id_invalid")
        filename = str(filename or "").strip()
        if filename not in self.ARTIFACT_FILENAMES:
            raise LimitedRealMatterPilotError("real_matter_pilot_artifact_not_allowed", status_code=404)
        self.verify_generation(generation_id)
        if self.evidence_root is None:
            raise LimitedRealMatterPilotError("pilot_root_not_configured", status_code=409)
        path = self.evidence_root / generation_id / filename
        media = "text/html" if filename.endswith(".html") else "application/json"
        return path, media


__all__ = ["LimitedRealMatterPilotError", "LimitedRealMatterPilotOperationsStore"]
