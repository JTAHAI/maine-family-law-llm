from __future__ import annotations

import importlib.util
import struct
from pathlib import Path
import zlib


def _load_validator():
    path = Path(__file__).resolve().parents[1] / "scripts" / "validate-visual-regression-evidence.py"
    spec = importlib.util.spec_from_file_location("visual_regression_evidence", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _png(width: int = 960, height: int = 720) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + (b"\x00" * width * 3) for _ in range(height))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def test_visual_regression_validator_requires_true_pngs_and_required_matrix(tmp_path: Path) -> None:
    validator = _load_validator()
    for name in validator.REQUIRED_CAPTURES:
        (tmp_path / name).write_bytes(_png())
    result = validator.validate_directory(tmp_path)
    assert result["status"] == "pass"
    assert result["capture_count"] == len(validator.REQUIRED_CAPTURES)
    assert all(row["true_png"] for row in result["captures"])


def test_visual_regression_validator_fails_closed_for_mislabeled_jpeg(tmp_path: Path) -> None:
    validator = _load_validator()
    for name in validator.REQUIRED_CAPTURES:
        (tmp_path / name).write_bytes(_png())
    (tmp_path / validator.REQUIRED_CAPTURES[0]).write_bytes(b"\xff\xd8\xff\xe0mislabeled-jpeg")
    result = validator.validate_directory(tmp_path)
    assert result["status"] == "fail"
    assert validator.REQUIRED_CAPTURES[0] in result["failures"]
