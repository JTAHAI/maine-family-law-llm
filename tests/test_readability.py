from legal.conversation import ReadabilityAuditor


def test_readability_auditor_is_deterministic() -> None:
    auditor = ReadabilityAuditor()
    text = "This is a short sentence. This is another short sentence."
    first = auditor.audit(text).as_dict()
    second = auditor.audit(text).as_dict()
    assert first == second
    assert first["sentence_count"] == 2
