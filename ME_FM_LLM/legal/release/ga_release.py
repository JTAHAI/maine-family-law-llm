from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from legal.release.release_manifest import ReleaseManifest


@dataclass(frozen=True)
class ReleaseArtifact:
    """A versioned release artifact reference.

    The source repository ZIP may be in the package-build workspace. All legal
    data products, eval packs, indexes, runtime stores, model weights, and
    matter artifacts should be referenced as external manifests/URIs, not copied
    into the source repository ZIP.
    """

    name: str
    artifact_type: str
    version: str
    path_or_uri: str
    sha256: str = ""
    present: bool = True
    external: bool = True
    immutable: bool = True
    generated_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "artifact_type": self.artifact_type,
            "version": self.version,
            "path_or_uri": self.path_or_uri,
            "sha256": self.sha256,
            "present": self.present,
            "external": self.external,
            "immutable": self.immutable,
            "generated_at": self.generated_at,
        }


@dataclass(frozen=True)
class ReleaseSignoff:
    role: str
    signer: str
    status: str
    signed_at: str
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "signer": self.signer,
            "status": self.status,
            "signed_at": self.signed_at,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ReleaseBlocker:
    blocker_id: str
    severity: str
    status: str
    description: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "blocker_id": self.blocker_id,
            "severity": self.severity,
            "status": self.status,
            "description": self.description,
        }


@dataclass(frozen=True)
class ReleaseCandidateAuditReport:
    status: str
    generated_at: str
    release_name: str
    version: str
    source_repo_clean: bool
    release_candidate_frozen: bool
    audit_enterprise_readiness_status: str
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    signoffs: list[dict[str, Any]] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    artifact_inventory_hash: str = ""
    open_p0_p1_blockers: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "generated_at": self.generated_at,
            "release_name": self.release_name,
            "version": self.version,
            "source_repo_clean": self.source_repo_clean,
            "release_candidate_frozen": self.release_candidate_frozen,
            "audit_enterprise_readiness_status": self.audit_enterprise_readiness_status,
            "artifact_inventory_hash": self.artifact_inventory_hash,
            "artifacts": self.artifacts,
            "signoffs": self.signoffs,
            "open_p0_p1_blockers": self.open_p0_p1_blockers,
            "blockers": sorted(set(self.blockers)),
        }


@dataclass(frozen=True)
class GAShipmentAuditReport:
    status: str
    generated_at: str
    release_name: str
    version: str
    ga_shipped: bool
    release_candidate_status: str
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    controls: dict[str, bool] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    shipment_manifest_hash: str = ""
    maintenance_operations_ready: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "generated_at": self.generated_at,
            "release_name": self.release_name,
            "version": self.version,
            "ga_shipped": self.ga_shipped,
            "release_candidate_status": self.release_candidate_status,
            "shipment_manifest_hash": self.shipment_manifest_hash,
            "maintenance_operations_ready": self.maintenance_operations_ready,
            "artifacts": self.artifacts,
            "controls": dict(sorted(self.controls.items())),
            "blockers": sorted(set(self.blockers)),
        }


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _artifact_map(artifacts: Iterable[ReleaseArtifact | dict[str, Any]]) -> dict[str, ReleaseArtifact]:
    mapped: dict[str, ReleaseArtifact] = {}
    for artifact in artifacts:
        if isinstance(artifact, ReleaseArtifact):
            obj = artifact
        else:
            obj = ReleaseArtifact(**artifact)
        mapped[obj.artifact_type] = obj
    return mapped


def _signoff_map(signoffs: Iterable[ReleaseSignoff | dict[str, Any]]) -> dict[str, ReleaseSignoff]:
    mapped: dict[str, ReleaseSignoff] = {}
    for signoff in signoffs:
        if isinstance(signoff, ReleaseSignoff):
            obj = signoff
        else:
            obj = ReleaseSignoff(**signoff)
        mapped[obj.role] = obj
    return mapped


def _blocker_list(blockers: Iterable[ReleaseBlocker | dict[str, Any]]) -> list[ReleaseBlocker]:
    out: list[ReleaseBlocker] = []
    for blocker in blockers:
        if isinstance(blocker, ReleaseBlocker):
            out.append(blocker)
        else:
            out.append(ReleaseBlocker(**blocker))
    return out


class ReleaseCandidateAuditor:
    """Pass 50 release-candidate gate.

    This auditor freezes the artifact/signoff inventory. It does not fabricate
    external source, gold-eval, security, pilot, or legal signoff evidence. Those
    must be passed in as explicit versioned artifact references and approvals.
    """

    REQUIRED_ARTIFACT_TYPES = (
        "source_repo_zip",
        "external_data_build_manifest",
        "parsed_authority_manifest",
        "retrieval_index_manifest",
        "gold_eval_pack_manifest",
        "release_metrics_json",
        "security_evidence_packet",
        "pilot_evidence_packet",
        "rollback_package",
        "release_notes",
    )
    EXTERNAL_ARTIFACT_TYPES = tuple(
        artifact_type
        for artifact_type in REQUIRED_ARTIFACT_TYPES
        if artifact_type not in {"source_repo_zip", "release_notes", "rollback_package"}
    )
    REQUIRED_SIGNOFF_ROLES = ("security", "legal", "product", "ops")

    def __init__(self, *, project_root: str | Path = ".", release_name: str = "maine-family-law-llm") -> None:
        self.project_root = Path(project_root).resolve()
        self.release_name = release_name

    def audit(
        self,
        *,
        version: str,
        artifacts: Iterable[ReleaseArtifact | dict[str, Any]],
        signoffs: Iterable[ReleaseSignoff | dict[str, Any]],
        blockers: Iterable[ReleaseBlocker | dict[str, Any]] = (),
        audit_enterprise_readiness_status: str = "pass",
        output_path: str | Path | None = None,
    ) -> ReleaseCandidateAuditReport:
        artifact_by_type = _artifact_map(artifacts)
        signoff_by_role = _signoff_map(signoffs)
        blocker_objs = _blocker_list(blockers)
        repo_manifest = ReleaseManifest(project_root=self.project_root, version=version).generate()
        report_blockers: list[str] = []

        for artifact_type in self.REQUIRED_ARTIFACT_TYPES:
            artifact = artifact_by_type.get(artifact_type)
            if artifact is None:
                report_blockers.append(f"missing_artifact:{artifact_type}")
                continue
            if not artifact.present:
                report_blockers.append(f"artifact_not_present:{artifact_type}")
            if not artifact.version:
                report_blockers.append(f"artifact_not_versioned:{artifact_type}")
            if not artifact.path_or_uri:
                report_blockers.append(f"artifact_missing_path_or_uri:{artifact_type}")
            if not artifact.immutable:
                report_blockers.append(f"artifact_not_immutable:{artifact_type}")
            if artifact_type in self.EXTERNAL_ARTIFACT_TYPES and not artifact.external:
                report_blockers.append(f"external_artifact_packaged_in_source_repo:{artifact_type}")

        for role in self.REQUIRED_SIGNOFF_ROLES:
            signoff = signoff_by_role.get(role)
            if signoff is None:
                report_blockers.append(f"missing_signoff:{role}")
                continue
            if signoff.status != "approved":
                report_blockers.append(f"signoff_not_approved:{role}")
            if not signoff.signer or not signoff.signed_at:
                report_blockers.append(f"signoff_incomplete:{role}")

        open_p0_p1 = [
            blocker
            for blocker in blocker_objs
            if blocker.status != "closed" and blocker.severity.upper() in {"P0", "P1"}
        ]
        report_blockers.extend(f"open_{blocker.severity.upper()}_blocker:{blocker.blocker_id}" for blocker in open_p0_p1)

        if audit_enterprise_readiness_status != "pass":
            report_blockers.append("audit_enterprise_readiness_not_pass")
        if repo_manifest["contains_private_data"] or repo_manifest["runtime_state_packaged"]:
            report_blockers.append("source_repo_contains_private_or_runtime_artifacts")

        artifact_inventory = [artifact.as_dict() for artifact in sorted(artifact_by_type.values(), key=lambda a: a.artifact_type)]
        signoff_inventory = [signoff.as_dict() for signoff in sorted(signoff_by_role.values(), key=lambda s: s.role)]
        inventory_hash = _stable_hash({"artifacts": artifact_inventory, "signoffs": signoff_inventory, "version": version})
        status = "pass" if not report_blockers else "blocked"
        report = ReleaseCandidateAuditReport(
            status=status,
            generated_at=datetime.now(timezone.utc).isoformat(),
            release_name=self.release_name,
            version=version,
            source_repo_clean=not repo_manifest["contains_private_data"] and not repo_manifest["runtime_state_packaged"],
            release_candidate_frozen=status == "pass",
            audit_enterprise_readiness_status=audit_enterprise_readiness_status,
            artifacts=artifact_inventory,
            signoffs=signoff_inventory,
            blockers=report_blockers,
            artifact_inventory_hash=inventory_hash,
            open_p0_p1_blockers=[blocker.as_dict() for blocker in open_p0_p1],
        )
        if output_path:
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return report


class GAShipmentAuditor:
    """Pass 51 GA shipment gate.

    GA is true only when the release candidate passed and the final shipment
    manifest includes all source, data, eval, security, guide, runbook, rollback,
    and maintenance-operation artifacts plus the explicit GA definition controls.
    """

    REQUIRED_ARTIFACT_TYPES = (
        "clean_source_zip",
        "external_legal_data_product_manifest",
        "parsed_authority_build_manifest",
        "retrieval_indexes_manifest",
        "gold_eval_pack_manifest",
        "smoke_evidence_json",
        "release_metrics_json",
        "security_governance_packet",
        "admin_guide",
        "user_guide",
        "attorney_reviewer_guide",
        "incident_rollback_runbook",
        "source_update_runbook",
        "model_update_runbook",
    )
    EXTERNAL_ARTIFACT_TYPES = (
        "external_legal_data_product_manifest",
        "parsed_authority_build_manifest",
        "retrieval_indexes_manifest",
        "gold_eval_pack_manifest",
    )
    REQUIRED_CONTROLS = (
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
    )

    def __init__(self, *, release_name: str = "maine-family-law-llm") -> None:
        self.release_name = release_name

    def audit(
        self,
        *,
        version: str,
        release_candidate_report: ReleaseCandidateAuditReport | dict[str, Any],
        artifacts: Iterable[ReleaseArtifact | dict[str, Any]],
        controls: dict[str, bool],
        output_path: str | Path | None = None,
    ) -> GAShipmentAuditReport:
        rc = release_candidate_report.as_dict() if isinstance(release_candidate_report, ReleaseCandidateAuditReport) else dict(release_candidate_report)
        artifact_by_type = _artifact_map(artifacts)
        report_blockers: list[str] = []

        if rc.get("status") != "pass" or not rc.get("release_candidate_frozen"):
            report_blockers.append("release_candidate_not_frozen_or_not_passed")

        for artifact_type in self.REQUIRED_ARTIFACT_TYPES:
            artifact = artifact_by_type.get(artifact_type)
            if artifact is None:
                report_blockers.append(f"missing_ga_artifact:{artifact_type}")
                continue
            if not artifact.present:
                report_blockers.append(f"ga_artifact_not_present:{artifact_type}")
            if not artifact.version:
                report_blockers.append(f"ga_artifact_not_versioned:{artifact_type}")
            if artifact_type in self.EXTERNAL_ARTIFACT_TYPES and not artifact.external:
                report_blockers.append(f"ga_external_artifact_packaged_in_source_repo:{artifact_type}")

        for control in self.REQUIRED_CONTROLS:
            if not controls.get(control, False):
                report_blockers.append(f"ga_control_not_satisfied:{control}")

        artifact_inventory = [artifact.as_dict() for artifact in sorted(artifact_by_type.values(), key=lambda a: a.artifact_type)]
        shipment_hash = _stable_hash({
            "artifacts": artifact_inventory,
            "controls": dict(sorted(controls.items())),
            "release_candidate_hash": rc.get("artifact_inventory_hash", ""),
            "version": version,
        })
        status = "pass" if not report_blockers else "blocked"
        report = GAShipmentAuditReport(
            status=status,
            generated_at=datetime.now(timezone.utc).isoformat(),
            release_name=self.release_name,
            version=version,
            ga_shipped=status == "pass",
            release_candidate_status=str(rc.get("status", "unknown")),
            artifacts=artifact_inventory,
            controls=dict(controls),
            blockers=report_blockers,
            shipment_manifest_hash=shipment_hash,
            maintenance_operations_ready=bool(controls.get("rollback_and_maintenance_operations_present", False)),
        )
        if output_path:
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return report


def build_release_artifact_fixture(version: str) -> tuple[list[ReleaseArtifact], list[ReleaseArtifact]]:
    """Return complete Pass 50 and Pass 51 artifact fixtures for tests/evidence.

    The fixture represents versioned external artifact references. It is not a
    substitute for production legal/source/eval evidence.
    """
    generated = datetime.now(timezone.utc).isoformat()
    rc_artifacts = [
        ReleaseArtifact("Source repository ZIP", "source_repo_zip", version, f"dist/maine-family-law-llm-{version}.zip", "sha256:fixture", external=False, generated_at=generated),
        ReleaseArtifact("External data build manifest", "external_data_build_manifest", version, f"s3://mfl/{version}/data-build-manifest.json", "sha256:fixture", generated_at=generated),
        ReleaseArtifact("Parsed authority manifest", "parsed_authority_manifest", version, f"s3://mfl/{version}/parsed-authority-manifest.json", "sha256:fixture", generated_at=generated),
        ReleaseArtifact("Retrieval index manifest", "retrieval_index_manifest", version, f"s3://mfl/{version}/retrieval-index-manifest.json", "sha256:fixture", generated_at=generated),
        ReleaseArtifact("Gold eval pack manifest", "gold_eval_pack_manifest", version, f"s3://mfl/{version}/gold-eval-pack-manifest.json", "sha256:fixture", generated_at=generated),
        ReleaseArtifact("Release metrics JSON", "release_metrics_json", version, f"s3://mfl/{version}/release-metrics.json", "sha256:fixture", generated_at=generated),
        ReleaseArtifact("Security evidence packet", "security_evidence_packet", version, f"s3://mfl/{version}/security-evidence-packet.json", "sha256:fixture", generated_at=generated),
        ReleaseArtifact("Pilot evidence packet", "pilot_evidence_packet", version, f"s3://mfl/{version}/pilot-evidence-packet.json", "sha256:fixture", generated_at=generated),
        ReleaseArtifact("Rollback package", "rollback_package", version, f"dist/rollback-{version}.tar.gz", "sha256:fixture", external=False, generated_at=generated),
        ReleaseArtifact("Release notes", "release_notes", version, "docs/release-notes.md", _hash_repo_file(Path("docs/release-notes.md")), external=False, generated_at=generated),
    ]
    ga_artifacts = [
        ReleaseArtifact("Clean source ZIP", "clean_source_zip", version, f"dist/maine-family-law-llm-{version}.zip", "sha256:fixture", external=False, generated_at=generated),
        ReleaseArtifact("External legal data product manifest", "external_legal_data_product_manifest", version, f"s3://mfl/{version}/external-legal-data-product-manifest.json", "sha256:fixture", generated_at=generated),
        ReleaseArtifact("Parsed authority build manifest", "parsed_authority_build_manifest", version, f"s3://mfl/{version}/parsed-authority-build-manifest.json", "sha256:fixture", generated_at=generated),
        ReleaseArtifact("Retrieval indexes manifest", "retrieval_indexes_manifest", version, f"s3://mfl/{version}/retrieval-indexes-manifest.json", "sha256:fixture", generated_at=generated),
        ReleaseArtifact("Gold eval pack manifest", "gold_eval_pack_manifest", version, f"s3://mfl/{version}/gold-eval-pack-manifest.json", "sha256:fixture", generated_at=generated),
        ReleaseArtifact("Smoke/evidence JSON", "smoke_evidence_json", version, "smoke_evidence_pass50_pass51_ga_release.json", "sha256:fixture", external=False, generated_at=generated),
        ReleaseArtifact("Release metrics JSON", "release_metrics_json", version, f"s3://mfl/{version}/release-metrics.json", "sha256:fixture", generated_at=generated),
        ReleaseArtifact("Security/governance packet", "security_governance_packet", version, f"s3://mfl/{version}/security-governance-packet.json", "sha256:fixture", generated_at=generated),
        ReleaseArtifact("Admin guide", "admin_guide", version, "docs/admin-guide.md", _hash_repo_file(Path("docs/admin-guide.md")), external=False, generated_at=generated),
        ReleaseArtifact("User guide", "user_guide", version, "docs/user-guide.md", _hash_repo_file(Path("docs/user-guide.md")), external=False, generated_at=generated),
        ReleaseArtifact("Attorney reviewer guide", "attorney_reviewer_guide", version, "docs/attorney-reviewer-guide.md", _hash_repo_file(Path("docs/attorney-reviewer-guide.md")), external=False, generated_at=generated),
        ReleaseArtifact("Incident/rollback runbook", "incident_rollback_runbook", version, "docs/incident-rollback-runbook.md", _hash_repo_file(Path("docs/incident-rollback-runbook.md")), external=False, generated_at=generated),
        ReleaseArtifact("Source update runbook", "source_update_runbook", version, "docs/source-update-runbook.md", _hash_repo_file(Path("docs/source-update-runbook.md")), external=False, generated_at=generated),
        ReleaseArtifact("Model update runbook", "model_update_runbook", version, "docs/model-update-runbook.md", _hash_repo_file(Path("docs/model-update-runbook.md")), external=False, generated_at=generated),
    ]
    return rc_artifacts, ga_artifacts


def build_approved_signoff_fixture() -> list[ReleaseSignoff]:
    now = datetime.now(timezone.utc).isoformat()
    return [
        ReleaseSignoff("security", "security-owner", "approved", now),
        ReleaseSignoff("legal", "legal-owner", "approved", now),
        ReleaseSignoff("product", "product-owner", "approved", now),
        ReleaseSignoff("ops", "ops-owner", "approved", now),
    ]


def build_ga_control_fixture() -> dict[str, bool]:
    return {control: True for control in GAShipmentAuditor.REQUIRED_CONTROLS}


def _hash_repo_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "sha256:missing-fixture-file"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
