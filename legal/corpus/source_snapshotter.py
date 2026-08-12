from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from legal.connectors.base import RetrievedSource
from legal.corpus.source_normalizer import slugify


@dataclass(frozen=True)
class SourceSnapshot:
    source_id: str
    raw_path: Path
    metadata_path: Path
    sha256: str
    previous_sha256: str = ""


class SourceSnapshotter:
    """Write raw official authority snapshots outside the source repository."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)

    def write(self, retrieved: RetrievedSource, *, source_id: str) -> SourceSnapshot:
        digest = retrieved.sha256
        target_dir = self.base_dir / slugify(source_id) / digest[:2]
        target_dir.mkdir(parents=True, exist_ok=True)
        latest_path = self.base_dir / slugify(source_id) / "latest.json"
        previous_sha256 = ""
        if latest_path.is_file():
            try:
                latest_payload = json.loads(latest_path.read_text(encoding="utf-8"))
                previous_sha256 = str(latest_payload.get("sha256") or "")
            except Exception:
                previous_sha256 = ""

        suffix = ".pdf" if "pdf" in retrieved.target.expected_content_type else ".html"
        raw_path = target_dir / f"{digest}{suffix}"
        metadata_path = target_dir / f"{digest}.json"
        raw_path.write_bytes(retrieved.content)
        metadata = {
            "source_id": source_id,
            "target_id": retrieved.target.target_id,
            "url": retrieved.target.url,
            "final_url": retrieved.final_url,
            "status_code": retrieved.status_code,
            "content_type": retrieved.content_type,
            "retrieved_at": retrieved.retrieved_at.isoformat(),
            "sha256": digest,
            "parser_name": retrieved.target.parser_name,
            "byte_count": len(retrieved.content),
            "previous_sha256": previous_sha256 or None,
            "fetch_metadata": retrieved.fetch_metadata,
        }
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
        latest_path.write_text(
            json.dumps(
                {
                    "source_id": source_id,
                    "sha256": digest,
                    "previous_sha256": previous_sha256 or None,
                    "snapshot_path": str(raw_path),
                    "metadata_path": str(metadata_path),
                    "retrieved_at": retrieved.retrieved_at.isoformat(),
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return SourceSnapshot(
            source_id=source_id,
            raw_path=raw_path,
            metadata_path=metadata_path,
            sha256=digest,
            previous_sha256=previous_sha256,
        )

    def write_manifest(self, records: list[dict[str, Any]], *, filename: str = "source_manifest.json") -> Path:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        path = self.base_dir / filename
        path.write_text(json.dumps(records, indent=2, sort_keys=True), encoding="utf-8")
        return path
