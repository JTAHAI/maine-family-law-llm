"""Pass 50 GA release-candidate operations and immutable evidence.

This module freezes a versioned release-candidate inventory, records explicit
security/legal/product/ops signoff references, tracks P0/P1 blockers, and builds
an immutable evidence packet.  It does not fabricate external legal data,
attorney-reviewed evaluations, pilot completion, Store certification, or GA
approval.  Pass 50 remains an external evidence gate.
"""

from __future__ import annotations

import html
import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from legal.security.durable_io import (
    DurableIOError,
    durable_append_text,
    exclusive_file_lock,
    read_bounded_regular_file,
)
from legal.security.strict_json import StrictJSONError, strict_json_load_path, strict_json_loads

from legal.ops.release_pilot_hardening import (
    ReleasePilotHardeningError,
    _HASH_RE,
    _SAFE_ID_RE,
    _canonical_json,
    _now_iso,
    _safe_external_root,
    _sha_bytes,
    _sha_file,
    find_source_root,
)
from legal.release.ga_release import (
    ReleaseArtifact,
    ReleaseBlocker,
    ReleaseCandidateAuditor,
    ReleaseSignoff,
)

MAX_LEDGER_ROWS = 50_000
MAX_ARTIFACTS = 64
MAX_BLOCKERS = 1_000
_RELEASE_CANDIDATE_LOCK = threading.RLock()
_URI_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:[^\s]{1,500}")
_ALLOWED_REFERENCE_SCHEMES = {"https", "urn"}
_VERSION_RE = re.compile(r"[0-9]+(?:\.[0-9]+){2}(?:[A-Za-z0-9_.+-]*)?")


class GAReleaseCandidateError(ReleasePilotHardeningError):
    """Fail-closed release-candidate error with an API-safe code."""


class GAReleaseCandidateOperationsStore:
    """Durable, external-root Pass 50 release-candidate operations."""

    REQUIRED_ARTIFACT_TYPES = set(ReleaseCandidateAuditor.REQUIRED_ARTIFACT_TYPES)
    EXTERNAL_ARTIFACT_TYPES = set(ReleaseCandidateAuditor.EXTERNAL_ARTIFACT_TYPES)
    REQUIRED_SIGNOFF_ROLES = set(ReleaseCandidateAuditor.REQUIRED_SIGNOFF_ROLES)
    SIGNOFF_STATUSES = {"approved", "rejected", "pending"}
    BLOCKER_SEVERITIES = {"P0", "P1", "P2", "P3"}
    BLOCKER_STATUSES = {"open", "mitigated_pending_retest", "closed"}
    ARTIFACT_FILENAMES = {
        "ga-release-candidate.json",
        "ga-release-candidate.html",
        "ga-release-candidate-receipt.json",
        "artifact-manifest.json",
    }

    def __init__(
        self,
        repo_root: str | Path,
        release_root: str | Path | None = None,
        *,
        policy_path: str | Path | None = None,
    ) -> None:
        self.repo_root = find_source_root(repo_root)
        configured = release_root or os.environ.get("MAINE_FAMILY_LAW_RELEASE_ROOT")
        try:
            self.root = _safe_external_root(configured, repo_root=self.repo_root, create=bool(configured))
        except ReleasePilotHardeningError as exc:
            raise GAReleaseCandidateError(exc.code, status_code=exc.status_code) from exc
        self.ledger_path = self.root / "ga-release-candidate-ledger.jsonl" if self.root else None
        self.evidence_root = self.root / "ga-release-candidate-evidence" if self.root else None
        self.policy_path = (
            Path(policy_path)
            if policy_path
            else self.repo_root / "configs" / "maine_ga_release_candidate_policy.json"
        )
        self.policy = self._load_policy()

    def _load_policy(self) -> dict[str, Any]:
        try:
            payload = strict_json_load_path(self.policy_path, max_bytes=2 * 1024 * 1024, require_object=True)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, StrictJSONError) as exc:
            raise GAReleaseCandidateError("ga_release_candidate_policy_unavailable", status_code=409) from exc
        if not isinstance(payload, dict):
            raise GAReleaseCandidateError("ga_release_candidate_policy_invalid", status_code=409)
        return payload

    @staticmethod
    def _safe_id(value: Any, code: str) -> str:
        text = str(value or "").strip()
        if not _SAFE_ID_RE.fullmatch(text):
            raise GAReleaseCandidateError(code, status_code=409)
        return text

    @staticmethod
    def _safe_hash(value: Any, code: str, *, required: bool = True) -> str:
        text = str(value or "").strip().casefold()
        if not text and not required:
            return ""
        if not _HASH_RE.fullmatch(text):
            raise GAReleaseCandidateError(code, status_code=409)
        return text

    @staticmethod
    def _safe_version(value: Any) -> str:
        text = str(value or "").strip()
        if not _VERSION_RE.fullmatch(text):
            raise GAReleaseCandidateError("ga_release_candidate_version_invalid", status_code=409)
        return text

    @staticmethod
    def _safe_reference(value: Any) -> str:
        text = str(value or "").strip()
        if not text or len(text) > 512 or "\\" in text or text.startswith("/") or ".." in text.split("/"):
            raise GAReleaseCandidateError("ga_release_candidate_artifact_reference_invalid", status_code=409)
        if _SAFE_ID_RE.fullmatch(text):
            return text
        if not _URI_RE.fullmatch(text):
            raise GAReleaseCandidateError("ga_release_candidate_artifact_reference_invalid", status_code=409)
        parsed = urlsplit(text)
        scheme = parsed.scheme.casefold()
        if scheme not in _ALLOWED_REFERENCE_SCHEMES:
            raise GAReleaseCandidateError("ga_release_candidate_artifact_reference_invalid", status_code=409)
        if scheme == "https" and (not parsed.netloc or parsed.username or parsed.password):
            raise GAReleaseCandidateError("ga_release_candidate_artifact_reference_invalid", status_code=409)
        if scheme == "urn" and not parsed.path:
            raise GAReleaseCandidateError("ga_release_candidate_artifact_reference_invalid", status_code=409)
        return text

    @staticmethod
    def _safe_zip_name(value: Any) -> str:
        text = str(value or "").strip()
        if (
            not text
            or len(text) > 180
            or not text.casefold().endswith(".zip")
            or "/" in text
            or "\\" in text
            or ":" in text
            or Path(text).name != text
            or text in {".", ".."}
        ):
            raise GAReleaseCandidateError("ga_release_candidate_source_zip_name_invalid", status_code=409)
        return text

    @staticmethod
    def _safe_signed_at(value: Any) -> str:
        text = str(value or "").strip()
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise GAReleaseCandidateError("ga_release_candidate_signed_at_invalid", status_code=409) from exc
        if "T" not in text or parsed.tzinfo is None or parsed.utcoffset() is None:
            raise GAReleaseCandidateError("ga_release_candidate_signed_at_timezone_required", status_code=409)
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
            raise GAReleaseCandidateError("ga_release_candidate_ledger_invalid", status_code=409) from exc
        rows: list[dict[str, Any]] = []
        for line in ledger_text.splitlines():
            if not line.strip():
                continue
            try:
                row = strict_json_loads(line, max_bytes=1024 * 1024, require_object=True)
            except (json.JSONDecodeError, StrictJSONError) as exc:
                raise GAReleaseCandidateError("ga_release_candidate_ledger_invalid_json", status_code=409) from exc
            if not isinstance(row, dict):
                raise GAReleaseCandidateError("ga_release_candidate_ledger_invalid_row", status_code=409)
            rows.append(row)
            if len(rows) > MAX_LEDGER_ROWS:
                raise GAReleaseCandidateError("ga_release_candidate_ledger_row_limit_exceeded", status_code=409)
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
            raise GAReleaseCandidateError("release_root_not_configured", status_code=409)
        lock_path = self.ledger_path.with_name(self.ledger_path.name + ".lock")
        with _RELEASE_CANDIDATE_LOCK, exclusive_file_lock(lock_path):
            rows = self._rows(lock_held=True)
            verification = self._verify_rows(rows)
            if verification["status"] != "pass":
                raise GAReleaseCandidateError("ga_release_candidate_ledger_verification_failed", status_code=409)
            previous = str(rows[-1].get("record_sha256") or "") if rows else "0" * 64
            body = {
                "schema_version": "ga_release_candidate_event_v1",
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
                raise GAReleaseCandidateError("ga_release_candidate_ledger_invalid", status_code=409) from exc
            return body

    def _candidate(self, candidate_id: str | None = None) -> dict[str, Any] | None:
        rows = [row for row in self._rows() if row.get("event_type") == "candidate_created"]
        if candidate_id:
            rows = [row for row in rows if row.get("candidate_id") == candidate_id]
        return rows[-1] if rows else None

    def create_candidate(
        self,
        *,
        candidate_id: str,
        version: str,
        source_repo_zip_sha256: str,
        source_repo_zip_name: str,
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise GAReleaseCandidateError("ga_release_candidate_approval_required", status_code=409)
        candidate_id = self._safe_id(candidate_id, "ga_release_candidate_id_invalid")
        version = self._safe_version(version)
        expected = str(self.policy.get("product_version") or "").strip()
        if expected and version != expected:
            raise GAReleaseCandidateError("ga_release_candidate_version_mismatch", status_code=409)
        name = self._safe_zip_name(source_repo_zip_name)
        digest = self._safe_hash(source_repo_zip_sha256, "ga_release_candidate_source_zip_hash_invalid")
        existing = self._candidate(candidate_id)
        if existing:
            same = (
                existing.get("version") == version
                and existing.get("source_repo_zip_sha256") == digest
                and existing.get("source_repo_zip_name") == name
            )
            if same:
                return existing
            raise GAReleaseCandidateError("ga_release_candidate_id_immutable", status_code=409)
        if self._candidate():
            raise GAReleaseCandidateError("ga_release_candidate_already_created", status_code=409)
        return self._append("candidate_created", {
            "candidate_id": candidate_id,
            "version": version,
            "source_repo_zip_name": name,
            "source_repo_zip_sha256": digest,
            "release_candidate_frozen": False,
            "pass50_complete": False,
        })

    def record_artifact(
        self,
        *,
        candidate_id: str,
        artifact_type: str,
        artifact_version: str,
        reference: str,
        sha256: str,
        present: bool,
        external: bool,
        immutable: bool,
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise GAReleaseCandidateError("ga_release_candidate_artifact_approval_required", status_code=409)
        candidate_id = self._safe_id(candidate_id, "ga_release_candidate_id_invalid")
        candidate = self._candidate(candidate_id)
        if not candidate:
            raise GAReleaseCandidateError("ga_release_candidate_not_found", status_code=404)
        artifact_type = str(artifact_type or "").strip()
        if artifact_type not in self.REQUIRED_ARTIFACT_TYPES:
            raise GAReleaseCandidateError("ga_release_candidate_artifact_type_invalid", status_code=409)
        artifact_version = self._safe_version(artifact_version)
        reference = self._safe_reference(reference)
        digest = self._safe_hash(sha256, "ga_release_candidate_artifact_hash_invalid")
        if artifact_type == "source_repo_zip" and digest != candidate.get("source_repo_zip_sha256"):
            raise GAReleaseCandidateError("ga_release_candidate_source_zip_hash_mismatch", status_code=409)
        if artifact_type in self.EXTERNAL_ARTIFACT_TYPES and external is not True:
            raise GAReleaseCandidateError("ga_release_candidate_external_artifact_must_remain_external", status_code=409)
        rows = [
            row for row in self._rows()
            if row.get("event_type") == "artifact_recorded"
            and row.get("candidate_id") == candidate_id
            and row.get("artifact_type") == artifact_type
        ]
        payload = {
            "candidate_id": candidate_id,
            "artifact_type": artifact_type,
            "artifact_version": artifact_version,
            "reference": reference,
            "sha256": digest,
            "present": bool(present),
            "external": bool(external),
            "immutable": bool(immutable),
        }
        if rows:
            prior = {key: rows[-1].get(key) for key in payload}
            if prior == payload:
                return rows[-1]
            raise GAReleaseCandidateError("ga_release_candidate_artifact_immutable", status_code=409)
        if len([row for row in self._rows() if row.get("event_type") == "artifact_recorded"]) >= MAX_ARTIFACTS:
            raise GAReleaseCandidateError("ga_release_candidate_artifact_limit_exceeded", status_code=409)
        return self._append("artifact_recorded", payload)

    def record_signoff(
        self,
        *,
        candidate_id: str,
        role: str,
        signer_label: str,
        status: str,
        signed_at: str,
        evidence_sha256: str,
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise GAReleaseCandidateError("ga_release_candidate_signoff_approval_required", status_code=409)
        candidate_id = self._safe_id(candidate_id, "ga_release_candidate_id_invalid")
        if not self._candidate(candidate_id):
            raise GAReleaseCandidateError("ga_release_candidate_not_found", status_code=404)
        role = str(role or "").strip().casefold()
        if role not in self.REQUIRED_SIGNOFF_ROLES:
            raise GAReleaseCandidateError("ga_release_candidate_signoff_role_invalid", status_code=409)
        status = str(status or "").strip().casefold()
        if status not in self.SIGNOFF_STATUSES:
            raise GAReleaseCandidateError("ga_release_candidate_signoff_status_invalid", status_code=409)
        signer_label = self._safe_id(signer_label, "ga_release_candidate_signer_label_invalid")
        signed_at = self._safe_signed_at(signed_at)
        evidence = self._safe_hash(evidence_sha256, "ga_release_candidate_signoff_hash_invalid")
        existing = [
            row for row in self._rows()
            if row.get("event_type") == "signoff_recorded"
            and row.get("candidate_id") == candidate_id
            and row.get("role") == role
        ]
        if existing and existing[-1].get("status") == "approved":
            raise GAReleaseCandidateError("ga_release_candidate_approved_signoff_immutable", status_code=409)
        return self._append("signoff_recorded", {
            "candidate_id": candidate_id,
            "role": role,
            "signer_label": signer_label,
            "status": status,
            "signed_at": signed_at,
            "evidence_sha256": evidence,
            "application_independently_verifies_signer_authority": False,
        })

    def record_blocker(
        self,
        *,
        candidate_id: str,
        blocker_id: str,
        severity: str,
        status: str,
        description_code: str,
        evidence_sha256: str,
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise GAReleaseCandidateError("ga_release_candidate_blocker_approval_required", status_code=409)
        candidate_id = self._safe_id(candidate_id, "ga_release_candidate_id_invalid")
        if not self._candidate(candidate_id):
            raise GAReleaseCandidateError("ga_release_candidate_not_found", status_code=404)
        blocker_id = self._safe_id(blocker_id, "ga_release_candidate_blocker_id_invalid")
        severity = str(severity or "").strip().upper()
        status = str(status or "").strip().casefold()
        if severity not in self.BLOCKER_SEVERITIES:
            raise GAReleaseCandidateError("ga_release_candidate_blocker_severity_invalid", status_code=409)
        if status not in self.BLOCKER_STATUSES:
            raise GAReleaseCandidateError("ga_release_candidate_blocker_status_invalid", status_code=409)
        description_code = self._safe_id(description_code, "ga_release_candidate_blocker_description_invalid")
        evidence = self._safe_hash(evidence_sha256, "ga_release_candidate_blocker_hash_invalid")
        current = [
            row for row in self._rows()
            if row.get("event_type") == "blocker_recorded"
            and row.get("candidate_id") == candidate_id
            and row.get("blocker_id") == blocker_id
        ]
        if len(current) >= MAX_BLOCKERS:
            raise GAReleaseCandidateError("ga_release_candidate_blocker_limit_exceeded", status_code=409)
        return self._append("blocker_recorded", {
            "candidate_id": candidate_id,
            "blocker_id": blocker_id,
            "severity": severity,
            "status": status,
            "description_code": description_code,
            "evidence_sha256": evidence,
        })

    def _latest_inventory(self, candidate_id: str) -> tuple[list[ReleaseArtifact], list[ReleaseSignoff], list[ReleaseBlocker]]:
        artifacts: dict[str, ReleaseArtifact] = {}
        signoffs: dict[str, ReleaseSignoff] = {}
        blockers: dict[str, ReleaseBlocker] = {}
        for row in self._rows():
            if row.get("candidate_id") != candidate_id:
                continue
            if row.get("event_type") == "artifact_recorded":
                artifacts[str(row.get("artifact_type"))] = ReleaseArtifact(
                    name=str(row.get("artifact_type") or ""),
                    artifact_type=str(row.get("artifact_type") or ""),
                    version=str(row.get("artifact_version") or ""),
                    path_or_uri=str(row.get("reference") or ""),
                    sha256=str(row.get("sha256") or ""),
                    present=row.get("present") is True,
                    external=row.get("external") is True,
                    immutable=row.get("immutable") is True,
                    generated_at=str(row.get("recorded_at") or ""),
                )
            elif row.get("event_type") == "signoff_recorded":
                signoffs[str(row.get("role") or "")] = ReleaseSignoff(
                    role=str(row.get("role") or ""),
                    signer=str(row.get("signer_label") or ""),
                    status=str(row.get("status") or ""),
                    signed_at=str(row.get("signed_at") or ""),
                    notes=f"evidence_sha256:{row.get('evidence_sha256')}",
                )
            elif row.get("event_type") == "blocker_recorded":
                blockers[str(row.get("blocker_id") or "")] = ReleaseBlocker(
                    blocker_id=str(row.get("blocker_id") or ""),
                    severity=str(row.get("severity") or ""),
                    status=str(row.get("status") or ""),
                    description=str(row.get("description_code") or ""),
                )
        return list(artifacts.values()), list(signoffs.values()), list(blockers.values())

    def freeze_candidate(
        self,
        *,
        candidate_id: str,
        audit_enterprise_readiness_status: str,
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise GAReleaseCandidateError("ga_release_candidate_freeze_approval_required", status_code=409)
        candidate_id = self._safe_id(candidate_id, "ga_release_candidate_id_invalid")
        candidate = self._candidate(candidate_id)
        if not candidate:
            raise GAReleaseCandidateError("ga_release_candidate_not_found", status_code=404)
        readiness = str(audit_enterprise_readiness_status or "").strip().casefold()
        if readiness not in {"pass", "blocked", "fail"}:
            raise GAReleaseCandidateError("ga_release_candidate_readiness_status_invalid", status_code=409)
        artifacts, signoffs, blockers = self._latest_inventory(candidate_id)
        report = ReleaseCandidateAuditor(project_root=self.repo_root).audit(
            version=str(candidate.get("version") or ""),
            artifacts=artifacts,
            signoffs=signoffs,
            blockers=blockers,
            audit_enterprise_readiness_status=readiness,
        ).as_dict()
        event = self._append("freeze_evaluated", {
            "candidate_id": candidate_id,
            "status": report["status"],
            "release_candidate_frozen": report["release_candidate_frozen"],
            "artifact_inventory_hash": report["artifact_inventory_hash"],
            "audit_enterprise_readiness_status": readiness,
            "open_p0_p1_count": len(report["open_p0_p1_blockers"]),
            "blockers": report["blockers"],
            "report_sha256": _sha_bytes(_canonical_json(report)),
            "pass50_complete": False,
            "external_release_signoff_required": True,
        })
        return {"event": event, "report": report, **self.status(candidate_id=candidate_id)}

    def status(self, *, candidate_id: str | None = None) -> dict[str, Any]:
        verification = self.verify()
        candidate = self._candidate(candidate_id)
        blockers: list[str] = []
        if self.root is None:
            blockers.append("release_root_not_configured")
        if verification["status"] != "pass":
            blockers.append("ga_release_candidate_ledger_verification_failed")
        if not candidate:
            blockers.append("ga_release_candidate_not_created")
            return {
                "schema_version": "ga_release_candidate_status_v1",
                "status": "blocked",
                "stage": "ga_release_candidate_operations",
                "policy_version": str(self.policy.get("version") or "unknown"),
                "product_version": str(self.policy.get("product_version") or "unknown"),
                "candidate_id": "",
                "release_candidate_frozen": False,
                "pass50_complete": False,
                "external_launch_evidence_gate_required": True,
                "blockers": blockers,
                "ledger_verification": verification,
            }
        cid = str(candidate.get("candidate_id") or "")
        artifacts, signoffs, blocker_objs = self._latest_inventory(cid)
        artifact_types = {item.artifact_type for item in artifacts}
        signoff_by_role = {item.role: item.status for item in signoffs}
        missing_artifacts = sorted(self.REQUIRED_ARTIFACT_TYPES - artifact_types)
        missing_signoffs = sorted(role for role in self.REQUIRED_SIGNOFF_ROLES if signoff_by_role.get(role) != "approved")
        open_p0_p1 = sorted(
            item.blocker_id for item in blocker_objs
            if item.status != "closed" and item.severity.upper() in {"P0", "P1"}
        )
        blockers.extend(f"missing_artifact:{item}" for item in missing_artifacts)
        blockers.extend(f"required_signoff_not_approved:{item}" for item in missing_signoffs)
        blockers.extend(f"open_release_blocker:{item}" for item in open_p0_p1)
        freeze_events = [
            row for row in self._rows()
            if row.get("event_type") == "freeze_evaluated" and row.get("candidate_id") == cid
        ]
        freeze = freeze_events[-1] if freeze_events else None
        if not freeze or freeze.get("release_candidate_frozen") is not True:
            blockers.append("release_candidate_not_frozen")
        state = "ready_for_external_pass50_gate" if not blockers else "blocked"
        return {
            "schema_version": "ga_release_candidate_status_v1",
            "status": state,
            "stage": "ga_release_candidate_operations",
            "policy_version": str(self.policy.get("version") or "unknown"),
            "product_version": str(candidate.get("version") or ""),
            "candidate_id": cid,
            "source_repo_zip_name": candidate.get("source_repo_zip_name"),
            "source_repo_zip_sha256": candidate.get("source_repo_zip_sha256"),
            "artifact_count": len(artifacts),
            "required_artifact_count": len(self.REQUIRED_ARTIFACT_TYPES),
            "recorded_artifact_types": sorted(artifact_types),
            "missing_artifact_types": missing_artifacts,
            "signoffs": dict(sorted(signoff_by_role.items())),
            "missing_or_unapproved_signoffs": missing_signoffs,
            "open_p0_p1_blockers": open_p0_p1,
            "release_candidate_frozen": bool(freeze and freeze.get("release_candidate_frozen") is True),
            "artifact_inventory_hash": str((freeze or {}).get("artifact_inventory_hash") or ""),
            "blockers": sorted(set(blockers)),
            "ledger_verification": verification,
            "pass50_complete": False,
            "external_launch_evidence_gate_required": True,
            "application_independently_verifies_signer_authority": False,
            "application_claims_store_or_ga_approval": False,
        }

    def _snapshot(self) -> dict[str, Any]:
        rows = self._rows()
        verification = self._verify_rows(rows)
        return {
            "schema_version": "ga_release_candidate_evidence_v1",
            "generated_at": _now_iso(),
            "status": self.status(),
            "ledger_sha256": verification.get("latest_record_sha256"),
            "events": rows,
            "private_matter_content_included": False,
            "pass50_complete": False,
            "external_launch_evidence_gate_required": True,
        }

    @staticmethod
    def _render_html(snapshot: dict[str, Any]) -> str:
        status = snapshot.get("status") or {}
        rows = "".join(
            f"<tr><td>{html.escape(str(row.get('artifact_type') or ''))}</td>"
            f"<td>{html.escape(str(row.get('artifact_version') or ''))}</td>"
            f"<td><code>{html.escape(str(row.get('sha256') or ''))}</code></td></tr>"
            for row in snapshot.get("events") or []
            if row.get("event_type") == "artifact_recorded"
        )
        return (
            "<!doctype html><html><head><meta charset='utf-8'><title>GA Release Candidate Evidence</title>"
            "<style>body{font-family:system-ui;margin:2rem;line-height:1.45}table{border-collapse:collapse;width:100%}th,td{border:1px solid #bbb;padding:.55rem;text-align:left}code{word-break:break-all}.blocked{color:#8b1e1e}.pass{color:#146c2e}</style></head><body>"
            f"<h1>GA Release Candidate Evidence</h1><p>Status: <strong>{html.escape(str(status.get('status') or 'blocked'))}</strong></p>"
            "<p>This packet records software-side Pass 50 operations. It does not create legal, security, product, ops, Store, or GA approval.</p>"
            f"<p>Candidate: <code>{html.escape(str(status.get('candidate_id') or ''))}</code> · Version {html.escape(str(status.get('product_version') or ''))}</p>"
            "<table><thead><tr><th>Artifact type</th><th>Version</th><th>SHA-256</th></tr></thead><tbody>"
            + rows
            + "</tbody></table>"
            f"<h2>Blockers</h2><pre>{html.escape(json.dumps(status.get('blockers') or [], indent=2))}</pre>"
            "</body></html>"
        )

    @staticmethod
    def _write_immutable(path: Path, data: bytes) -> None:
        if path.exists() and path.is_symlink():
            raise GAReleaseCandidateError("ga_release_candidate_evidence_symlink_refused", status_code=409)
        if path.exists() and path.read_bytes() != data:
            raise GAReleaseCandidateError("ga_release_candidate_generation_collision", status_code=409)
        path.write_bytes(data)

    def build_evidence_packet(self, *, approved: bool) -> dict[str, Any]:
        if approved is not True:
            raise GAReleaseCandidateError("ga_release_candidate_evidence_approval_required", status_code=409)
        if self.root is None or self.evidence_root is None:
            raise GAReleaseCandidateError("release_root_not_configured", status_code=409)
        snapshot = self._snapshot()
        generation_id = _sha_bytes(_canonical_json(snapshot))
        generation = self.evidence_root / generation_id
        if self.evidence_root.exists() and self.evidence_root.is_symlink():
            raise GAReleaseCandidateError("ga_release_candidate_evidence_symlink_refused", status_code=409)
        if generation.exists() and generation.is_symlink():
            raise GAReleaseCandidateError("ga_release_candidate_evidence_symlink_refused", status_code=409)
        generation.mkdir(parents=True, exist_ok=True)
        packet_bytes = json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n"
        html_bytes = self._render_html(snapshot).encode("utf-8")
        packet_path = generation / "ga-release-candidate.json"
        html_path = generation / "ga-release-candidate.html"
        receipt_path = generation / "ga-release-candidate-receipt.json"
        self._write_immutable(packet_path, packet_bytes)
        self._write_immutable(html_path, html_bytes)
        receipt = {
            "schema_version": "ga_release_candidate_receipt_v1",
            "generation_id": generation_id,
            "packet_sha256": _sha_bytes(packet_bytes),
            "html_sha256": _sha_bytes(html_bytes),
            "ledger_sha256": snapshot.get("ledger_sha256"),
            "status": (snapshot.get("status") or {}).get("status"),
            "pass50_complete": False,
        }
        receipt_bytes = json.dumps(receipt, indent=2, sort_keys=True).encode("utf-8") + b"\n"
        self._write_immutable(receipt_path, receipt_bytes)
        artifacts = [
            {"filename": path.name, "sha256": _sha_file(path), "size_bytes": path.stat().st_size}
            for path in (packet_path, html_path, receipt_path)
        ]
        manifest = {
            "schema_version": "ga_release_candidate_artifact_manifest_v1",
            "generation_id": generation_id,
            "artifacts": sorted(artifacts, key=lambda row: row["filename"]),
        }
        manifest_path = generation / "artifact-manifest.json"
        self._write_immutable(manifest_path, json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8") + b"\n")
        self.verify_generation(generation_id)
        return {
            "schema_version": "ga_release_candidate_build_result_v1",
            "status": "pass",
            "generation_id": generation_id,
            "candidate_status": (snapshot.get("status") or {}).get("status"),
            "artifacts": [
                {"filename": filename, "sha256": _sha_file(generation / filename), "size_bytes": (generation / filename).stat().st_size}
                for filename in sorted(self.ARTIFACT_FILENAMES)
            ],
            "pass50_complete": False,
            "external_launch_evidence_gate_required": True,
        }

    def verify_generation(self, generation_id: str) -> dict[str, Any]:
        generation_id = self._safe_hash(generation_id, "ga_release_candidate_generation_id_invalid")
        if self.evidence_root is None:
            raise GAReleaseCandidateError("release_root_not_configured", status_code=409)
        generation = self.evidence_root / generation_id
        if not generation.is_dir() or generation.is_symlink():
            raise GAReleaseCandidateError("ga_release_candidate_generation_not_found", status_code=404)
        try:
            manifest = strict_json_loads((generation / "artifact-manifest.json").read_bytes(), max_bytes=8 * 1024 * 1024, require_object=True)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, StrictJSONError) as exc:
            raise GAReleaseCandidateError("ga_release_candidate_manifest_invalid", status_code=409) from exc
        rows = manifest.get("artifacts") if isinstance(manifest, dict) else None
        expected = self.ARTIFACT_FILENAMES - {"artifact-manifest.json"}
        if not isinstance(rows, list) or manifest.get("generation_id") != generation_id:
            raise GAReleaseCandidateError("ga_release_candidate_manifest_invalid", status_code=409)
        names = {str(row.get("filename") or "") for row in rows if isinstance(row, dict)}
        if names != expected or len(rows) != len(expected):
            raise GAReleaseCandidateError("ga_release_candidate_manifest_artifact_set_mismatch", status_code=409)
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
            packet = strict_json_loads((generation / "ga-release-candidate.json").read_bytes(), max_bytes=16 * 1024 * 1024, require_object=True)
            receipt = strict_json_loads((generation / "ga-release-candidate-receipt.json").read_bytes(), max_bytes=16 * 1024 * 1024, require_object=True)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, StrictJSONError):
            blockers.append("packet_or_receipt_invalid")
            packet, receipt = {}, {}
        if not isinstance(packet, dict) or _sha_bytes(_canonical_json(packet)) != generation_id:
            blockers.append("generation_content_hash_mismatch")
        if str(receipt.get("generation_id") or "") != generation_id:
            blockers.append("receipt_generation_id_mismatch")
        if str(receipt.get("packet_sha256") or "") != _sha_file(generation / "ga-release-candidate.json"):
            blockers.append("receipt_packet_hash_mismatch")
        if str(receipt.get("html_sha256") or "") != _sha_file(generation / "ga-release-candidate.html"):
            blockers.append("receipt_html_hash_mismatch")
        if blockers:
            raise GAReleaseCandidateError("ga_release_candidate_generation_verification_failed", status_code=409)
        return {"status": "pass", "generation_id": generation_id, "blockers": []}

    def resolve_artifact(self, generation_id: str, filename: str) -> tuple[Path, str]:
        generation_id = self._safe_hash(generation_id, "ga_release_candidate_generation_id_invalid")
        filename = str(filename or "").strip()
        if filename not in self.ARTIFACT_FILENAMES:
            raise GAReleaseCandidateError("ga_release_candidate_artifact_not_allowed", status_code=404)
        self.verify_generation(generation_id)
        if self.evidence_root is None:
            raise GAReleaseCandidateError("release_root_not_configured", status_code=409)
        path = self.evidence_root / generation_id / filename
        return path, "text/html" if filename.endswith(".html") else "application/json"


__all__ = ["GAReleaseCandidateError", "GAReleaseCandidateOperationsStore"]
