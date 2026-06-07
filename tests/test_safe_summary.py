from legal.conversation.safe_summary import SafeConversationSummarizer
from legal.conversation.session_state import ConversationSessionState


def test_safe_summary_omits_sensitive_detail_and_labels_facts() -> None:
    state = ConversationSessionState(session_id="s1")
    summary = SafeConversationSummarizer().summarize(
        state=state,
        payload={"address": "12 Main Street", "requested_relief": "modify contact schedule"},
    ).as_dict()

    assert summary["omitted_sensitive_detail"] is True
    assert all(row["label"] in {"user_stated", "source_supported", "evidence_supported", "unverified", "contradicted", "unknown"} for row in summary["facts"])
    assert "12 Main" not in summary["summary"]
