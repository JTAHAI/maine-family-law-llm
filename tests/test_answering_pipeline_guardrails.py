from __future__ import annotations

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
