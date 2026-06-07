from legal.evals.conversation_eval import ConversationEvalRunner


def test_conversation_eval_runner_passes_and_hard_safety_metrics_hold() -> None:
    report = ConversationEvalRunner().run().as_dict()
    assert report["status"] == "pass"
    assert report["hard_safety_checks"]["review_required_pass"] is True
    assert report["hard_safety_checks"]["filing_ready_gate_pass"] is True
    assert report["hard_safety_checks"]["prompt_injection_resistance"] is True


def test_conversation_eval_contains_prompt_injection_case() -> None:
    report = ConversationEvalRunner().run().as_dict()
    injection = [row for row in report["cases"] if row["case_id"] == "prompt_injection_document"][0]
    assert injection["metrics"]["prompt_injection_resistance"] is True
