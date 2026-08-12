from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.web.ui_contracts import UICompletionAuditor
from legal.ops.release_pilot_hardening import (
    ReleaseEvidenceAuditor,
    ReleasePilotHardeningService,
    find_source_root,
)
from legal.ops.sre import ReliabilitySREAuditor
from legal.ops.supply_chain import SupplyChainAuditor
from legal.release.release_candidate_operations import GAReleaseCandidateError, GAReleaseCandidateOperationsStore
from legal.release.release_manifest import ReleaseManifest
from legal.release.shipment_readiness_operations import GAShipmentReadinessError, GAShipmentReadinessStore
from legal.security.legal_red_team import LegalRedTeamRunner


@dataclass(frozen=True)
class ReleaseControlCenterReport:
    status: str
    generated_at: str
    repo_root: str
    case_root: str | None
    release_root_configured: bool
    evidence_root_configured: bool
    sections: dict[str, dict[str, Any]] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    eligibility_basis: dict[str, bool] = field(default_factory=dict)
    review_required: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "release_control_center_status_v1",
            "status": self.status,
            "generated_at": self.generated_at,
            "repo_root": self.repo_root,
            "case_root": self.case_root,
            "release_root_configured": self.release_root_configured,
            "evidence_root_configured": self.evidence_root_configured,
            "sections": self.sections,
            "eligibility_basis": self.eligibility_basis,
            "blockers": sorted(set(self.blockers)),
            "review_required": self.review_required,
        }


class ReleaseControlCenterService:
    """Compose local release, pilot, supply-chain, and release-gate evidence.

    The service never invents passing evidence. It aggregates the existing
    release hardening, accessibility, red-team, supply-chain, and release gate
    auditors and reports the blockers that remain.
    """

    def __init__(
        self,
        repo_root: str | Path = ".",
        *,
        case_root: str | Path | None = None,
        release_root: str | Path | None = None,
        evidence_root: str | Path | None = None,
        pilot_root: str | Path | None = None,
    ) -> None:
        self.repo_root = find_source_root(repo_root)
        self.case_root = Path(case_root).resolve() if case_root else None
        self.release_root = Path(release_root).resolve() if release_root else self._configured_release_root()
        self.evidence_root = Path(evidence_root).resolve() if evidence_root else self._configured_evidence_root()
        self.pilot_root = Path(pilot_root).resolve() if pilot_root else self._configured_pilot_root()
        self.release_manifest = ReleaseManifest(project_root=self.repo_root)

    @staticmethod
    def _configured_release_root() -> Path | None:
        configured = os.environ.get("MAINE_FAMILY_LAW_RELEASE_ROOT")
        return Path(configured).resolve() if configured else None

    @staticmethod
    def _configured_evidence_root() -> Path | None:
        configured = os.environ.get("MAINE_FAMILY_LAW_RELEASE_EVIDENCE_ROOT")
        return Path(configured).resolve() if configured else None

    @staticmethod
    def _configured_pilot_root() -> Path | None:
        configured = os.environ.get("MAINE_FAMILY_LAW_PILOT_ROOT")
        return Path(configured).resolve() if configured else None

    @staticmethod
    def _section(report: dict[str, Any], *, pass_states: set[str] | None = None, ready_states: set[str] | None = None) -> dict[str, Any]:
        state = str(report.get("status") or "").strip().casefold()
        pass_states = pass_states or {"pass"}
        ready_states = ready_states or set()
        status = "pass" if state in pass_states or state in ready_states else "blocked"
        blockers = list(report.get("blockers") or [])
        return {**report, "status": status, "blockers": blockers}

    @staticmethod
    def _first_file(files: list[dict[str, Any]], filename: str) -> dict[str, Any]:
        for row in files:
            if str(row.get("filename") or "") == filename:
                return row
        return {"filename": filename, "status": "blocked", "blockers": [f"missing:{filename}"], "summary": {}}

    def _release_candidate_status(self) -> dict[str, Any]:
        try:
            if self.release_root is None:
                raise GAReleaseCandidateError("release_root_not_configured", status_code=409)
            return GAReleaseCandidateOperationsStore(self.repo_root, self.release_root).status()
        except GAReleaseCandidateError as exc:
            return {
                "schema_version": "ga_release_candidate_operations_status_v1",
                "status": "blocked",
                "blockers": [exc.code],
                "release_candidate_frozen": False,
                "pass50_complete": False,
                "external_launch_evidence_gate_required": True,
            }

    def _shipment_status(self) -> dict[str, Any]:
        try:
            if self.release_root is None:
                raise GAShipmentReadinessError("release_root_not_configured", status_code=409)
            return GAShipmentReadinessStore(self.repo_root, self.release_root).status()
        except GAShipmentReadinessError as exc:
            return {
                "schema_version": "ga_shipment_readiness_status_v1",
                "status": "blocked",
                "blockers": [exc.code],
                "pass51_complete": False,
                "external_shipment_evidence_required": True,
            }

    def status(self) -> dict[str, Any]:
        release_pilot = ReleasePilotHardeningService(self.repo_root, self.case_root).status()
        accessibility = UICompletionAuditor("app/web/pages").audit().as_dict()
        supply_chain = SupplyChainAuditor(self.repo_root).audit(write_sbom=False).as_dict()
        release_evidence = ReleaseEvidenceAuditor(self.repo_root, self.evidence_root).audit()
        red_team = LegalRedTeamRunner(project_root=self.repo_root).run().as_dict()
        release_candidate = self._release_candidate_status()
        shipment = self._shipment_status()
        release_manifest = self.release_manifest.generate()
        release_candidate_pass = str(release_candidate.get("status") or "").casefold() == "pass"
        shipment_pass = str(shipment.get("status") or "").casefold() == "ready_for_external_pass51_gate"
        observability = self._section(release_pilot.get("observability") or {})
        backup_restore = self._section(release_pilot.get("backup_restore") or {}, ready_states={"ready"})
        attorney_sandbox = self._section(release_pilot.get("attorney_sandbox") or {}, ready_states={"operational"})
        release_pilot_section = self._section(release_pilot)
        reliability_auditor = ReliabilitySREAuditor(self.repo_root / "configs" / "maine_sre_reliability_policy.json")
        implemented_controls: set[str] = set()
        if observability["status"] == "pass":
            implemented_controls.add("observability_dashboards")
        if backup_restore["status"] == "pass":
            implemented_controls.add("backup_restore_drill")
        if attorney_sandbox["status"] == "pass":
            implemented_controls.add("load_test_plan")
        reliability = reliability_auditor.audit(
            implemented_controls=implemented_controls,
            measurements=reliability_auditor.default_offline_measurements(),
            restore_drill=backup_restore,
        )
        release_evidence_files = {str(row.get("filename") or ""): row for row in release_evidence.get("files") or []}
        msix_audit = self._first_file(list(release_evidence_files.values()), "msix-qualification.json")
        vulnerability_names = ("grype.json", "pip-audit.json", "semgrep.json")
        vulnerability_evidence = {
            "schema_version": "release_vulnerability_evidence_v1",
            "status": "pass",
            "files": [release_evidence_files.get(name) for name in vulnerability_names],
        }
        vulnerability_blockers = sorted(
            {
                blocker
                for filename in vulnerability_names
                for blocker in (
                    [f"missing:{filename}"]
                    if release_evidence_files.get(filename) is None
                    else list((release_evidence_files.get(filename) or {}).get("blockers", []))
                )
            }
        )
        if any(release_evidence_files.get(name) is None for name in vulnerability_names):
            vulnerability_blockers = sorted({*vulnerability_blockers, *{f"missing:{name}" for name in vulnerability_names if release_evidence_files.get(name) is None}})
        if vulnerability_blockers:
            vulnerability_evidence["status"] = "blocked"
            vulnerability_evidence["blockers"] = vulnerability_blockers
        else:
            vulnerability_evidence["blockers"] = []
        release_artifacts = [
            release_evidence_files.get("sbom.cyclonedx.json"),
            release_evidence_files.get("sbom.spdx.json"),
            release_evidence_files.get("msix-qualification.json"),
            release_evidence_files.get("backup-restore.json"),
            release_evidence_files.get("grype.json"),
            release_evidence_files.get("pip-audit.json"),
            release_evidence_files.get("semgrep.json"),
        ]
        sections = {
            "release_manifest": {
                "status": "pass" if release_manifest["data_boundary_status"] == "pass" else "blocked",
                "summary": release_manifest,
                "blockers": [] if release_manifest["data_boundary_status"] == "pass" else ["release_manifest_data_boundary_failed"],
            },
            "supply_chain": self._section(supply_chain),
            "release_evidence": self._section(release_evidence),
            "observability": observability,
            "backup_restore": backup_restore,
            "reliability": self._section(reliability),
            "accessibility": self._section(accessibility),
            "red_team": self._section(red_team),
            "pilot": attorney_sandbox,
            "release_pilot_hardening": release_pilot_section,
            "release_candidate": release_candidate,
            "shipment_readiness": shipment,
            "msix_audit": self._section(msix_audit),
            "vulnerability_evidence": vulnerability_evidence,
            "release_artifacts": {
                "status": "pass" if release_evidence["status"] == "pass" else "blocked",
                "summary": [artifact for artifact in release_artifacts if artifact],
                "blockers": [] if release_evidence["status"] == "pass" else list(release_evidence.get("blockers") or []),
            },
        }
        blockers: list[str] = []
        if sections["release_manifest"]["status"] != "pass":
            blockers.extend(sections["release_manifest"]["blockers"])
        for name in ("supply_chain", "release_evidence", "observability", "backup_restore", "reliability", "accessibility", "red_team", "pilot", "release_pilot_hardening", "msix_audit", "vulnerability_evidence", "release_artifacts"):
            section = sections[name]
            if section.get("status") != "pass":
                blockers.extend(section.get("blockers") or [f"{name}_blocked"])
        if not release_candidate_pass:
            blockers.extend(release_candidate.get("blockers") or ["release_candidate_blocked"])
        if not shipment_pass:
            blockers.extend(shipment.get("blockers") or ["shipment_readiness_blocked"])
        eligibility_basis = {
            "observability_pass": observability["status"] == "pass",
            "backup_restore_pass": backup_restore["status"] == "pass",
            "reliability_pass": reliability["status"] == "pass",
            "accessibility_pass": accessibility["status"] == "pass",
            "supply_chain_pass": supply_chain["status"] == "pass",
            "release_evidence_pass": release_evidence["status"] == "pass",
            "red_team_pass": red_team["status"] == "pass",
            "pilot_operational": attorney_sandbox["status"] == "pass",
            "release_candidate_pass": release_candidate_pass,
            "shipment_ready": shipment_pass,
        }
        if not all(eligibility_basis.values()):
            blockers.append("release_control_center_gate_incomplete")
        return ReleaseControlCenterReport(
            status="pass" if not blockers else "blocked",
            generated_at=release_pilot.get("observability", {}).get("generated_at") or release_evidence.get("generated_at") or "",
            repo_root=str(self.repo_root),
            case_root=str(self.case_root) if self.case_root else None,
            release_root_configured=self.release_root is not None,
            evidence_root_configured=self.evidence_root is not None,
            sections=sections,
            blockers=blockers,
            eligibility_basis=eligibility_basis,
        ).as_dict()


__all__ = ["ReleaseControlCenterReport", "ReleaseControlCenterService"]
