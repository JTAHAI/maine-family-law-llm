from legal.conversation.draft_review_checklist import DraftReviewChecklistBuilder


def test_draft_review_checklist_covers_core_review_gates() -> None:
    rows = DraftReviewChecklistBuilder().build(draft_type="motion_to_modify", blockers=["missing_required_facts"])
    checks = {row["check"] for row in rows}
    assert {"facts", "authority", "citations", "quotes", "filing_ready"}.issubset(checks)
    assert all(row["status"] == "blocked" for row in rows)
