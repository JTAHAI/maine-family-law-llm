"""Disposable longitudinal matter-contract evaluation.

This evaluator exercises durable local components using a fictional matter in
an external evaluation root.  It never opens an active user matter, and the
public report retains only scenario identifiers, hashes, counters, and review
states.  It is software-contract evidence only: it is not attorney review,
pilot evidence, a migration of an installed package, or a legal conclusion.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal.evals.citation_quote_metrics import read_jsonl, write_json
from legal.evidence.matter_command_center import MatterCommandCenterStore
from legal.evidence.review_workbench import EvidenceReviewStore
from legal.matter.intake_workbench import MatterIntakeStore
from legal.runtime.schema_migration_lab import SchemaMigrationLab


LONGITUDINAL_SCENARIOS = frozenset(
    {
        "multi_session_changes",
        "corrected_fact",
        "amended_authority",
        "restart_reopen",
        "migration_recovery",
        "stale_work",
    }
)
_SHA256_LENGTH = 64


def _hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _is_sha256(value: object) -> bool:
    candidate = str(value or "").strip().casefold()
    return len(candidate) == _SHA256_LENGTH and all(char in "0123456789abcdef" for char in candidate)


@dataclass
class LongitudinalMatterMetricReport:
    status: str
    readiness: str
    generated_at: str
    scenario_total: int = 0
    scenario_passed: int = 0
    scenario_counts: dict[str, int] = field(default_factory=dict)
    encrypted_state_verified: bool = False
    append_only_history_verified: bool = False
    source_drill_down_verified: bool = False
    migration_contract_verified: bool = False
    stale_work_verified: bool = False
    blockers: list[str] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "readiness": self.readiness,
            "generated_at": self.generated_at,
            "scenario_total": self.scenario_total,
            "scenario_passed": self.scenario_passed,
            "scenario_counts": self.scenario_counts,
            "encrypted_state_verified": self.encrypted_state_verified,
            "append_only_history_verified": self.append_only_history_verified,
            "source_drill_down_verified": self.source_drill_down_verified,
            "migration_contract_verified": self.migration_contract_verified,
            "stale_work_verified": self.stale_work_verified,
            "blockers": sorted(set(self.blockers)),
            "findings": self.findings,
            "review_required": True,
            "matter_scope": "disposable_fictional_evaluation_only",
            "network_used": False,
            "private_matter_data_used": False,
            "attorney_reviewed": False,
            "pilot_evidence": False,
            "package_or_frozen_runtime_verified": False,
            "notice": "This runs deterministic fictional software contracts only. It does not establish attorney review, live-matter migration, a pilot, or release readiness.",
        }


class LongitudinalMatterMetricRunner:
    """Exercise multi-session integrity behaviour without touching a user matter."""

    dataset_name = "maine_longitudinal_matter_gold.jsonl"

    def run(
        self,
        *,
        eval_root: str | Path,
        output_path: str | Path | None = None,
        strict_provenance: bool = False,
    ) -> LongitudinalMatterMetricReport:
        root = Path(eval_root)
        dataset = root / self.dataset_name
        rows = list(read_jsonl(dataset)) if dataset.is_file() else []
        blockers: list[str] = []
        findings: list[dict[str, Any]] = []
        covered: dict[str, int] = {}
        if not rows:
            blockers.append("longitudinal_scenario_manifest_missing_or_empty")
        for row_number, row in enumerate(rows, start=1):
            scenario = str(row.get("scenario") or "").strip().casefold()
            if strict_provenance:
                errors = _manifest_errors(row, scenario)
                if errors:
                    blockers.extend(errors)
                    findings.extend({"row_number": row_number, "code": code} for code in errors)
                    continue
            if scenario not in LONGITUDINAL_SCENARIOS:
                blockers.append("longitudinal_scenario_invalid")
                findings.append({"row_number": row_number, "code": "longitudinal_scenario_invalid"})
                continue
            covered[scenario] = covered.get(scenario, 0) + 1
        if strict_provenance:
            for scenario in sorted(LONGITUDINAL_SCENARIOS):
                if not covered.get(scenario):
                    blockers.append(f"longitudinal_scenario_coverage_missing:{scenario}")

        outcomes = self._run_disposable_suite(root)
        for scenario in sorted(LONGITUDINAL_SCENARIOS):
            outcome = outcomes.get(scenario) or {"status": "blocked", "code": "longitudinal_scenario_not_executed"}
            if outcome.get("status") != "pass":
                blockers.append(str(outcome.get("code") or f"longitudinal_{scenario}_failed"))
                findings.append({"scenario": scenario, "code": str(outcome.get("code") or "longitudinal_scenario_failed")})

        measured = sum(covered.values()) if strict_provenance else len(LONGITUDINAL_SCENARIOS)
        passed = sum(1 for scenario in LONGITUDINAL_SCENARIOS if covered.get(scenario, 1) and outcomes.get(scenario, {}).get("status") == "pass")
        report = LongitudinalMatterMetricReport(
            status="pass" if not blockers and passed == len(LONGITUDINAL_SCENARIOS) else "blocked",
            readiness="longitudinal_matter_contract_ready" if not blockers and passed == len(LONGITUDINAL_SCENARIOS) else "longitudinal_matter_contract_blocked",
            generated_at=datetime.now(timezone.utc).isoformat(),
            scenario_total=measured,
            scenario_passed=passed,
            scenario_counts={scenario: covered.get(scenario, 0) for scenario in sorted(LONGITUDINAL_SCENARIOS)},
            encrypted_state_verified=outcomes.get("restart_reopen", {}).get("encrypted_state_verified") is True,
            append_only_history_verified=outcomes.get("corrected_fact", {}).get("append_only_history_verified") is True,
            source_drill_down_verified=outcomes.get("corrected_fact", {}).get("source_drill_down_verified") is True,
            migration_contract_verified=outcomes.get("migration_recovery", {}).get("migration_contract_verified") is True,
            stale_work_verified=outcomes.get("stale_work", {}).get("stale_work_verified") is True,
            blockers=blockers,
            findings=findings,
        )
        if output_path:
            write_json(Path(output_path), report.as_dict())
        return report

    def _run_disposable_suite(self, root: Path) -> dict[str, dict[str, Any]]:
        runs = root / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        outcomes: dict[str, dict[str, Any]] = {}
        with tempfile.TemporaryDirectory(prefix="mfll-longitudinal-fictional-", dir=runs) as temporary:
            case_root = Path(temporary) / "fictional-matter"
            case_root.mkdir()
            key = "longitudinal-fictional-evaluation-key"
            records = _fictional_records()
            try:
                intake = MatterIntakeStore(case_root, encryption_key=key)
                created = intake.create(
                    {
                        "matter_id": "fictional_longitudinal_case",
                        "matter_type_candidates": ["parental_rights_responsibilities"],
                        "court": {"court": "Fictional Court", "county": "Fictional", "docket_safe_identifier": "fictional-001"},
                        "record_scope": {"included_records": [{"record_id": "record_base", "source_hash": records[0]["source_hash"]}]},
                    }
                )
                encrypted_path = case_root / "20_MATTER_INTAKE" / "fictional_longitudinal_case" / "intake.json.enc"
                encrypted_bytes = encrypted_path.read_bytes()
                intake.update(
                    "fictional_longitudinal_case",
                    {"record_scope": {"included_records": [{"record_id": "record_corrected", "source_hash": records[1]["source_hash"]}]}},
                )
                reopened = MatterIntakeStore(case_root, encryption_key=key).get("fictional_longitudinal_case")
                encrypted_ok = bool(
                    created.get("review_required")
                    and reopened.get("revision", 0) >= 2
                    and len(reopened.get("history") or []) >= 2
                    and b"Fictional Court" not in encrypted_bytes
                )
                outcomes["restart_reopen"] = {
                    "status": "pass" if encrypted_ok else "blocked",
                    "code": "restart_reopen_verified" if encrypted_ok else "encrypted_intake_reopen_failed",
                    "encrypted_state_verified": encrypted_ok,
                }

                command = MatterCommandCenterStore(case_root)
                baseline = command.freeze_snapshot("fictional-longitudinal", records, variant="metadata_only", approved=True)
                reopened_center = MatterCommandCenterStore(case_root).command_center("fictional-longitudinal", records)
                multi_ok = bool(
                    reopened_center.get("latest_snapshot_id") == baseline.get("snapshot_id")
                    and reopened_center.get("stale_snapshot_detected") is False
                    and baseline.get("review_required") is True
                )
                outcomes["multi_session_changes"] = {
                    "status": "pass" if multi_ok else "blocked",
                    "code": "multi_session_snapshot_verified" if multi_ok else "multi_session_snapshot_reopen_failed",
                }

                timeline = EvidenceReviewStore(case_root)
                created_event = timeline.create_event(
                    {
                        "event_label": "Fictional record date",
                        "date_value": "2026-01-10",
                        "source_record_id": "record_base",
                        "source_hash": records[0]["source_hash"],
                        "reviewer_status": "review_required",
                    },
                    records=records,
                )
                event_id = str(created_event["event"]["event_id"])
                corrected = timeline.patch_event(
                    event_id,
                    {
                        "date_value": "2026-01-11",
                        "source_record_id": "record_corrected",
                        "source_hash": records[1]["source_hash"],
                        "reason": "Fictional source-bound correction.",
                    },
                    records=records,
                )
                history = EvidenceReviewStore(case_root).get_event_history(event_id)
                corrected_ok = bool(
                    corrected.get("event", {}).get("source_record_id") == "record_corrected"
                    and corrected.get("event", {}).get("review_required") is True
                    and len(history.get("history") or []) >= 2
                    and history.get("source_drill_down_available") is True
                )
                outcomes["corrected_fact"] = {
                    "status": "pass" if corrected_ok else "blocked",
                    "code": "corrected_fact_history_verified" if corrected_ok else "corrected_fact_history_failed",
                    "append_only_history_verified": corrected_ok,
                    "source_drill_down_verified": corrected_ok,
                }

                amended = [dict(row) for row in records]
                amended[2] = {**amended[2], "source_hash": "d" * 64, "text": "Fictional amended authority fixture."}
                changed = MatterCommandCenterStore(case_root).command_center("fictional-longitudinal", amended)
                authority_ok = bool(changed.get("stale_snapshot_detected") and "matter_snapshot_source_changed" in (changed.get("stale_reasons") or []))
                outcomes["amended_authority"] = {
                    "status": "pass" if authority_ok else "blocked",
                    "code": "amended_authority_stale_verified" if authority_ok else "amended_authority_stale_not_detected",
                }
                outcomes["stale_work"] = {
                    "status": "pass" if authority_ok else "blocked",
                    "code": "stale_work_blocker_visible" if authority_ok else "stale_work_blocker_missing",
                    "stale_work_verified": authority_ok,
                }

                migration = SchemaMigrationLab(case_root, encryption_key=key).run(
                    source_schema="all", scenario="full_suite", actor_role="reviewer", tenant_id="fictional-evaluation"
                )
                migration_ok = bool(
                    migration.get("status") == "pass_review_required"
                    and all(row.get("status") == "pass" for row in migration.get("checks") or [])
                    and migration.get("live_matter_changed") is False
                )
                outcomes["migration_recovery"] = {
                    "status": "pass" if migration_ok else "blocked",
                    "code": "migration_recovery_contract_verified" if migration_ok else "migration_recovery_contract_failed",
                    "migration_contract_verified": migration_ok,
                }
            except Exception as exc:  # Fail closed while keeping error details out of the public report.
                code = f"longitudinal_suite_exception:{type(exc).__name__}"
                for scenario in LONGITUDINAL_SCENARIOS:
                    outcomes.setdefault(scenario, {"status": "blocked", "code": code})
        return outcomes


def _manifest_errors(row: dict[str, Any], scenario: str) -> list[str]:
    errors: list[str] = []
    if scenario not in LONGITUDINAL_SCENARIOS:
        errors.append("longitudinal_scenario_invalid")
    if str(row.get("data_class") or "").strip().casefold() != "synthetic":
        errors.append("longitudinal_synthetic_data_class_required")
    if not str(row.get("fixture_id") or "").strip():
        errors.append("longitudinal_fixture_id_missing")
    for field in ("fixture_manifest_sha256", "scenario_evidence_sha256"):
        if not _is_sha256(row.get(field)):
            errors.append(f"longitudinal_{field}_invalid")
    # ``False`` is the required explicit value here, so do not use a truthy
    # fallback that would turn the valid JSON boolean into an empty string.
    if str(row.get("attorney_reviewed", "")).strip().casefold() not in {"false", "no", "0"}:
        errors.append("longitudinal_not_attorney_evidence_required")
    return errors


def _fictional_records() -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": "record_base",
            "title": "Fictional base record",
            "source_type": "communication",
            "source_hash": "a" * 64,
            "text": "Fictional source event on January 10, 2026.",
            "page_number": 1,
            "privacy_status": "review_required",
        },
        {
            "evidence_id": "record_corrected",
            "title": "Fictional corrected record",
            "source_type": "communication",
            "source_hash": "b" * 64,
            "text": "Fictional correction source event on January 11, 2026.",
            "page_number": 2,
            "privacy_status": "review_required",
        },
        {
            "evidence_id": "authority_fixture",
            "title": "Fictional authority fixture",
            "source_type": "authority",
            "source_hash": "c" * 64,
            "text": "Fictional authority fixture; no legal conclusion.",
            "page_number": 1,
            "privacy_status": "review_required",
        },
    ]


__all__ = ["LONGITUDINAL_SCENARIOS", "LongitudinalMatterMetricReport", "LongitudinalMatterMetricRunner"]
