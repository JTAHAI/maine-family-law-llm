from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class LaunchEvidenceArtifact:
    pass_number: int
    name: str
    path: str
    required_statuses: tuple[str, ...]
    present: bool
    status_value: str = ""
    sha256: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "pass": self.pass_number,
            "name": self.name,
            "path": self.path,
            "required_statuses": list(self.required_statuses),
            "present": self.present,
            "status_value": self.status_value,
            "sha256": self.sha256,
            "payload_keys": sorted(self.payload.keys()),
        }


@dataclass(frozen=True)
class LaunchEvidenceReport:
    status: str
    readiness: str
    generated_at: str
    artifacts: list[LaunchEvidenceArtifact]
    blockers: list[str] = field(default_factory=list)
    closed_passes: list[int] = field(default_factory=list)
    open_passes: list[int] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "readiness": self.readiness,
            "generated_at": self.generated_at,
            "closed_passes": list(self.closed_passes),
            "open_passes": list(self.open_passes),
            "artifacts": [artifact.as_dict() for artifact in self.artifacts],
            "blockers": sorted(set(self.blockers)),
        }


@dataclass(frozen=True)
class RequiredLaunchArtifact:
    pass_number: int
    name: str
    filename: str
    required_statuses: tuple[str, ...]
    validator: Callable[[dict[str, Any]], list[str]]


def _str_field(payload: dict[str, Any], key: str) -> str:
    return str(payload.get(key) or "").strip()


def _int_field(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key, 0)
    if isinstance(value, bool):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _bool_field(payload: dict[str, Any], key: str) -> bool:
    return payload.get(key) is True


def _require_source(payload: dict[str, Any], expected: str) -> list[str]:
    return [] if _str_field(payload, "source") == expected else [f"source_must_be:{expected}"]


def _require_signature(payload: dict[str, Any]) -> list[str]:
    blockers = []
    if not _str_field(payload, "signed_by"):
        blockers.append("signed_by_missing")
    if not _str_field(payload, "signed_at"):
        blockers.append("signed_at_missing")
    return blockers


def _validate_pass48_attorney_sandbox(payload: dict[str, Any]) -> list[str]:
    blockers = [*_require_source(payload, "external_pilot"), *_require_signature(payload)]
    if _int_field(payload, "attorney_reviewer_count") < 1:
        blockers.append("attorney_reviewer_count_must_be_at_least_1")
    if not _bool_field(payload, "bar_status_verified"):
        blockers.append("bar_status_verified_must_be_true")
    if not _bool_field(payload, "training_complete"):
        blockers.append("training_complete_must_be_true")
    if payload.get("real_matter_allowed") is not False:
        blockers.append("real_matter_allowed_must_be_false")
    if _int_field(payload, "critical_open_count") != 0:
        blockers.append("critical_open_count_must_be_zero")
    if not _bool_field(payload, "feedback_queue_reviewed"):
        blockers.append("feedback_queue_reviewed_must_be_true")
    return blockers


def _validate_pass49_limited_real_matter(payload: dict[str, Any]) -> list[str]:
    blockers = [*_require_source(payload, "external_pilot"), *_require_signature(payload)]
    if _int_field(payload, "matter_count") < 1:
        blockers.append("matter_count_must_be_at_least_1")
    for key in (
        "all_matters_have_explicit_consent",
        "tenant_isolation_verified",
        "encrypted_storage_verified",
        "human_review_completed",
        "attorney_signoff_complete",
        "daily_review_complete",
    ):
        if not _bool_field(payload, key):
            blockers.append(f"{key}_must_be_true")
    if _bool_field(payload, "training_use_allowed"):
        blockers.append("training_use_allowed_must_be_false")
    if _int_field(payload, "data_leakage_count") != 0:
        blockers.append("data_leakage_count_must_be_zero")
    if _int_field(payload, "unsupported_export_attempt_count") != 0:
        blockers.append("unsupported_export_attempt_count_must_be_zero")
    if _int_field(payload, "open_incident_count") != 0:
        blockers.append("open_incident_count_must_be_zero")
    return blockers


def _signoff_roles(payload: dict[str, Any]) -> dict[str, str]:
    signoffs = payload.get("signoffs")
    if not isinstance(signoffs, list):
        return {}
    roles: dict[str, str] = {}
    for signoff in signoffs:
        if isinstance(signoff, dict):
            roles[_str_field(signoff, "role")] = _str_field(signoff, "status")
    return roles


def _validate_pass50_release_candidate(payload: dict[str, Any]) -> list[str]:
    blockers = [*_require_source(payload, "external_release"), *_require_signature(payload)]
    if not _bool_field(payload, "release_candidate_frozen"):
        blockers.append("release_candidate_frozen_must_be_true")
    if _int_field(payload, "open_p0_p1_count") != 0:
        blockers.append("open_p0_p1_count_must_be_zero")
    if not _str_field(payload, "artifact_inventory_hash"):
        blockers.append("artifact_inventory_hash_missing")
    roles = _signoff_roles(payload)
    for role in ("security", "legal", "product", "ops"):
        if roles.get(role) != "approved":
            blockers.append(f"required_signoff_not_approved:{role}")
    return blockers


def _validate_pass51_ga_shipment(payload: dict[str, Any]) -> list[str]:
    blockers = [*_require_source(payload, "external_release"), *_require_signature(payload)]
    if not _bool_field(payload, "ga_shipped"):
        blockers.append("ga_shipped_must_be_true")
    if _str_field(payload, "release_candidate_status") != "pass":
        blockers.append("release_candidate_status_must_be_pass")
    if not _str_field(payload, "shipment_manifest_hash"):
        blockers.append("shipment_manifest_hash_missing")
    controls = payload.get("controls")
    if not isinstance(controls, dict):
        blockers.append("controls_must_be_object")
    else:
        for control in (
            "runs_from_clean_deployment",
            "uses_real_official_maine_authority",
            "attorney_reviewed_evals_present",
            "release_metrics_pass",
            "unsupported_filing_ready_output_blocked",
            "private_matter_data_protected",
            "audit_trails_present",
            "security_controls_present",
            "pilot_evidence_present",
            "rollback_and_maintenance_operations_present",
        ):
            if controls.get(control) is not True:
                blockers.append(f"ga_control_not_satisfied:{control}")
    return blockers


class LaunchEvidenceGate:
    """Fail-closed external evidence gate for Passes 48-51.

    This gate deliberately does not create pilot, signoff, or GA-shipment evidence.
    It verifies externally supplied reports/signoffs and checks that they contain
    enough structured facts to support the pass. A placeholder JSON file with only
    ``{"status": "pass"}`` remains blocked.
    """

    REQUIRED_ARTIFACTS = (
        RequiredLaunchArtifact(48, "attorney_sandbox_pilot_report", "attorney_sandbox_pilot_report.json", ("pass",), _validate_pass48_attorney_sandbox),
        RequiredLaunchArtifact(49, "limited_real_matter_pilot_report", "limited_real_matter_pilot_report.json", ("pass",), _validate_pass49_limited_real_matter),
        RequiredLaunchArtifact(50, "ga_release_candidate_signoff", "ga_release_candidate_signoff.json", ("pass", "signed"), _validate_pass50_release_candidate),
        RequiredLaunchArtifact(51, "ga_shipment_signoff", "ga_shipment_signoff.json", ("pass", "signed"), _validate_pass51_ga_shipment),
    )

    def audit(self, *, pilot_root: str | Path, release_root: str | Path | None = None) -> LaunchEvidenceReport:
        pilot_root = Path(pilot_root)
        release_root = Path(release_root) if release_root is not None else pilot_root
        artifacts: list[LaunchEvidenceArtifact] = []
        blockers: list[str] = []
        closed: list[int] = []
        open_passes: list[int] = []

        for required in self.REQUIRED_ARTIFACTS:
            root = pilot_root if required.pass_number in {48, 49} else release_root
            path = root / required.filename
            artifact, artifact_blockers = self._load_artifact(required=required, path=path)
            artifacts.append(artifact)
            if artifact_blockers:
                blockers.extend(artifact_blockers)
                open_passes.append(required.pass_number)
            else:
                closed.append(required.pass_number)

        status = "pass" if not blockers else "blocked"
        return LaunchEvidenceReport(
            status=status,
            readiness="pass48_51_launch_evidence_ready" if status == "pass" else "pass48_51_launch_evidence_blocked",
            generated_at=datetime.now(timezone.utc).isoformat(),
            artifacts=artifacts,
            blockers=blockers,
            closed_passes=closed,
            open_passes=open_passes,
        )

    def _load_artifact(self, *, required: RequiredLaunchArtifact, path: Path) -> tuple[LaunchEvidenceArtifact, list[str]]:
        if not path.exists() or not path.is_file() or path.stat().st_size == 0:
            return (
                LaunchEvidenceArtifact(
                    pass_number=required.pass_number,
                    name=required.name,
                    path=str(path),
                    required_statuses=required.required_statuses,
                    present=False,
                ),
                [f"pass{required.pass_number}_missing_artifact:{path.name}"],
            )
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return (
                LaunchEvidenceArtifact(
                    pass_number=required.pass_number,
                    name=required.name,
                    path=str(path),
                    required_statuses=required.required_statuses,
                    present=True,
                    sha256=sha,
                ),
                [f"pass{required.pass_number}_artifact_not_json:{path.name}"],
            )
        if not isinstance(payload, dict):
            return (
                LaunchEvidenceArtifact(
                    pass_number=required.pass_number,
                    name=required.name,
                    path=str(path),
                    required_statuses=required.required_statuses,
                    present=True,
                    sha256=sha,
                ),
                [f"pass{required.pass_number}_artifact_not_object:{path.name}"],
            )
        status_value = str(
            payload.get("status")
            or payload.get("readiness")
            or payload.get("signoff_status")
            or payload.get("approval_status")
            or ""
        ).strip()
        artifact = LaunchEvidenceArtifact(
            pass_number=required.pass_number,
            name=required.name,
            path=str(path),
            required_statuses=required.required_statuses,
            present=True,
            status_value=status_value,
            sha256=sha,
            payload=payload,
        )
        artifact_blockers: list[str] = []
        if status_value not in required.required_statuses:
            artifact_blockers.append(
                f"pass{required.pass_number}_artifact_status_not_ready:{path.name}:{status_value or 'missing_status'}"
            )
        artifact_blockers.extend(f"pass{required.pass_number}_{blocker}" for blocker in required.validator(payload))
        return artifact, artifact_blockers
