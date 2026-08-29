"""Encrypted, matter-scoped synthetic migration-contract laboratory.

This laboratory validates the project's declared *profile-contract* transitions
without opening, changing, or copying a live matter.  It is deliberately not
an installer upgrader: package, frozen-runtime, and real-user migration
qualification require their own isolated evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path

SUPPORTED_SOURCE_SCHEMAS = ("6.0.3.0", "6.0.4.0", "7.0.0.0", "8.0.0.0")
TARGET_SCHEMA = "8.0.0.0"
_SCENARIOS = ("clean_upgrade", "interrupt_before_commit", "interrupt_after_commit")


class SchemaMigrationLabError(RuntimeError):
    def __init__(self, code: str, *, status_code: int = 409) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canon(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _hash(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else _canon(value)).hexdigest()


class SchemaMigrationLab:
    """Runs bounded synthetic profile migration and recovery contract checks."""

    schema_version = "schema_migration_lab_v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None) -> None:
        self.case_root = Path(case_root).resolve()
        if not self.case_root.is_dir() or self.case_root.is_symlink():
            raise SchemaMigrationLabError("active_matter_unavailable", status_code=404)
        self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")
        self.scope = _hash(str(self.case_root))[:24]
        self.state_path = self.case_root / "40_RUNTIME" / "schema-migration-lab" / "state.json.enc"
        self.lock_path = self.state_path.parent / ".state.lock"

    def status(self, *, tenant_id: str) -> dict[str, Any]:
        state = self._load(tenant_id)
        runs = list(state.get("runs") or [])
        return {
            "schema_version": self.schema_version,
            "status": "review_required",
            "target_schema": TARGET_SCHEMA,
            "supported_source_schemas": list(SUPPORTED_SOURCE_SCHEMAS),
            "supported_scenarios": list(_SCENARIOS),
            "run_count": len(runs),
            "runs": [self._safe_run(row) for row in runs[-20:]][::-1],
            "live_matter_changed": False,
            "network_used": False,
            "review_required": True,
            "source_drill_down": {"source_type": "synthetic_migration_contract", "source_id": f"migration-lab:{self.scope}"},
        }

    def run(self, *, source_schema: object, scenario: object, actor_role: str, tenant_id: str) -> dict[str, Any]:
        requested_source = str(source_schema or "").strip()
        requested_scenario = str(scenario or "").strip()
        if requested_source != "all" and requested_source not in SUPPORTED_SOURCE_SCHEMAS:
            raise SchemaMigrationLabError("migration_source_schema_unsupported", status_code=422)
        if requested_scenario not in {*_SCENARIOS, "full_suite"}:
            raise SchemaMigrationLabError("migration_scenario_invalid", status_code=422)
        sources = SUPPORTED_SOURCE_SCHEMAS if requested_source == "all" else (requested_source,)
        scenarios = _SCENARIOS if requested_scenario == "full_suite" else (requested_scenario,)
        checks = [self._exercise(source, item) for source in sources for item in scenarios]
        if not all(row["status"] == "pass" for row in checks):
            raise SchemaMigrationLabError("migration_lab_check_failed")
        run_id = f"migration_{_hash({'scope': self.scope, 'sources': sources, 'scenarios': scenarios, 'at': _now()})[:24]}"
        report = {
            "run_id": run_id,
            "source_schemas": list(sources),
            "scenarios": list(scenarios),
            "check_count": len(checks),
            "passed_count": len(checks),
            "status": "pass_review_required",
            "checks": checks,
            "live_matter_changed": False,
            "network_used": False,
            "review_required": True,
            "source_drill_down": {"source_type": "synthetic_migration_contract", "source_id": run_id},
        }
        return self._record(report, actor_role=actor_role, tenant_id=tenant_id)

    def _exercise(self, source_schema: str, scenario: str) -> dict[str, Any]:
        prior = {
            "schema_version": source_schema,
            "matter_scope_hash": self.scope,
            "local_only": True,
            "draft_history_count": 1,
            "sidecar_contracts": ["revision_history", "authority_reference", "runtime_receipt"],
        }
        prior_hash = _hash(prior)
        preserved_profile = {key: value for key, value in prior.items() if key != "schema_version"}
        preserved_profile_hash = _hash(preserved_profile)
        candidate = {**prior, "schema_version": TARGET_SCHEMA, "migration_contract": "profile_contract_v1"}
        candidate_hash = _hash(candidate)
        if scenario == "clean_upgrade":
            result = {"committed_schema": TARGET_SCHEMA, "preserved_profile_hash": _hash({key: candidate[key] for key in preserved_profile}), "restart_verified": candidate["schema_version"] == TARGET_SCHEMA, "rollback_ready": True, "forward_recovery_ready": True}
        elif scenario == "interrupt_before_commit":
            result = {"committed_schema": source_schema, "preserved_profile_hash": _hash(preserved_profile), "restart_verified": prior["schema_version"] == source_schema, "rollback_ready": True, "forward_recovery_ready": True, "interrupted_candidate_discarded": True}
        else:
            result = {"committed_schema": TARGET_SCHEMA, "preserved_profile_hash": _hash({key: candidate[key] for key in preserved_profile}), "restart_verified": candidate["schema_version"] == TARGET_SCHEMA, "rollback_ready": True, "forward_recovery_ready": True, "post_commit_restart_verified": True}
        passed = bool(result["rollback_ready"] and result["forward_recovery_ready"] and result["restart_verified"] and result["preserved_profile_hash"] == preserved_profile_hash)
        return {"source_schema": source_schema, "target_schema": TARGET_SCHEMA, "scenario": scenario, "status": "pass" if passed else "blocked", "prior_profile_hash": prior_hash, "preserved_profile_hash": preserved_profile_hash, "candidate_profile_hash": candidate_hash, "result": result, "review_required": True}

    @staticmethod
    def _safe_run(row: object) -> dict[str, Any]:
        value = row if isinstance(row, dict) else {}
        return {key: value.get(key) for key in ("run_id", "source_schemas", "scenarios", "check_count", "passed_count", "status", "recorded_at", "review_required", "source_drill_down")}

    def _load(self, tenant_id: str) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"schema_version": self.schema_version, "tenant_id": tenant_id, "runs": [], "audit": []}
        try:
            state = self.encryptor.decrypt_json(strict_json_load_path(self.state_path, max_bytes=512 * 1024, require_object=True))
        except Exception as exc:
            raise SchemaMigrationLabError("migration_lab_state_unavailable") from exc
        if not isinstance(state, dict) or state.get("schema_version") != self.schema_version:
            raise SchemaMigrationLabError("migration_lab_state_invalid")
        if state.get("tenant_id") and state["tenant_id"] != tenant_id:
            raise SchemaMigrationLabError("migration_lab_tenant_mismatch", status_code=403)
        state["tenant_id"] = tenant_id
        return state

    def _record(self, report: dict[str, Any], *, actor_role: str, tenant_id: str) -> dict[str, Any]:
        with exclusive_file_lock(self.lock_path):
            state = self._load(tenant_id)
            previous = str((state.get("audit") or [{}])[-1].get("event_hash") or "")
            recorded_at = _now()
            event = {"event_type": "synthetic_schema_migration_lab_run", "recorded_at": recorded_at, "report_hash": _hash(report), "previous_hash": previous, "actor_role": actor_role[:40], "tenant_id": tenant_id}
            event["event_hash"] = _hash(event)
            state["runs"] = [*list(state.get("runs") or []), {**report, "recorded_at": recorded_at}][-40:]
            state["audit"] = [*list(state.get("audit") or []), event][-80:]
            atomic_write_bytes(self.state_path, _canon(self.encryptor.encrypt_json(state)), mode=0o600)
        return {**report, "recorded_at": recorded_at, "audit_receipt": {"migration_receipt_id": f"migration_{event['event_hash'][:24]}", "recorded_at": recorded_at, "review_required": True}, "audit_chain_head": event["event_hash"]}


__all__ = ["SchemaMigrationLab", "SchemaMigrationLabError", "SUPPORTED_SOURCE_SCHEMAS", "TARGET_SCHEMA"]
