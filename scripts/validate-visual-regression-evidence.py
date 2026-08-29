"""Validate browser-captured visual-regression evidence without decoding private content.

The validator deliberately checks container-level properties only: required capture
names, PNG signature/IHDR dimensions, size, and SHA-256.  It does not OCR or
otherwise inspect a screenshot, so a release operator must still certify that a
capture used fictional data before it is included in a release bundle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path
from typing import Any


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_CAPTURE_BYTES = 50 * 1024 * 1024
MIN_WIDTH = 900
MIN_HEIGHT = 700
REQUIRED_CAPTURES = (
    "01-chat-default.png",
    "02-workbench-default.png",
    "03-chat-compact-960.png",
    "04-recovery-empty.png",
    "05-source-drilldown-compact.png",
    "06-review-blockers-compact.png",
    "07-recovery-error-safe.png",
)


def _png_details(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    status = "pass"
    reasons: list[str] = []
    width = 0
    height = 0
    true_png = False
    if len(payload) < 45 or payload[:8] != PNG_SIGNATURE:
        reasons.append("not_true_png")
    else:
        offset = 8
        chunks: list[tuple[bytes, bytes]] = []
        while offset + 12 <= len(payload):
            length = struct.unpack(">I", payload[offset : offset + 4])[0]
            chunk_end = offset + 12 + length
            if chunk_end > len(payload):
                reasons.append("truncated_png_chunk")
                break
            kind = payload[offset + 4 : offset + 8]
            data = payload[offset + 8 : offset + 8 + length]
            expected_crc = struct.unpack(">I", payload[offset + 8 + length : chunk_end])[0]
            actual_crc = zlib.crc32(kind + data) & 0xFFFFFFFF
            if actual_crc != expected_crc:
                reasons.append("invalid_png_crc")
                break
            chunks.append((kind, data))
            offset = chunk_end
            if kind == b"IEND":
                break
        if offset != len(payload) or not chunks or chunks[0][0] != b"IHDR":
            reasons.append("invalid_png_structure")
        elif len(chunks[0][1]) != 13 or not any(kind == b"IDAT" for kind, _ in chunks) or chunks[-1][0] != b"IEND":
            reasons.append("incomplete_png_structure")
        else:
            width, height = struct.unpack(">II", chunks[0][1][:8])
            true_png = True
    if not true_png:
        status = "fail"
        if "not_true_png" not in reasons:
            reasons.append("not_true_png")
    else:
        if width < MIN_WIDTH or height < MIN_HEIGHT:
            status = "fail"
            reasons.append("below_minimum_capture_dimensions")
    if len(payload) > MAX_CAPTURE_BYTES:
        status = "fail"
        reasons.append("capture_exceeds_50_mb")
    return {
        "name": path.name,
        "status": status,
        "reasons": reasons,
        "true_png": true_png,
        "width": width,
        "height": height,
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def validate_directory(evidence_dir: Path) -> dict[str, Any]:
    captures: list[dict[str, Any]] = []
    for name in REQUIRED_CAPTURES:
        candidate = evidence_dir / name
        if not candidate.is_file():
            captures.append({"name": name, "status": "fail", "reasons": ["required_capture_missing"]})
            continue
        captures.append(_png_details(candidate))
    failures = [capture["name"] for capture in captures if capture["status"] != "pass"]
    return {
        "schema_version": "visual_regression_evidence_v1",
        "evidence_dir": str(evidence_dir),
        "capture_count": len(captures),
        "required_capture_count": len(REQUIRED_CAPTURES),
        "status": "pass" if not failures else "fail",
        "failures": failures,
        "limitations": [
            "Valid PNG encoding and dimensions do not prove visual correctness.",
            "The capture operator must use fictional/no-private-data state.",
            "This validator does not prove dark theme, forced colors, zoom, frozen executable, or MSIX rendering.",
        ],
        "captures": captures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_directory(args.evidence_dir)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
