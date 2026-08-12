"""Bridge source cards and host answers into local-agent contracts."""

from __future__ import annotations

from hashlib import sha256
from typing import Any, Iterable

from legal.agent_runtime import ContextManifestBuilder, ContextSource, ProvenanceReceipt
from legal.agent_runtime.contracts import canonical_json, sha256_text, utc_now

MAX_BRIDGE_SOURCE_TEXT = 20_000


def context_sources_from_cards(cards: Iterable[dict[str, Any]]) -> tuple[ContextSource, ...]:
    sources: list[ContextSource] = []
    for offset, raw in enumerate(cards, start=1):
        if not isinstance(raw, dict):
            continue
        metadata = dict(raw.get("metadata") or {})
        lane = str(metadata.get("source_lane") or "legal_authority").strip().lower()
        if lane not in {"legal_authority", "private_record"}:
            lane = "legal_authority"
        text = str(
            raw.get("snippet")
            or raw.get("text")
            or metadata.get("text_excerpt")
            or metadata.get("matched_text")
            or ""
        ).replace("\x00", "")
        if not text.strip():
            continue
        source_id = str(
            raw.get("source_id")
            or raw.get("evidence_id")
            or metadata.get("source_id")
            or metadata.get("id")
            or f"source-{offset}"
        )
        title = str(raw.get("title") or metadata.get("title") or metadata.get("safe_filename") or source_id)
        locator = str(
            raw.get("locator")
            or metadata.get("source_locator_basename")
            or metadata.get("safe_locator")
            or metadata.get("citation_hint")
            or ""
        ) or None
        sources.append(
            ContextSource(
                source_id=source_id,
                lane=lane,
                title=title,
                text=text[:MAX_BRIDGE_SOURCE_TEXT],
                locator=locator,
                source_class=str(metadata.get("source_class") or metadata.get("source_type") or raw.get("type") or "") or None,
                authority_status=str(metadata.get("authority_status") or "") or None,
                freshness_status=str(metadata.get("freshness_status") or metadata.get("freshness") or "") or None,
                instruction_like_text_detected=bool(metadata.get("instruction_like_text_detected")),
            )
        )
    return tuple(sources)


def empty_context_manifest(*, question: str, run_id: str) -> dict[str, Any]:
    created_at = utc_now()
    base = {
        "schema_version": "local_agent_context_manifest_v1",
        "run_id": run_id,
        "question_sha256": sha256_text(question),
        "created_at": created_at,
        "entries": [],
        "total_chars": 0,
        "lane_counts": {},
        "exact_context_sha256": sha256(canonical_json([])).hexdigest(),
        "truncated": False,
        "warnings": ["no_source_context_available"],
    }
    base["manifest_sha256"] = sha256(canonical_json(base)).hexdigest()
    return {
        **base,
        "entry_count": 0,
        "review_required": True,
        "transmission_scope": "loopback_local_model_only",
    }


def build_host_context_and_receipt(
    *,
    question: str,
    answer: str,
    cards: Iterable[dict[str, Any]],
    run_id: str,
    retrieval_diagnostics: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    sources = context_sources_from_cards(cards)
    if not sources:
        manifest_payload = empty_context_manifest(question=question, run_id=run_id)
        receipt_base = {
            "schema_version": "local_agent_provenance_receipt_v1",
            "run_id": run_id,
            "question_sha256": sha256_text(question),
            "context_manifest_sha256": manifest_payload["manifest_sha256"],
            "exact_context_sha256": manifest_payload["exact_context_sha256"],
            "answer_sha256": sha256_text(answer),
            "provider_id": "deterministic_host",
            "model_id": "no_model",
            "endpoint_class": "no_network",
            "status": "host_answer_review_required",
            "citation_refs": [],
            "tool_receipt_hashes": [],
            "retrieval_diagnostics_sha256": sha256(canonical_json(retrieval_diagnostics or {})).hexdigest(),
            "created_at": utc_now(),
        }
        receipt_base["receipt_sha256"] = sha256(canonical_json(receipt_base)).hexdigest()
        return manifest_payload, {
            **receipt_base,
            "review_required": True,
            "legal_authority": False,
            "evidence": False,
        }

    manifest, _ = ContextManifestBuilder().build(question=question, sources=sources, run_id=run_id)
    receipt = ProvenanceReceipt.create(
        run_id=run_id,
        question=question,
        manifest=manifest,
        answer=answer,
        provider_id="deterministic_host",
        model_id="no_model",
        endpoint_class="no_network",
        status="host_answer_review_required",
        retrieval_diagnostics=retrieval_diagnostics,
    )
    return manifest.to_dict(), receipt.to_dict()


def source_cards_from_payload(cards: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return only fields needed for a local-agent preview request."""
    safe: list[dict[str, Any]] = []
    for raw in cards:
        if not isinstance(raw, dict):
            continue
        metadata = dict(raw.get("metadata") or {})
        safe.append(
            {
                "source_id": raw.get("source_id") or raw.get("evidence_id") or metadata.get("source_id") or metadata.get("id"),
                "title": raw.get("title") or metadata.get("title") or metadata.get("safe_filename"),
                "snippet": raw.get("snippet") or raw.get("text") or metadata.get("text_excerpt") or metadata.get("matched_text"),
                "locator": raw.get("locator") or metadata.get("source_locator_basename") or metadata.get("safe_locator") or metadata.get("citation_hint"),
                "metadata": {
                    "source_lane": metadata.get("source_lane"),
                    "source_class": metadata.get("source_class") or metadata.get("source_type"),
                    "authority_status": metadata.get("authority_status"),
                    "freshness_status": metadata.get("freshness_status") or metadata.get("freshness"),
                    "instruction_like_text_detected": bool(metadata.get("instruction_like_text_detected")),
                },
            }
        )
    return safe
