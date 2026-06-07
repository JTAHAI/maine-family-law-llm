from legal.conversation.reviewer_feedback import ReviewerFeedbackValidator


def test_reviewer_feedback_does_not_count_without_real_attorney_evidence() -> None:
    feedback = {
        "reviewer_role": "law_student",
        "attorney_licensed_in_maine": False,
        "supervised_by_attorney_faculty": False,
        "reviewed_sources": True,
        "reviewed_citations": True,
        "reviewed_plain_language": True,
        "legal_accuracy_rating": 4,
        "citation_accuracy_rating": 4,
        "usability_rating": 5,
        "safety_concern_rating": 2,
        "blocking_issue": False,
        "comments": "Usability feedback only.",
        "recommended_eval_case": "custody_self_represented",
        "may_count_for_attorney_review": True,
        "evidence_file_path": "",
    }
    result = ReviewerFeedbackValidator().validate(feedback)
    assert result["status"] == "blocked"
    assert result["may_count_for_attorney_review"] is False
    assert result["does_not_mark_ga_complete"] is True
