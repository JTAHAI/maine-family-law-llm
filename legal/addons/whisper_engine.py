"""Pinned, offline whisper.cpp runtime adapter.

The desktop package carries a CPU-only whisper.cpp executable and compact
English model under ``store/whisper``.  Runtime code never downloads engines or
models.  A build-cache copy is admitted for source-tree QA only after the same
hash checks used for the packaged payload pass.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from legal.security.durable_io import read_bounded_regular_file
from legal.security.strict_json import strict_json_load_path


WHISPER_CPP_VERSION = "1.9.2"
WHISPER_CLI_SHA256 = "95e3c0b0e778ad9499eb0125f97c1dcf437dd9eb4ea77050b043574f93c2631d"
WHISPER_MODEL_NAME = "ggml-tiny.en-q5_1.bin"
WHISPER_MODEL_SHA256 = "c77c5766f1cef09b6b7d47f21b546cbddd4157886b3b5d6d4f709e91e66c7c2b"
MAX_ENGINE_BINARY_BYTES = 64 * 1024 * 1024
MAX_MODEL_BYTES = 256 * 1024 * 1024


class WhisperEngineError(RuntimeError):
    """A safe, non-private native-engine failure."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class WhisperEngine:
    root: Path
    executable: Path
    model: Path
    executable_sha256: str
    model_sha256: str
    version: str = WHISPER_CPP_VERSION


def _sha256_file(path: Path, *, max_bytes: int) -> str:
    return hashlib.sha256(read_bounded_regular_file(path, max_bytes=max_bytes)).hexdigest()


def _runtime_candidates() -> list[Path]:
    candidates: list[Path] = []
    explicit = os.environ.get("MFL_WHISPER_BUNDLE_ROOT", "").strip()
    if explicit:
        candidates.append(Path(explicit))
    executable_root = Path(sys.executable).resolve().parent
    candidates.append(executable_root / "store" / "whisper")
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        cache = (
            Path(local_app_data)
            / "MaineFamilyLawLLM"
            / "build-cache"
            / "whisper-cpp"
            / f"v{WHISPER_CPP_VERSION}"
        )
        candidates.extend((cache / "runtime", cache))
    unique: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in unique:
            unique.append(resolved)
    return unique


def _paths_for_root(root: Path) -> tuple[Path, Path]:
    direct_cli = root / "whisper-cli.exe"
    nested_cli = root / "bin" / "Release" / "whisper-cli.exe"
    executable = direct_cli if direct_cli.is_file() else nested_cli
    direct_model = root / WHISPER_MODEL_NAME
    nested_model = root.parent / WHISPER_MODEL_NAME if root.name == "runtime" else direct_model
    model = direct_model if direct_model.is_file() else nested_model
    return executable, model


def discover_whisper_engine() -> WhisperEngine | None:
    """Return the first hash-admitted local engine, or ``None``."""

    if os.environ.get("MFL_WHISPER_DISABLE_BUILTIN", "").strip() == "1":
        return None
    for root in _runtime_candidates():
        executable, model = _paths_for_root(root)
        if not executable.is_file() or not model.is_file():
            continue
        if executable.is_symlink() or model.is_symlink():
            continue
        try:
            executable_hash = _sha256_file(executable, max_bytes=MAX_ENGINE_BINARY_BYTES)
            model_hash = _sha256_file(model, max_bytes=MAX_MODEL_BYTES)
        except (OSError, ValueError):
            continue
        if executable_hash != WHISPER_CLI_SHA256 or model_hash != WHISPER_MODEL_SHA256:
            continue
        return WhisperEngine(
            root=executable.parent,
            executable=executable,
            model=model,
            executable_sha256=executable_hash,
            model_sha256=model_hash,
        )
    return None


def _normalize_result(payload: dict[str, Any]) -> tuple[str, list[dict[str, Any]], str]:
    raw_segments = payload.get("transcription")
    if not isinstance(raw_segments, list):
        raise WhisperEngineError("whisper_output_invalid")
    segments: list[dict[str, Any]] = []
    text_parts: list[str] = []
    for index, raw in enumerate(raw_segments[:20_000]):
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text") or "").strip()
        offsets = raw.get("offsets") if isinstance(raw.get("offsets"), dict) else {}
        timestamps = raw.get("timestamps") if isinstance(raw.get("timestamps"), dict) else {}
        if text:
            text_parts.append(text)
        segments.append(
            {
                "segment": index,
                "start_ms": max(0, int(offsets.get("from") or 0)),
                "end_ms": max(0, int(offsets.get("to") or 0)),
                "start": str(timestamps.get("from") or ""),
                "end": str(timestamps.get("to") or ""),
                "text": text,
            }
        )
    transcript = " ".join(text_parts).strip()
    if not transcript:
        raise WhisperEngineError("whisper_transcript_empty")
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    return transcript, segments, str(result.get("language") or "unknown")[:20]


def transcribe_with_whisper(
    engine: WhisperEngine,
    source: Path,
    *,
    work_root: Path,
    timeout_seconds: int = 900,
) -> dict[str, Any]:
    """Run the admitted engine and return normalized source-bound output."""

    work_root.mkdir(parents=True, exist_ok=True)
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with tempfile.TemporaryDirectory(prefix="whisper-", dir=work_root) as temporary:
        output_prefix = Path(temporary) / "transcript"
        command = [
            str(engine.executable),
            "-m",
            str(engine.model),
            "-f",
            str(source),
            "-l",
            "en",
            "-oj",
            "-of",
            str(output_prefix),
            "-nt",
            "-np",
        ]
        env = dict(os.environ)
        env.update(
            {
                "HTTP_PROXY": "",
                "HTTPS_PROXY": "",
                "ALL_PROXY": "",
                "NO_PROXY": "*",
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
            }
        )
        try:
            completed = subprocess.run(
                command,
                cwd=str(engine.root),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=max(30, min(timeout_seconds, 3600)),
                check=False,
                creationflags=creationflags,
            )
        except subprocess.TimeoutExpired as exc:
            raise WhisperEngineError("whisper_engine_timeout") from exc
        except OSError as exc:
            raise WhisperEngineError("whisper_engine_launch_failed") from exc
        output_path = output_prefix.with_suffix(".json")
        if completed.returncode != 0 or not output_path.is_file():
            raise WhisperEngineError("whisper_engine_failed")
        raw = strict_json_load_path(output_path, max_bytes=16 * 1024 * 1024, require_object=True)
        transcript, segments, language = _normalize_result(raw)
    return {
        "text": transcript,
        "segments": segments,
        "language": language,
        "engine": "whisper.cpp",
        "engine_version": engine.version,
        "engine_executable_sha256": engine.executable_sha256,
        "model_name": engine.model.name,
        "model_sha256": engine.model_sha256,
    }


__all__ = [
    "WHISPER_CLI_SHA256",
    "WHISPER_CPP_VERSION",
    "WHISPER_MODEL_NAME",
    "WHISPER_MODEL_SHA256",
    "WhisperEngine",
    "WhisperEngineError",
    "discover_whisper_engine",
    "transcribe_with_whisper",
]
