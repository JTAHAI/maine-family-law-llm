from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal.data_boundaries.storage_layout import is_inside_project_repo
from legal.ops.networked_source_gate import NetworkedSourceGateAuditor


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_load_json(path: Path) -> Any:
    try:
        return _load_json(path)
    except Exception:
        return None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_policy(repo_root: Path) -> dict[str, Any]:
    return _load_json(repo_root / "configs" / "maine_production_promotion_policy.json")


def _contains_fixture_marker(obj: Any, markers: list[str]) -> bool:
    text = json.dumps(obj, sort_keys=True, default=str).lower()
    return any(marker.lower() in text for marker in markers)


def _metric_map(metrics_obj: Any) -> dict[str, float]:
    if not isinstance(metrics_obj, dict):
        return {}
    raw_metrics = metrics_obj.get("metrics", metrics_obj)
    out: dict[str, float] = {}
    if isinstance(raw_metrics, list):
        for item in raw_metrics:
            if isinstance(item, dict) and "name" in item and "value" in item:
                try:
                    out[str(item["name"])] = float(item["value"])
                except (TypeError, ValueError):
                    continue
    elif isinstance(raw_metrics, dict):
        for key, value in raw_metrics.items():
            if isinstance(value, dict) and "value" in value:
                value = value["value"]
            try:
                out[str(key)] = float(value)
            except (TypeError, ValueError):
                continue
    return out


@dataclass(frozen=True)
class ProductionPromotionFinding:
    check: str
    status: str
    message: str
    path: str | None = None
    severity: str = "blocker"

    def as_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "status": self.status,
            "message": self.message,
            "path": self.path,
            "severity": self.severity,
        }


@dataclass(frozen=True)
class ProductionPromotionReport:
    status: str
    production_legal_ready: bool
    promotion_locked: bool
    repo_root: str
    data_root: str
    generated_at: str
    networked_source_gate_status: str
    missing_required_external_files: list[str] = field(default_factory=list)
    external_file_hashes: dict[str, str] = field(default_factory=dict)
    metric_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    attorney_reviewed_rows_total: int = 0
    owner_signoff_roles_present: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    findings: list[ProductionPromotionFinding] = field(default_factory=list)
    next_commands: list[str] = field(default_factory=list)
    interpretation: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "production_legal_ready": self.production_legal_ready,
            "promotion_locked": self.promotion_locked,
            "repo_root": self.repo_root,
            "data_root": self.data_root,
            "generated_at": self.generated_at,
            "networked_source_gate_status": self.networked_source_gate_status,
            "missing_required_external_files": list(self.missing_required_external_files),
            "external_file_hashes": dict(self.external_file_hashes),
            "metric_results": self.metric_results,
            "attorney_reviewed_rows_total": self.attorney_reviewed_rows_total,
            "owner_signoff_roles_present": list(self.owner_signoff_roles_present),
            "blockers": sorted(set(self.blockers)),
            "findings": [finding.as_dict() for finding in self.findings],
            "next_commands": list(self.next_commands),
            "interpretation": self.interpretation,
        }


class ProductionPromotionGateAuditor:
    """Final hard gate for production-legal-ready promotion.

    Local tests, public-source readiness, and even fixture-based GA scaffolding are not enough.
    This auditor requires the external data root to contain live/non-fixture official-source,
    attorney-review, metric, pilot, security, rollback, and owner-signoff evidence.
    """

    def __init__(self, repo_root: str | Path = ".", data_root: str | Path | None = None) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.policy = _load_policy(self.repo_root)
        self.data_root = Path(data_root or self.policy["default_windows_data_root"]).expanduser().resolve()

    def _read_required_file(
        self,
        rel: str,
        findings: list[ProductionPromotionFinding],
        blockers: list[str],
        missing: list[str],
        hashes: dict[str, str],
    ) -> Any:
        path = self.data_root / rel
        if not path.is_file():
            missing.append(rel)
            blockers.append("missing_required_external_file")
            findings.append(
                ProductionPromotionFinding(
                    check="required_external_file",
                    status="fail",
                    path=rel,
                    message="Required production-promotion evidence file is missing.",
                )
            )
            return None
        hashes[rel] = _sha256(path)
        loaded = _safe_load_json(path)
        if loaded is None:
            blockers.append("required_external_file_not_json")
            findings.append(
                ProductionPromotionFinding(
                    check="required_external_file_json",
                    status="fail",
                    path=rel,
                    message="Required production-promotion evidence file is not valid JSON.",
                )
            )
        return loaded

    def audit(self) -> ProductionPromotionReport:
        blockers: list[str] = []
        findings: list[ProductionPromotionFinding] = []
        missing: list[str] = []
        hashes: dict[str, str] = {}
        loaded: dict[str, Any] = {}

        if is_inside_project_repo(self.data_root, self.repo_root):
            blockers.append("data_root_inside_source_repo")
            findings.append(
                ProductionPromotionFinding(
                    check="data_boundary",
                    status="fail",
                    path=str(self.data_root),
                    message="Production evidence data root must not be inside the source repository.",
                )
            )

        networked = NetworkedSourceGateAuditor(self.repo_root, self.data_root).audit().as_dict()
        if networked.get("status") != "pass" or networked.get("production_legal_ready") is not True:
            blockers.append("networked_source_gate_not_passed")
            findings.append(
                ProductionPromotionFinding(
                    check="networked_source_gate",
                    status="fail",
                    message="Networked official-source gate must pass before production promotion.",
                    path="official_authority_store/source_manifest.json",
                )
            )

        for rel in self.policy.get("required_external_files", []):
            loaded[rel] = self._read_required_file(rel, findings, blockers, missing, hashes)

        markers = [str(item) for item in self.policy.get("fixture_markers", [])]
        for rel, obj in loaded.items():
            if obj is not None and _contains_fixture_marker(obj, markers):
                blockers.append("fixture_marker_detected")
                findings.append(
                    ProductionPromotionFinding(
                        check="fixture_marker",
                        status="fail",
                        path=rel,
                        message="Fixture/offline/synthetic marker detected in production-promotion evidence.",
                    )
                )

        gold = loaded.get("eval_store/gold_eval_pack_manifest.json")
        attorney_rows = 0
        if isinstance(gold, dict):
            try:
                attorney_rows = int(gold.get("attorney_reviewed_rows_total", 0))
            except (TypeError, ValueError):
                attorney_rows = 0
        min_rows = int(self.policy.get("minimum_attorney_reviewed_rows_total", 0))
        if attorney_rows < min_rows:
            blockers.append("attorney_reviewed_rows_minimum_not_met")
            findings.append(
                ProductionPromotionFinding(
                    check="attorney_reviewed_rows_total",
                    status="fail",
                    path="eval_store/gold_eval_pack_manifest.json",
                    message=f"Attorney-reviewed rows {attorney_rows}; expected at least {min_rows}.",
                )
            )

        metrics = _metric_map(loaded.get("eval_store/release_metrics_evidence.json"))
        metric_results: dict[str, dict[str, Any]] = {}
        for name, threshold in self.policy.get("metric_thresholds", {}).items():
            actual = metrics.get(name)
            direction = threshold.get("direction")
            target = float(threshold.get("value"))
            passed = actual is not None and ((direction == ">=" and actual >= target) or (direction == "<=" and actual <= target))
            metric_results[name] = {"actual": actual, "direction": direction, "target": target, "status": "pass" if passed else "fail"}
            if not passed:
                blockers.append("metric_threshold_not_met")
                findings.append(
                    ProductionPromotionFinding(
                        check="metric_threshold",
                        status="fail",
                        path="eval_store/release_metrics_evidence.json",
                        message=f"Metric {name}={actual}; expected {direction} {target}.",
                    )
                )

        pilot = loaded.get("release_evidence/pilot_evidence_packet.json")
        if not isinstance(pilot, dict) or any(pilot.get(field) is not True and field != "pilot_status" for field in self.policy.get("required_pilot_fields", [])) or (isinstance(pilot, dict) and pilot.get("pilot_status") not in {"passed", "complete", "approved"}):
            blockers.append("pilot_evidence_incomplete")
            findings.append(
                ProductionPromotionFinding(
                    check="pilot_evidence",
                    status="fail",
                    path="release_evidence/pilot_evidence_packet.json",
                    message="Pilot evidence must show passed/complete status, no leakage, no unsupported exports, and attorney signoff.",
                )
            )

        security = loaded.get("release_evidence/security_governance_packet.json")
        if not isinstance(security, dict) or any(security.get(field) is not True for field in self.policy.get("required_security_fields", [])):
            blockers.append("security_governance_evidence_incomplete")
            findings.append(
                ProductionPromotionFinding(
                    check="security_governance_evidence",
                    status="fail",
                    path="release_evidence/security_governance_packet.json",
                    message="Security/governance evidence packet is incomplete.",
                )
            )

        signoffs = loaded.get("release_evidence/owner_signoffs.json")
        roles_present: list[str] = []
        if isinstance(signoffs, dict):
            raw_signoffs = signoffs.get("signoffs", signoffs)
            if isinstance(raw_signoffs, list):
                for row in raw_signoffs:
                    if isinstance(row, dict) and row.get("approved") is True:
                        roles_present.append(str(row.get("role")))
            elif isinstance(raw_signoffs, dict):
                for role, value in raw_signoffs.items():
                    if value is True or (isinstance(value, dict) and value.get("approved") is True):
                        roles_present.append(str(role))
        for role in self.policy.get("required_signoff_roles", []):
            if role not in roles_present:
                blockers.append("owner_signoff_missing_or_unapproved")
                findings.append(
                    ProductionPromotionFinding(
                        check="owner_signoff",
                        status="fail",
                        path="release_evidence/owner_signoffs.json",
                        message=f"Missing approved owner signoff role: {role}.",
                    )
                )

        rollback = loaded.get("release_evidence/rollback_package_manifest.json")
        if not isinstance(rollback, dict) or rollback.get("rollback_package_ready") is not True:
            blockers.append("rollback_package_missing_or_incomplete")
            findings.append(
                ProductionPromotionFinding(
                    check="rollback_package",
                    status="fail",
                    path="release_evidence/rollback_package_manifest.json",
                    message="Rollback package manifest must mark rollback_package_ready true.",
                )
            )

        next_commands = [
            "cd C:\\dev\\ME_FM_LLM",
            "python scripts\\collect-enterprise-resources.py --project-root C:\\dev\\ME_FM_LLM --data-root C:\\dev\\ME_FM_LLM_data",
            "python scripts\\ingest-maine-authority.py --data-root C:\\dev\\ME_FM_LLM_data",
            "python scripts\\build-parsed-authority-store.py --data-root C:\\dev\\ME_FM_LLM_data",
            "python scripts\\build-authority-layer.py --data-root C:\\dev\\ME_FM_LLM_data",
            "python scripts\\build-retrieval-indexes.py --data-root C:\\dev\\ME_FM_LLM_data",
            "python scripts\\run-networked-source-gate.py --data-root C:\\dev\\ME_FM_LLM_data",
            "python scripts\\run-production-promotion-gate.py --data-root C:\\dev\\ME_FM_LLM_data",
        ]
        ready = not blockers
        return ProductionPromotionReport(
            status="pass" if ready else "fail",
            production_legal_ready=ready,
            promotion_locked=not ready,
            repo_root=str(self.repo_root),
            data_root=str(self.data_root),
            generated_at=_utc_now(),
            networked_source_gate_status=str(networked.get("status", "unknown")),
            missing_required_external_files=missing,
            external_file_hashes=hashes,
            metric_results=metric_results,
            attorney_reviewed_rows_total=attorney_rows,
            owner_signoff_roles_present=sorted(set(roles_present)),
            blockers=blockers,
            findings=findings,
            next_commands=next_commands,
            interpretation=(
                "Pass means external evidence is sufficient to promote a build to production legal readiness. "
                "Fail means the source repo may still be locally test-ready, but production promotion remains locked."
            ),
        )

    def write(self, output_path: str | Path) -> ProductionPromotionReport:
        report = self.audit()
        path = Path(output_path)
        if not path.is_absolute():
            path = self.repo_root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return report


def run_production_promotion_gate(project_root: str | Path = ".", data_root: str | Path | None = None) -> dict[str, Any]:
    return ProductionPromotionGateAuditor(project_root, data_root).audit().as_dict()
