"""Strict, model-empty fleet plan validation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FAST_INTERCHANGE_CAPABILITIES = frozenset(
    {
        "intake_triage",
        "evidence_review",
        "authority_review",
        "drafting",
        "parenting_plan_review",
        "financial_disclosure_review",
        "safety_privacy_review",
    }
)


class FleetError(ValueError):
    """Raised when a fleet plan would overstate or weaken its boundary."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


@dataclass(frozen=True)
class FastInterchangeFleet:
    schema: str
    status: str
    slots: tuple[dict[str, Any], ...]
    fingerprint: str

    @classmethod
    def load(cls, path: str | Path) -> FastInterchangeFleet:
        try:
            value = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FleetError("fast_interchange_fleet_invalid") from exc
        return cls.from_dict(value)

    @classmethod
    def from_dict(cls, value: Any) -> FastInterchangeFleet:
        if (
            not isinstance(value, dict)
            or value.get("schema") != "maine-family-law-llm.fast-interchange-fleet.v1"
        ):
            raise FleetError("fast_interchange_fleet_schema_invalid")
        if (
            value.get("promotion_authority") is not False
            or value.get("external_worker_required") is not True
        ):
            raise FleetError("fast_interchange_fleet_policy_invalid")
        base = value.get("shared_base")
        if (
            not isinstance(base, dict)
            or base.get("shared_kv_cache") is not False
            or base.get("remote_downloads") is not False
        ):
            raise FleetError("fast_interchange_shared_base_policy_invalid")
        slots = value.get("model_slots")
        if not isinstance(slots, list) or len(slots) != len(FAST_INTERCHANGE_CAPABILITIES):
            raise FleetError("fast_interchange_slot_count_invalid")
        ids: set[str] = set()
        capabilities: set[str] = set()
        normalized: list[dict[str, Any]] = []
        for slot in slots:
            if not isinstance(slot, dict):
                raise FleetError("fast_interchange_slot_invalid")
            slot_id = str(slot.get("slot_id") or "")
            capability = str(slot.get("capability") or "")
            if (
                not slot_id
                or slot_id in ids
                or capability not in FAST_INTERCHANGE_CAPABILITIES
                or capability in capabilities
            ):
                raise FleetError("fast_interchange_slot_identity_invalid")
            if (
                slot.get("adapter_kind") != "lora"
                or slot.get("release_state") != "specified_untrained"
            ):
                raise FleetError("fast_interchange_slot_release_state_invalid")
            if int(slot.get("lora_rank") or 0) < 1:
                raise FleetError("fast_interchange_slot_rank_invalid")
            ids.add(slot_id)
            capabilities.add(capability)
            normalized.append(
                {
                    "slot_id": slot_id,
                    "capability": capability,
                    "adapter_kind": "lora",
                    "release_state": "specified_untrained",
                    "lora_rank": int(slot["lora_rank"]),
                }
            )
        if capabilities != FAST_INTERCHANGE_CAPABILITIES:
            raise FleetError("fast_interchange_capability_set_invalid")
        return cls(
            schema=str(value["schema"]),
            status=str(value.get("status") or ""),
            slots=tuple(sorted(normalized, key=lambda item: item["slot_id"])),
            fingerprint=hashlib.sha256(_canonical(value)).hexdigest(),
        )
