from legal.conversation import OutputRenderer


def test_output_renderer_keeps_blockers_visible() -> None:
    renderer = OutputRenderer()
    payload = {
        "short_answer": "Review required.",
        "plain_language_explanation": "Review required.",
        "source_scope_status": "source_unknown_freshness",
        "source_freshness_status": "source_unknown_freshness",
        "filing_ready_blockers": ["review_required", "citation_unverified"],
        "review_required": True,
        "issue_labels": ["divorce"],
        "task_type": "query",
        "procedural_posture": "initial_complaint",
        "warnings": [],
        "limitations": ["Filing-ready use is blocked."],
    }
    rendered = renderer.render(payload, "why_not_filing_ready_report")
    assert rendered["visible_blockers"] == ["review_required", "citation_unverified"]


def test_output_renderer_declares_required_renderer_set() -> None:
    renderer = OutputRenderer()
    assert "attorney_research_memo" in renderer.required_renderers()
