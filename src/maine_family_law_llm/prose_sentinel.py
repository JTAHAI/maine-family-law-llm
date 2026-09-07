"""Local ProSe-SENTINEL compatibility boundary for model-training review.

This module deliberately does not train or run a model.  It creates a
deterministic, source-anchor-only admission packet that a separate local model
workflow can require before it accepts family-law source cards.  The packet
never contains source text, does not persist anything, and cannot file, serve,
sign, or otherwise execute an external or case action.
"""

from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Iterable


SENTINEL_NAME = "ProSe-SENTINEL AI"
SENTINEL_ADAPTER_VERSION = "1.0.0"
SENTINEL_CONTRACT_VERSION = "family-law-training-admission-v1"
PUBLIC_EDITION_VERSION = "9.0.0"
MAX_SOURCE_CARDS = 32
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}$")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _text(value: Any, *, limit: int = 20_000) -> str:
    return str(value or "").replace("\x00", "")[:limit]


def _safe_identifier(value: Any, *, fallback: str) -> str:
    candidate = _text(value, limit=96).strip()
    return candidate if _SAFE_IDENTIFIER.fullmatch(candidate) else fallback


def sentinel_status() -> dict[str, Any]:
    """Return the fixed local boundary offered to model-training workflows."""

    return {
        "service": SENTINEL_NAME,
        "adapter_version": SENTINEL_ADAPTER_VERSION,
        "contract_version": SENTINEL_CONTRACT_VERSION,
        "public_edition_version": PUBLIC_EDITION_VERSION,
        "status": "available_review_required",
        "local_only": True,
        "source_anchored": True,
        "human_review_required": True,
        "model_training_execution": False,
        "canonical_writeback": False,
        "external_execution": False,
        "stores_source_text": False,
        "boundaries": [
            "Creates only a local source-anchor admission packet.",
            "Never trains, runs, files, serves, signs, or submits anything.",
            "Human review remains required before a separate model workflow uses source context.",
        ],
    }


def _anchor_source_cards(cards: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    anchors: list[dict[str, Any]] = []
    blockers: list[str] = []
    for index, raw in enumerate(cards, start=1):
        if len(anchors) >= MAX_SOURCE_CARDS:
            blockers.append("source_card_limit_reached")
            break
        if not isinstance(raw, dict):
            blockers.append("invalid_source_card_omitted")
            continue
        metadata = raw.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        source_id = _safe_identifier(
            raw.get("source_id") or raw.get("evidence_id") or metadata.get("source_id") or metadata.get("id"),
            fallback=f"source-{index}",
        )
        lane = _text(metadata.get("source_lane") or "legal_authority", limit=48).strip().lower()
        if lane not in {"legal_authority", "private_record"}:
            lane = "legal_authority"
            blockers.append("source_lane_normalized")
        source_text = _text(
            raw.get("snippet")
            or raw.get("text")
            or metadata.get("text_excerpt")
            or metadata.get("matched_text")
        )
        if not source_text.strip():
            blockers.append("empty_source_card_omitted")
            continue
        instruction_like = bool(metadata.get("instruction_like_text_detected"))
        if instruction_like:
            blockers.append("instruction_like_source_requires_human_review")
        anchors.append(
            {
                "source_id": source_id,
                "source_lane": lane,
                "source_sha256": sha256(source_text.encode("utf-8")).hexdigest(),
                "source_class": _text(metadata.get("source_class") or metadata.get("source_type"), limit=80).strip(),
                "authority_status": _text(metadata.get("authority_status"), limit=80).strip(),
                "freshness_status": _text(metadata.get("freshness_status") or metadata.get("freshness"), limit=80).strip(),
                "instruction_like_text_detected": instruction_like,
            }
        )
    return anchors, sorted(set(blockers))


def prepare_training_admission(*, model_id: str, source_cards: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Create a non-executing, source-anchor-only training admission packet.

    A separate model manager may inspect this packet, but this layer does not
    approve a model run or retain caller/source content.
    """

    normalized_model_id = _safe_identifier(model_id, fallback="")
    if not normalized_model_id:
        raise ValueError("invalid_model_id")
    anchors, blockers = _anchor_source_cards(source_cards)
    if not anchors:
        blockers = sorted(set([*blockers, "no_source_anchors_available"]))
    packet = {
        "service": SENTINEL_NAME,
        "adapter_version": SENTINEL_ADAPTER_VERSION,
        "contract_version": SENTINEL_CONTRACT_VERSION,
        "model_id": normalized_model_id,
        "admission_status": "review_required" if anchors else "blocked",
        "human_review_required": True,
        "model_training_execution": False,
        "canonical_writeback": False,
        "external_execution": False,
        "source_anchor_count": len(anchors),
        "source_anchors": anchors,
        "blockers": blockers,
        "next_step": (
            "A human reviewer must inspect the source anchors and separately authorize any local model workflow."
            if anchors
            else "Provide reviewable source cards before a separate local model workflow can consider admission."
        ),
    }
    packet["packet_sha256"] = sha256(_canonical_json(packet)).hexdigest()
    return packet
