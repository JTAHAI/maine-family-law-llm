"""Bind hash-verified answer provenance to review-required drafts."""

from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any

_HASH_RE = re.compile(r"^[a-f0-9]{64}$")
_RECEIPT_KEYS = (
    "schema_version",
    "run_id",
    "question_sha256",
    "context_manifest_sha256",
    "exact_context_sha256",
    "answer_sha256",
    "provider_id",
    "model_id",
    "endpoint_class",
    "status",
    "citation_refs",
    "tool_receipt_hashes",
    "retrieval_diagnostics_sha256",
    "created_at",
)


def _canonical(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def validate_provenance_receipt(receipt: dict[str, Any] | None) -> dict[str, Any]:
    if not receipt:
        return {
            "status": "not_supplied",
            "verified": False,
            "review_required": True,
            "receipt": None,
            "blockers": ["generation_provenance_not_supplied"],
        }
    safe = {key: receipt.get(key) for key in _RECEIPT_KEYS}
    safe["receipt_sha256"] = str(receipt.get("receipt_sha256") or "").lower()
    blockers: list[str] = []
    for key in (
        "question_sha256",
        "context_manifest_sha256",
        "exact_context_sha256",
        "answer_sha256",
        "retrieval_diagnostics_sha256",
        "receipt_sha256",
    ):
        if not _HASH_RE.fullmatch(str(safe.get(key) or "")):
            blockers.append(f"invalid_provenance_hash:{key}")
    expected = sha256(_canonical({key: safe.get(key) for key in _RECEIPT_KEYS})).hexdigest()
    if _HASH_RE.fullmatch(safe["receipt_sha256"]) and expected != safe["receipt_sha256"]:
        blockers.append("provenance_receipt_hash_mismatch")
    if str(safe.get("status") or "").lower() in {"filing_ready", "verified_legal_correctness"}:
        blockers.append("model_provenance_may_not_certify_legal_validity")
    return {
        "schema_version": "draft_generation_provenance_v1",
        "status": "verified" if not blockers else "invalid",
        "verified": not blockers,
        "review_required": True,
        "receipt": safe,
        "blockers": blockers,
        "source_role": "analytical_work_product_not_authority_or_evidence",
    }
