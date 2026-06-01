from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from .registry import CERTIFICATION_TASKS, ModelAdmissionRecord, ModelRegistry
from .roles import RoleCatalog


@dataclass(frozen=True)
class ModelReplacementEvent:
    event_id: str
    event_type: str
    old_model_id: str | None
    new_model_id: str
    role: str
    reason: str
    evidence_hash: str
    created_at: str
    previous_event_hash: str
    event_hash: str

    @classmethod
    def create(
        cls,
        *,
        old_model_id: str | None,
        new_model_id: str,
        role: str,
        reason: str,
        evidence: dict[str, Any],
        previous_event_hash: str = "0" * 64,
    ) -> "ModelReplacementEvent":
        created_at = datetime.now(timezone.utc).isoformat()
        evidence_hash = sha256(json.dumps(evidence, sort_keys=True).encode("utf-8")).hexdigest()
        event_id = sha256(
            f"{old_model_id}:{new_model_id}:{role}:{reason}:{created_at}".encode("utf-8")
        ).hexdigest()[:24]
        payload = {
            "event_id": event_id,
            "event_type": "model_replacement",
            "old_model_id": old_model_id,
            "new_model_id": new_model_id,
            "role": role,
            "reason": reason,
            "evidence_hash": evidence_hash,
            "created_at": created_at,
            "previous_event_hash": previous_event_hash,
        }
        event_hash = sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        return cls(event_hash=event_hash, **payload)

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "old_model_id": self.old_model_id,
            "new_model_id": self.new_model_id,
            "role": self.role,
            "reason": self.reason,
            "evidence_hash": self.evidence_hash,
            "created_at": self.created_at,
            "previous_event_hash": self.previous_event_hash,
            "event_hash": self.event_hash,
        }


class ModelReplacementLedger:
    """Append-only model replacement ledger for governance evidence.

    The source repo stores only policy and smoke evidence. Production deployments should
    persist this ledger in immutable audit storage.
    """

    def __init__(self, events: list[ModelReplacementEvent] | None = None):
        self.events = list(events or [])

    @property
    def chain_head(self) -> str:
        return self.events[-1].event_hash if self.events else "0" * 64

    def append(
        self,
        *,
        old_model_id: str | None,
        new_model_id: str,
        role: str,
        reason: str,
        evidence: dict[str, Any],
    ) -> ModelReplacementEvent:
        event = ModelReplacementEvent.create(
            old_model_id=old_model_id,
            new_model_id=new_model_id,
            role=role,
            reason=reason,
            evidence=evidence,
            previous_event_hash=self.chain_head,
        )
        self.events.append(event)
        return event

    def verify(self) -> bool:
        previous = "0" * 64
        for event in self.events:
            if event.previous_event_hash != previous:
                return False
            payload = event.as_dict()
            event_hash = payload.pop("event_hash")
            computed = sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
            if computed != event_hash:
                return False
            previous = event_hash
        return True

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_count": len(self.events),
            "chain_head": self.chain_head,
            "verified": self.verify(),
            "events": [event.as_dict() for event in self.events],
        }


@dataclass(frozen=True)
class ModelGovernanceReport:
    status: str
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    role_count: int = 0
    admitted_record_count: int = 0
    production_record_count: int = 0
    certification_tasks_reserved_to_system_gates: list[str] = field(default_factory=list)
    registry_records: list[dict[str, Any]] = field(default_factory=list)
    replacement_ledger: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "role_count": self.role_count,
            "admitted_record_count": self.admitted_record_count,
            "production_record_count": self.production_record_count,
            "certification_tasks_reserved_to_system_gates": list(
                self.certification_tasks_reserved_to_system_gates
            ),
            "registry_records": [dict(record) for record in self.registry_records],
            "replacement_ledger": dict(self.replacement_ledger),
        }


class ModelGovernanceAuditor:
    def __init__(
        self,
        *,
        role_catalog_path: str | Path,
        admission_policy_path: str | Path,
        governance_policy_path: str | Path,
    ):
        self.role_catalog = RoleCatalog.from_config(role_catalog_path)
        self.registry = ModelRegistry(self.role_catalog, admission_policy_path)
        self.governance_policy = json.loads(Path(governance_policy_path).read_text(encoding="utf-8"))

    def load_seed_records(self, path: str | Path) -> list[ModelAdmissionRecord]:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return [ModelAdmissionRecord.from_dict(record) for record in data.get("records", [])]

    def audit(
        self,
        records: list[ModelAdmissionRecord],
        *,
        replacement_ledger: ModelReplacementLedger | None = None,
    ) -> ModelGovernanceReport:
        blockers: list[str] = []
        warnings: list[str] = []
        for role in self.governance_policy.get("required_model_roles", []):
            if role not in self.role_catalog.roles:
                blockers.append(f"missing_required_role:{role}")

        registered_records: list[dict[str, Any]] = []
        production_count = 0
        for record in records:
            issues = self.registry.register(record)
            if issues:
                blockers.extend(
                    f"model_admission_invalid:{record.model_id}:{issue.field}:{issue.reason}"
                    for issue in issues
                )
            else:
                if record.admission_status == "admitted_for_production":
                    production_count += 1
                registered_records.append(record.as_dict())

            forbidden_cert_tasks = sorted(set(record.allowed_tasks).intersection(CERTIFICATION_TASKS))
            if forbidden_cert_tasks:
                blockers.append(
                    f"model_attempts_legal_certification:{record.model_id}:{','.join(forbidden_cert_tasks)}"
                )
            if record.role == "maine_final_generator" and record.admission_status == "admitted_for_production":
                warnings.append("generator_admitted_for_production_requires_heightened_human_review")

        ledger = replacement_ledger or ModelReplacementLedger()
        if not ledger.events:
            ledger.append(
                old_model_id=None,
                new_model_id=records[0].model_id if records else "none",
                role=records[0].role if records else "none",
                reason="initial_governance_baseline",
                evidence={"record_count": len(records), "policy_version": self.governance_policy.get("version")},
            )
        if not ledger.verify():
            blockers.append("model_replacement_ledger_invalid")

        required_cert_tasks = set(self.governance_policy.get("certification_tasks_reserved_to_system_gates", []))
        if required_cert_tasks != CERTIFICATION_TASKS:
            blockers.append("certification_task_policy_mismatch")

        status = "pass" if not blockers else "fail"
        return ModelGovernanceReport(
            status=status,
            blockers=blockers,
            warnings=warnings,
            role_count=len(self.role_catalog.roles),
            admitted_record_count=len(registered_records),
            production_record_count=production_count,
            certification_tasks_reserved_to_system_gates=sorted(CERTIFICATION_TASKS),
            registry_records=registered_records,
            replacement_ledger=ledger.as_dict(),
        )
