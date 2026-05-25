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
    REFUSAL_REASON_GENERATOR_FAILED_WITH_RETRIEVAL_FALLBACK,
    REFUSAL_REASON_INSUFFICIENT_SOURCE_MATERIAL,
    REFUSAL_REASON_NO_RELEVANT_SOURCES,
    SourceSnippet,
)
from .ollama_adapter import GenerationClient
from .retrieval import InMemoryCorpusRetriever


GENERATION_FAILED_WARNING = "generation_failed_retrieval_fallback"


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
            has_corpus = getattr(self._retriever, "source_count", 0) > 0
            warning = (
                REFUSAL_REASON_NO_RELEVANT_SOURCES
                if has_corpus
                else REFUSAL_REASON_INSUFFICIENT_SOURCE_MATERIAL
            )
            hint = (
                "No indexed source snippet matched the question. Add or fetch official Maine "
                "family-law sources for this topic, then retry."
                if has_corpus
                else "Add official Maine family-law source material to the local corpus, then retry."
            )
            return AnswerResult(
                answer=INSUFFICIENT_SOURCE_RESPONSE,
                citations=(),
                grounded=False,
                used_model=None,
                warning=warning,
                refusal_reason=warning,
                remediation_hint=hint,
            )

        prompt = self._build_prompt(request, snippets)

        if self._generator is None:
            generated = self._retrieval_only_answer()
            used_model = None
            warning = None
        else:
            used_model = self._generator.model_name
            try:
                generated = self._generator.generate(prompt)
                warning = None
            except Exception:
                generated = self._retrieval_only_answer()
                warning = GENERATION_FAILED_WARNING
                refusal_reason = REFUSAL_REASON_GENERATOR_FAILED_WITH_RETRIEVAL_FALLBACK
                remediation_hint = (
                    "The generator failed, so the response fell back to retrieved snippets only. "
                    "Inspect the local model/runtime before relying on generated prose."
                )
            else:
                refusal_reason = None
                remediation_hint = None
        if self._generator is None:
            refusal_reason = None
            remediation_hint = None

        answer = self._append_disclaimer(generated)
        return AnswerResult(
            answer=answer,
            citations=snippets,
            grounded=True,
            used_model=used_model,
            warning=warning,
            refusal_reason=refusal_reason,
            remediation_hint=remediation_hint,
        )

    @staticmethod
    def _retrieval_only_answer() -> str:
        return (
            "I found source material that may be relevant. Review the cited "
            "snippets before relying on the answer."
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
