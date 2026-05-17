"""Small local retrieval utilities for the Maine Family Law LLM MVP."""

from __future__ import annotations

from pathlib import Path
import re

from .models import SourceSnippet


_TOKEN_RE = re.compile(r"[a-zA-Z0-9_']+")


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(text) if len(token) > 2}


class InMemoryCorpusRetriever:
    """Simple deterministic retriever for local MVP and tests.

    This is intentionally dependency-free. It gives the product a safe local
    retrieval seam while heavier vector or hybrid retrieval can plug in later.
    """

    def __init__(self, snippets: list[SourceSnippet] | tuple[SourceSnippet, ...]):
        self._snippets = tuple(snippets)

    def search(self, query: str, *, limit: int = 5) -> list[SourceSnippet]:
        query_tokens = _tokens(query)
        if not query_tokens:
            return []

        scored: list[tuple[int, int, SourceSnippet]] = []
        for index, snippet in enumerate(self._snippets):
            haystack = f"{snippet.title} {snippet.text}"
            score = len(query_tokens.intersection(_tokens(haystack)))
            if score > 0:
                scored.append((score, -index, snippet))

        scored.sort(reverse=True)
        return [snippet for _, _, snippet in scored[:limit]]


def load_plaintext_corpus(root: str | Path) -> list[SourceSnippet]:
    """Load .txt/.md files as source snippets from a local corpus folder.

    The loader does not claim the files are authoritative. Upstream ingestion
    should still label official source status and provenance.
    """

    root_path = Path(root)
    if not root_path.exists():
        return []

    snippets: list[SourceSnippet] = []
    for path in sorted(root_path.rglob("*")):
        if path.suffix.lower() not in {".txt", ".md"} or not path.is_file():
            continue

        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            continue

        rel = path.relative_to(root_path).as_posix()
        snippets.append(
            SourceSnippet(
                source_id=rel,
                title=path.stem.replace("_", " ").replace("-", " ").strip() or rel,
                text=text,
                path=str(path),
                locator="local plaintext corpus",
            )
        )

    return snippets
