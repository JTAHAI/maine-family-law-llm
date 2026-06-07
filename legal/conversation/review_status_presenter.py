from __future__ import annotations

from typing import Any


class ReviewStatusPresenter:
    def present(self, response: dict[str, Any]) -> dict[str, Any]:
        review_required = bool(response.get("review_required", True))
        filing_ready_status = str(response.get("filing_ready_status") or "blocked_from_filing_ready")
        blockers = list(response.get("filing_ready_blockers") or (["review_required"] if review_required else []))
        return {
            "review_required": review_required,
            "review_label": "Review required" if review_required else "Review gate passed",
            "filing_ready_status": filing_ready_status,
            "filing_ready_label": "Blocked from filing-ready use" if filing_ready_status != "filing_ready_passed" else "Filing-ready gate passed",
            "blockers": blockers,
        }
