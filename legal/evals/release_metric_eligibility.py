"""Fail-closed eligibility checks for signed enterprise metric evidence.

This module is deliberately narrower than a release decision.  It verifies
that an externally stored metric-measurement bundle is complete, non-synthetic,
licensed, reproducible, hash-linked, and signed by a key in an externally
provisioned trust configuration.  It does *not* turn a local test fixture, a
role header, or a signature alone into attorney review, pilot evidence, or an
Enterprise GA decision.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from legal.evals.external_eval_root import ExternalEvalRootError, resolve_external_eval_root
from legal.evals.release_measurements import ReleaseMetricMeasurementAuditor, required_external_metric_names
from legal.production.release_gates import ReleaseGateRunner


MEASUREMENT_FILENAME = "release_metric_measurements.json"
ARTIFACT_MANIFEST_FILENAME = "release_metric_artifacts.json"
ATTESTATION_FILENAME = "release_metric_eligibility_attestation.json"
TRUST_FILENAME = "release_metric_eligibility_trust.json"
_HASH = re.compile(r"^[0-9a-f]{64}$")
_SAFE_BUILD_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")
_EXTERNAL_DATA_CLASS = "external_attorney_reviewed"
_LICENSE_STATUS = "externally_verified"
_REPRODUCTION_STATUS = "reproduced"
_REQUIRED_HASH_FIELDS = (
    "source_snapshot_sha256",
    "reviewer_evidence_sha256",
    "license_evidence_sha256",
    "input_manifest_sha256",
    "environment_manifest_sha256",
    "output_manifest_sha256",
)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_object(path: Path, *, max_bytes: int = 2 * 1024 * 1024) -> dict[str, Any] | None:
    try:
        if not path.is_file() or path.stat().st_size > max_bytes:
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    value = payload.get("metrics")
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        return [{"name": str(name), **row} for name, row in value.items() if isinstance(row, dict)]
    return []


def _signature_payload(attestation: dict[str, Any]) -> bytes:
    payload = dict(attestation)
    payload.pop("signature", None)
    return _canonical(payload)


@dataclass(frozen=True)
class ReleaseMetricEligibilityStatus:
    metric: str
    status: str
    blockers: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"metric": self.metric, "status": self.status, "blockers": sorted(set(self.blockers))}


@dataclass
class ReleaseMetricEligibilityReport:
    status: str
    readiness: str
    generated_at: str
    required_metrics: list[str] = field(default_factory=list)
    metric_statuses: list[ReleaseMetricEligibilityStatus] = field(default_factory=list)
    measurement_audit_status: str = "blocked"
    artifact_manifest_verified: bool = False
    attestation_verified: bool = False
    signature_verification: str = "not_verified"
    enterprise_decision_eligible: bool = False
    enterprise_blockers: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    review_required: bool = True
    private_matter_data_used: bool = False
    network_used: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "release_metric_eligibility_report_v1",
            "status": self.status,
            "readiness": self.readiness,
            "generated_at": self.generated_at,
            "required_metrics": self.required_metrics,
            "metric_statuses": [item.as_dict() for item in self.metric_statuses],
            "measurement_audit_status": self.measurement_audit_status,
            "artifact_manifest_verified": self.artifact_manifest_verified,
            "attestation_verified": self.attestation_verified,
            "signature_verification": self.signature_verification,
            "enterprise_decision_eligible": self.enterprise_decision_eligible,
            "enterprise_blockers": sorted(set(self.enterprise_blockers)),
            "blockers": sorted(set(self.blockers)),
            "review_required": self.review_required,
            "private_matter_data_used": self.private_matter_data_used,
            "network_used": self.network_used,
        }


class ReleaseMetricEligibilityGate:
    """Verify the evidence contract before metrics can enter an enterprise gate.

    All inputs remain in a configured external evaluation root.  The report
    intentionally exposes codes and counts, not external paths, source text,
    reviewer identities, or matter data.
    """

    def __init__(self, *, project_root: str | Path = ".", gate_runner: ReleaseGateRunner | None = None) -> None:
        self.project_root = Path(project_root).resolve()
        self.gate_runner = gate_runner or ReleaseGateRunner()

    def run(self, *, eval_root: str | Path | None) -> ReleaseMetricEligibilityReport:
        required = required_external_metric_names(self.gate_runner)
        try:
            if eval_root is None or not str(eval_root).strip():
                raise ExternalEvalRootError("release_metric_eligibility_root_not_configured", "External release-metric evidence root is required.")
            root = resolve_external_eval_root(eval_root, project_root=self.project_root, create=False)
        except ExternalEvalRootError as exc:
            return self._finish(required=required, blockers=[exc.code])

        measurement_path = root / MEASUREMENT_FILENAME
        artifact_path = root / ARTIFACT_MANIFEST_FILENAME
        attestation_path = root / ATTESTATION_FILENAME
        trust_path = root / TRUST_FILENAME
        blockers: list[str] = []
        statuses: list[ReleaseMetricEligibilityStatus] = []

        measurement_audit = ReleaseMetricMeasurementAuditor(project_root=self.project_root, gate_runner=self.gate_runner).audit(
            measurement_path=measurement_path,
        ).as_dict()
        if measurement_audit["status"] != "pass":
            blockers.extend(str(item) for item in measurement_audit.get("blockers") or [])

        measurement = _load_object(measurement_path)
        if measurement is None:
            blockers.append("release_metric_measurement_bundle_unavailable")
            return self._finish(required=required, blockers=blockers, measurement_audit_status=str(measurement_audit["status"]))
        if measurement.get("schema_version") != "release_metric_measurements_v1":
            blockers.append("release_metric_measurement_schema_unsupported")
        metric_rows = {str(row.get("name") or ""): row for row in _rows(measurement)}

        artifacts = _load_object(artifact_path)
        artifact_hashes: set[str] = set()
        artifact_manifest_verified = False
        if artifacts is None or artifacts.get("schema_version") != "release_metric_artifact_manifest_v1":
            blockers.append("release_metric_artifact_manifest_unavailable")
        else:
            values = artifacts.get("artifacts")
            if not isinstance(values, list):
                blockers.append("release_metric_artifact_manifest_malformed")
            else:
                artifact_hashes = {
                    str(item.get("sha256") or "").casefold()
                    for item in values
                    if isinstance(item, dict) and _HASH.fullmatch(str(item.get("sha256") or "").casefold())
                }
                artifact_manifest_verified = bool(artifact_hashes)
                if not artifact_manifest_verified:
                    blockers.append("release_metric_artifact_manifest_empty")

        for name in required:
            row = metric_rows.get(name)
            status = self._audit_metric(name=name, row=row, artifact_hashes=artifact_hashes)
            statuses.append(status)
            blockers.extend(status.blockers)

        attestation_verified, signature_verification, attestation_blockers = self._verify_attestation(
            attestation_path=attestation_path,
            trust_path=trust_path,
            measurement_sha256=_sha256_bytes(measurement_path.read_bytes()),
            artifact_manifest_sha256=_sha256_bytes(artifact_path.read_bytes()) if artifact_path.is_file() else "",
            required=required,
        )
        blockers.extend(attestation_blockers)
        contract_pass = not blockers and artifact_manifest_verified and attestation_verified
        enterprise_blockers = [
            "actual_attorney_evaluation_and_reviewer_credential_evidence_requires_external_governance_review",
            "actual_controlled_pilot_and_organizational_signoffs_required_for_enterprise_decision",
        ]
        return ReleaseMetricEligibilityReport(
            status="pass" if contract_pass else "blocked",
            readiness="release_metric_evidence_eligible_for_external_enterprise_review" if contract_pass else "release_metric_evidence_ineligible",
            generated_at=_now(),
            required_metrics=required,
            metric_statuses=statuses,
            measurement_audit_status=str(measurement_audit["status"]),
            artifact_manifest_verified=artifact_manifest_verified,
            attestation_verified=attestation_verified,
            signature_verification=signature_verification,
            enterprise_decision_eligible=False,
            enterprise_blockers=enterprise_blockers,
            blockers=blockers,
        )

    def _audit_metric(self, *, name: str, row: dict[str, Any] | None, artifact_hashes: set[str]) -> ReleaseMetricEligibilityStatus:
        metric_blockers: list[str] = []
        if row is None:
            return ReleaseMetricEligibilityStatus(metric=name, status="blocked", blockers=[f"metric_evidence_missing:{name}"])
        evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
        if str(evidence.get("data_class") or "").strip().casefold() != _EXTERNAL_DATA_CLASS:
            metric_blockers.append(f"metric_data_class_not_external_attorney_reviewed:{name}")
        if str(evidence.get("license_status") or "").strip().casefold() != _LICENSE_STATUS:
            metric_blockers.append(f"metric_license_not_externally_verified:{name}")
        if not _SAFE_BUILD_ID.fullmatch(str(evidence.get("authority_build_id") or "")):
            metric_blockers.append(f"metric_authority_build_id_invalid:{name}")
        reproduction = evidence.get("reproducibility") if isinstance(evidence.get("reproducibility"), dict) else {}
        if str(reproduction.get("status") or "").strip().casefold() != _REPRODUCTION_STATUS:
            metric_blockers.append(f"metric_reproducibility_not_proven:{name}")
        try:
            repeated_runs = int(reproduction.get("independent_runs", 0) or 0)
        except (TypeError, ValueError):
            repeated_runs = 0
        if repeated_runs < 2:
            metric_blockers.append(f"metric_reproducibility_runs_insufficient:{name}")
        for field in _REQUIRED_HASH_FIELDS:
            value = str(evidence.get(field) or "").casefold()
            if not _HASH.fullmatch(value):
                metric_blockers.append(f"metric_{field}_invalid:{name}")
            elif value not in artifact_hashes:
                metric_blockers.append(f"metric_{field}_not_in_artifact_manifest:{name}")
        return ReleaseMetricEligibilityStatus(metric=name, status="pass" if not metric_blockers else "blocked", blockers=metric_blockers)

    def _verify_attestation(
        self,
        *,
        attestation_path: Path,
        trust_path: Path,
        measurement_sha256: str,
        artifact_manifest_sha256: str,
        required: list[str],
    ) -> tuple[bool, str, list[str]]:
        attestation = _load_object(attestation_path)
        trust = _load_object(trust_path, max_bytes=256 * 1024)
        blockers: list[str] = []
        if attestation is None:
            return False, "not_verified", ["release_metric_attestation_unavailable"]
        if trust is None or trust.get("schema_version") != "release_metric_eligibility_trust_v1":
            blockers.append("release_metric_trust_config_unavailable")
            trust = {}
        if attestation.get("schema_version") != "release_metric_eligibility_attestation_v1":
            blockers.append("release_metric_attestation_schema_unsupported")
        if str(attestation.get("measurement_sha256") or "").casefold() != measurement_sha256:
            blockers.append("release_metric_attestation_measurement_hash_mismatch")
        if str(attestation.get("artifact_manifest_sha256") or "").casefold() != artifact_manifest_sha256:
            blockers.append("release_metric_attestation_artifact_manifest_hash_mismatch")
        metric_names = attestation.get("metric_names")
        if not isinstance(metric_names, list) or sorted(str(item) for item in metric_names) != sorted(required):
            blockers.append("release_metric_attestation_metric_coverage_mismatch")
        signature = attestation.get("signature") if isinstance(attestation.get("signature"), dict) else {}
        keys = trust.get("trusted_keys") if isinstance(trust.get("trusted_keys"), dict) else {}
        key_id = str(signature.get("key_id") or "").strip()
        key_text = keys.get(key_id)
        if not isinstance(key_text, str) or not key_text:
            blockers.append("release_metric_attestation_key_untrusted")
        else:
            try:
                public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(key_text, validate=True))
                public_key.verify(base64.b64decode(str(signature.get("signature") or ""), validate=True), _signature_payload(attestation))
            except (ValueError, InvalidSignature):
                blockers.append("release_metric_attestation_signature_invalid")
        return not blockers, "verified" if not blockers else "blocked", blockers

    def _finish(
        self,
        *,
        required: list[str],
        blockers: list[str],
        measurement_audit_status: str = "blocked",
    ) -> ReleaseMetricEligibilityReport:
        return ReleaseMetricEligibilityReport(
            status="blocked",
            readiness="release_metric_evidence_ineligible",
            generated_at=_now(),
            required_metrics=required,
            measurement_audit_status=measurement_audit_status,
            enterprise_decision_eligible=False,
            enterprise_blockers=[
                "actual_attorney_evaluation_and_reviewer_credential_evidence_requires_external_governance_review",
                "actual_controlled_pilot_and_organizational_signoffs_required_for_enterprise_decision",
            ],
            blockers=blockers,
        )


__all__ = [
    "ARTIFACT_MANIFEST_FILENAME",
    "ATTESTATION_FILENAME",
    "MEASUREMENT_FILENAME",
    "ReleaseMetricEligibilityGate",
    "ReleaseMetricEligibilityReport",
    "ReleaseMetricEligibilityStatus",
    "TRUST_FILENAME",
]
