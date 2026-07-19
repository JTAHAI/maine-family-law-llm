"""Citation-first answer pipeline for the Maine Family Law LLM MVP."""

from .models import (
    AnswerRequest,
    AnswerResult,
    INSUFFICIENT_SOURCE_RESPONSE,
    RetrievedContext,
    SourceSnippet,
)
from .pipeline import CitationFirstAnswerPipeline
from .retrieval import InMemoryCorpusRetriever, load_plaintext_corpus

__all__ = [
    "AnswerRequest",
    "AnswerResult",
    "CitationFirstAnswerPipeline",
    "INSUFFICIENT_SOURCE_RESPONSE",
    "InMemoryCorpusRetriever",
    "RetrievedContext",
    "SourceSnippet",
    "load_plaintext_corpus",
]
