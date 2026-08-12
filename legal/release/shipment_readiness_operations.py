"""Pass 51 GA shipment-readiness operations and immutable evidence.

The control plane records a versioned shipment manifest, release-channel
qualification evidence, GA-definition controls, blockers, and deterministic
operator evidence.  It deliberately does not claim Store approval, deployment,
or GA shipment.  Pass 51 remains an external evidence gate.
"""

from __future__ import annotations

import html
import json
import os
import re
import threading
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
from legal.release.ga_release import GAShipmentAuditor, ReleaseArtifact

MAX_LEDGER_ROWS = 50_000
MAX_ARTIFACTS = 96
MAX_BLOCKERS = 1_000
_SHIPMENT_LOCK = threading.RLock()
_URI_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:[^\s]{1,500}")
_ALLOWED_REFERENCE_SCHEMES = {"https", "urn"}
_VERSION_RE = re.compile(r"[0-9]+(?:\.[0-9]+){2}(?:[A-Za-z0-9_.+-]*)?")


class GAShipmentReadinessError(ReleasePilotHardeningError):
    """Fail-closed shipment-readiness error with an API-safe code."""


class GAShipmentReadinessStore:
    """Durable, external-root Pass 51 shipment-readiness operations."""

    REQUIRED_ARTIFACT_TYPES = set(GAShipmentAuditor.REQUIRED_ARTIFACT_TYPES)
    EXTERNAL_ARTIFACT_TYPES = set(GAShipmentAuditor.EXTERNAL_ARTIFACT_TYPES)
    REQUIRED_CONTROLS = set(GAShipmentAuditor.REQUIRED_CONTROLS)
    CHANNELS = {"source_release", "microsoft_store", "enterprise_managed"}
    CHANNEL_STATUSES = {"planned", "qualified", "released", "revoked"}
    BLOCKER_SEVERITIES = {"P0", "P1", "P2", "P3"}
    BLOCKER_STATUSES = {"open", "mitigated_pending_retest", "closed"}
    ARTIFACT_FILENAMES = {
        "ga-shipment-readiness.json",
        "ga-shipment-readiness.html",
        "ga-shipment-readiness-receipt.json",
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
            raise GAShipmentReadinessError(exc.code, status_code=exc.status_code) from exc
        self.ledger_path = self.root / "ga-shipment-readiness-ledger.jsonl" if self.root else None
        self.evidence_root = self.root / "ga-shipment-readiness-evidence" if self.root else None
        self.policy_path = Path(policy_path) if policy_path else self.repo_root / "configs" / "maine_ga_shipment_readiness_policy.json"
        self.policy = self._load_policy()

    def _load_policy(self) -> dict[str, Any]:
        try:
            payload = strict_json_load_path(self.policy_path, max_bytes=2 * 1024 * 1024, require_object=True)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, StrictJSONError) as exc:
            raise GAShipmentReadinessError("ga_shipment_policy_unavailable", status_code=409) from exc
        if not isinstance(payload, dict):
            raise GAShipmentReadinessError("ga_shipment_policy_invalid", status_code=409)
        return payload

    @staticmethod
    def _safe_id(value: Any, code: str) -> str:
        text = str(value or "").strip()
        if not _SAFE_ID_RE.fullmatch(text):
            raise GAShipmentReadinessError(code, status_code=409)
        return text

    @staticmethod
    def _safe_hash(value: Any, code: str, *, required: bool = True) -> str:
        text = str(value or "").strip().casefold()
        if not text and not required:
            return ""
        if not _HASH_RE.fullmatch(text):
            raise GAShipmentReadinessError(code, status_code=409)
        return text

    @staticmethod
    def _safe_version(value: Any) -> str:
        text = str(value or "").strip()
        if not _VERSION_RE.fullmatch(text):
            raise GAShipmentReadinessError("ga_shipment_version_invalid", status_code=409)
        return text

    @staticmethod
    def _safe_reference(value: Any) -> str:
        text = str(value or "").strip()
        if not text or len(text) > 512 or "\\" in text or text.startswith("/") or ".." in text.split("/"):
            raise GAShipmentReadinessError("ga_shipment_reference_invalid", status_code=409)
        if _SAFE_ID_RE.fullmatch(text):
            return text
        if not _URI_RE.fullmatch(text):
            raise GAShipmentReadinessError("ga_shipment_reference_invalid", status_code=409)
        parsed = urlsplit(text)
        scheme = parsed.scheme.casefold()
        if scheme not in _ALLOWED_REFERENCE_SCHEMES:
            raise GAShipmentReadinessError("ga_shipment_reference_invalid", status_code=409)
        if scheme == "https" and (not parsed.netloc or parsed.username or parsed.password):
            raise GAShipmentReadinessError("ga_shipment_reference_invalid", status_code=409)
        if scheme == "urn" and not parsed.path:
            raise GAShipmentReadinessError("ga_shipment_reference_invalid", status_code=409)
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
            raise GAShipmentReadinessError("ga_shipment_source_zip_name_invalid", status_code=409)
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
            raise GAShipmentReadinessError("ga_shipment_ledger_invalid", status_code=409) from exc
        rows: list[dict[str, Any]] = []
        for line in ledger_text.splitlines():
            if not line.strip():
                continue
            try:
                row = strict_json_loads(line, max_bytes=1024 * 1024, require_object=True)
            except (json.JSONDecodeError, StrictJSONError) as exc:
                raise GAShipmentReadinessError("ga_shipment_ledger_invalid_json", status_code=409) from exc
            if not isinstance(row, dict):
                raise GAShipmentReadinessError("ga_shipment_ledger_invalid_row", status_code=409)
            rows.append(row)
            if len(rows) > MAX_LEDGER_ROWS:
                raise GAShipmentReadinessError("ga_shipment_ledger_row_limit_exceeded", status_code=409)
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
            raise GAShipmentReadinessError("release_root_not_configured", status_code=409)
        lock_path = self.ledger_path.with_name(self.ledger_path.name + ".lock")
        with _SHIPMENT_LOCK, exclusive_file_lock(lock_path):
            rows = self._rows(lock_held=True)
            verification = self._verify_rows(rows)
            if verification["status"] != "pass":
                raise GAShipmentReadinessError("ga_shipment_ledger_verification_failed", status_code=409)
            previous = str(rows[-1].get("record_sha256") or "") if rows else "0" * 64
            body = {
                "schema_version": "ga_shipment_readiness_event_v1",
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
                raise GAShipmentReadinessError("ga_shipment_ledger_invalid", status_code=409) from exc
            return body

    def _shipment(self, shipment_id: str | None = None) -> dict[str, Any] | None:
        rows = [row for row in self._rows() if row.get("event_type") == "shipment_created"]
        if shipment_id:
            rows = [row for row in rows if row.get("shipment_id") == shipment_id]
        return rows[-1] if rows else None

    def create_shipment(
        self,
        *,
        shipment_id: str,
        version: str,
        source_repo_zip_name: str,
        source_repo_zip_sha256: str,
        release_candidate_id: str,
        release_candidate_report_sha256: str,
        release_candidate_inventory_hash: str,
        release_channel: str,
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise GAShipmentReadinessError("ga_shipment_approval_required", status_code=409)
        shipment_id = self._safe_id(shipment_id, "ga_shipment_id_invalid")
        version = self._safe_version(version)
        expected = str(self.policy.get("product_version") or "").strip()
        if expected and version != expected:
            raise GAShipmentReadinessError("ga_shipment_version_mismatch", status_code=409)
        source_name = self._safe_zip_name(source_repo_zip_name)
        channel = str(release_channel or "").strip().casefold()
        if channel not in self.CHANNELS:
            raise GAShipmentReadinessError("ga_shipment_channel_invalid", status_code=409)
        payload = {
            "shipment_id": shipment_id,
            "version": version,
            "source_repo_zip_name": source_name,
            "source_repo_zip_sha256": self._safe_hash(source_repo_zip_sha256, "ga_shipment_source_zip_hash_invalid"),
            "release_candidate_id": self._safe_id(release_candidate_id, "ga_shipment_release_candidate_id_invalid"),
            "release_candidate_report_sha256": self._safe_hash(release_candidate_report_sha256, "ga_shipment_release_candidate_report_hash_invalid"),
            "release_candidate_inventory_hash": self._safe_hash(release_candidate_inventory_hash, "ga_shipment_release_candidate_inventory_hash_invalid"),
            "release_channel": channel,
            "pass51_complete": False,
        }
        current = self._shipment(shipment_id)
        if current:
            comparable = {key: current.get(key) for key in payload}
            if comparable != payload:
                raise GAShipmentReadinessError("ga_shipment_id_immutable", status_code=409)
            return current
        return self._append("shipment_created", payload)

    def record_artifact(
        self,
        *,
        shipment_id: str,
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
            raise GAShipmentReadinessError("ga_shipment_artifact_approval_required", status_code=409)
        shipment_id = self._safe_id(shipment_id, "ga_shipment_id_invalid")
        shipment = self._shipment(shipment_id)
        if not shipment:
            raise GAShipmentReadinessError("ga_shipment_not_found", status_code=404)
        artifact_type = str(artifact_type or "").strip()
        if artifact_type not in self.REQUIRED_ARTIFACT_TYPES:
            raise GAShipmentReadinessError("ga_shipment_artifact_type_invalid", status_code=409)
        digest = self._safe_hash(sha256, "ga_shipment_artifact_hash_invalid")
        if artifact_type == "clean_source_zip" and digest != shipment.get("source_repo_zip_sha256"):
            raise GAShipmentReadinessError("ga_shipment_source_zip_hash_mismatch", status_code=409)
        if artifact_type in self.EXTERNAL_ARTIFACT_TYPES and external is not True:
            raise GAShipmentReadinessError("ga_shipment_external_artifact_must_remain_external", status_code=409)
        payload = {
            "shipment_id": shipment_id,
            "artifact_type": artifact_type,
            "artifact_version": self._safe_version(artifact_version),
            "reference": self._safe_reference(reference),
            "sha256": digest,
            "present": bool(present),
            "external": bool(external),
            "immutable": bool(immutable),
        }
        rows = [row for row in self._rows() if row.get("event_type") == "artifact_recorded" and row.get("shipment_id") == shipment_id and row.get("artifact_type") == artifact_type]
        if rows:
            previous = rows[-1]
            if {key: previous.get(key) for key in payload} != payload:
                raise GAShipmentReadinessError("ga_shipment_artifact_immutable", status_code=409)
            return previous
        if len([row for row in self._rows() if row.get("event_type") == "artifact_recorded" and row.get("shipment_id") == shipment_id]) >= MAX_ARTIFACTS:
            raise GAShipmentReadinessError("ga_shipment_artifact_limit_exceeded", status_code=409)
        return self._append("artifact_recorded", payload)

    def record_control(
        self,
        *,
        shipment_id: str,
        control: str,
        satisfied: bool,
        evidence_sha256: str,
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise GAShipmentReadinessError("ga_shipment_control_approval_required", status_code=409)
        shipment_id = self._safe_id(shipment_id, "ga_shipment_id_invalid")
        if not self._shipment(shipment_id):
            raise GAShipmentReadinessError("ga_shipment_not_found", status_code=404)
        control = str(control or "").strip()
        if control not in self.REQUIRED_CONTROLS:
            raise GAShipmentReadinessError("ga_shipment_control_invalid", status_code=409)
        payload = {
            "shipment_id": shipment_id,
            "control": control,
            "satisfied": bool(satisfied),
            "evidence_sha256": self._safe_hash(evidence_sha256, "ga_shipment_control_hash_invalid"),
        }
        rows = [row for row in self._rows() if row.get("event_type") == "control_recorded" and row.get("shipment_id") == shipment_id and row.get("control") == control]
        if rows and rows[-1].get("satisfied") is True and {key: rows[-1].get(key) for key in payload} != payload:
            raise GAShipmentReadinessError("ga_shipment_satisfied_control_immutable", status_code=409)
        return self._append("control_recorded", payload)

    def record_channel(
        self,
        *,
        shipment_id: str,
        channel: str,
        status: str,
        package_sha256: str,
        qualification_evidence_sha256: str,
        rollback_evidence_sha256: str,
        distribution_reference: str,
        receipt_sha256: str,
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise GAShipmentReadinessError("ga_shipment_channel_approval_required", status_code=409)
        shipment_id = self._safe_id(shipment_id, "ga_shipment_id_invalid")
        shipment = self._shipment(shipment_id)
        if not shipment:
            raise GAShipmentReadinessError("ga_shipment_not_found", status_code=404)
        channel = str(channel or "").strip().casefold()
        if channel not in self.CHANNELS or channel != shipment.get("release_channel"):
            raise GAShipmentReadinessError("ga_shipment_channel_mismatch", status_code=409)
        status = str(status or "").strip().casefold()
        if status not in self.CHANNEL_STATUSES:
            raise GAShipmentReadinessError("ga_shipment_channel_status_invalid", status_code=409)
        payload = {
            "shipment_id": shipment_id,
            "channel": channel,
            "status": status,
            "package_sha256": self._safe_hash(package_sha256, "ga_shipment_channel_package_hash_invalid"),
            "qualification_evidence_sha256": self._safe_hash(qualification_evidence_sha256, "ga_shipment_channel_qualification_hash_invalid"),
            "rollback_evidence_sha256": self._safe_hash(rollback_evidence_sha256, "ga_shipment_channel_rollback_hash_invalid"),
            "distribution_reference": self._safe_reference(distribution_reference),
            "receipt_sha256": self._safe_hash(receipt_sha256, "ga_shipment_channel_receipt_hash_invalid"),
        }
        rows = [row for row in self._rows() if row.get("event_type") == "channel_recorded" and row.get("shipment_id") == shipment_id]
        if rows and rows[-1].get("status") == "released" and {key: rows[-1].get(key) for key in payload} != payload:
            raise GAShipmentReadinessError("ga_shipment_released_channel_immutable", status_code=409)
        return self._append("channel_recorded", payload)

    def record_blocker(
        self,
        *,
        shipment_id: str,
        blocker_id: str,
        severity: str,
        status: str,
        description_code: str,
        evidence_sha256: str,
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise GAShipmentReadinessError("ga_shipment_blocker_approval_required", status_code=409)
        shipment_id = self._safe_id(shipment_id, "ga_shipment_id_invalid")
        if not self._shipment(shipment_id):
            raise GAShipmentReadinessError("ga_shipment_not_found", status_code=404)
        blocker_id = self._safe_id(blocker_id, "ga_shipment_blocker_id_invalid")
        severity = str(severity or "").strip().upper()
        status = str(status or "").strip().casefold()
        if severity not in self.BLOCKER_SEVERITIES:
            raise GAShipmentReadinessError("ga_shipment_blocker_severity_invalid", status_code=409)
        if status not in self.BLOCKER_STATUSES:
            raise GAShipmentReadinessError("ga_shipment_blocker_status_invalid", status_code=409)
        payload = {
            "shipment_id": shipment_id,
            "blocker_id": blocker_id,
            "severity": severity,
            "status": status,
            "description_code": self._safe_id(description_code, "ga_shipment_blocker_description_invalid"),
            "evidence_sha256": self._safe_hash(evidence_sha256, "ga_shipment_blocker_hash_invalid"),
        }
        if len([row for row in self._rows() if row.get("event_type") == "blocker_recorded" and row.get("shipment_id") == shipment_id]) >= MAX_BLOCKERS:
            raise GAShipmentReadinessError("ga_shipment_blocker_limit_exceeded", status_code=409)
        return self._append("blocker_recorded", payload)

    def _latest_inventory(self, shipment_id: str) -> tuple[list[ReleaseArtifact], dict[str, bool], list[dict[str, Any]], dict[str, Any] | None]:
        artifacts: dict[str, ReleaseArtifact] = {}
        controls: dict[str, bool] = {}
        blockers: dict[str, dict[str, Any]] = {}
        channel: dict[str, Any] | None = None
        for row in self._rows():
            if row.get("shipment_id") != shipment_id:
                continue
            event = row.get("event_type")
            if event == "artifact_recorded":
                artifacts[str(row.get("artifact_type") or "")] = ReleaseArtifact(
                    name=str(row.get("artifact_type") or "").replace("_", " ").title(),
                    artifact_type=str(row.get("artifact_type") or ""),
                    version=str(row.get("artifact_version") or ""),
                    path_or_uri=str(row.get("reference") or ""),
                    sha256=str(row.get("sha256") or ""),
                    present=bool(row.get("present")),
                    external=bool(row.get("external")),
                    immutable=bool(row.get("immutable")),
                    generated_at=str(row.get("recorded_at") or ""),
                )
            elif event == "control_recorded":
                controls[str(row.get("control") or "")] = bool(row.get("satisfied"))
            elif event == "blocker_recorded":
                blockers[str(row.get("blocker_id") or "")] = dict(row)
            elif event == "channel_recorded":
                channel = dict(row)
        return list(artifacts.values()), controls, list(blockers.values()), channel

    def evaluate_shipment(
        self,
        *,
        shipment_id: str,
        release_candidate_status: str,
        release_candidate_frozen: bool,
        release_candidate_inventory_hash: str,
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise GAShipmentReadinessError("ga_shipment_evaluation_approval_required", status_code=409)
        shipment_id = self._safe_id(shipment_id, "ga_shipment_id_invalid")
        shipment = self._shipment(shipment_id)
        if not shipment:
            raise GAShipmentReadinessError("ga_shipment_not_found", status_code=404)
        supplied_inventory = self._safe_hash(release_candidate_inventory_hash, "ga_shipment_release_candidate_inventory_hash_invalid")
        if supplied_inventory != shipment.get("release_candidate_inventory_hash"):
            raise GAShipmentReadinessError("ga_shipment_release_candidate_inventory_hash_mismatch", status_code=409)
        rc_status = str(release_candidate_status or "").strip().casefold()
        if rc_status not in {"pass", "blocked", "fail"}:
            raise GAShipmentReadinessError("ga_shipment_release_candidate_status_invalid", status_code=409)
        artifacts, controls, blockers, channel = self._latest_inventory(shipment_id)
        rc_report = {
            "status": rc_status,
            "release_candidate_frozen": bool(release_candidate_frozen),
            "artifact_inventory_hash": supplied_inventory,
        }
        report = GAShipmentAuditor().audit(
            version=str(shipment.get("version") or ""),
            release_candidate_report=rc_report,
            artifacts=artifacts,
            controls=controls,
        ).as_dict()
        open_p0_p1 = sorted(
            str(item.get("blocker_id") or "") for item in blockers
            if item.get("status") != "closed" and str(item.get("severity") or "").upper() in {"P0", "P1"}
        )
        extra_blockers = [f"open_{str(item.get('severity') or '').upper()}_blocker:{item.get('blocker_id')}" for item in blockers if item.get("status") != "closed" and str(item.get("severity") or "").upper() in {"P0", "P1"}]
        if not channel or channel.get("status") not in {"qualified", "released"}:
            extra_blockers.append("release_channel_not_qualified")
        software_status = "pass" if report.get("status") == "pass" and not extra_blockers else "blocked"
        combined = sorted(set(list(report.get("blockers") or []) + extra_blockers))
        event = self._append("shipment_evaluated", {
            "shipment_id": shipment_id,
            "software_gate_status": software_status,
            "auditor_status": report.get("status"),
            "shipment_manifest_hash": report.get("shipment_manifest_hash"),
            "release_candidate_inventory_hash": supplied_inventory,
            "release_channel_status": str((channel or {}).get("status") or ""),
            "open_p0_p1_blockers": open_p0_p1,
            "blockers": combined,
            "report_sha256": _sha_bytes(_canonical_json(report)),
            "pass51_complete": False,
            "external_shipment_evidence_required": True,
        })
        return {"event": event, "report": {**report, "status": software_status, "blockers": combined, "ga_shipped": False}, **self.status(shipment_id=shipment_id)}

    def status(self, *, shipment_id: str | None = None) -> dict[str, Any]:
        verification = self.verify()
        shipment = self._shipment(shipment_id)
        blockers: list[str] = []
        if self.root is None:
            blockers.append("release_root_not_configured")
        if verification["status"] != "pass":
            blockers.append("ga_shipment_ledger_verification_failed")
        if not shipment:
            blockers.append("ga_shipment_not_created")
            return {
                "schema_version": "ga_shipment_readiness_status_v1",
                "status": "blocked",
                "stage": "ga_shipment_readiness_operations",
                "policy_version": str(self.policy.get("version") or "unknown"),
                "product_version": str(self.policy.get("product_version") or "unknown"),
                "shipment_id": "",
                "pass51_complete": False,
                "external_shipment_evidence_required": True,
                "blockers": blockers,
                "ledger_verification": verification,
            }
        sid = str(shipment.get("shipment_id") or "")
        artifacts, controls, blocker_rows, channel = self._latest_inventory(sid)
        artifact_types = {item.artifact_type for item in artifacts}
        missing_artifacts = sorted(self.REQUIRED_ARTIFACT_TYPES - artifact_types)
        missing_controls = sorted(control for control in self.REQUIRED_CONTROLS if controls.get(control) is not True)
        open_p0_p1 = sorted(
            str(item.get("blocker_id") or "") for item in blocker_rows
            if item.get("status") != "closed" and str(item.get("severity") or "").upper() in {"P0", "P1"}
        )
        blockers.extend(f"missing_ga_artifact:{item}" for item in missing_artifacts)
        blockers.extend(f"ga_control_not_satisfied:{item}" for item in missing_controls)
        blockers.extend(f"open_shipment_blocker:{item}" for item in open_p0_p1)
        if not channel or channel.get("status") not in {"qualified", "released"}:
            blockers.append("release_channel_not_qualified")
        evals = [row for row in self._rows() if row.get("event_type") == "shipment_evaluated" and row.get("shipment_id") == sid]
        evaluation = evals[-1] if evals else None
        if not evaluation or evaluation.get("software_gate_status") != "pass":
            blockers.append("shipment_software_gate_not_passed")
        state = "ready_for_external_pass51_gate" if not blockers else "blocked"
        return {
            "schema_version": "ga_shipment_readiness_status_v1",
            "status": state,
            "stage": "ga_shipment_readiness_operations",
            "policy_version": str(self.policy.get("version") or "unknown"),
            "product_version": str(shipment.get("version") or ""),
            "shipment_id": sid,
            "release_candidate_id": shipment.get("release_candidate_id"),
            "release_candidate_report_sha256": shipment.get("release_candidate_report_sha256"),
            "release_candidate_inventory_hash": shipment.get("release_candidate_inventory_hash"),
            "source_repo_zip_name": shipment.get("source_repo_zip_name"),
            "source_repo_zip_sha256": shipment.get("source_repo_zip_sha256"),
            "release_channel": shipment.get("release_channel"),
            "release_channel_status": str((channel or {}).get("status") or ""),
            "artifact_count": len(artifacts),
            "required_artifact_count": len(self.REQUIRED_ARTIFACT_TYPES),
            "missing_artifact_types": missing_artifacts,
            "controls": dict(sorted(controls.items())),
            "missing_or_unsatisfied_controls": missing_controls,
            "open_p0_p1_blockers": open_p0_p1,
            "shipment_manifest_hash": str((evaluation or {}).get("shipment_manifest_hash") or ""),
            "blockers": sorted(set(blockers)),
            "ledger_verification": verification,
            "pass51_complete": False,
            "external_shipment_evidence_required": True,
            "application_claims_store_approval": False,
            "application_claims_ga_shipment": False,
        }

    def _snapshot(self) -> dict[str, Any]:
        rows = self._rows()
        verification = self._verify_rows(rows)
        return {
            "schema_version": "ga_shipment_readiness_evidence_v1",
            "generated_at": _now_iso(),
            "status": self.status(),
            "ledger_sha256": verification.get("latest_record_sha256"),
            "events": rows,
            "private_matter_content_included": False,
            "pass51_complete": False,
            "external_shipment_evidence_required": True,
        }

    @staticmethod
    def _render_html(snapshot: dict[str, Any]) -> str:
        status = snapshot.get("status") or {}
        artifacts = "".join(
            f"<tr><td>{html.escape(str(row.get('artifact_type') or ''))}</td><td>{html.escape(str(row.get('artifact_version') or ''))}</td><td><code>{html.escape(str(row.get('sha256') or ''))}</code></td></tr>"
            for row in snapshot.get("events") or [] if row.get("event_type") == "artifact_recorded"
        )
        controls = "".join(
            f"<tr><td>{html.escape(str(row.get('control') or ''))}</td><td>{'yes' if row.get('satisfied') else 'no'}</td><td><code>{html.escape(str(row.get('evidence_sha256') or ''))}</code></td></tr>"
            for row in snapshot.get("events") or [] if row.get("event_type") == "control_recorded"
        )
        return (
            "<!doctype html><html><head><meta charset='utf-8'><title>GA Shipment Readiness Evidence</title>"
            "<style>body{font-family:system-ui;margin:2rem;line-height:1.45}table{border-collapse:collapse;width:100%;margin-bottom:1.5rem}th,td{border:1px solid #bbb;padding:.55rem;text-align:left}code{word-break:break-all}</style></head><body>"
            f"<h1>GA Shipment Readiness Evidence</h1><p>Status: <strong>{html.escape(str(status.get('status') or 'blocked'))}</strong></p>"
            "<p>This packet records software-side Pass 51 readiness. It does not create Store approval, production deployment, or GA shipment.</p>"
            f"<p>Shipment: <code>{html.escape(str(status.get('shipment_id') or ''))}</code> · Version {html.escape(str(status.get('product_version') or ''))}</p>"
            "<h2>Artifacts</h2><table><thead><tr><th>Type</th><th>Version</th><th>SHA-256</th></tr></thead><tbody>" + artifacts + "</tbody></table>"
            "<h2>GA controls</h2><table><thead><tr><th>Control</th><th>Satisfied</th><th>Evidence SHA-256</th></tr></thead><tbody>" + controls + "</tbody></table>"
            f"<h2>Blockers</h2><pre>{html.escape(json.dumps(status.get('blockers') or [], indent=2))}</pre></body></html>"
        )

    @staticmethod
    def _write_immutable(path: Path, data: bytes) -> None:
        if path.exists() and path.is_symlink():
            raise GAShipmentReadinessError("ga_shipment_evidence_symlink_refused", status_code=409)
        if path.exists() and path.read_bytes() != data:
            raise GAShipmentReadinessError("ga_shipment_generation_collision", status_code=409)
        path.write_bytes(data)

    def build_evidence_packet(self, *, approved: bool) -> dict[str, Any]:
        if approved is not True:
            raise GAShipmentReadinessError("ga_shipment_evidence_approval_required", status_code=409)
        if self.root is None or self.evidence_root is None:
            raise GAShipmentReadinessError("release_root_not_configured", status_code=409)
        snapshot = self._snapshot()
        generation_id = _sha_bytes(_canonical_json(snapshot))
        generation = self.evidence_root / generation_id
        if self.evidence_root.exists() and self.evidence_root.is_symlink():
            raise GAShipmentReadinessError("ga_shipment_evidence_symlink_refused", status_code=409)
        if generation.exists() and generation.is_symlink():
            raise GAShipmentReadinessError("ga_shipment_evidence_symlink_refused", status_code=409)
        generation.mkdir(parents=True, exist_ok=True)
        packet_bytes = json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n"
        html_bytes = self._render_html(snapshot).encode("utf-8")
        packet_path = generation / "ga-shipment-readiness.json"
        html_path = generation / "ga-shipment-readiness.html"
        receipt_path = generation / "ga-shipment-readiness-receipt.json"
        self._write_immutable(packet_path, packet_bytes)
        self._write_immutable(html_path, html_bytes)
        receipt = {
            "schema_version": "ga_shipment_readiness_receipt_v1",
            "generation_id": generation_id,
            "packet_sha256": _sha_bytes(packet_bytes),
            "html_sha256": _sha_bytes(html_bytes),
            "ledger_sha256": snapshot.get("ledger_sha256"),
            "status": (snapshot.get("status") or {}).get("status"),
            "pass51_complete": False,
        }
        receipt_bytes = json.dumps(receipt, indent=2, sort_keys=True).encode("utf-8") + b"\n"
        self._write_immutable(receipt_path, receipt_bytes)
        artifacts = [{"filename": path.name, "sha256": _sha_file(path), "size_bytes": path.stat().st_size} for path in (packet_path, html_path, receipt_path)]
        manifest = {"schema_version": "ga_shipment_readiness_artifact_manifest_v1", "generation_id": generation_id, "artifacts": sorted(artifacts, key=lambda row: row["filename"])}
        manifest_path = generation / "artifact-manifest.json"
        self._write_immutable(manifest_path, json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8") + b"\n")
        self.verify_generation(generation_id)
        return {
            "schema_version": "ga_shipment_readiness_build_result_v1",
            "status": "pass",
            "generation_id": generation_id,
            "shipment_status": (snapshot.get("status") or {}).get("status"),
            "artifacts": [{"filename": filename, "sha256": _sha_file(generation / filename), "size_bytes": (generation / filename).stat().st_size} for filename in sorted(self.ARTIFACT_FILENAMES)],
            "pass51_complete": False,
            "external_shipment_evidence_required": True,
        }

    def verify_generation(self, generation_id: str) -> dict[str, Any]:
        generation_id = self._safe_hash(generation_id, "ga_shipment_generation_id_invalid")
        if self.evidence_root is None:
            raise GAShipmentReadinessError("release_root_not_configured", status_code=409)
        generation = self.evidence_root / generation_id
        if not generation.is_dir() or generation.is_symlink():
            raise GAShipmentReadinessError("ga_shipment_generation_not_found", status_code=404)
        try:
            manifest = strict_json_loads((generation / "artifact-manifest.json").read_bytes(), max_bytes=8 * 1024 * 1024, require_object=True)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, StrictJSONError) as exc:
            raise GAShipmentReadinessError("ga_shipment_manifest_invalid", status_code=409) from exc
        rows = manifest.get("artifacts") if isinstance(manifest, dict) else None
        expected = self.ARTIFACT_FILENAMES - {"artifact-manifest.json"}
        if not isinstance(rows, list) or manifest.get("generation_id") != generation_id:
            raise GAShipmentReadinessError("ga_shipment_manifest_invalid", status_code=409)
        names = {str(row.get("filename") or "") for row in rows if isinstance(row, dict)}
        if names != expected or len(rows) != len(expected):
            raise GAShipmentReadinessError("ga_shipment_manifest_artifact_set_mismatch", status_code=409)
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
            packet = strict_json_loads((generation / "ga-shipment-readiness.json").read_bytes(), max_bytes=16 * 1024 * 1024, require_object=True)
            receipt = strict_json_loads((generation / "ga-shipment-readiness-receipt.json").read_bytes(), max_bytes=16 * 1024 * 1024, require_object=True)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, StrictJSONError):
            blockers.append("packet_or_receipt_invalid")
            packet, receipt = {}, {}
        if not isinstance(packet, dict) or _sha_bytes(_canonical_json(packet)) != generation_id:
            blockers.append("generation_content_hash_mismatch")
        if str(receipt.get("generation_id") or "") != generation_id:
            blockers.append("receipt_generation_id_mismatch")
        if str(receipt.get("packet_sha256") or "") != _sha_file(generation / "ga-shipment-readiness.json"):
            blockers.append("receipt_packet_hash_mismatch")
        if str(receipt.get("html_sha256") or "") != _sha_file(generation / "ga-shipment-readiness.html"):
            blockers.append("receipt_html_hash_mismatch")
        if blockers:
            raise GAShipmentReadinessError("ga_shipment_generation_verification_failed", status_code=409)
        return {"status": "pass", "generation_id": generation_id, "blockers": []}

    def resolve_artifact(self, generation_id: str, filename: str) -> tuple[Path, str]:
        generation_id = self._safe_hash(generation_id, "ga_shipment_generation_id_invalid")
        filename = str(filename or "").strip()
        if filename not in self.ARTIFACT_FILENAMES:
            raise GAShipmentReadinessError("ga_shipment_artifact_not_allowed", status_code=404)
        self.verify_generation(generation_id)
        if self.evidence_root is None:
            raise GAShipmentReadinessError("release_root_not_configured", status_code=409)
        path = self.evidence_root / generation_id / filename
        return path, "text/html" if filename.endswith(".html") else "application/json"


__all__ = ["GAShipmentReadinessError", "GAShipmentReadinessStore"]
