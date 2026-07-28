#!/usr/bin/env python3
"""Safely extract embedded media from a DOCX for local visual review.

Adapted from the MIT-licensed extract_images.py in
zeweihan/A-market-ecm-lawyer-plugin. This version rejects malformed archives,
limits total extracted bytes and member count, writes only basenames under the
selected output directory, and never executes extracted content.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

_MAX_MEMBERS = 500
_MAX_MEMBER_BYTES = 50 * 1024 * 1024
_MAX_TOTAL_BYTES = 250 * 1024 * 1024
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


class DocxMediaError(ValueError):
    pass


@dataclass(frozen=True)
class ExtractedMedia:
    source_member: str
    output_path: str
    size_bytes: int


def _safe_filename(value: str, index: int) -> str:
    cleaned = _SAFE_NAME_RE.sub("_", Path(value).name).strip("._")
    return cleaned or f"media_{index:04d}.bin"


def extract_media(
    docx_path: Path,
    output_dir: Path | None = None,
    *,
    max_members: int = _MAX_MEMBERS,
    max_member_bytes: int = _MAX_MEMBER_BYTES,
    max_total_bytes: int = _MAX_TOTAL_BYTES,
) -> tuple[ExtractedMedia, ...]:
    source = docx_path.expanduser().resolve(strict=True)
    if source.suffix.lower() != ".docx":
        raise DocxMediaError("input must use the .docx extension")
    if not zipfile.is_zipfile(source):
        raise DocxMediaError("input is not a valid ZIP-based DOCX")
    destination = (
        output_dir.expanduser().resolve()
        if output_dir is not None
        else Path(tempfile.mkdtemp(prefix=f"mfl_docx_media_{source.stem[:40]}_"))
    )
    destination.mkdir(parents=True, exist_ok=True)

    extracted: list[ExtractedMedia] = []
    total = 0
    used_names: set[str] = set()
    with zipfile.ZipFile(source) as archive:
        media = [item for item in archive.infolist() if item.filename.startswith("word/media/")]
        if len(media) > max_members:
            raise DocxMediaError(f"DOCX contains too many media members: {len(media)}")
        for index, item in enumerate(media, start=1):
            if item.is_dir():
                continue
            if item.file_size > max_member_bytes:
                raise DocxMediaError(f"media member exceeds size limit: {item.filename}")
            total += item.file_size
            if total > max_total_bytes:
                raise DocxMediaError("total embedded-media size exceeds limit")
            name = _safe_filename(item.filename, index)
            if name in used_names:
                stem, suffix = os.path.splitext(name)
                name = f"{stem}_{index}{suffix}"
            used_names.add(name)
            target = destination / name
            resolved_parent = target.parent.resolve(strict=True)
            if resolved_parent != destination:
                raise DocxMediaError("output path escaped destination")
            data = archive.read(item)
            if len(data) != item.file_size:
                raise DocxMediaError(f"media size mismatch: {item.filename}")
            target.write_bytes(data)
            extracted.append(
                ExtractedMedia(
                    source_member=item.filename,
                    output_path=str(target),
                    size_bytes=len(data),
                )
            )
    return tuple(extracted)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("docx", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        items = extract_media(args.docx, args.out)
    except (DocxMediaError, OSError, zipfile.BadZipFile) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.as_json:
        import json

        print(json.dumps([asdict(item) for item in items], ensure_ascii=False, indent=2))
    elif not items:
        print("No embedded media found.")
    else:
        print(f"Extracted {len(items)} media item(s) to {Path(items[0].output_path).parent}")
        for item in items:
            print(f"  {item.size_bytes:>10,} bytes  {item.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
