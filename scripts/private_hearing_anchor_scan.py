"""Create a private, metadata-only candidate index for a hearing order anchor.

The source corpus and output must be an explicitly chosen private workspace.
This helper never uploads data or writes document text, excerpts, prompts, or
model inputs.  It records only source-local identifiers, file hashes, parser
state, and keyword/date flags for human review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ORDER_DATE = re.compile(r"(?:2026[-_. ]?02[-_. ]?11|02[-_. ]?11[-_. ]?2026|02112026)", re.I)
KEYWORDS = (
    "order",
    "judgment",
    "decree",
    "ordered",
    "shall",
    "must",
    "effective",
    "compliance",
    "enforcement",
    "contempt",
)
SUPPORTED = {".pdf", ".docx", ".txt", ".html", ".htm", ".eml"}


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def bounded_text(path: Path) -> tuple[str, str]:
    """Extract at most a bounded local diagnostic text string; never persist it."""
    suffix = path.suffix.casefold()
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(path, strict=False)
        return "pdf", "\n".join((page.extract_text() or "") for page in reader.pages[:12])[:120_000]
    if suffix == ".docx":
        from docx import Document

        return "docx", "\n".join(item.text for item in Document(path).paragraphs)[:120_000]
    data = path.read_bytes()[:1_000_000]
    return suffix.lstrip("."), data.decode("utf-8", errors="replace")[:120_000]


def private_candidate(path: Path, corpus: Path, record: dict[str, Any]) -> dict[str, Any]:
    relative = path.relative_to(corpus).as_posix()
    result: dict[str, Any] = {
        "private_record_id": record["private_record_id"],
        "source_relative_path": relative,
        "file_type": path.suffix.casefold(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "review_required": True,
        "legal_conclusion": False,
        "content_persisted": False,
        "date_name_match": bool(ORDER_DATE.search(path.name)),
    }
    try:
        parser, text = bounded_text(path)
        folded = text.casefold()
        result.update(
            parser=parser,
            parser_status="parsed" if text.strip() else "no_extractable_text",
            extracted_character_count=len(text),
            feb_11_2026_text_match=bool(
                re.search(r"(?:february\s+11,?\s+2026|02/11/2026|2026-02-11)", folded)
            ),
            keyword_hits={term: folded.count(term) for term in KEYWORDS if term in folded},
        )
    except Exception as exc:  # A bad private document is a review item, not a crash.
        result.update(
            parser="unavailable",
            parser_status=f"{type(exc).__name__}",
            extracted_character_count=0,
            feb_11_2026_text_match=False,
            keyword_hits={},
        )
    result["order_anchor_score"] = (
        int(result["date_name_match"])
        + 3 * int(result["feb_11_2026_text_match"])
        + min(4, len(result["keyword_hits"]))
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--anchor-index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    corpus = args.corpus_root.resolve(strict=True)
    output = args.output.resolve()
    if not output.is_relative_to(corpus):
        raise ValueError("private_anchor_output_must_stay_inside_private_corpus")
    index = json.loads(args.anchor_index.read_text(encoding="utf-8"))
    if index.get("content_read") is not False or not isinstance(index.get("candidates"), list):
        raise ValueError("private_anchor_index_invalid")
    selected = []
    for item in index["candidates"]:
        if not isinstance(item, dict) or item.get("file_type") not in SUPPORTED:
            continue
        relative = item.get("source_relative_path")
        if not isinstance(relative, str) or not ORDER_DATE.search(relative):
            continue
        candidate = (corpus / relative).resolve()
        if not candidate.is_relative_to(corpus) or not candidate.is_file() or candidate.is_symlink():
            continue
        selected.append(private_candidate(candidate, corpus, item))
    result = {
        "schema": "mfl.private-hearing-order-anchor-scan.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "corpus_root": str(corpus),
        "content_persisted": False,
        "legal_conclusions": False,
        "review_required": True,
        "candidate_count": len(selected),
        "candidates": sorted(selected, key=lambda item: (-item["order_anchor_score"], item["private_record_id"])),
    }
    pending = output.with_suffix(output.suffix + ".pending")
    pending.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    pending.replace(output)
    print(json.dumps({"candidate_count": len(selected), "content_persisted": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
