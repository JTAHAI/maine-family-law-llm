from __future__ import annotations

import json
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from legal.connectors.base import RetrievedSource
from legal.corpus.source_normalizer import slugify, stable_source_id
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock, read_bounded_regular_file

_MANIFEST_NAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}\.json")
_WINDOWS_DEVICES = {"CON", "PRN", "AUX", "NUL"} | {
    f"{prefix}{number}" for prefix in ("COM", "LPT") for number in range(1, 10)
}


def _check_authority_path(path: Path) -> None:
    for part in (path, *path.parents):
        try:
            metadata = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, "st_file_attributes", 0) & 0x400:
            raise ValueError("authority_snapshot_link_refused")


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
        component = slugify(source_id)
        if component != source_id or component.upper() in _WINDOWS_DEVICES:
            component = stable_source_id("snapshot", source_id)
        source_dir = self.base_dir / component
        lock = source_dir / ".snapshot.lock"
        _check_authority_path(lock)
        with exclusive_file_lock(lock):
            return self._write_snapshot(retrieved, source_id=source_id, source_dir=source_dir)

    def _write_snapshot(self, retrieved: RetrievedSource, *, source_id: str, source_dir: Path) -> SourceSnapshot:
        digest = retrieved.sha256
        target_dir = source_dir / digest[:2]
        latest_path = source_dir / "latest.json"
        _check_authority_path(latest_path)
        previous_sha256 = ""
        if latest_path.is_file():
            latest_payload = json.loads(read_bounded_regular_file(latest_path, max_bytes=64 * 1024))
            if latest_payload.get("source_id") != source_id:
                raise ValueError("authority_snapshot_identity_collision")
            previous_sha256 = str(latest_payload.get("sha256") or "")

        suffix = ".pdf" if "pdf" in retrieved.target.expected_content_type else ".html"
        raw_path = target_dir / f"{digest}{suffix}"
        metadata_path = target_dir / f"{digest}.json"
        _check_authority_path(raw_path)
        _check_authority_path(metadata_path)
        if raw_path.exists():
            if read_bounded_regular_file(raw_path, max_bytes=len(retrieved.content)) != retrieved.content:
                raise ValueError("authority_snapshot_hash_mismatch")
        else:
            atomic_write_bytes(raw_path, retrieved.content)
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
        if not metadata_path.exists():
            self._write_json(metadata_path, metadata)
        self._write_json(latest_path, {
            "source_id": source_id,
            "sha256": digest,
            "previous_sha256": previous_sha256 or None,
            "snapshot_path": str(raw_path),
            "metadata_path": str(metadata_path),
            "retrieved_at": retrieved.retrieved_at.isoformat(),
        })
        return SourceSnapshot(
            source_id=source_id,
            raw_path=raw_path,
            metadata_path=metadata_path,
            sha256=digest,
            previous_sha256=previous_sha256,
        )

    def write_manifest(self, records: list[dict[str, Any]], *, filename: str = "source_manifest.json") -> Path:
        return self.write_json_report(records, filename=filename)

    def write_json_report(self, payload: Any, *, filename: str) -> Path:
        if not _MANIFEST_NAME.fullmatch(filename) or filename.partition(".")[0].upper() in _WINDOWS_DEVICES:
            raise ValueError("authority_manifest_filename_invalid")
        path = self.base_dir / filename
        _check_authority_path(path)
        self._write_json(path, payload)
        return path

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        atomic_write_bytes(path, json.dumps(payload, indent=2, sort_keys=True).encode("utf-8"))
