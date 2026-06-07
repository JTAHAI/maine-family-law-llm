from legal.conversation import NextQuestionGenerator


def test_next_question_generator_asks_one_safe_question_at_a_time() -> None:
    generator = NextQuestionGenerator()
    result = generator.choose(
        workflow="divorce",
        payload={"county": "York"},
        audience="self_represented",
        text="I need help with divorce in Maine.",
    )
    assert result["severity"] in {"required", "red_flag"}
    assert "one step at a time" in result["question"]
