from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_loaded_legal = sys.modules.get("legal")
if _loaded_legal is not None:
    loaded_path = str(getattr(_loaded_legal, "__file__", "") or "")
    if "\\tests\\legal\\" in loaded_path or "/tests/legal/" in loaded_path:
        del sys.modules["legal"]

from legal.answering import (
    AnswerRequest,
    CitationFirstAnswerPipeline,
    InMemoryCorpusRetriever,
    load_plaintext_corpus,
)
from legal.answering.ollama_adapter import OllamaGenerationClient


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ask the local Maine Family Law LLM MVP with citation-first guardrails."
    )
    parser.add_argument("question", help="Question to ask")
    parser.add_argument(
        "--corpus",
        default="corpus",
        help="Folder containing local .txt/.md source material",
    )
    parser.add_argument(
        "--model",
        default="qwen2.5-coder:7b",
        help="Ollama model name",
    )
    parser.add_argument(
        "--max-sources",
        type=int,
        default=5,
        help="Maximum number of source snippets to retrieve",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of human-readable text",
    )
    parser.add_argument(
        "--no-ollama",
        action="store_true",
        help="Use retrieval-only response without calling Ollama",
    )
    args = parser.parse_args()

    snippets = load_plaintext_corpus(Path(args.corpus))
    retriever = InMemoryCorpusRetriever(snippets)
    generator = None if args.no_ollama else OllamaGenerationClient(model_name=args.model)

    pipeline = CitationFirstAnswerPipeline(retriever=retriever, generator=generator)
    result = pipeline.answer(
        AnswerRequest(question=args.question, max_sources=max(1, args.max_sources))
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    else:
        print(result.answer)
        if result.citations:
            print("\nCitations:")
            for index, citation in enumerate(result.citations, start=1):
                print(f"[{index}] {citation.citation_label()}")

        if result.warning:
            print(f"\nWarning: {result.warning}", file=sys.stderr)

    return 0 if result.grounded else 2


if __name__ == "__main__":
    raise SystemExit(main())
