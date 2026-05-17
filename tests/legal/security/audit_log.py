from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    user_id: str
    tenant_id: str
    matter_id: str | None = None
    source_id: str | None = None
    model_id: str | None = None
    prompt_hash: str | None = None
    output_hash: str | None = None
    verifier_status: str | None = None
    export_status: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "matter_id": self.matter_id,
            "source_id": self.source_id,
            "model_id": self.model_id,
            "prompt_hash": self.prompt_hash,
            "output_hash": self.output_hash,
            "verifier_status": self.verifier_status,
            "export_status": self.export_status,
            "metadata": dict(self.metadata),
            "timestamp": self.timestamp,
        }


class InMemoryAuditLog:
    """Append-only audit sink for tests and local demos.

    Production deployments must replace this with encrypted immutable storage.
    """

    def __init__(self):
        self._events: list[dict[str, Any]] = []
        self._chain_head = "0" * 64

    def append(self, event: AuditEvent) -> dict[str, Any]:
        record = event.as_dict()
        record["previous_hash"] = self._chain_head
        canonical = repr(sorted(record.items())).encode("utf-8")
        record_hash = sha256(canonical).hexdigest()
        record["event_hash"] = record_hash
        self._chain_head = record_hash
        self._events.append(record)
        return record

    def list_events(self) -> list[dict[str, Any]]:
        return [dict(event) for event in self._events]

    def verify_chain(self) -> bool:
        head = "0" * 64
        for event in self._events:
            expected = dict(event)
            event_hash = expected.pop("event_hash")
            previous_hash = expected.get("previous_hash")
            if previous_hash != head:
                return False
            canonical = repr(sorted(expected.items())).encode("utf-8")
            head = sha256(canonical).hexdigest()
            if head != event_hash:
                return False
        return True
