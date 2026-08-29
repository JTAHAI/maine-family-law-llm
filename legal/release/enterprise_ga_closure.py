"""Fail-closed package provenance and Enterprise GA evidence contracts.

The release controls in this module are deliberately evidence *verifiers*, not
release approvers.  They can produce exact hashes and validate signed external
bundles, but cannot turn local fixtures, role headers, or a successful parser
into Store approval, attorney review, organizational authorization, or an
Enterprise GA decision.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree import ElementTree

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from legal.evals.external_eval_root import ExternalEvalRootError, resolve_external_eval_root
from legal.ops.supply_chain import SupplyChainAuditor


_HASH = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")
_MAX_PACKAGE_BYTES = 16 * 1024 * 1024 * 1024
_MAX_MEMBERS = 120_000
_MAX_MEMBER_BYTES = 2 * 1024 * 1024 * 1024
_VULNERABILITY_FILENAME = "release_vulnerability_audit.json"
_REPRODUCIBILITY_FILENAME = "release_reproducibility_runs.json"
_REPRODUCIBILITY_ATTESTATION_FILENAME = "release_reproducibility_attestation.json"
_REPRODUCIBILITY_TRUST_FILENAME = "release_reproducibility_trust.json"
_SIGNOFF_FILENAME = "organizational_signoff_bundle.json"
_SIGNOFF_ATTESTATION_FILENAME = "organizational_signoff_attestation.json"
_SIGNOFF_TRUST_FILENAME = "organizational_signoff_trust.json"
_DECISION_FILENAME = "enterprise_ga_evidence_manifest.json"
_DECISION_ATTESTATION_FILENAME = "enterprise_ga_evidence_attestation.json"
_DECISION_TRUST_FILENAME = "enterprise_ga_evidence_trust.json"

REQUIRED_VULNERABILITY_TOOLS = ("syft", "grype", "pip_audit", "semgrep")
REQUIRED_SIGNOFF_LANES = ("legal", "security", "privacy", "accessibility", "product", "operations", "release")
REQUIRED_DECISION_EVIDENCE = (
    "live_authority",
    "attorney_evaluation",
    "security_assessment",
    "controlled_pilot",
    "store_qualification",
    "rollback",
    "support",
    "organization_signoffs",
    "package_provenance",
    "reproducibility",
    "incident_response",
)
TABLETOP_SCENARIOS = {
    "fictional_private_record_exposure": ("P0", "contain_local_access", "preserve_hash_only_evidence", "prepare_user_notice", "restore_verified_state", "postmortem_required"),
    "fictional_malicious_document": ("P1", "isolate_record", "preserve_parser_receipt", "prepare_user_notice", "recover_from_safe_original", "postmortem_required"),
    "fictional_authority_integrity_failure": ("P1", "disable_affected_authority_generation", "preserve_build_hashes", "prepare_user_notice", "restore_verified_generation", "postmortem_required"),
}


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else _canonical(value)).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_object(path: Path, *, limit: int = 4 * 1024 * 1024) -> dict[str, Any] | None:
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > limit:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _safe_external_root(root: str | Path | None, *, project_root: Path) -> tuple[Path | None, list[str]]:
    if root is None or not str(root).strip():
        return None, ["external_release_evidence_root_not_configured"]
    try:
        return resolve_external_eval_root(root, project_root=project_root, create=False), []
    except ExternalEvalRootError as exc:
        return None, [exc.code]


def _signature_payload(payload: dict[str, Any]) -> bytes:
    clean = dict(payload)
    clean.pop("signature", None)
    return _canonical(clean)


def _verify_signed_payload(
    *,
    payload: dict[str, Any] | None,
    trust: dict[str, Any] | None,
    expected_payload_schema: str,
    expected_trust_schema: str,
    prefix: str,
) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    if payload is None:
        return False, [f"{prefix}_unavailable"]
    if payload.get("schema_version") != expected_payload_schema:
        blockers.append(f"{prefix}_schema_unsupported")
    if trust is None or trust.get("schema_version") != expected_trust_schema:
        blockers.append(f"{prefix}_trust_unavailable")
        trust = {}
    signature = payload.get("signature") if isinstance(payload.get("signature"), dict) else {}
    key_id = str(signature.get("key_id") or "").strip()
    trusted_keys = trust.get("trusted_keys") if isinstance(trust.get("trusted_keys"), dict) else {}
    key_text = trusted_keys.get(key_id)
    if not isinstance(key_text, str) or not key_text:
        blockers.append(f"{prefix}_key_untrusted")
    else:
        try:
            key = Ed25519PublicKey.from_public_bytes(base64.b64decode(key_text, validate=True))
            encoded_signature = base64.b64decode(str(signature.get("signature") or ""), validate=True)
            key.verify(encoded_signature, _signature_payload(payload))
        except (ValueError, InvalidSignature):
            blockers.append(f"{prefix}_signature_invalid")
    return not blockers, blockers


def _safe_package_path(value: str | Path | None) -> tuple[Path | None, list[str]]:
    if value is None or not str(value).strip():
        return None, ["msix_package_not_configured"]
    path = Path(value).expanduser()
    try:
        if not path.is_file() or path.is_symlink() or path.suffix.casefold() != ".msix":
            return None, ["msix_package_unavailable"]
        resolved = path.resolve(strict=True)
        if resolved.stat().st_size <= 0 or resolved.stat().st_size > _MAX_PACKAGE_BYTES:
            return None, ["msix_package_size_out_of_bounds"]
        return resolved, []
    except OSError:
        return None, ["msix_package_unavailable"]


def _member_path(value: str) -> bool:
    path = PurePosixPath(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts and "\\" not in value


def _manifest_identity(raw: bytes) -> dict[str, str]:
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError:
        return {}
    namespace = {"m": "http://schemas.microsoft.com/appx/manifest/foundation/windows10"}
    identity = root.find("m:Identity", namespace)
    application = root.find(".//m:Application", namespace)
    resource = root.find(".//m:Resources/m:Resource", namespace)
    if identity is None or application is None:
        return {}
    return {
        "name": str(identity.attrib.get("Name") or ""),
        "publisher": str(identity.attrib.get("Publisher") or ""),
        "version": str(identity.attrib.get("Version") or ""),
        "architecture": str(identity.attrib.get("ProcessorArchitecture") or ""),
        "executable": str(application.attrib.get("Executable") or ""),
        "language": str(resource.attrib.get("Language") if resource is not None else ""),
    }


@dataclass
class PackageSbomReport:
    status: str
    generated_at: str
    package_sha256: str = ""
    payload_manifest_sha256: str = ""
    source_sbom_sha256: str = ""
    package_member_count: int = 0
    package_member_bytes: int = 0
    source_component_count: int = 0
    license_status: str = "blocked"
    license_file_count: int = 0
    vulnerability_status: str = "blocked"
    vulnerability_tools: list[str] = field(default_factory=list)
    vulnerability_blocking_count: int = 0
    package_identity: dict[str, str] = field(default_factory=dict)
    sbom_artifacts: dict[str, str] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    review_required: bool = True
    network_used: bool = False
    private_matter_data_used: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "exact_package_sbom_report_v1",
            "status": self.status,
            "generated_at": self.generated_at,
            "package_sha256": self.package_sha256,
            "payload_manifest_sha256": self.payload_manifest_sha256,
            "source_sbom_sha256": self.source_sbom_sha256,
            "package_member_count": self.package_member_count,
            "package_member_bytes": self.package_member_bytes,
            "source_component_count": self.source_component_count,
            "license_status": self.license_status,
            "license_file_count": self.license_file_count,
            "vulnerability_status": self.vulnerability_status,
            "vulnerability_tools": self.vulnerability_tools,
            "vulnerability_blocking_count": self.vulnerability_blocking_count,
            "package_identity": self.package_identity,
            "sbom_artifacts": self.sbom_artifacts,
            "blockers": sorted(set(self.blockers)),
            "review_required": self.review_required,
            "network_used": self.network_used,
            "private_matter_data_used": self.private_matter_data_used,
            "origins": {"source": "source_checkout", "package": "exact_msix_archive", "vulnerability": "external_signed_evidence"},
        }


class PackageSbomGate:
    """Build an exact hash inventory for one MSIX and its source checkout."""

    def __init__(self, *, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()

    def audit(self, *, package: str | Path | None, evidence_root: str | Path | None) -> PackageSbomReport:
        package_path, blockers = _safe_package_path(package)
        source = SupplyChainAuditor(self.project_root).audit(write_sbom=False).sbom
        source_copy = dict(source)
        source_copy.pop("generated_at", None)
        source_sha = _digest(source_copy) if source_copy else ""
        source_count = len(source_copy.get("components") or []) if source_copy else 0
        if not source_copy:
            blockers.append("exact_source_sbom_unavailable")
        if package_path is None:
            return PackageSbomReport(status="blocked", generated_at=_now(), source_sbom_sha256=source_sha, source_component_count=source_count, blockers=blockers)
        members: list[dict[str, Any]] = []
        license_files: list[str] = []
        identity: dict[str, str] = {}
        try:
            with zipfile.ZipFile(package_path, "r") as archive:
                entries = [entry for entry in archive.infolist() if not entry.is_dir()]
                if len(entries) > _MAX_MEMBERS:
                    blockers.append("msix_member_count_out_of_bounds")
                names: set[str] = set()
                for entry in entries[:_MAX_MEMBERS]:
                    if not _member_path(entry.filename) or entry.filename in names:
                        blockers.append("msix_member_path_or_duplicate_invalid")
                        continue
                    names.add(entry.filename)
                    if entry.file_size < 0 or entry.file_size > _MAX_MEMBER_BYTES:
                        blockers.append("msix_member_size_out_of_bounds")
                        continue
                    data = archive.read(entry)
                    members.append({"path": entry.filename, "size": len(data), "sha256": hashlib.sha256(data).hexdigest(), "origin": "msix_payload"})
                    low = entry.filename.casefold()
                    if any(token in low for token in ("license", "notice", "attribution", "third_party")):
                        license_files.append(entry.filename)
                    if entry.filename == "AppxManifest.xml":
                        identity = _manifest_identity(data)
        except (OSError, zipfile.BadZipFile, RuntimeError):
            blockers.append("msix_archive_unreadable")
        if not identity:
            blockers.append("msix_manifest_identity_unavailable")
        if not license_files:
            blockers.append("msix_license_or_notice_missing")
        payload_manifest = _digest(sorted(members, key=lambda item: item["path"].casefold())) if members else ""
        root, root_blockers = _safe_external_root(evidence_root, project_root=self.project_root)
        blockers.extend(root_blockers)
        vuln_status, vuln_tools, vuln_count, vuln_blockers = self._vulnerability(
            root=root,
            package_sha256=_file_hash(package_path),
            source_sbom_sha256=source_sha,
        )
        blockers.extend(vuln_blockers)
        sbom_artifacts: dict[str, str] = {}
        if root is not None and members:
            try:
                sbom_artifacts = self._write_exact_sboms(
                    root=root,
                    source_sbom=source_copy,
                    source_sha256=source_sha,
                    package_path=package_path,
                    package_sha256=_file_hash(package_path),
                    payload_manifest_sha256=payload_manifest,
                    package_identity=identity,
                    package_components=members,
                    license_files=license_files,
                )
            except OSError:
                blockers.append("exact_sbom_artifact_write_failed")
        return PackageSbomReport(
            status="pass" if not blockers else "blocked",
            generated_at=_now(),
            package_sha256=_file_hash(package_path),
            payload_manifest_sha256=payload_manifest,
            source_sbom_sha256=source_sha,
            package_member_count=len(members),
            package_member_bytes=sum(int(item["size"]) for item in members),
            source_component_count=source_count,
            license_status="pass" if license_files else "blocked",
            license_file_count=len(license_files),
            vulnerability_status=vuln_status,
            vulnerability_tools=vuln_tools,
            vulnerability_blocking_count=vuln_count,
            package_identity=identity,
            sbom_artifacts=sbom_artifacts,
            blockers=blockers,
        )

    @staticmethod
    def _write_exact_sboms(
        *,
        root: Path,
        source_sbom: dict[str, Any],
        source_sha256: str,
        package_path: Path,
        package_sha256: str,
        payload_manifest_sha256: str,
        package_identity: dict[str, str],
        package_components: list[dict[str, Any]],
        license_files: list[str],
    ) -> dict[str, str]:
        """Write deterministic SBOM artifacts only under approved external evidence."""

        documents = {
            "exact-source-sbom.json": {
                "schema_version": "exact_source_sbom_v1",
                "source_sbom_sha256": source_sha256,
                "components": source_sbom.get("components") or [],
                "origin": "source_checkout",
                "private_matter_data_included": False,
            },
            "exact-msix-sbom.json": {
                "schema_version": "exact_msix_sbom_v1",
                "package_file_name": package_path.name,
                "package_sha256": package_sha256,
                "payload_manifest_sha256": payload_manifest_sha256,
                "identity": package_identity,
                "components": package_components,
                "license_notice_members": sorted(license_files, key=str.casefold),
                "origin": "exact_msix_archive",
                "private_matter_data_included": False,
            },
        }
        artifacts: dict[str, str] = {}
        for name, document in documents.items():
            target = root / name
            encoded = json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
            temporary = target.with_name(f".{target.name}.tmp")
            temporary.write_bytes(encoded)
            temporary.replace(target)
            artifacts[name] = hashlib.sha256(encoded).hexdigest()
        return artifacts

    def _vulnerability(self, *, root: Path | None, package_sha256: str, source_sbom_sha256: str) -> tuple[str, list[str], int, list[str]]:
        if root is None:
            return "blocked", [], 0, ["external_release_vulnerability_audit_required"]
        report = _load_object(root / _VULNERABILITY_FILENAME)
        blockers: list[str] = []
        if report is None or report.get("schema_version") != "release_vulnerability_audit_v1":
            return "blocked", [], 0, ["release_vulnerability_audit_unavailable"]
        if str(report.get("package_sha256") or "").casefold() != package_sha256:
            blockers.append("release_vulnerability_package_hash_mismatch")
        if str(report.get("source_sbom_sha256") or "").casefold() != source_sbom_sha256:
            blockers.append("release_vulnerability_source_sbom_hash_mismatch")
        tools = report.get("tools") if isinstance(report.get("tools"), list) else []
        statuses = {str(row.get("tool") or "").casefold(): str(row.get("status") or "").casefold() for row in tools if isinstance(row, dict)}
        for tool in REQUIRED_VULNERABILITY_TOOLS:
            if statuses.get(tool) != "pass":
                blockers.append(f"release_vulnerability_tool_not_passed:{tool}")
        try:
            count = max(0, int(report.get("blocking_finding_count", 0) or 0))
        except (TypeError, ValueError):
            count = 1
        if count:
            blockers.append("release_vulnerability_blocking_findings_present")
        return ("pass" if not blockers else "blocked", sorted(statuses), count, blockers)


@dataclass
class ReproducibilityReport:
    status: str
    generated_at: str
    independent_run_count: int = 0
    exact_package_match: bool = False
    payload_manifest_match: bool = False
    source_sbom_match: bool = False
    toolchain_pinned: bool = False
    attestation_verified: bool = False
    blockers: list[str] = field(default_factory=list)
    review_required: bool = True
    network_used: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "release_reproducibility_report_v1", "status": self.status, "generated_at": self.generated_at,
            "independent_run_count": self.independent_run_count, "exact_package_match": self.exact_package_match,
            "payload_manifest_match": self.payload_manifest_match, "source_sbom_match": self.source_sbom_match,
            "toolchain_pinned": self.toolchain_pinned, "attestation_verified": self.attestation_verified,
            "blockers": sorted(set(self.blockers)), "review_required": self.review_required, "network_used": self.network_used,
            "release_decision": "not_made",
        }


class ReleaseReproducibilityGate:
    def __init__(self, *, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()

    def verify(self, *, evidence_root: str | Path | None, package_report: PackageSbomReport) -> ReproducibilityReport:
        root, blockers = _safe_external_root(evidence_root, project_root=self.project_root)
        if root is None:
            return ReproducibilityReport(status="blocked", generated_at=_now(), blockers=blockers)
        runs_path = root / _REPRODUCIBILITY_FILENAME
        runs = _load_object(runs_path)
        if runs is None or runs.get("schema_version") != "release_reproducibility_runs_v1":
            return ReproducibilityReport(status="blocked", generated_at=_now(), blockers=["release_reproducibility_runs_unavailable"])
        rows = runs.get("runs") if isinstance(runs.get("runs"), list) else []
        valid_rows = [row for row in rows if isinstance(row, dict) and str(row.get("status") or "").casefold() == "pass" and _SAFE_ID.fullmatch(str(row.get("run_id") or ""))]
        hashes = {str(row.get("package_sha256") or "").casefold() for row in valid_rows}
        payloads = {str(row.get("payload_manifest_sha256") or "").casefold() for row in valid_rows}
        sources = {str(row.get("source_sbom_sha256") or "").casefold() for row in valid_rows}
        toolchains = {str(row.get("toolchain_manifest_sha256") or "").casefold() for row in valid_rows}
        exact_package = len(valid_rows) >= 2 and hashes == {package_report.package_sha256}
        payload_match = len(valid_rows) >= 2 and payloads == {package_report.payload_manifest_sha256}
        source_match = len(valid_rows) >= 2 and sources == {package_report.source_sbom_sha256}
        pinned = len(valid_rows) >= 2 and len(toolchains) == 1 and all(_HASH.fullmatch(item) for item in toolchains)
        if not exact_package: blockers.append("release_reproducibility_package_hash_mismatch")
        if not payload_match: blockers.append("release_reproducibility_payload_manifest_mismatch")
        if not source_match: blockers.append("release_reproducibility_source_sbom_mismatch")
        if not pinned: blockers.append("release_reproducibility_toolchain_not_pinned")
        attestation = _load_object(root / _REPRODUCIBILITY_ATTESTATION_FILENAME)
        trust = _load_object(root / _REPRODUCIBILITY_TRUST_FILENAME, limit=256 * 1024)
        verified, signature_blockers = _verify_signed_payload(payload=attestation, trust=trust, expected_payload_schema="release_reproducibility_attestation_v1", expected_trust_schema="release_reproducibility_trust_v1", prefix="release_reproducibility_attestation")
        blockers.extend(signature_blockers)
        if attestation is not None and str(attestation.get("runs_sha256") or "").casefold() != _file_hash(runs_path):
            blockers.append("release_reproducibility_attestation_runs_hash_mismatch")
        if attestation is not None and str(attestation.get("package_sha256") or "").casefold() != package_report.package_sha256:
            blockers.append("release_reproducibility_attestation_package_hash_mismatch")
        return ReproducibilityReport(status="pass" if not blockers else "blocked", generated_at=_now(), independent_run_count=len(valid_rows), exact_package_match=exact_package, payload_manifest_match=payload_match, source_sbom_match=source_match, toolchain_pinned=pinned, attestation_verified=verified, blockers=blockers)


class IncidentResponseProgram:
    """A content-free response template and fictional tabletop contract."""

    def status(self) -> dict[str, Any]:
        return {
            "schema_version": "incident_response_program_v1", "status": "implemented_review_required", "generated_at": _now(),
            "severity_levels": ["P0", "P1", "P2", "P3"], "required_templates": ["containment", "evidence_preservation", "user_notice", "recovery", "postmortem"],
            "fictional_tabletop_scenarios": sorted(TABLETOP_SCENARIOS), "operational_drill_verified": False,
            "blockers": ["external_incident_response_owner_training_and_tabletop_evidence_required"], "review_required": True,
            "network_used": False, "private_matter_data_used": False,
        }

    def tabletop(self, scenario_id: str) -> dict[str, Any]:
        scenario = str(scenario_id or "").strip()
        if scenario not in TABLETOP_SCENARIOS:
            return {**self.status(), "status": "blocked", "blockers": ["fictional_incident_tabletop_scenario_invalid"]}
        severity, *actions = TABLETOP_SCENARIOS[scenario]
        plan = {"scenario_id": scenario, "severity": severity, "actions": actions, "synthetic_only": True}
        return {**self.status(), "status": "fictional_tabletop_completed_review_required", "tabletop": {"scenario_id": scenario, "severity": severity, "action_count": len(actions), "plan_sha256": _digest(plan)}, "blockers": ["external_incident_response_owner_training_and_tabletop_evidence_required"]}


@dataclass
class OrganizationalSignoffReport:
    status: str
    generated_at: str
    approved_lanes: list[str] = field(default_factory=list)
    attestation_verified: bool = False
    organization_authorization_verified: bool = False
    blockers: list[str] = field(default_factory=list)
    review_required: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "organizational_signoff_report_v1", "status": self.status, "generated_at": self.generated_at,
            "required_lanes": list(REQUIRED_SIGNOFF_LANES), "approved_lanes": self.approved_lanes,
            "attestation_verified": self.attestation_verified, "organization_authorization_verified": self.organization_authorization_verified,
            "blockers": sorted(set(self.blockers)), "review_required": self.review_required, "network_used": False,
            "enterprise_ga_decision": "not_made",
        }


class OrganizationalSignoffGate:
    def __init__(self, *, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()

    def verify(self, *, evidence_root: str | Path | None) -> OrganizationalSignoffReport:
        root, blockers = _safe_external_root(evidence_root, project_root=self.project_root)
        if root is None:
            return OrganizationalSignoffReport(status="blocked", generated_at=_now(), blockers=blockers)
        bundle_path = root / _SIGNOFF_FILENAME
        bundle = _load_object(bundle_path)
        if bundle is None or bundle.get("schema_version") != "organizational_signoff_bundle_v1":
            return OrganizationalSignoffReport(status="blocked", generated_at=_now(), blockers=["organizational_signoff_bundle_unavailable"])
        approvals = bundle.get("approvals") if isinstance(bundle.get("approvals"), list) else []
        valid_lanes: set[str] = set()
        for approval in approvals:
            if not isinstance(approval, dict):
                continue
            lane = str(approval.get("lane") or "").casefold()
            if lane in REQUIRED_SIGNOFF_LANES and str(approval.get("decision") or "").casefold() == "approved" and _HASH.fullmatch(str(approval.get("authorization_evidence_sha256") or "").casefold()):
                valid_lanes.add(lane)
        missing = sorted(set(REQUIRED_SIGNOFF_LANES) - valid_lanes)
        blockers.extend(f"organizational_signoff_missing:{lane}" for lane in missing)
        attestation = _load_object(root / _SIGNOFF_ATTESTATION_FILENAME)
        trust = _load_object(root / _SIGNOFF_TRUST_FILENAME, limit=256 * 1024)
        verified, signature_blockers = _verify_signed_payload(payload=attestation, trust=trust, expected_payload_schema="organizational_signoff_attestation_v1", expected_trust_schema="organizational_signoff_trust_v1", prefix="organizational_signoff_attestation")
        blockers.extend(signature_blockers)
        if attestation is not None and str(attestation.get("bundle_sha256") or "").casefold() != _file_hash(bundle_path):
            blockers.append("organizational_signoff_attestation_bundle_hash_mismatch")
        # A local verifier cannot establish that the signing key holder held the
        # claimed organizational authority.  This remains an external decision.
        blockers.append("external_organizational_authority_validation_required")
        return OrganizationalSignoffReport(status="blocked", generated_at=_now(), approved_lanes=sorted(valid_lanes), attestation_verified=verified, organization_authorization_verified=False, blockers=blockers)


@dataclass
class EnterpriseDecisionReport:
    status: str
    generated_at: str
    store_ga_decision: str
    enterprise_ga_decision: str
    evidence_categories_present: list[str] = field(default_factory=list)
    attestation_verified: bool = False
    blockers: list[str] = field(default_factory=list)
    review_required: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "enterprise_ga_decision_packet_v1", "status": self.status, "generated_at": self.generated_at,
            "store_ga_decision": self.store_ga_decision, "enterprise_ga_decision": self.enterprise_ga_decision,
            "required_evidence_categories": list(REQUIRED_DECISION_EVIDENCE), "evidence_categories_present": self.evidence_categories_present,
            "attestation_verified": self.attestation_verified, "blockers": sorted(set(self.blockers)), "review_required": self.review_required,
            "network_used": False, "automated_release_or_publication": False,
        }


class EnterpriseDecisionPacket:
    def __init__(self, *, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()

    def assemble(self, *, evidence_root: str | Path | None) -> EnterpriseDecisionReport:
        root, blockers = _safe_external_root(evidence_root, project_root=self.project_root)
        if root is None:
            return EnterpriseDecisionReport(status="blocked", generated_at=_now(), store_ga_decision="STORE_GA_NOT_EVALUATED", enterprise_ga_decision="ENTERPRISE_GA_BLOCKED", blockers=blockers)
        manifest_path = root / _DECISION_FILENAME
        manifest = _load_object(manifest_path)
        if manifest is None or manifest.get("schema_version") != "enterprise_ga_evidence_manifest_v1":
            return EnterpriseDecisionReport(status="blocked", generated_at=_now(), store_ga_decision="STORE_GA_NOT_EVALUATED", enterprise_ga_decision="ENTERPRISE_GA_BLOCKED", blockers=["enterprise_ga_evidence_manifest_unavailable"])
        rows = manifest.get("evidence") if isinstance(manifest.get("evidence"), list) else []
        present: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            category = str(row.get("category") or "")
            if category in REQUIRED_DECISION_EVIDENCE and str(row.get("status") or "").casefold() == "pass" and _HASH.fullmatch(str(row.get("sha256") or "").casefold()) and row.get("external_attested") is True:
                present.add(category)
        blockers.extend(f"enterprise_ga_evidence_missing:{category}" for category in sorted(set(REQUIRED_DECISION_EVIDENCE) - present))
        attestation = _load_object(root / _DECISION_ATTESTATION_FILENAME)
        trust = _load_object(root / _DECISION_TRUST_FILENAME, limit=256 * 1024)
        verified, signature_blockers = _verify_signed_payload(payload=attestation, trust=trust, expected_payload_schema="enterprise_ga_evidence_attestation_v1", expected_trust_schema="enterprise_ga_evidence_trust_v1", prefix="enterprise_ga_evidence_attestation")
        blockers.extend(signature_blockers)
        if attestation is not None and str(attestation.get("manifest_sha256") or "").casefold() != _file_hash(manifest_path):
            blockers.append("enterprise_ga_evidence_attestation_manifest_hash_mismatch")
        # This program intentionally has no authority to declare either a Store
        # submission accepted or an organization released to Enterprise GA.
        blockers.append("external_release_authority_decision_required")
        store = "STORE_GA_NOT_EVALUATED" if "store_qualification" not in present else "STORE_GA_BLOCKED"
        return EnterpriseDecisionReport(status="blocked", generated_at=_now(), store_ga_decision=store, enterprise_ga_decision="ENTERPRISE_GA_BLOCKED", evidence_categories_present=sorted(present), attestation_verified=verified, blockers=blockers)


__all__ = [
    "EnterpriseDecisionPacket", "IncidentResponseProgram", "OrganizationalSignoffGate", "PackageSbomGate",
    "PackageSbomReport", "ReleaseReproducibilityGate", "REQUIRED_DECISION_EVIDENCE", "REQUIRED_SIGNOFF_LANES",
    "REQUIRED_VULNERABILITY_TOOLS", "TABLETOP_SCENARIOS",
]
