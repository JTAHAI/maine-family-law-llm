"""Tenant-scoped verification of local governance audit chains and signatures."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from legal.governance.legal_hold import LegalHoldStore
from legal.governance.retention_policy_engine import RetentionPolicyEngine
from legal.governance.signed_policy_pack_lifecycle import SignedPolicyPackStore
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path

_MAX_STATE_BYTES = 1024 * 1024
_MAX_RECEIPTS = 160


class AuditVerificationError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else _canonical(value)).hexdigest()


def _root() -> Path:
    default = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "MaineFamilyLawLLM" / "audit-verification"
    return Path(os.environ.get("MFL_AUDIT_VERIFICATION_ROOT") or default).resolve()


def _verify_chain(events: Any) -> dict[str, Any]:
    if not isinstance(events, list):
        return {"status": "blocked", "event_count": 0, "gaps": ["audit_events_invalid"], "clock_anomalies": [], "chain_head": ""}
    gaps: list[str] = []; clock_anomalies: list[str] = []; previous = ""; last_time: datetime | None = None
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            gaps.append(f"audit_event_invalid:{index}"); continue
        actual = str(event.get("event_hash") or "")
        basis = {key: value for key, value in event.items() if key != "event_hash"}
        if actual != _digest(basis): gaps.append(f"audit_hash_invalid:{index}")
        if str(event.get("previous_hash") or "") != previous: gaps.append(f"audit_chain_gap:{index}")
        recorded = str(event.get("recorded_at") or "")
        try:
            current = datetime.fromisoformat(recorded.replace("Z", "+00:00"))
            if last_time is not None and current < last_time: clock_anomalies.append(f"audit_clock_regression:{index}")
            last_time = current
        except ValueError:
            clock_anomalies.append(f"audit_clock_invalid:{index}")
        previous = actual
    return {"status": "pass" if not gaps and not clock_anomalies else "blocked", "event_count": len(events), "gaps": gaps, "clock_anomalies": clock_anomalies, "chain_head": previous}


class AuditVerificationConsole:
    def __init__(self, root: str | Path | None = None, *, encryption_key: str | None = None) -> None:
        self.root = Path(root or _root()).resolve()
        self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")

    def _path(self, tenant_id: str) -> Path:
        return self.root / f"{_digest(tenant_id)[:32]}.json.enc"

    def _load_receipts(self, path: Path) -> dict[str, Any]:
        if not path.exists(): return {"schema_version": "audit_verification_receipts_v1", "tenant_id": "", "receipts": [], "audit": []}
        try: state = self.encryptor.decrypt_json(strict_json_load_path(path, max_bytes=_MAX_STATE_BYTES, require_object=True))
        except Exception as exc: raise AuditVerificationError("audit_verification_receipt_store_unavailable") from exc
        if not isinstance(state, dict) or state.get("schema_version") != "audit_verification_receipts_v1": raise AuditVerificationError("audit_verification_receipt_store_unavailable")
        return state

    def _load_store(self, store: Any, tenant_id: str) -> dict[str, Any]:
        try: return store._load(store._path(tenant_id))
        except Exception as exc: raise AuditVerificationError("audit_verification_source_unavailable") from exc

    def verify(self, *, tenant_id: str, matter_scope: str) -> dict[str, Any]:
        holds = self._load_store(LegalHoldStore(), tenant_id)
        retention = self._load_store(RetentionPolicyEngine(), tenant_id)
        packs = self._load_store(SignedPolicyPackStore(), tenant_id)
        chains = {"legal_holds": _verify_chain(holds.get("audit")), "retention_plans": _verify_chain(retention.get("audit")), "signed_policy_packs": _verify_chain(packs.get("audit"))}
        signatures = []
        for pack in dict(packs.get("packs") or {}).values():
            if not isinstance(pack, dict): continue
            signature = dict(pack.get("signature") or {})
            signatures.append({"pack_id": str(pack.get("pack_id") or "")[:80], "signature_status": str(signature.get("status") or "unverified"), "key_id": str(signature.get("key_id") or "")[:100], "blockers": list(signature.get("blockers") or [])[:20]})
        current_matter_holds = [record for record in dict(holds.get("holds") or {}).values() if isinstance(record, dict) and record.get("matter_scope") == matter_scope]
        current_matter_plans = [record for record in dict(retention.get("plans") or {}).values() if isinstance(record, dict) and record.get("matter_scope") == matter_scope]
        blockers = [f"audit_chain:{name}" for name, chain in chains.items() if chain["status"] != "pass"]
        blockers.extend(f"policy_pack_signature:{row['pack_id']}" for row in signatures if row["signature_status"] != "verified")
        return {"schema_version": "audit_verification_console_v1", "status": "review_required" if not blockers else "blocked", "tenant_scope": tenant_id, "matter_scope": matter_scope, "chains": chains, "signature_verification": signatures, "scope_summary": {"legal_hold_count": len(current_matter_holds), "retention_plan_count": len(current_matter_plans), "private_record_content_included": False}, "blockers": sorted(set(blockers)), "source_drill_down": {"audit_chain_heads": {name: chain["chain_head"] for name, chain in chains.items()}, "signature_count": len(signatures), "review_required": True}, "private_record_content_included": False, "paths_disclosed": False, "network_used": False, "review_required": True, "notice": "This verifies local hash-chain structure and recorded policy-pack signature state. It is not an external signed audit opinion or a release approval."}

    def export_scope_report(self, report: dict[str, Any], *, tenant_id: str) -> dict[str, Any]:
        if report.get("tenant_scope") != tenant_id or report.get("private_record_content_included") is not False:
            raise AuditVerificationError("audit_verification_scope_invalid")
        path = self._path(tenant_id)
        with exclusive_file_lock(path.with_suffix(path.suffix + ".lock")):
            state = self._load_receipts(path)
            if state.get("tenant_id") and state["tenant_id"] != tenant_id: raise AuditVerificationError("audit_verification_tenant_mismatch")
            previous = str((state.get("audit") or [{}])[-1].get("event_hash") or "")
            report_hash = _digest(report); basis = {"event_type": "audit_scope_report_exported", "tenant_id": tenant_id, "report_hash": report_hash, "previous_hash": previous}
            event = {**basis, "event_hash": _digest(basis)}
            receipt = {"receipt_id": f"audit_export_{event['event_hash'][:24]}", "report_hash": report_hash, "status": report.get("status"), "review_required": True}
            state["tenant_id"] = tenant_id; state["receipts"] = [*list(state.get("receipts") or []), receipt][-_MAX_RECEIPTS:]; state["audit"] = [*list(state.get("audit") or []), event][-_MAX_RECEIPTS:]
            path.parent.mkdir(parents=True, exist_ok=True); atomic_write_bytes(path, _canonical(self.encryptor.encrypt_json(state)), mode=0o600)
        return {"scoped_report": report, "export_receipt": receipt, "audit_chain_head": event["event_hash"], "exported_to_network": False, "review_required": True}


__all__ = ["AuditVerificationConsole", "AuditVerificationError"]
