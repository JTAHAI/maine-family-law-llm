"""Matter-local reviewer queue derived from revision-bound review records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from legal.documents.workspace import list_documents
from .review_ledger import list_pending_review_packets, list_review_history

MAX_QUEUE_ITEMS = 500


def build_reviewer_queue(case_root: Path, *, include_completed: bool = False, limit: int = 200) -> dict[str, Any]:
    limit = max(1, min(int(limit or 200), MAX_QUEUE_ITEMS))
    documents = list_documents(case_root, include_deleted=False, limit=MAX_QUEUE_ITEMS)
    items: list[dict[str, Any]] = []
    for document in documents:
        document_id = str(document.get("document_id") or "")
        if not document_id:
            continue
        history = list_review_history(case_root, document_id)
        pending = list_pending_review_packets(case_root, document_id)
        latest = history.get("latest") or {}
        current_revision = str(document.get("current_revision_id") or "")
        latest_revision = str(latest.get("revision_id") or "")
        latest_gate = latest.get("filing_gate") if isinstance(latest.get("filing_gate"), dict) else {}
        blockers = list(latest_gate.get("blockers") or [])
        if pending.get("count"):
            queue_status = "awaiting_reviewer"
        elif latest and latest_revision != current_revision:
            queue_status = "stale_review_after_revision_change"
        elif latest.get("decision") == "request_changes":
            queue_status = "changes_requested"
        elif latest.get("decision") == "reject":
            queue_status = "rejected"
        elif latest_gate.get("filing_ready"):
            queue_status = "filing_gate_passed"
        elif latest.get("decision") == "approve_review":
            queue_status = "review_complete_blocked"
        else:
            queue_status = "needs_review_packet"

        if not include_completed and queue_status == "filing_gate_passed":
            continue
        packet = (pending.get("packets") or [None])[0]
        item = {
            "document_id": document_id,
            "title": str(document.get("title") or "Untitled")[:240],
            "document_type": str(document.get("document_type") or "draft")[:80],
            "current_revision_id": current_revision,
            "queue_status": queue_status,
            "pending_packet_count": int(pending.get("count") or 0),
            "latest_decision": latest.get("decision"),
            "latest_decision_status": latest.get("status"),
            "latest_review_revision_id": latest_revision,
            "filing_ready": bool(latest_gate.get("filing_ready")),
            "blockers": blockers[:100],
            "packet_summary": packet,
            "updated_at": document.get("updated_at") or document.get("created_at"),
            "review_required": not bool(latest_gate.get("filing_ready")),
        }
        items.append(item)

    priority = {
        "awaiting_reviewer": 0,
        "stale_review_after_revision_change": 1,
        "changes_requested": 2,
        "review_complete_blocked": 3,
        "needs_review_packet": 4,
        "rejected": 5,
        "filing_gate_passed": 9,
    }
    items.sort(key=lambda row: (priority.get(str(row["queue_status"]), 8), str(row.get("updated_at") or ""), str(row["document_id"])), reverse=False)
    items = items[:limit]
    counts: dict[str, int] = {}
    for item in items:
        status = str(item["queue_status"])
        counts[status] = counts.get(status, 0) + 1
    return {
        "schema_version": "matter_reviewer_queue_v1",
        "items": items,
        "count": len(items),
        "status_counts": counts,
        "include_completed": bool(include_completed),
        "local_only": True,
        "review_required": True,
    }
