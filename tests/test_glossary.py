from legal.conversation import Glossary


def test_glossary_contains_required_terms() -> None:
    glossary = Glossary()
    for term in (
        "parental rights and responsibilities",
        "rule 52 findings",
        "review required",
        "unsupported claim",
    ):
        assert glossary.lookup(term)
