"""Citation-first answer pipeline.

The pipeline refuses to answer when no source snippets are available. This keeps
the MVP grounded while ingestion, retrieval, and official-source verification
continue to mature.
"""

from __future__ import annotations

from .models import (
    AnswerRequest,
    AnswerResult,
    INSUFFICIENT_SOURCE_RESPONSE,
    SourceSnippet,
)
from .ollama_adapter import GenerationClient
from .retrieval import InMemoryCorpusRetriever


class CitationFirstAnswerPipeline:
    """Answer questions only from retrieved source snippets."""

    def __init__(
        self,
        retriever: InMemoryCorpusRetriever,
        generator: GenerationClient | None = None,
    ) -> None:
        self._retriever = retriever
        self._generator = generator

    def answer(self, request: AnswerRequest) -> AnswerResult:
        snippets = tuple(
            self._retriever.search(request.question, limit=request.max_sources)
        )

        if not snippets:
            return AnswerResult(
                answer=INSUFFICIENT_SOURCE_RESPONSE,
                citations=(),
                grounded=False,
                used_model=None,
                warning="insufficient_source_material",
            )

        prompt = self._build_prompt(request, snippets)

        if self._generator is None:
            generated = (
                "I found source material that may be relevant. Review the cited "
                "snippets before relying on the answer."
            )
            used_model = None
        else:
            generated = self._generator.generate(prompt)
            used_model = self._generator.model_name

        answer = self._append_disclaimer(generated)
        return AnswerResult(
            answer=answer,
            citations=snippets,
            grounded=True,
            used_model=used_model,
            warning=None,
        )

    def _build_prompt(
        self,
        request: AnswerRequest,
        snippets: tuple[SourceSnippet, ...],
    ) -> str:
        sources = "\n\n".join(
            f"[{index}] {snippet.citation_label()}\n{snippet.text}"
            for index, snippet in enumerate(snippets, start=1)
        )
        matter = request.matter_type or "unspecified"

        return f"""You are an informational Maine family-law research assistant.

Rules:
- Use only the source snippets below.
- Do not invent law, citations, facts, deadlines, or holdings.
- Do not provide legal advice.
- If the snippets do not support the answer, say the source material is insufficient.
- Cite snippets by bracket number.

Jurisdiction: {request.jurisdiction}
Matter type: {matter}
Question: {request.question}

Source snippets:
{sources}

Answer:
"""

    @staticmethod
    def _append_disclaimer(text: str) -> str:
        cleaned = text.strip()
        disclaimer = (
            "This is general legal information, not legal advice. "
            "Consult a qualified Maine attorney for advice about a specific case."
        )
        if not cleaned:
            return disclaimer
        if disclaimer.lower() in cleaned.lower():
            return cleaned
        return f"{cleaned}\n\n{disclaimer}"
