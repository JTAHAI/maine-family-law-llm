from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class KeyRotationEvent:
    key_id: str
    action: str
    actor: str
    reason: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, str]:
        return {
            "key_id": self.key_id,
            "action": self.action,
            "actor": self.actor,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


class KeyRotationLedger:
    """Hash-chained key-rotation ledger for deployment evidence."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []
        self._chain_head = "0" * 64

    def append(self, *, key_id: str, action: str, actor: str, reason: str) -> dict[str, Any]:
        record = KeyRotationEvent(key_id=key_id, action=action, actor=actor, reason=reason).as_dict()
        record["previous_hash"] = self._chain_head
        record_hash = sha256(json.dumps(record, sort_keys=True).encode("utf-8")).hexdigest()
        record["event_hash"] = record_hash
        self._chain_head = record_hash
        self._events.append(record)
        return dict(record)

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_count": len(self._events),
            "chain_head": self._chain_head,
            "verified": self.verify_chain(),
            "events": [dict(event) for event in self._events],
        }

    def verify_chain(self) -> bool:
        head = "0" * 64
        for event in self._events:
            expected = dict(event)
            event_hash = expected.pop("event_hash")
            if expected.get("previous_hash") != head:
                return False
            head = sha256(json.dumps(expected, sort_keys=True).encode("utf-8")).hexdigest()
            if head != event_hash:
                return False
        return True


@dataclass(frozen=True)
class ExportEvent:
    export_id: str
    user_id: str
    tenant_id: str
    matter_id: str
    export_status: str
    verifier_status: str
    filing_ready_gate_hash: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, str]:
        return {
            "export_id": self.export_id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "matter_id": self.matter_id,
            "export_status": self.export_status,
            "verifier_status": self.verifier_status,
            "filing_ready_gate_hash": self.filing_ready_gate_hash,
            "timestamp": self.timestamp,
        }


class ImmutableExportLog:
    """Append-only export log where failed gates cannot be silently converted to pass."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []
        self._chain_head = "0" * 64

    def append(self, event: ExportEvent) -> dict[str, Any]:
        if event.export_status == "filing_ready" and event.verifier_status != "pass":
            raise ValueError("filing_ready export requires verifier_status=pass")
        record = event.as_dict()
        record["previous_hash"] = self._chain_head
        record_hash = sha256(json.dumps(record, sort_keys=True).encode("utf-8")).hexdigest()
        record["event_hash"] = record_hash
        self._chain_head = record_hash
        self._events.append(record)
        return dict(record)

    def verify_chain(self) -> bool:
        head = "0" * 64
        for event in self._events:
            expected = dict(event)
            event_hash = expected.pop("event_hash")
            if expected.get("previous_hash") != head:
                return False
            head = sha256(json.dumps(expected, sort_keys=True).encode("utf-8")).hexdigest()
            if head != event_hash:
                return False
        return True

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_count": len(self._events),
            "verified": self.verify_chain(),
            "chain_head": self._chain_head,
            "events": [dict(event) for event in self._events],
        }


@dataclass(frozen=True)
class AnswerProvenanceRecord:
    user_id: str
    tenant_id: str
    matter_id: str
    source_id: str
    model_id: str
    prompt_hash: str
    retrieved_context_hash: str
    output_hash: str
    verifier_status: str
    export_status: str
    route: str = "/api/query"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, str]:
        return {
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "matter_id": self.matter_id,
            "source_id": self.source_id,
            "model_id": self.model_id,
            "prompt_hash": self.prompt_hash,
            "retrieved_context_hash": self.retrieved_context_hash,
            "output_hash": self.output_hash,
            "verifier_status": self.verifier_status,
            "export_status": self.export_status,
            "route": self.route,
            "timestamp": self.timestamp,
        }


class AnswerProvenanceTrail:
    REQUIRED_FIELDS = {
        "user_id",
        "tenant_id",
        "matter_id",
        "source_id",
        "model_id",
        "prompt_hash",
        "retrieved_context_hash",
        "output_hash",
        "verifier_status",
        "export_status",
    }

    @staticmethod
    def hash_text(text: str) -> str:
        return sha256(text.encode("utf-8")).hexdigest()

    def build_record(
        self,
        *,
        user_id: str,
        tenant_id: str,
        matter_id: str,
        source_id: str,
        model_id: str,
        prompt: str,
        retrieved_context: str,
        output: str,
        verifier_status: str,
        export_status: str,
    ) -> AnswerProvenanceRecord:
        return AnswerProvenanceRecord(
            user_id=user_id,
            tenant_id=tenant_id,
            matter_id=matter_id,
            source_id=source_id,
            model_id=model_id,
            prompt_hash=self.hash_text(prompt),
            retrieved_context_hash=self.hash_text(retrieved_context),
            output_hash=self.hash_text(output),
            verifier_status=verifier_status,
            export_status=export_status,
        )

    def explain(self, record: AnswerProvenanceRecord | dict[str, Any]) -> dict[str, Any]:
        payload = record.as_dict() if isinstance(record, AnswerProvenanceRecord) else dict(record)
        missing = sorted(self.REQUIRED_FIELDS - set(payload))
        return {
            "status": "pass" if not missing else "fail",
            "missing_fields": missing,
            "admin_explanation_available": not missing,
            "explanation": {
                "who": payload.get("user_id"),
                "tenant": payload.get("tenant_id"),
                "matter": payload.get("matter_id"),
                "source": payload.get("source_id"),
                "model": payload.get("model_id"),
                "prompt_hash": payload.get("prompt_hash"),
                "retrieved_context_hash": payload.get("retrieved_context_hash"),
                "output_hash": payload.get("output_hash"),
                "verifier_status": payload.get("verifier_status"),
                "export_status": payload.get("export_status"),
            },
        }


class SecurityImplementationAuditor:
    def __init__(self, policy_path: str | Path):
        self.policy_path = Path(policy_path)
        self.policy = json.loads(self.policy_path.read_text(encoding="utf-8"))

    def audit(
        self,
        *,
        implemented_controls: set[str] | None = None,
        provenance_record: AnswerProvenanceRecord | dict[str, Any] | None = None,
        key_rotation_ledger: KeyRotationLedger | None = None,
        export_log: ImmutableExportLog | None = None,
    ) -> dict[str, Any]:
        configured_controls = self.policy.get("required_controls", {})
        implemented_controls = implemented_controls or {
            name for name, spec in configured_controls.items() if spec.get("status") in {"implemented", "policy_required"}
        }
        missing = sorted(set(configured_controls) - implemented_controls)
        control_results = []
        for name, spec in sorted(configured_controls.items()):
            control_results.append(
                {
                    "control": name,
                    "status": "pass" if name in implemented_controls else "missing",
                    "configured_status": spec.get("status"),
                    "evidence": list(spec.get("evidence", [])),
                    "blocks_release_if_missing": bool(spec.get("blocks_release_if_missing", True)),
                }
            )

        provenance = AnswerProvenanceTrail().explain(provenance_record or {})
        key_rotation = key_rotation_ledger.as_dict() if key_rotation_ledger else {"verified": False, "event_count": 0}
        exports = export_log.as_dict() if export_log else {"verified": False, "event_count": 0}
        blockers = []
        if missing:
            blockers.extend(f"missing_security_control:{control}" for control in missing)
        if provenance["status"] != "pass":
            blockers.append("audit_trail_missing_required_answer_fields")
        if not key_rotation.get("verified") or key_rotation.get("event_count", 0) < 1:
            blockers.append("key_rotation_ledger_missing_or_unverified")
        if not exports.get("verified") or exports.get("event_count", 0) < 1:
            blockers.append("immutable_export_log_missing_or_unverified")

        return {
            "status": "pass" if not blockers else "fail",
            "policy_version": self.policy.get("version"),
            "control_results": control_results,
            "missing_controls": missing,
            "audit_trail": provenance,
            "key_rotation_ledger": key_rotation,
            "immutable_export_log": exports,
            "blockers": blockers,
            "readiness": self.policy.get("readiness"),
        }
