from pathlib import Path


def test_v188_packages_required_public_repo_hygiene_files() -> None:
    root = Path(__file__).resolve().parents[1]
    required = [
        ".gitignore",
        ".github/PULL_REQUEST_TEMPLATE.md",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/config.yml",
        ".github/workflows/ci.yml",
    ]
    missing = [path for path in required if not (root / path).is_file()]
    assert missing == []


def test_v188_restores_enterprise_collection_model_modules() -> None:
    from legal.answering.models import AnswerRequest, SourceSnippet
    from legal.documents.models import CourtForm, SourceLocation, StatuteSection
    from legal.matter.models import Matter, MatterDocument
    from legal.retrieval.models import RetrievalDocument, RetrievalResult

    assert AnswerRequest(question="test").jurisdiction == "maine"
    assert SourceSnippet(source_id="s", title="T", text="body").text_preview() == "body"
    assert SourceLocation(source_id="s").validate() == []
    assert StatuteSection(
        document_id="d",
        source_location=SourceLocation(source_id="s"),
        document_type="statute_section",
        title="Title",
    ).source_card().source_id == "s"
    assert CourtForm(
        document_id="f",
        source_location=SourceLocation(source_id="s"),
        document_type="court_form",
        title="Form",
        form_id="FM-001",
    ).form_id == "FM-001"
    assert Matter(matter_id="m").training_allowed is False
    assert MatterDocument.__name__ == "MatterDocument"
    document = RetrievalDocument(source_id="s", document_id="d", title="T", text="body")
    assert RetrievalResult(document=document, score=1.0, method="unit").source_id == "s"
