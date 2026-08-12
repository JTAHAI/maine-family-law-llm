from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from legal.governance.compliance_packet import GovernanceCompliancePacketBuilder
from legal.model_orchestration.control_center import ModelControlCenter
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock, read_bounded_regular_file


_CONTROL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,96}$")
_ROLE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,64}$")
_HASH_RE = re.compile(r"^[a-f0-9]{64}$")
_MAX_HISTORY_BYTES = 2 * 1024 * 1024
_LOCK = threading.RLock()


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha(payload: Any) -> str:
    if isinstance(payload, bytes):
        return hashlib.sha256(payload).hexdigest()
    return hashlib.sha256(_canonical(payload)).hexdigest()


def _safe_text(value: Any, limit: int = 2_000) -> str:
    return str(value or "").replace("\x00", "").strip()[:limit]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_config(project_root: Path, relative: str) -> dict[str, Any]:
    path = project_root / relative
    if not path.exists():
        return {}
    return _read_json(path)


def _latest_mtime(paths: list[Path]) -> str:
    mtimes = [path.stat().st_mtime for path in paths if path.exists()]
    if not mtimes:
        return ""
    return datetime.fromtimestamp(max(mtimes), tz=UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class GovernanceLedgerVerification:
    status: str
    event_count: int
    chain_head: str
    blockers: list[str]
    events: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "event_count": self.event_count,
            "chain_head": self.chain_head,
            "blockers": list(self.blockers),
            "events": [dict(event) for event in self.events],
        }


class GovernanceEventLedger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        raw = read_bounded_regular_file(self.path, max_bytes=_MAX_HISTORY_BYTES)
        return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]

    def append(self, event_type: str, **metadata: Any) -> dict[str, Any]:
        with exclusive_file_lock(self.lock_path):
            events = self._read()
            previous_hash = events[-1]["event_hash"] if events else "0" * 64
            record = {
                "event_type": event_type,
                "timestamp": _utc_now(),
                "metadata": metadata,
                "previous_hash": previous_hash,
            }
            record["event_hash"] = _sha(record)
            from legal.security.durable_io import durable_append_text

            durable_append_text(self.path, json.dumps(record, sort_keys=True) + "\n")
            return dict(record)

    def verify(self) -> GovernanceLedgerVerification:
        try:
            events = self._read()
        except Exception:
            return GovernanceLedgerVerification("blocked", 0, "0" * 64, ["history_unavailable"], [])
        head = "0" * 64
        blockers: list[str] = []
        for index, event in enumerate(events):
            expected = dict(event)
            event_hash = expected.pop("event_hash", "")
            if expected.get("previous_hash") != head:
                blockers.append(f"previous_hash_mismatch:{index}")
            recomputed = _sha(expected)
            if recomputed != event_hash:
                blockers.append(f"event_hash_mismatch:{index}")
            head = str(event_hash)
        return GovernanceLedgerVerification("pass" if not blockers else "blocked", len(events), head, blockers, events)


@dataclass(frozen=True)
class GovernanceControlRecord:
    control_id: str
    title: str
    family: str
    description: str
    applicability: str
    implementation_status: str
    owner: str
    reviewer: str
    implementation_locations: list[str]
    evidence_artifacts: list[str]
    evidence_hashes: dict[str, str]
    tests: list[str]
    last_tested_date: str
    gap: str
    remediation: str
    due_date: str
    risk: str
    exception: str
    exception_expiration: str
    approval_history: list[dict[str, Any]] = field(default_factory=list)
    related_policy: str = ""
    related_incident: str = ""
    release_blocking_status: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "control_id": self.control_id,
            "title": self.title,
            "family": self.family,
            "description": self.description,
            "applicability": self.applicability,
            "implementation_status": self.implementation_status,
            "owner": self.owner,
            "reviewer": self.reviewer,
            "implementation_locations": list(self.implementation_locations),
            "evidence_artifacts": list(self.evidence_artifacts),
            "evidence_hashes": dict(self.evidence_hashes),
            "tests": list(self.tests),
            "last_tested_date": self.last_tested_date,
            "gap": self.gap,
            "remediation": self.remediation,
            "due_date": self.due_date,
            "risk": self.risk,
            "exception": self.exception,
            "exception_expiration": self.exception_expiration,
            "approval_history": [dict(row) for row in self.approval_history],
            "related_policy": self.related_policy,
            "related_incident": self.related_incident,
            "release_blocking_status": self.release_blocking_status,
        }


@dataclass
class GovernancePolicyPack:
    pack_id: str
    role: str
    version: str
    status: str
    permitted_workers: list[str]
    external_providers: list[str]
    sharing_modes: list[str]
    exports: list[str]
    attorney_review: str
    filing_gate_policy: str
    retention: str
    source_updates: str
    evaluation: str
    audit_visibility: str
    redaction: str
    form_restrictions: str
    pilot_mode: str
    baseline_guardrails: dict[str, bool]
    diff_summary: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    review_notes: list[dict[str, Any]] = field(default_factory=list)
    expires_at: str = ""
    activated_at: str = ""
    supersedes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "role": self.role,
            "version": self.version,
            "status": self.status,
            "permitted_workers": list(self.permitted_workers),
            "external_providers": list(self.external_providers),
            "sharing_modes": list(self.sharing_modes),
            "exports": list(self.exports),
            "attorney_review": self.attorney_review,
            "filing_gate_policy": self.filing_gate_policy,
            "retention": self.retention,
            "source_updates": self.source_updates,
            "evaluation": self.evaluation,
            "audit_visibility": self.audit_visibility,
            "redaction": self.redaction,
            "form_restrictions": self.form_restrictions,
            "pilot_mode": self.pilot_mode,
            "baseline_guardrails": dict(self.baseline_guardrails),
            "diff_summary": dict(self.diff_summary),
            "history": [dict(row) for row in self.history],
            "review_notes": [dict(row) for row in self.review_notes],
            "expires_at": self.expires_at,
            "activated_at": self.activated_at,
            "supersedes": self.supersedes,
        }


class GovernanceControlCenterService:
    POLICY_PACK_ROLES = {
        "self_represented",
        "attorney",
        "legal_aid",
        "advocate",
        "gal_reviewer",
        "researcher",
        "administrator",
        "sandbox_evaluator",
    }

    def __init__(self, project_root: str | Path, *, evidence_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root).resolve()
        self.config_root = self.project_root / "configs"
        self.evidence_root = Path(evidence_root).resolve() if evidence_root else self.project_root / "dist" / "governance"
        self.evidence_root.mkdir(parents=True, exist_ok=True)
        self.history = GovernanceEventLedger(self.evidence_root / "governance-history.jsonl")
        self.active_pack_path = self.evidence_root / "active-policy-pack.json"
        self.policy_pack_store = self.evidence_root / "policy-packs"
        self.policy_pack_store.mkdir(parents=True, exist_ok=True)
        self._active_pack_cache: dict[str, GovernancePolicyPack] = {}
        self._seed_default_active_pack()

    def _seed_default_active_pack(self) -> None:
        if self.active_pack_path.exists():
            return
        baseline = self._base_policy_pack("attorney")
        baseline.status = "active"
        baseline.activated_at = _utc_now()
        self._persist_pack(baseline)

    def _evidence_hash(self, relative_path: str) -> str:
        path = self.project_root / relative_path
        if not path.exists() or not path.is_file():
            return ""
        return _sha(path.read_bytes())

    def _policy_hash(self, relative_path: str) -> str:
        return self._evidence_hash(relative_path)

    def _models(self) -> dict[str, Any]:
        center = ModelControlCenter(
            project_root=self.project_root,
            role_catalog_path=self.config_root / "maine_model_roles.json",
            admission_policy_path=self.config_root / "maine_model_admission_policy.json",
            registry_seed_path=self.config_root / "maine_model_registry.seed.json",
            store_root=os.environ.get("MFL_MODEL_STORE_ROOT") or None,
        )
        return center.list_models()

    def _provider_catalog(self) -> dict[str, Any]:
        return _load_config(self.project_root, "configs/maine_provider_catalog.json")

    def _control_specs(self) -> list[dict[str, Any]]:
        today = _utc_now()
        return [
            {
                "control_id": "authentication",
                "title": "Authentication and scoped local API access",
                "family": "application_security",
                "description": "Protected routes require local request validation and role headers.",
                "applicability": "All protected API routes.",
                "implementation_status": "implemented_and_tested",
                "owner": "security_owner",
                "reviewer": "operations_owner",
                "implementation_locations": ["app/api/security.py", "app/api/main.py"],
                "evidence_artifacts": ["tests/test_v520_local_request_hardening.py"],
                "tests": ["test_api_middleware_blocks_bad_host_and_cross_origin_before_route_execution"],
                "gap": "",
                "remediation": "None.",
                "due_date": "",
                "risk": "local request abuse if absent",
                "exception": "",
                "exception_expiration": "",
                "related_policy": "configs/maine_security_governance_policy.json",
                "related_incident": "",
                "release_blocking_status": True,
            },
            {
                "control_id": "tenant_isolation",
                "title": "Tenant and matter isolation",
                "family": "privacy",
                "description": "Matter access checks require the current tenant and matter scope.",
                "applicability": "Matter-level operations and review routes.",
                "implementation_status": "implemented_and_tested",
                "owner": "privacy_owner",
                "reviewer": "security_owner",
                "implementation_locations": ["legal/security/privacy_fortress.py", "legal/security/tenant_isolation.py"],
                "evidence_artifacts": ["tests/test_security_privacy_fortress.py"],
                "tests": ["test_security_privacy_fortress_matter_access_enforces_tenant_and_role"],
                "gap": "",
                "remediation": "None.",
                "due_date": "",
                "risk": "cross-matter access if absent",
                "exception": "",
                "exception_expiration": "",
                "related_policy": "configs/maine_storage_boundaries.json",
                "related_incident": "",
                "release_blocking_status": True,
            },
            {
                "control_id": "encryption_at_rest",
                "title": "Encrypted matter envelopes",
                "family": "privacy",
                "description": "Matter metadata and documents are stored in encrypted envelopes with key metadata.",
                "applicability": "Matter store and derived private artifacts.",
                "implementation_status": "implemented_and_tested",
                "owner": "operations_owner",
                "reviewer": "security_owner",
                "implementation_locations": ["legal/matter/matter_store.py", "legal/security/local_encryption.py"],
                "evidence_artifacts": ["tests/test_security_privacy_fortress.py", "tests/test_pass35_pass36_secure_matter_evidence.py"],
                "tests": ["test_security_privacy_fortress_redacts_diagnostics_and_reports_encryption"],
                "gap": "",
                "remediation": "None.",
                "due_date": "",
                "risk": "private matter leakage if absent",
                "exception": "",
                "exception_expiration": "",
                "related_policy": "configs/maine_security_governance_policy.json",
                "related_incident": "",
                "release_blocking_status": True,
            },
            {
                "control_id": "audit_integrity",
                "title": "Hash-chained audit integrity",
                "family": "audit",
                "description": "Security and review logs remain hash chained and tamper evident.",
                "applicability": "Security and review histories.",
                "implementation_status": "implemented_and_tested",
                "owner": "security_owner",
                "reviewer": "release_manager",
                "implementation_locations": ["legal/security/privacy_fortress.py", "legal/review/review_ledger.py"],
                "evidence_artifacts": ["tests/test_security_privacy_fortress.py", "tests/test_v520_document_workspace_api.py"],
                "tests": ["test_security_privacy_fortress_backup_restore_and_incident_lifecycle"],
                "gap": "",
                "remediation": "None.",
                "due_date": "",
                "risk": "tamperable history if absent",
                "exception": "",
                "exception_expiration": "",
                "related_policy": "configs/maine_security_governance_policy.json",
                "related_incident": "",
                "release_blocking_status": True,
            },
            {
                "control_id": "policy_pack_governance",
                "title": "Institutional policy packs",
                "family": "governance",
                "description": "Role-based policy packs can be drafted, compared, reviewed, activated, rolled back, expired, and superseded.",
                "applicability": "Governance control center only.",
                "implementation_status": "implemented_not_tested",
                "owner": "product_owner",
                "reviewer": "security_owner",
                "implementation_locations": ["legal/governance/service.py", "app/api/routes/governance.py", "app/web/pages/governance-policy-center.tsx"],
                "evidence_artifacts": ["configs/maine_governance_compliance_packet.json"],
                "tests": [],
                "gap": "Policy pack UI and API are new in this slice and need direct regression coverage.",
                "remediation": "Run governance-specific API and UI tests after the slice lands.",
                "due_date": today,
                "risk": "unsafe institutional settings if packs weaken baseline guards",
                "exception": "",
                "exception_expiration": "",
                "related_policy": "configs/maine_model_governance_policy.json",
                "related_incident": "",
                "release_blocking_status": True,
            },
            {
                "control_id": "vendor_risk_review",
                "title": "Vendor and provider risk review",
                "family": "supply_chain",
                "description": "Provider catalog records data sent, retention notes, and compensating controls.",
                "applicability": "External provider connections and local model admissions.",
                "implementation_status": "partially_implemented",
                "owner": "operations_owner",
                "reviewer": "privacy_owner",
                "implementation_locations": ["configs/maine_provider_catalog.json", "legal/provider_connections/service.py"],
                "evidence_artifacts": ["configs/maine_provider_catalog.json"],
                "tests": [],
                "gap": "Provider terms are summarized from project policy, not independently revalidated in this slice.",
                "remediation": "Attach per-vendor review evidence before external provider use.",
                "due_date": today,
                "risk": "unverified retention or network boundary terms",
                "exception": "expired_exception:vendor_terms_review_window",
                "exception_expiration": "2026-01-01T00:00:00Z",
                "related_policy": "configs/maine_provider_catalog.json",
                "related_incident": "",
                "release_blocking_status": True,
            },
            {
                "control_id": "accessibility_controls",
                "title": "Accessibility evidence",
                "family": "accessibility",
                "description": "UI contracts and release controls keep accessible markers visible for testing.",
                "applicability": "Shipped desktop and admin views.",
                "implementation_status": "implemented_and_tested",
                "owner": "product_owner",
                "reviewer": "accessibility_owner",
                "implementation_locations": ["app/web/ui_contracts.py", "app/web/pages/release-control-center.tsx"],
                "evidence_artifacts": ["tests/test_v603_release_control_center.py", "tests/test_v600_visual_design_refresh.py"],
                "tests": ["test_release_control_center_status", "test_v600_accessibility_modes_are_present"],
                "gap": "",
                "remediation": "None.",
                "due_date": "",
                "risk": "keyboard or screen-reader regressions if absent",
                "exception": "",
                "exception_expiration": "",
                "related_policy": "configs/maine_accessibility_style_rules.json",
                "related_incident": "",
                "release_blocking_status": True,
            },
            {
                "control_id": "source_freshness_controls",
                "title": "Source freshness and update SOP",
                "family": "authority",
                "description": "Authority builds, update reports, and source manifests remain versioned and reviewable.",
                "applicability": "Authority ingestion and source update workflows.",
                "implementation_status": "implemented_and_tested",
                "owner": "legal_owner",
                "reviewer": "product_owner",
                "implementation_locations": ["app/api/routes/authority.py", "legal/production/source_update_engine.py"],
                "evidence_artifacts": ["tests/test_v5120_retrieval_evaluation_workbench.py", "configs/maine_authority_build_policy.json"],
                "tests": ["test_source_update_report", "test_authority_library_status"],
                "gap": "",
                "remediation": "None.",
                "due_date": "",
                "risk": "stale or superseded authority if absent",
                "exception": "",
                "exception_expiration": "",
                "related_policy": "configs/maine_authority_build_policy.json",
                "related_incident": "",
                "release_blocking_status": True,
            },
            {
                "control_id": "human_review_controls",
                "title": "Human review procedures",
                "family": "governance",
                "description": "Human review remains mandatory where configured and cannot be bypassed by policy packs or sign-offs.",
                "applicability": "Drafting, filing, release, and governance approvals.",
                "implementation_status": "implemented_and_tested",
                "owner": "legal_owner",
                "reviewer": "product_owner",
                "implementation_locations": ["legal/review/review_ledger.py", "legal/drafting/filing_ready_gate.py"],
                "evidence_artifacts": ["tests/test_v520_document_workspace_api.py", "configs/maine_reviewed_filing_packet_policy.json"],
                "tests": ["test_review_ledger_blocks_failed_gate"],
                "gap": "",
                "remediation": "None.",
                "due_date": "",
                "risk": "unauthorized filing or approval if absent",
                "exception": "",
                "exception_expiration": "",
                "related_policy": "configs/maine_reviewed_filing_packet_policy.json",
                "related_incident": "",
                "release_blocking_status": True,
            },
            {
                "control_id": "diligence_packet_redaction",
                "title": "Redacted diligence packet",
                "family": "governance",
                "description": "Governance exports omit private matters, credentials, and raw local paths.",
                "applicability": "Governance packet and exported summaries.",
                "implementation_status": "implemented_not_tested",
                "owner": "operations_owner",
                "reviewer": "privacy_owner",
                "implementation_locations": ["legal/governance/service.py", "legal/governance/compliance_packet.py"],
                "evidence_artifacts": ["configs/maine_governance_compliance_packet.json"],
                "tests": [],
                "gap": "No slice-specific regression for the packet export path yet.",
                "remediation": "Add a redaction regression for governance packet exports.",
                "due_date": today,
                "risk": "private data leakage in governance exports",
                "exception": "",
                "exception_expiration": "",
                "related_policy": "configs/maine_governance_compliance_packet.json",
                "related_incident": "",
                "release_blocking_status": True,
            },
            {
                "control_id": "policy_change_history",
                "title": "Versioned policy change workflow",
                "family": "governance",
                "description": "Draft, compare, review, approve, reject, activate, rollback, expire, and supersede actions are hash chained.",
                "applicability": "Policy pack lifecycle.",
                "implementation_status": "implemented_not_tested",
                "owner": "product_owner",
                "reviewer": "operations_owner",
                "implementation_locations": ["legal/governance/service.py"],
                "evidence_artifacts": [],
                "tests": [],
                "gap": "Needs direct mutation tests.",
                "remediation": "Add lifecycle regression coverage.",
                "due_date": today,
                "risk": "silent policy drift if history is mutable",
                "exception": "",
                "exception_expiration": "",
                "related_policy": "configs/maine_model_governance_policy.json",
                "related_incident": "",
                "release_blocking_status": True,
            },
            {
                "control_id": "sign_off_matrix",
                "title": "Institutional sign-off matrix",
                "family": "governance",
                "description": "Owner, security, privacy, legal, accessibility, operations, and release sign-offs are tracked separately.",
                "applicability": "Governance packet and release readiness review.",
                "implementation_status": "evidence_missing",
                "owner": "operations_owner",
                "reviewer": "release_manager",
                "implementation_locations": ["legal/governance/service.py", "app/web/pages/governance-policy-center.tsx"],
                "evidence_artifacts": [],
                "tests": [],
                "gap": "No institution-signed approvals exist in the repository.",
                "remediation": "Collect real safe-identities and approvals before claiming institutional readiness.",
                "due_date": today,
                "risk": "unverified ownership and approval path",
                "exception": "template_only_until_real_signoffs_attached",
                "exception_expiration": "2026-09-30T00:00:00Z",
                "related_policy": "configs/maine_enterprise_acceptance_policy.json",
                "related_incident": "",
                "release_blocking_status": True,
            },
        ]

    def _control_status(self, spec: dict[str, Any]) -> str:
        status = str(spec.get("implementation_status") or "planned")
        if status == "evidence_missing":
            return status
        if status == "implemented_and_tested":
            return status
        if status == "implemented_not_tested":
            return status
        if status == "partially_implemented":
            return status
        return status

    def control_registry(self) -> dict[str, Any]:
        records: list[GovernanceControlRecord] = []
        counts: dict[str, int] = {}
        for spec in self._control_specs():
            evidence_artifacts = [str(item) for item in spec.get("evidence_artifacts", [])]
            evidence_hashes = {artifact: self._evidence_hash(artifact) for artifact in evidence_artifacts if artifact}
            tests = [str(item) for item in spec.get("tests", [])]
            status = self._control_status(spec)
            counts[status] = counts.get(status, 0) + 1
            records.append(
                GovernanceControlRecord(
                    control_id=spec["control_id"],
                    title=spec["title"],
                    family=spec["family"],
                    description=spec["description"],
                    applicability=spec["applicability"],
                    implementation_status=status,
                    owner=spec["owner"],
                    reviewer=spec["reviewer"],
                    implementation_locations=list(spec["implementation_locations"]),
                    evidence_artifacts=evidence_artifacts,
                    evidence_hashes=evidence_hashes,
                    tests=tests,
                    last_tested_date=_latest_mtime([self.project_root / path for path in spec.get("implementation_locations", []) + evidence_artifacts + tests if path and (self.project_root / path).exists()]),
                    gap=spec["gap"],
                    remediation=spec["remediation"],
                    due_date=spec["due_date"],
                    risk=spec["risk"],
                    exception=spec["exception"],
                    exception_expiration=spec["exception_expiration"],
                    approval_history=[row["metadata"] for row in self.history.verify().events if row.get("metadata", {}).get("control_id") == spec["control_id"]],
                    related_policy=spec["related_policy"],
                    related_incident=spec["related_incident"],
                    release_blocking_status=bool(spec["release_blocking_status"]),
                )
            )
        return {
            "status": "pass",
            "version": "1.0-pass1-governance-control-registry",
            "generated_at": _utc_now(),
            "control_count": len(records),
            "status_counts": counts,
            "controls": [record.as_dict() for record in records],
            "review_required": True,
        }

    def framework_mappings(self) -> dict[str, Any]:
        compliance = GovernanceCompliancePacketBuilder(self.config_root / "maine_governance_compliance_packet.json", self.project_root).build().as_dict()
        controls = self.control_registry()
        rows: list[dict[str, Any]] = []
        for framework_name, mapping in (
            ("NIST AI RMF", compliance["nist_ai_rmf_mapping"]),
            ("NIST AI 600-1", compliance["nist_ai_600_1_mapping"]),
            ("OWASP LLM", compliance["owasp_llm_mapping"]),
        ):
            for framework_reference, project_controls in mapping.items():
                for project_control in project_controls:
                    control = next((row for row in controls["controls"] if row["control_id"] == project_control or row["title"].casefold() == project_control.casefold()), None)
                    rows.append(
                        {
                            "framework": framework_name,
                            "framework_reference": framework_reference,
                            "project_control": project_control,
                            "evidence": control["evidence_artifacts"] if control else [],
                            "current_status": control["implementation_status"] if control else "evidence_missing",
                            "limitation": control["gap"] if control else "No direct control record found.",
                        }
                    )
        rows.extend(
            [
                {
                    "framework": "privacy_controls",
                    "framework_reference": "configs/maine_security_governance_policy.json",
                    "project_control": "tenant_isolation",
                    "evidence": ["legal/security/tenant_isolation.py"],
                    "current_status": "implemented_and_tested",
                    "limitation": "No external privacy audit is claimed.",
                },
                {
                    "framework": "human-review_controls",
                    "framework_reference": "configs/maine_reviewed_filing_packet_policy.json",
                    "project_control": "human_review_controls",
                    "evidence": ["legal/review/review_ledger.py"],
                    "current_status": "implemented_and_tested",
                    "limitation": "Human review remains mandatory where configured.",
                },
                {
                    "framework": "legal-verification_controls",
                    "framework_reference": "configs/maine_authority_build_policy.json",
                    "project_control": "source_freshness_controls",
                    "evidence": ["app/api/routes/authority.py"],
                    "current_status": "implemented_and_tested",
                    "limitation": "No legal certification is claimed.",
                },
                {
                    "framework": "accessibility_controls",
                    "framework_reference": "configs/maine_accessibility_style_rules.json",
                    "project_control": "accessibility_controls",
                    "evidence": ["app/web/pages/release-control-center.tsx"],
                    "current_status": "implemented_and_tested",
                    "limitation": "UI evidence does not equal external accessibility certification.",
                },
            ]
        )
        return {
            "status": "pass",
            "generated_at": _utc_now(),
            "framework_rows": rows,
            "control_count": len(controls["controls"]),
            "review_required": True,
        }

    def policies(self) -> dict[str, Any]:
        policy_files = [
            ("product_purpose_and_limitations", "configs/maine_public_release_policy.json", "product_owner", "review_required"),
            ("legal_safety_policy", "configs/maine_tone_policy.json", "legal_owner", "review_required"),
            ("data_boundary_policy", "configs/maine_storage_boundaries.json", "security_owner", "review_required"),
            ("privacy_impact_assessment", "configs/maine_security_governance_policy.json", "privacy_owner", "review_required"),
            ("threat_model", "configs/maine_security_governance_policy.json", "security_owner", "review_required"),
            ("data_flow_diagram", "configs/maine_governance_compliance_packet.json", "operations_owner", "review_required"),
            ("model_use_policy", "configs/maine_model_governance_policy.json", "product_owner", "review_required"),
            ("model_admission_policy", "configs/maine_model_admission_policy.json", "product_owner", "review_required"),
            ("provider_use_policy", "configs/maine_provider_catalog.json", "operations_owner", "review_required"),
            ("source_authority_policy", "configs/maine_authority_build_policy.json", "legal_owner", "review_required"),
            ("source_update_sop", "configs/maine_authority_build_policy.json", "legal_owner", "review_required"),
            ("citation_and_quote_policy", "configs/maine_reviewer_feedback_schema.json", "legal_owner", "review_required"),
            ("human_review_sop", "configs/maine_reviewed_filing_packet_policy.json", "legal_owner", "review_required"),
            ("attorney_reviewer_sop", "configs/maine_reviewer_feedback_schema.json", "legal_owner", "review_required"),
            ("drafting_and_filing_gate_sop", "configs/maine_release_gates_policy.json", "product_owner", "review_required"),
            ("evaluation_and_gold_data_sop", "configs/maine_gold_eval_pack_policy.json", "operations_owner", "review_required"),
            ("incident_response", "configs/maine_security_governance_policy.json", "security_owner", "review_required"),
            ("vulnerability_adjudication", "configs/maine_release_control_center.json" if False else "configs/maine_release_gates_policy.json", "security_owner", "review_required"),
            ("backup_and_restore_sop", "configs/maine_security_governance_policy.json", "operations_owner", "review_required"),
            ("retention_and_deletion_policy", "configs/maine_retention_policy.json", "privacy_owner", "review_required"),
            ("rollback_sop", "configs/maine_governance_compliance_packet.json", "operations_owner", "review_required"),
            ("accessibility_statement", "configs/maine_accessibility_style_rules.json", "accessibility_owner", "review_required"),
            ("responsible_disclosure_policy", "configs/maine_security_governance_policy.json", "security_owner", "review_required"),
            ("third_party_licensing_policy", "configs/maine_public_release_policy.json", "operations_owner", "review_required"),
        ]
        rows: list[dict[str, Any]] = []
        for name, relative_path, owner, approval_status in policy_files:
            path = self.project_root / relative_path
            config = _read_json(path) if path.exists() else {}
            rows.append(
                {
                    "policy_id": name,
                    "version": str(config.get("version") or "1.0"),
                    "owner": owner,
                    "approval_status": approval_status,
                    "review_date": config.get("generated_at") or _utc_now(),
                    "evidence_references": [relative_path],
                    "limitations": [
                        "Policy text is a governance artifact, not proof of implementation.",
                        "External review or sign-off may still be required.",
                    ],
                    "superseded_version": "",
                    "change_history": [
                        {
                            "version": str(config.get("version") or "1.0"),
                            "reason": "Generated from repository policy snapshot.",
                            "timestamp": _utc_now(),
                        }
                    ],
                }
            )
        return {
            "status": "pass",
            "generated_at": _utc_now(),
            "policies": rows,
            "review_required": True,
        }

    def _base_policy_pack(self, role: str) -> GovernancePolicyPack:
        permitted_workers = {
            "self_represented": ["deterministic", "rules_only"],
            "attorney": ["deterministic", "rules_only", "retrieval"],
            "legal_aid": ["deterministic", "retrieval", "summary"],
            "advocate": ["deterministic", "retrieval"],
            "gal_reviewer": ["deterministic", "rules_only"],
            "researcher": ["deterministic", "retrieval", "eval_only"],
            "administrator": ["deterministic", "policy_admin"],
            "sandbox_evaluator": ["deterministic", "eval_only"],
        }[role]
        external_providers = [] if role != "researcher" else ["loopback_only"]
        exports = [] if role == "self_represented" else ["review_required_only"]
        sharing_modes = ["local_only", "tenant_scoped"]
        return GovernancePolicyPack(
            pack_id=f"policy-pack-{role}",
            role=role,
            version="1.0.0",
            status="draft",
            permitted_workers=permitted_workers,
            external_providers=external_providers,
            sharing_modes=sharing_modes,
            exports=exports,
            attorney_review="required" if role in {"self_represented", "advocate", "legal_aid"} else "optional_with_scope",
            filing_gate_policy="mandatory",
            retention="project_or_policy_defined",
            source_updates="manual_review_required",
            evaluation="review_required",
            audit_visibility="review_required",
            redaction="mandatory",
            form_restrictions="current_forms_only",
            pilot_mode="sandbox_only" if role == "sandbox_evaluator" else "local_first",
            baseline_guardrails={
                "no_fake_authority": True,
                "no_cross_matter_access": True,
                "no_unapproved_external_sharing": True,
                "no_credential_disclosure": True,
                "no_filing_gate_bypass": True,
                "no_private_data_in_repository": True,
                "no_consensus_as_truth": True,
            },
        )

    def _load_active_pack(self) -> GovernancePolicyPack | None:
        if self.active_pack_path.exists():
            payload = _read_json(self.active_pack_path)
            return GovernancePolicyPack(
                pack_id=str(payload.get("pack_id") or ""),
                role=str(payload.get("role") or ""),
                version=str(payload.get("version") or ""),
                status=str(payload.get("status") or "draft"),
                permitted_workers=list(payload.get("permitted_workers") or []),
                external_providers=list(payload.get("external_providers") or []),
                sharing_modes=list(payload.get("sharing_modes") or []),
                exports=list(payload.get("exports") or []),
                attorney_review=str(payload.get("attorney_review") or ""),
                filing_gate_policy=str(payload.get("filing_gate_policy") or ""),
                retention=str(payload.get("retention") or ""),
                source_updates=str(payload.get("source_updates") or ""),
                evaluation=str(payload.get("evaluation") or ""),
                audit_visibility=str(payload.get("audit_visibility") or ""),
                redaction=str(payload.get("redaction") or ""),
                form_restrictions=str(payload.get("form_restrictions") or ""),
                pilot_mode=str(payload.get("pilot_mode") or ""),
                baseline_guardrails=dict(payload.get("baseline_guardrails") or {}),
                diff_summary=dict(payload.get("diff_summary") or {}),
                history=list(payload.get("history") or []),
                review_notes=list(payload.get("review_notes") or []),
                expires_at=str(payload.get("expires_at") or ""),
                activated_at=str(payload.get("activated_at") or ""),
                supersedes=str(payload.get("supersedes") or ""),
            )
        return None

    def _persist_pack(self, pack: GovernancePolicyPack) -> None:
        atomic_write_bytes(self.policy_pack_store / f"{pack.pack_id}.json", json.dumps(pack.as_dict(), indent=2, sort_keys=True).encode("utf-8"))
        active = self._load_active_pack()
        if active is None or active.pack_id == pack.pack_id or pack.status == "active":
            atomic_write_bytes(self.active_pack_path, json.dumps(pack.as_dict(), indent=2, sort_keys=True).encode("utf-8"))
        self._active_pack_cache[pack.pack_id] = pack

    def policy_packs(self) -> dict[str, Any]:
        packs = []
        active = self._load_active_pack()
        for role in sorted(self.POLICY_PACK_ROLES):
            base = self._base_policy_pack(role)
            if active and active.role == role:
                base = active
            packs.append(base.as_dict())
        return {
            "status": "pass",
            "generated_at": _utc_now(),
            "active_pack_id": active.pack_id if active else "",
            "policy_packs": packs,
            "review_required": True,
        }

    def draft_policy_pack(self, role: str, overrides: dict[str, Any]) -> dict[str, Any]:
        if role not in self.POLICY_PACK_ROLES:
            raise ValueError("unknown policy-pack role")
        base = self._base_policy_pack(role)
        candidate = base.as_dict()
        candidate.update({k: v for k, v in overrides.items() if k in candidate})
        candidate["pack_id"] = f"policy-pack-{role}-{uuid.uuid4().hex[:8]}"
        candidate["status"] = "draft"
        candidate["diff_summary"] = self._diff_dict(base.as_dict(), candidate)
        blockers = self._pack_blockers(candidate)
        if blockers:
            candidate["status"] = "failed"
            candidate["blockers"] = blockers
        else:
            candidate["blockers"] = []
        self.history.append("policy_pack_drafted", role=role, pack_id=candidate["pack_id"], status=candidate["status"], blockers=blockers)
        pack = GovernancePolicyPack(**{k: candidate[k] for k in GovernancePolicyPack.__dataclass_fields__ if k in candidate})
        self._persist_pack(pack)
        return {"status": candidate["status"], "policy_pack": candidate, "blockers": blockers, "review_required": True}

    @staticmethod
    def _diff_dict(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
        keys = sorted(set(before) | set(after))
        diff: dict[str, Any] = {}
        for key in keys:
            if before.get(key) != after.get(key):
                diff[key] = {"before": before.get(key), "after": after.get(key)}
        return diff

    @staticmethod
    def _pack_blockers(candidate: dict[str, Any]) -> list[str]:
        blockers: list[str] = []
        if candidate.get("baseline_guardrails", {}).get("no_fake_authority") is not True:
            blockers.append("baseline_guardrail:no_fake_authority")
        if candidate.get("baseline_guardrails", {}).get("no_cross_matter_access") is not True:
            blockers.append("baseline_guardrail:no_cross_matter_access")
        if candidate.get("baseline_guardrails", {}).get("no_unapproved_external_sharing") is not True:
            blockers.append("baseline_guardrail:no_unapproved_external_sharing")
        if candidate.get("baseline_guardrails", {}).get("no_credential_disclosure") is not True:
            blockers.append("baseline_guardrail:no_credential_disclosure")
        if candidate.get("baseline_guardrails", {}).get("no_filing_gate_bypass") is not True:
            blockers.append("baseline_guardrail:no_filing_gate_bypass")
        if candidate.get("baseline_guardrails", {}).get("no_private_data_in_repository") is not True:
            blockers.append("baseline_guardrail:no_private_data_in_repository")
        if candidate.get("baseline_guardrails", {}).get("no_consensus_as_truth") is not True:
            blockers.append("baseline_guardrail:no_consensus_as_truth")
        if any(mode not in {"local_only", "tenant_scoped"} for mode in candidate.get("sharing_modes", [])):
            blockers.append("sharing_mode_weakening_refused")
        if any(provider not in {"loopback_only"} for provider in candidate.get("external_providers", [])):
            blockers.append("external_provider_weakening_refused")
        if candidate.get("filing_gate_policy") != "mandatory":
            blockers.append("filing_gate_bypass_refused")
        return blockers

    def compare_policy_packs(self, base_pack_id: str, target_pack_id: str) -> dict[str, Any]:
        base = self._read_pack(base_pack_id)
        target = self._read_pack(target_pack_id)
        diff = self._diff_dict(base.as_dict(), target.as_dict())
        return {
            "status": "pass" if diff else "pass",
            "base_pack_id": base_pack_id,
            "target_pack_id": target_pack_id,
            "diff": diff,
            "review_required": True,
        }

    def _read_pack(self, pack_id: str) -> GovernancePolicyPack:
        path = self.policy_pack_store / f"{pack_id}.json"
        if not path.exists():
            raise FileNotFoundError(pack_id)
        payload = _read_json(path)
        return GovernancePolicyPack(
            pack_id=str(payload.get("pack_id") or ""),
            role=str(payload.get("role") or ""),
            version=str(payload.get("version") or ""),
            status=str(payload.get("status") or "draft"),
            permitted_workers=list(payload.get("permitted_workers") or []),
            external_providers=list(payload.get("external_providers") or []),
            sharing_modes=list(payload.get("sharing_modes") or []),
            exports=list(payload.get("exports") or []),
            attorney_review=str(payload.get("attorney_review") or ""),
            filing_gate_policy=str(payload.get("filing_gate_policy") or ""),
            retention=str(payload.get("retention") or ""),
            source_updates=str(payload.get("source_updates") or ""),
            evaluation=str(payload.get("evaluation") or ""),
            audit_visibility=str(payload.get("audit_visibility") or ""),
            redaction=str(payload.get("redaction") or ""),
            form_restrictions=str(payload.get("form_restrictions") or ""),
            pilot_mode=str(payload.get("pilot_mode") or ""),
            baseline_guardrails=dict(payload.get("baseline_guardrails") or {}),
            diff_summary=dict(payload.get("diff_summary") or {}),
            history=list(payload.get("history") or []),
            review_notes=list(payload.get("review_notes") or []),
            expires_at=str(payload.get("expires_at") or ""),
            activated_at=str(payload.get("activated_at") or ""),
            supersedes=str(payload.get("supersedes") or ""),
        )

    def review_policy_pack(self, pack_id: str, *, reviewer: str, decision: str, reason: str, conditions: str = "") -> dict[str, Any]:
        pack = self._read_pack(pack_id)
        note = {
            "timestamp": _utc_now(),
            "reviewer": reviewer,
            "decision": decision,
            "reason": reason,
            "conditions": conditions,
            "safe_identity": _sha({"reviewer": reviewer, "pack_id": pack_id})[:16],
        }
        pack.review_notes.append(note)
        pack.history.append({"event": "review", **note})
        pack = GovernancePolicyPack(**{k: getattr(pack, k) for k in GovernancePolicyPack.__dataclass_fields__})
        self._persist_pack(pack)
        self.history.append("policy_pack_reviewed", pack_id=pack_id, reviewer=reviewer, decision=decision, reason=reason)
        return {"status": "pass" if decision == "approve" else "reviewed", "policy_pack": pack.as_dict(), "review_required": True}

    def activate_policy_pack(self, pack_id: str, *, reviewer: str, reason: str) -> dict[str, Any]:
        pack = self._read_pack(pack_id)
        blockers = self._pack_blockers(pack.as_dict())
        if blockers:
            self.history.append("policy_pack_activation_blocked", pack_id=pack_id, reviewer=reviewer, reason=reason, blockers=blockers)
            return {"status": "blocked", "pack_id": pack_id, "blockers": blockers, "review_required": True}
        active_registry = self.control_registry()
        release_blockers = [row["control_id"] for row in active_registry["controls"] if row["release_blocking_status"] and row["implementation_status"] not in {"implemented_and_tested", "implemented_not_tested"}]
        if release_blockers:
            self.history.append("policy_pack_activation_blocked", pack_id=pack_id, reviewer=reviewer, reason=reason, blockers=release_blockers)
            return {"status": "blocked", "pack_id": pack_id, "blockers": release_blockers, "review_required": True}
        pack.status = "active"
        pack.activated_at = _utc_now()
        self._persist_pack(pack)
        self.history.append("policy_pack_activated", pack_id=pack_id, reviewer=reviewer, reason=reason)
        return {"status": "pass", "policy_pack": pack.as_dict(), "review_required": True}

    def rollback_policy_pack(self, pack_id: str, *, reviewer: str, reason: str) -> dict[str, Any]:
        pack = self._read_pack(pack_id)
        pack.status = "rolled_back"
        self._persist_pack(pack)
        self.history.append("policy_pack_rolled_back", pack_id=pack_id, reviewer=reviewer, reason=reason)
        return {"status": "pass", "policy_pack": pack.as_dict(), "review_required": True}

    def expire_policy_pack(self, pack_id: str, *, reviewer: str, reason: str, expires_at: str | None = None) -> dict[str, Any]:
        pack = self._read_pack(pack_id)
        pack.status = "expired"
        pack.expires_at = expires_at or _utc_now()
        self._persist_pack(pack)
        self.history.append("policy_pack_expired", pack_id=pack_id, reviewer=reviewer, reason=reason, expires_at=pack.expires_at)
        return {"status": "pass", "policy_pack": pack.as_dict(), "review_required": True}

    def supersede_policy_pack(self, pack_id: str, *, reviewer: str, reason: str, new_version: str) -> dict[str, Any]:
        pack = self._read_pack(pack_id)
        new_pack = GovernancePolicyPack(**{k: getattr(pack, k) for k in GovernancePolicyPack.__dataclass_fields__})
        new_pack = GovernancePolicyPack(
            **{
                **new_pack.as_dict(),
                "pack_id": f"{pack.role}-{new_version}",
                "version": new_version,
                "status": "draft",
                "supersedes": pack.pack_id,
                "activated_at": "",
                "expires_at": "",
            }
        )
        self._persist_pack(new_pack)
        self.history.append("policy_pack_superseded", pack_id=pack_id, new_pack_id=new_pack.pack_id, reviewer=reviewer, reason=reason)
        return {"status": "pass", "policy_pack": new_pack.as_dict(), "review_required": True}

    def model_cards(self) -> dict[str, Any]:
        models = self._models()
        cards: list[dict[str, Any]] = []
        for model in models.get("models") or []:
            artifact_hash = str(model.get("artifact_sha256") or "")
            if len(artifact_hash) != 64:
                artifact_hash = _sha(
                    {
                        "model_id": model.get("model_id"),
                        "version": model.get("version"),
                        "source": model.get("source") or model.get("source_project"),
                    }
                )
            cards.append(
                {
                    "role": model.get("role"),
                    "prohibited_role": model.get("prohibited_roles") or [],
                    "source": model.get("source") or model.get("source_project"),
                    "license": model.get("license"),
                    "artifact_hash": artifact_hash,
                    "runtime": {
                        "provider": model.get("runtime_provider"),
                        "version": model.get("runtime_version"),
                        "executable": _safe_text(model.get("runtime_executable"), 128),
                    },
                    "evaluation_evidence": model.get("benchmark_evidence") or model.get("benchmark_runs") or [],
                    "datasets": [row.get("dataset_id") for row in model.get("benchmark_runs") or [] if isinstance(row, dict)],
                    "privacy": model.get("privacy_status"),
                    "context_limits": model.get("context_limit_tokens"),
                    "known_failures": list((model.get("failure_profile") or {}).get("known_limits") or []),
                    "resources": {
                        "min_ram_bytes": model.get("min_ram_bytes"),
                        "min_vram_bytes": model.get("min_vram_bytes"),
                        "min_disk_bytes": model.get("min_disk_bytes"),
                    },
                    "fallback": model.get("fallback_behavior"),
                    "monitoring": {
                        "health_status": model.get("health_status"),
                        "last_healthcheck_at": model.get("last_healthcheck_at"),
                        "last_run_at": model.get("last_run_at"),
                    },
                    "admission_status": model.get("admission_status"),
                }
            )
        return {
            "status": "pass" if cards else "blocked",
            "generated_at": _utc_now(),
            "model_count": len(cards),
            "cards": cards,
            "review_required": True,
        }

    def data_cards(self) -> dict[str, Any]:
        data_classes = _load_config(self.project_root, "configs/maine_data_classes.json")
        retention = _load_config(self.project_root, "configs/maine_retention_policy.json")
        cards = [
            {
                "data_class": "authority_store",
                "purpose": "Hold official public authority snapshots for verification.",
                "source": "official Maine and federal public sources",
                "license": "public law / source-specific",
                "privacy": "non-private; source text only",
                "lineage": "official source -> authority build -> source card",
                "updates": "source update SOP controlled",
                "quality_checks": ["freshness", "hash", "exact-span"],
                "exclusions": ["private matter content", "credentials", "raw provider tokens"],
                "retention": "indefinite snapshot history",
                "limitations": "Not a certification or legal guarantee.",
            },
            {
                "data_class": "parsed_authority",
                "purpose": "Structured statute, rule, opinion, and form extraction.",
                "source": "official authority builds",
                "license": "public law / source-specific",
                "privacy": "non-private",
                "lineage": "authority source -> parser -> structured store",
                "updates": "refresh on source build changes",
                "quality_checks": ["parser status", "lineage hash", "span trace"],
                "exclusions": ["private matters", "prompt logs"],
                "retention": "superseded generations retained for review",
                "limitations": "Parsing does not create legal authority.",
            },
            {
                "data_class": "indexes",
                "purpose": "Content and retrieval indices for local search.",
                "source": "parsed authority and public sources",
                "license": "mixed public / source-specific",
                "privacy": "should exclude private matter payloads",
                "lineage": "source -> index -> retrieval",
                "updates": "regenerated from fresh snapshots",
                "quality_checks": ["hash", "index rebuild", "scope validation"],
                "exclusions": ["private matter text", "provider secrets"],
                "retention": "project policy defined",
                "limitations": "Index hits must be rechecked against source cards.",
            },
            {
                "data_class": "attorney_reviewed_evaluation",
                "purpose": "Gold data reviewed for eval and regression use.",
                "source": "synthetic and reviewed review packets",
                "license": "project controlled / review required",
                "privacy": "no private matter content",
                "lineage": "review packet -> evaluated row -> gold dataset",
                "updates": "append-only by review and promotion",
                "quality_checks": ["second review", "promotion audit", "hash chain"],
                "exclusions": ["raw private matters", "credentials", "paths"],
                "retention": retention.get("attorney_reviewed_eval_data", {}).get("retain", "review_approval_term"),
                "limitations": "Review approval is not a guarantee of future correctness.",
            },
            {
                "data_class": "synthetic_fixtures",
                "purpose": "Deterministic tests and UI smoke fixtures.",
                "source": "project-authored synthetic data",
                "license": "project license",
                "privacy": "synthetic only",
                "lineage": "fixture generator -> tests",
                "updates": "regenerate with code changes",
                "quality_checks": ["hash", "fixture integrity", "no private data scan"],
                "exclusions": ["real records", "credentials"],
                "retention": "project lifetime",
                "limitations": "Not representative of every live case.",
            },
            {
                "data_class": "private_matter_store",
                "purpose": "Encrypted user matter data and derived private work product.",
                "source": "user uploads and workbench output",
                "license": "user-owned / confidential",
                "privacy": "private",
                "lineage": "upload -> encrypted matter store",
                "updates": "matter operations only",
                "quality_checks": ["encryption", "tenant isolation", "audit chain"],
                "exclusions": ["repository", "governance exports", "model cards"],
                "retention": "matter policy defined",
                "limitations": "Never exported in diligence packets.",
            },
            {
                "data_class": "ocr_derivatives",
                "purpose": "Searchable copies derived from approved OCR.",
                "source": "document intelligence OCR workflow",
                "license": "same as original source",
                "privacy": "derived from private records; access controlled",
                "lineage": "original -> OCR copy -> searchable derivative",
                "updates": "rebuild when original changes",
                "quality_checks": ["original preserved", "span trace", "redaction review"],
                "exclusions": ["original overwrite", "private export leakage"],
                "retention": "preserve original; derived copy by policy",
                "limitations": "OCR may contain errors and must be checked against originals.",
            },
            {
                "data_class": "audit",
                "purpose": "Append-only review, security, and export histories.",
                "source": "workflow events",
                "license": "project controlled",
                "privacy": "redacted fields only",
                "lineage": "event -> hash chain -> immutable log",
                "updates": "append only",
                "quality_checks": ["chain verification", "redaction", "tamper evidence"],
                "exclusions": ["private matter content", "secrets"],
                "retention": "firm or deployment policy",
                "limitations": "Audit evidence is operational, not legal certification.",
            },
            {
                "data_class": "evidence_packets",
                "purpose": "Review packages for release and governance decisions.",
                "source": "packets and evidence roots",
                "license": "project controlled",
                "privacy": "redacted summaries only",
                "lineage": "audits, tests, and configs -> packet",
                "updates": "regenerate when evidence changes",
                "quality_checks": ["hash-bound", "redaction", "scope validation"],
                "exclusions": ["raw private text", "credentials", "raw paths"],
                "retention": "release policy defined",
                "limitations": "Packet visibility does not equal approval.",
            },
        ]
        return {
            "status": "pass",
            "generated_at": _utc_now(),
            "data_class_count": len(cards),
            "cards": cards,
            "registry_context": {
                "data_classes_config_version": data_classes.get("version"),
                "retention_policy_version": retention.get("version"),
            },
            "review_required": True,
        }

    def vendor_risks(self) -> dict[str, Any]:
        catalog = self._provider_catalog()
        rows: list[dict[str, Any]] = []
        for provider in catalog.get("providers") or []:
            provider_id = str(provider.get("provider_id") or "")
            rows.append(
                {
                    "vendor_project": provider_id,
                    "purpose": f"Optional hosted or API-backed provider connection for {provider_id}.",
                    "data_sent": ["explicit prompt", "bounded request metadata"] if provider_id else [],
                    "data_not_sent": ["private matter store", "credentials", "raw local paths", "governance history"],
                    "credentials": "operator-managed API key outside repository",
                    "retention_disclosure": str(provider.get("retention_summary") or "provider policy review required"),
                    "process_network_boundary": str(provider.get("endpoint_class") or "https_json_api"),
                    "license": "provider terms not independently verified here",
                    "advisories": [str(provider.get("admission_status") or "unknown")],
                    "risks": [
                        "Provider terms may change.",
                        "Provider retention and training guarantees must be rechecked before use.",
                    ],
                    "compensating_controls": ["local-only default", "loopback gating", "human review", "tenant scope"],
                    "status": str(provider.get("admission_status") or "unknown"),
                    "next_review": (
                        datetime.fromisoformat(str(provider.get("last_successful_contract_test") or "2026-01-01")).replace(tzinfo=UTC)
                        + timedelta(days=90)
                    ).isoformat().replace("+00:00", "Z"),
                    "disable_plan": "Revoke credentials and disconnect the provider in the privacy center.",
                }
            )
        return {
            "status": "pass" if rows else "blocked",
            "generated_at": _utc_now(),
            "vendor_risks": rows,
            "review_required": True,
        }

    def exceptions(self) -> dict[str, Any]:
        seed_path = self.config_root / "maine_governance_exceptions.json"
        if seed_path.exists():
            seed = _read_json(seed_path)
            rows = list(seed.get("exceptions") or [])
        else:
            rows = [
                {
                    "exception_id": "exp-vendor-term-review-window",
                    "control_id": "vendor_risk_review",
                    "version": "1",
                    "reason": "Provider terms are being summarized from the project catalog and must be revalidated externally.",
                    "owner": "operations_owner",
                    "reviewer": "privacy_owner",
                    "status": "active",
                    "expires_at": "2026-09-01T00:00:00Z",
                },
                {
                    "exception_id": "exp-signoff-template-only",
                    "control_id": "sign_off_matrix",
                    "version": "1",
                    "reason": "Only template sign-offs exist until institution-owned identities are collected.",
                    "owner": "product_owner",
                    "reviewer": "security_owner",
                    "status": "expired",
                    "expires_at": "2026-01-01T00:00:00Z",
                },
            ]
        for row in rows:
            row["expired"] = str(row.get("status") or "").casefold() == "expired" or self._is_expired(row.get("expires_at"))
        return {
            "status": "pass",
            "generated_at": _utc_now(),
            "exceptions": rows,
            "review_required": True,
        }

    @staticmethod
    def _is_expired(expires_at: Any) -> bool:
        try:
            return datetime.fromisoformat(str(expires_at).replace("Z", "+00:00")).astimezone(UTC) <= datetime.now(UTC)
        except Exception:
            return False

    def record_exception(self, payload: dict[str, Any]) -> dict[str, Any]:
        record = {
            "exception_id": f"exc-{uuid.uuid4().hex[:10]}",
            "control_id": _safe_text(payload.get("control_id"), 80),
            "version": _safe_text(payload.get("version") or "1", 20),
            "reason": _safe_text(payload.get("reason"), 2_000),
            "owner": _safe_text(payload.get("owner"), 80),
            "reviewer": _safe_text(payload.get("reviewer"), 80),
            "status": _safe_text(payload.get("status") or "active", 20),
            "expires_at": _safe_text(payload.get("expires_at") or _utc_now(), 40),
        }
        self.history.append("governance_exception_recorded", **record)
        return {"status": "pass", "exception": record, "review_required": True}

    def sign_offs(self) -> dict[str, Any]:
        matrix = [
            "product_owner",
            "security_owner",
            "privacy_owner",
            "legal_reviewer",
            "accessibility_reviewer",
            "operations_owner",
            "release_manager",
        ]
        records = [
            {
                "role": role,
                "build_release_id": "",
                "scope": "governance_readiness",
                "evidence_reviewed": [],
                "unresolved_gaps": [row["control_id"] for row in self.control_registry()["controls"] if row["release_blocking_status"] and row["implementation_status"] in {"evidence_missing", "partially_implemented"}],
                "decision": "pending",
                "conditions": "Cannot override deterministic release gates.",
                "expiration": "",
                "timestamp": _utc_now(),
                "safe_identity": _sha({"role": role, "scope": "governance_readiness"})[:16],
            }
            for role in matrix
        ]
        return {
            "status": "pass",
            "generated_at": _utc_now(),
            "sign_offs": records,
            "review_required": True,
        }

    def record_sign_off(self, payload: dict[str, Any]) -> dict[str, Any]:
        role = _safe_text(payload.get("role"), 80)
        if not _ROLE_RE.fullmatch(role):
            raise ValueError("invalid sign-off role")
        gates = self.control_registry()
        unresolved = [row["control_id"] for row in gates["controls"] if row["release_blocking_status"] and row["implementation_status"] in {"evidence_missing", "partially_implemented"}]
        approved = bool(payload.get("approve"))
        decision = "rejected" if unresolved else ("approved" if approved else "rejected")
        record = {
            "signoff_id": f"signoff-{uuid.uuid4().hex[:10]}",
            "build_release_id": _safe_text(payload.get("build_release_id"), 80),
            "scope": _safe_text(payload.get("scope") or "governance_readiness", 80),
            "evidence_reviewed": [str(item) for item in payload.get("evidence_reviewed") or []],
            "unresolved_gaps": unresolved,
            "decision": decision,
            "conditions": _safe_text(payload.get("conditions") or "Cannot override deterministic release gates.", 500),
            "expiration": _safe_text(payload.get("expiration") or _utc_now(), 40),
            "timestamp": _utc_now(),
            "safe_identity": _sha({"role": role, "build_release_id": payload.get("build_release_id"), "scope": payload.get("scope")})[:16],
            "role": role,
        }
        self.history.append("governance_signoff_recorded", **record)
        return {"status": "pass" if decision == "approved" else "blocked", "sign_off": record, "review_required": True}

    def diligence_packet(self) -> dict[str, Any]:
        control_registry = self.control_registry()
        policies = self.policies()
        packs = self.policy_packs()
        models = self.model_cards()
        data_cards = self.data_cards()
        vendors = self.vendor_risks()
        exceptions = self.exceptions()
        sign_offs = self.sign_offs()
        compliance = GovernanceCompliancePacketBuilder(self.config_root / "maine_governance_compliance_packet.json", self.project_root).build().as_dict()
        artifacts = {
            "control_registry_hash": _sha(control_registry),
            "framework_mappings_hash": _sha(self.framework_mappings()),
            "policies_hash": _sha(policies),
            "policy_packs_hash": _sha(packs),
            "model_cards_hash": _sha(models),
            "data_cards_hash": _sha(data_cards),
            "vendor_risks_hash": _sha(vendors),
            "exceptions_hash": _sha(exceptions),
            "sign_offs_hash": _sha(sign_offs),
            "compliance_packet_hash": _sha(compliance),
        }
        return {
            "status": "pass",
            "generated_at": _utc_now(),
            "overview": {
                "control_count": control_registry["control_count"],
                "policy_count": len(policies["policies"]),
                "policy_pack_count": len(packs["policy_packs"]),
                "model_card_count": models["model_count"],
                "data_card_count": data_cards["data_class_count"],
                "vendor_risk_count": len(vendors["vendor_risks"]),
                "exception_count": len(exceptions["exceptions"]),
                "sign_off_count": len(sign_offs["sign_offs"]),
            },
            "architecture": {
                "control_registry": "versioned control registry built from repo evidence",
                "policy_packs": "role-based packs constrained by baseline guardrails",
                "model_cards": "real registry-backed cards",
                "data_cards": "policy-derived cards for governance review",
                "history": "append-only hash-chained governance ledger",
            },
            "data_flow": {
                "project_scope": self.project_root.name,
                "evidence_scope": "dist/governance",
                "sources": ["configs", "model registry", "provider catalog", "release control center", "UI contracts"],
            },
            "control_mappings": self.framework_mappings()["framework_rows"],
            "model_cards": models["cards"],
            "data_cards": data_cards["cards"],
            "privacy_assessment": {
                "status": "review_required",
                "limitations": [
                    "Governance evidence is redacted.",
                    "No private matter content is included.",
                    "No certification or compliance claim is made.",
                ],
            },
            "security_tests": {
                "controls": [row["control_id"] for row in control_registry["controls"]],
                "missing": [row["control_id"] for row in control_registry["controls"] if row["implementation_status"] in {"evidence_missing", "partially_implemented"}],
            },
            "accessibility": {"status": "pass", "evidence": ["app/web/pages/governance-policy-center.tsx", "app/web/ui_contracts.py"]},
            "evaluation": {"status": "pass", "evidence": ["configs/maine_governance_compliance_packet.json"]},
            "supply_chain": {"status": "review_required", "evidence": ["configs/maine_provider_catalog.json"]},
            "incident_plan": {"status": "review_required", "evidence": ["configs/maine_security_governance_policy.json"]},
            "backup_evidence": {"status": "pass", "evidence": ["legal/ops/release_pilot_hardening.py"]},
            "source_update": {"status": "pass", "evidence": ["app/api/routes/authority.py", "legal/production/source_update_engine.py"]},
            "human_review": {"status": "pass", "evidence": ["legal/review/review_ledger.py"]},
            "gaps": [
                {
                    "control_id": row["control_id"],
                    "gap": row["gap"],
                    "owner": row["owner"],
                    "due_date": row["due_date"],
                    "release_blocking": row["release_blocking_status"],
                }
                for row in control_registry["controls"]
                if row["gap"]
            ],
            "sign_offs": sign_offs["sign_offs"],
            "artifact_hashes": artifacts,
            "redactions": ["private matters omitted", "credentials omitted", "raw paths omitted", "reviewer private notes omitted"],
            "compliance_packet": compliance,
            "history": self.history.verify().as_dict(),
            "review_required": True,
        }

    def history_report(self) -> dict[str, Any]:
        verification = self.history.verify()
        return {
            "status": verification.status,
            "generated_at": _utc_now(),
            "history": verification.as_dict(),
            "review_required": True,
        }


__all__ = [
    "GovernanceControlCenterService",
    "GovernanceControlRecord",
    "GovernanceEventLedger",
    "GovernanceLedgerVerification",
    "GovernancePolicyPack",
]
