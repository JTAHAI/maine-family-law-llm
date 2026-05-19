from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT_TEXT = str(_REPO_ROOT)

sys.path = [
    path
    for path in sys.path
    if path and Path(path).resolve() != (_REPO_ROOT / "tests").resolve()
]
if _REPO_ROOT_TEXT not in sys.path:
    sys.path.insert(0, _REPO_ROOT_TEXT)

_loaded_legal = sys.modules.get("legal")
if _loaded_legal is not None:
    loaded_path = str(getattr(_loaded_legal, "__file__", "") or "")
    if "\\tests\\legal\\" in loaded_path or "/tests/legal/" in loaded_path:
        del sys.modules["legal"]

from legal.answering import (
    AnswerRequest,
    CitationFirstAnswerPipeline,
    INSUFFICIENT_SOURCE_RESPONSE,
    InMemoryCorpusRetriever,
    SourceSnippet,
    load_plaintext_corpus,
    RetrievedContext,
)


class FakeGenerator:
    model_name = "fake-local-model"

    def __init__(self) -> None:
        self.prompt = ""

    def generate(self, prompt: str) -> str:
        self.prompt = prompt
        return "Based on [1], the available source discusses parental rights."


def test_pipeline_refuses_without_source_material() -> None:
    pipeline = CitationFirstAnswerPipeline(InMemoryCorpusRetriever([]))

    result = pipeline.answer(AnswerRequest(question="Can I modify parental rights?"))

    assert result.grounded is False
    assert result.citations == ()
    assert result.warning == "insufficient_source_material"
    assert result.answer == INSUFFICIENT_SOURCE_RESPONSE


def test_pipeline_requires_citations_when_sources_exist() -> None:
    snippet = SourceSnippet(
        source_id="sample-source",
        title="Sample non-legal source",
        text="This sample text mentions parental rights and modification.",
        locator="sample locator",
    )
    generator = FakeGenerator()
    pipeline = CitationFirstAnswerPipeline(
        InMemoryCorpusRetriever([snippet]),
        generator=generator,
    )

    result = pipeline.answer(AnswerRequest(question="parental rights modification"))

    assert result.grounded is True
    assert result.used_model == "fake-local-model"
    assert result.citations == (snippet,)
    assert "not legal advice" in result.answer.lower()
    assert "Source snippets:" in generator.prompt
    assert "Do not invent law" in generator.prompt
    assert "[1] Sample non-legal source - sample locator" in generator.prompt


def test_plaintext_corpus_loader_creates_source_snippets(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    sample = corpus / "parental-rights-sample.txt"
    sample.write_text(
        "Sample non-legal text about parental rights and modification.",
        encoding="utf-8",
    )

    snippets = load_plaintext_corpus(corpus)

    assert len(snippets) == 1
    assert snippets[0].source_id == "parental-rights-sample.txt"
    assert snippets[0].title == "parental rights sample"
    assert snippets[0].locator == "local plaintext corpus"
    assert "parental rights" in snippets[0].text


def test_ask_local_cli_returns_grounded_citations_with_local_corpus(
    tmp_path: Path,
) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    sample = corpus / "parental-rights-sample.txt"
    sample.write_text(
        "Sample non-legal source text about parental rights and modification.",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "scripts" / "ask-local.py"),
            "parental rights modification",
            "--corpus",
            str(corpus),
            "--no-ollama",
        ],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "review the cited snippets" in completed.stdout.lower()
    assert "Citations:" in completed.stdout
    assert "[1] parental rights sample - local plaintext corpus" in completed.stdout
    assert completed.stderr == ""


def test_answer_result_serializes_citations_for_cli_json() -> None:
    snippet = SourceSnippet(
        source_id="sample-source",
        title="Sample source",
        text="Sample text",
        locator="sample locator",
    )
    pipeline = CitationFirstAnswerPipeline(InMemoryCorpusRetriever([snippet]))

    result = pipeline.answer(AnswerRequest(question="sample source"))

    payload = result.to_dict()
    assert payload["grounded"] is True
    assert payload["warning"] is None
    assert payload["citations"] == [
        {
            "source_id": "sample-source",
            "title": "Sample source",
            "path": None,
            "locator": "sample locator",
            "text_preview": "Sample text",
            "citation_label": "Sample source - sample locator",
        }
    ]


def test_ask_local_cli_json_refusal_is_machine_readable(tmp_path: Path) -> None:
    corpus = tmp_path / "empty-corpus"
    corpus.mkdir()

    completed = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "scripts" / "ask-local.py"),
            "parental rights modification",
            "--corpus",
            str(corpus),
            "--no-ollama",
            "--json",
        ],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(completed.stdout)

    assert completed.returncode == 2
    assert completed.stderr == ""
    assert payload["grounded"] is False
    assert payload["warning"] == "insufficient_source_material"
    assert payload["citations"] == []
    assert "not have enough cited Maine family-law source material" in payload["answer"]


def test_ask_local_cli_json_success_respects_max_sources(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    first = corpus / "a-parental-rights-sample.txt"
    second = corpus / "b-parental-rights-sample.txt"
    first.write_text(
        "Sample source one mentions parental rights and modification.",
        encoding="utf-8",
    )
    second.write_text(
        "Sample source two mentions parental rights and modification.",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "scripts" / "ask-local.py"),
            "parental rights modification",
            "--corpus",
            str(corpus),
            "--no-ollama",
            "--max-sources",
            "1",
            "--json",
        ],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert payload["grounded"] is True
    assert len(payload["citations"]) == 1
    assert payload["citations"][0]["source_id"] == "a-parental-rights-sample.txt"

class FailingGenerator:
    model_name = "broken-local-model"

    def generate(self, prompt: str) -> str:
        raise TimeoutError("simulated local model timeout")


def test_pipeline_falls_back_to_retrieval_answer_when_generator_fails() -> None:
    snippet = SourceSnippet(
        source_id="sample-source",
        title="Sample source",
        text="Sample text about parental rights modification.",
        locator="sample locator",
    )
    pipeline = CitationFirstAnswerPipeline(
        InMemoryCorpusRetriever([snippet]),
        generator=FailingGenerator(),
    )

    result = pipeline.answer(AnswerRequest(question="parental rights modification"))

    assert result.grounded is True
    assert result.used_model == "broken-local-model"
    assert result.warning == "generation_failed_retrieval_fallback"
    assert result.citations == (snippet,)
    assert "review the cited snippets" in result.answer.lower()
    assert "not legal advice" in result.answer.lower()


def test_ask_local_json_shape_includes_warning_field_for_success(
    tmp_path: Path,
) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    sample = corpus / "parental-rights-sample.txt"
    sample.write_text(
        "Sample source one mentions parental rights and modification.",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "scripts" / "ask-local.py"),
            "parental rights modification",
            "--corpus",
            str(corpus),
            "--no-ollama",
            "--json",
        ],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["grounded"] is True
    assert payload["warning"] is None
    assert payload["used_model"] is None
    assert len(payload["citations"]) == 1

def test_source_snippet_text_preview_is_bounded_for_long_text() -> None:
    long_text = "A" * 400
    snippet = SourceSnippet(
        source_id="sample-source",
        title="Sample source",
        text=long_text,
        locator="sample locator",
    )

    payload = snippet.to_dict()

    assert "text_preview" in payload
    assert len(payload["text_preview"]) <= 160
    assert payload["text_preview"].endswith("...")
    assert payload["text_preview"] != long_text

def test_source_snippet_to_dict_includes_preview_and_citation_label() -> None:
    snippet = SourceSnippet(
        source_id="sample-source",
        title="Sample source",
        text="Sample text for preview",
        locator="sample locator",
    )

    payload = snippet.to_dict()

    assert payload["text_preview"] == "Sample text for preview"
    assert payload["citation_label"] == "Sample source - sample locator"

def test_source_snippet_text_preview_limit_argument_is_honored() -> None:
    snippet = SourceSnippet(
        source_id="sample-source",
        title="Sample source",
        text="alpha beta gamma delta epsilon zeta eta theta",
        locator="sample locator",
    )

    preview = snippet.text_preview(limit=20)

    assert len(preview) <= 20
    assert preview.endswith("...")

def test_retrieved_context_to_dict_serializes_source_snippet_preview() -> None:
    snippet = SourceSnippet(
        source_id="sample-source",
        title="Sample source",
        text="Sample text for preview",
        locator="sample locator",
    )
    context = RetrievedContext(question="sample question", snippets=(snippet,))

    payload = context.to_dict()

    assert payload["question"] == "sample question"
    assert payload["snippets"]
    assert payload["snippets"][0]["text_preview"] == "Sample text for preview"

def test_answer_result_to_dict_includes_source_transparency_metadata() -> None:
    snippet = SourceSnippet(
        source_id="sample-source",
        title="Sample source",
        text="Sample text",
        locator="sample locator",
    )
    pipeline = CitationFirstAnswerPipeline(InMemoryCorpusRetriever([snippet]))

    result = pipeline.answer(AnswerRequest(question="sample source"))
    payload = result.to_dict()

    assert payload["source_count"] == 1
    assert payload["has_source_citations"] is True
    assert payload["citations"][0]["source_id"] == "sample-source"
