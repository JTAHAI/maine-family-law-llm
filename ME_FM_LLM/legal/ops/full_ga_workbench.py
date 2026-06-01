from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal.data_boundaries.storage_layout import is_inside_project_repo
from legal.ops.networked_source_gate import NetworkedSourceGateAuditor
from legal.ops.operator_test_battery import OperatorTestBatteryAuditor
from legal.ops.production_promotion import ProductionPromotionGateAuditor


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


def _contains_marker(obj: Any, markers: list[str]) -> bool:
    if obj is None:
        return False
    text = json.dumps(obj, sort_keys=True, default=str).lower()
    return any(marker.lower() in text for marker in markers)


@dataclass(frozen=True)
class FullGAEvidenceFile:
    path: str
    present: bool
    valid_json: bool
    sha256: str | None = None
    size_bytes: int | None = None
    fixture_marker_detected: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "present": self.present,
            "valid_json": self.valid_json,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "fixture_marker_detected": self.fixture_marker_detected,
        }


@dataclass(frozen=True)
class FullGAPhase:
    name: str
    status: str
    blockers: list[str] = field(default_factory=list)
    message: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "blockers": sorted(set(self.blockers)),
            "message": self.message,
        }


@dataclass(frozen=True)
class FullGAWorkbenchReport:
    status: str
    ready_for_local_testing: bool
    networked_source_ready: bool
    production_legal_ready: bool
    repo_root: str
    data_root: str
    generated_at: str
    evidence_inventory: list[FullGAEvidenceFile] = field(default_factory=list)
    phases: list[FullGAPhase] = field(default_factory=list)
    operator_test_battery: dict[str, Any] = field(default_factory=dict)
    networked_source_gate: dict[str, Any] = field(default_factory=dict)
    production_promotion_gate: dict[str, Any] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    next_commands: list[str] = field(default_factory=list)
    interpretation: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "ready_for_local_testing": self.ready_for_local_testing,
            "networked_source_ready": self.networked_source_ready,
            "production_legal_ready": self.production_legal_ready,
            "repo_root": self.repo_root,
            "data_root": self.data_root,
            "generated_at": self.generated_at,
            "evidence_inventory": [item.as_dict() for item in self.evidence_inventory],
            "phases": [phase.as_dict() for phase in self.phases],
            "operator_test_battery": self.operator_test_battery,
            "networked_source_gate": self.networked_source_gate,
            "production_promotion_gate": self.production_promotion_gate,
            "blockers": sorted(set(self.blockers)),
            "next_commands": list(self.next_commands),
            "interpretation": self.interpretation,
        }


class FullGAWorkbenchBuilder:
    """Build a single, honest GA readiness report for operators.

    This is not a shortcut around the hard gates. It aggregates the operator/local test
    battery, networked official-source gate, and final production promotion gate into one
    deterministic artifact so the repo can be driven toward full GA without confusing
    fixture/source readiness for legal-production readiness.
    """

    def __init__(self, repo_root: str | Path = ".", data_root: str | Path | None = None) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.policy = _load_json(self.repo_root / "configs" / "maine_full_ga_workbench_policy.json")
        self.data_root = Path(data_root or self.policy["default_windows_data_root"]).expanduser().resolve()

    def _inventory_evidence(self) -> tuple[list[FullGAEvidenceFile], list[str]]:
        markers = [str(item) for item in self.policy.get("fixture_markers", [])]
        inventory: list[FullGAEvidenceFile] = []
        blockers: list[str] = []
        for rel in self.policy.get("evidence_inventory_files", []):
            path = self.data_root / rel
            if not path.is_file():
                inventory.append(FullGAEvidenceFile(path=rel, present=False, valid_json=False))
                blockers.append("missing_ga_evidence_file")
                continue
            loaded = _safe_load_json(path)
            fixture = _contains_marker(loaded, markers)
            if loaded is None:
                blockers.append("ga_evidence_file_not_json")
            if fixture:
                blockers.append("fixture_marker_detected")
            inventory.append(
                FullGAEvidenceFile(
                    path=rel,
                    present=True,
                    valid_json=loaded is not None,
                    sha256=_sha256(path),
                    size_bytes=path.stat().st_size,
                    fixture_marker_detected=fixture,
                )
            )
        return inventory, blockers

    def build(self, *, create_external_dirs: bool = True, write_probe: bool = False) -> FullGAWorkbenchReport:
        blockers: list[str] = []
        phases: list[FullGAPhase] = []

        if is_inside_project_repo(self.data_root, self.repo_root):
            blockers.append("data_root_inside_source_repo")

        operator = OperatorTestBatteryAuditor(self.repo_root, self.data_root).audit(
            create_external_dirs=create_external_dirs,
            write_probe=write_probe,
        ).as_dict()
        ready_for_local = operator.get("status") == "pass" and operator.get("ready_for_operator_local_test") is True
        phases.append(
            FullGAPhase(
                name="source_local_test",
                status="pass" if ready_for_local else "fail",
                blockers=list(operator.get("blockers", [])),
                message="Source tree/operator fixture testing is ready." if ready_for_local else "Local operator testing is blocked.",
            )
        )
        if not ready_for_local:
            blockers.append("operator_local_test_not_ready")

        inventory, inventory_blockers = self._inventory_evidence()
        blockers.extend(inventory_blockers)

        networked = NetworkedSourceGateAuditor(self.repo_root, self.data_root).audit().as_dict()
        networked_ready = networked.get("status") == "pass" and networked.get("networked_source_ready") is True
        phases.append(
            FullGAPhase(
                name="networked_official_authority",
                status="pass" if networked_ready else "fail",
                blockers=list(networked.get("blockers", [])),
                message="External official authority evidence passes the networked source gate."
                if networked_ready
                else "External official authority evidence is missing, fixture-marked, or below policy minimums.",
            )
        )
        if not networked_ready:
            blockers.append("networked_source_gate_not_passed")

        parsed_counts = networked.get("parsed_record_counts", {}) if isinstance(networked, dict) else {}
        indexes = networked.get("retrieval_indexes_present", []) if isinstance(networked, dict) else []
        parsed_and_indexed = networked_ready and bool(parsed_counts) and {"bm25", "vector", "hybrid"}.issubset(set(indexes))
        phases.append(
            FullGAPhase(
                name="parsed_authority_and_indexes",
                status="pass" if parsed_and_indexed else "fail",
                blockers=[] if parsed_and_indexed else ["parsed_store_or_retrieval_indexes_not_ready"],
                message="Parsed authority stores and all retrieval index classes are present."
                if parsed_and_indexed
                else "Parsed authority stores or retrieval indexes are not yet complete.",
            )
        )
        if not parsed_and_indexed:
            blockers.append("parsed_store_or_retrieval_indexes_not_ready")

        gold_rows = int(networked.get("gold_eval_rows_total", 0) or 0)
        gold_ready = gold_rows > 0 and not any(item.path.endswith("gold_eval_pack_manifest.json") and item.fixture_marker_detected for item in inventory)
        phases.append(
            FullGAPhase(
                name="attorney_reviewed_gold",
                status="pass" if gold_ready else "fail",
                blockers=[] if gold_ready else ["attorney_reviewed_gold_not_ready"],
                message=f"Gold eval rows present: {gold_rows}." if gold_ready else "Attorney-reviewed gold eval manifest is missing or not yet accepted.",
            )
        )
        if not gold_ready:
            blockers.append("attorney_reviewed_gold_not_ready")

        metric_names = networked.get("release_metric_names_present", []) if isinstance(networked, dict) else []
        metrics_ready = len(metric_names) >= 7 and not any(item.path.endswith("release_metrics_evidence.json") and item.fixture_marker_detected for item in inventory)
        phases.append(
            FullGAPhase(
                name="release_metrics",
                status="pass" if metrics_ready else "fail",
                blockers=[] if metrics_ready else ["release_metrics_not_ready"],
                message="Release metric evidence is present." if metrics_ready else "Release metric evidence is missing or incomplete.",
            )
        )
        if not metrics_ready:
            blockers.append("release_metrics_not_ready")

        promotion = ProductionPromotionGateAuditor(self.repo_root, self.data_root).audit().as_dict()
        pilot_security_signoffs = not any(
            blocker in set(promotion.get("blockers", []))
            for blocker in {
                "pilot_evidence_incomplete",
                "security_governance_evidence_incomplete",
                "owner_signoff_missing_or_unapproved",
                "rollback_package_missing_or_incomplete",
            }
        )
        phases.append(
            FullGAPhase(
                name="pilot_security_and_signoffs",
                status="pass" if pilot_security_signoffs else "fail",
                blockers=[
                    blocker
                    for blocker in promotion.get("blockers", [])
                    if blocker
                    in {
                        "pilot_evidence_incomplete",
                        "security_governance_evidence_incomplete",
                        "owner_signoff_missing_or_unapproved",
                        "rollback_package_missing_or_incomplete",
                    }
                ],
                message="Pilot, security/governance, rollback, and owner signoff evidence are present."
                if pilot_security_signoffs
                else "Pilot, security/governance, rollback, or owner signoff evidence is still incomplete.",
            )
        )
        if not pilot_security_signoffs:
            blockers.append("pilot_security_signoff_package_not_ready")

        promoted = promotion.get("status") == "pass" and promotion.get("production_legal_ready") is True
        phases.append(
            FullGAPhase(
                name="production_promotion",
                status="pass" if promoted else "fail",
                blockers=list(promotion.get("blockers", [])),
                message="Production promotion gate passed." if promoted else "Production promotion remains locked.",
            )
        )
        if not promoted:
            blockers.append("production_promotion_gate_not_passed")

        status = "pass" if promoted and not blockers else "fail"
        return FullGAWorkbenchReport(
            status=status,
            ready_for_local_testing=ready_for_local,
            networked_source_ready=networked_ready,
            production_legal_ready=promoted,
            repo_root=str(self.repo_root),
            data_root=str(self.data_root),
            generated_at=_utc_now(),
            evidence_inventory=inventory,
            phases=phases,
            operator_test_battery=operator,
            networked_source_gate=networked,
            production_promotion_gate=promotion,
            blockers=blockers,
            next_commands=list(self.policy.get("windows_full_ga_commands", [])),
            interpretation=(
                "This full-GA workbench report aggregates the local operator test battery, networked official-source gate, "
                "and production promotion gate. It may pass local testing while production_legal_ready remains false. "
                "Only a pass on production_promotion may certify production legal readiness."
            ),
        )

    def write(self, output_path: str | Path, **kwargs: Any) -> FullGAWorkbenchReport:
        report = self.build(**kwargs)
        path = Path(output_path)
        if not path.is_absolute():
            path = self.repo_root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return report


def build_full_ga_workbench(
    project_root: str | Path = ".",
    data_root: str | Path | None = None,
    *,
    create_external_dirs: bool = True,
    write_probe: bool = False,
) -> dict[str, Any]:
    return FullGAWorkbenchBuilder(project_root, data_root).build(
        create_external_dirs=create_external_dirs,
        write_probe=write_probe,
    ).as_dict()
