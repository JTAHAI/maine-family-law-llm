"""Small JSON index for local fixture retrieval."""

from __future__ import annotations

import json
from pathlib import Path

from .chunk import Chunk


def build_index(chunks: list[Chunk]) -> dict[str, object]:
    return {
        "schema": "maine_family_law_llm.index.v1",
        "chunk_count": len(chunks),
        "chunks": [chunk.to_dict() for chunk in chunks],
    }


def save_index(path: str | Path, chunks: list[Chunk]) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build_index(chunks), indent=2) + "\n", encoding="utf-8")
    return out


def load_index(path: str | Path) -> list[dict[str, object]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return list(payload.get("chunks", []))
