from __future__ import annotations

import hashlib
import importlib.util
import json
import mimetypes
import os
import re
import secrets
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from difflib import SequenceMatcher
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

from .baseline import extract_baseline_blocks
from .contracts import AdapterStatus
from .privacy import deterministic_privacy_review, merge_privacy_findings
from pypdf import PdfReader
from maine_family_law_llm.local_corpus_index import local_ocr_engine_status

MAX_SOURCE_BYTES = 128 * 1024 * 1024
MAX_TEXT_CHARS = 8_000_000
ALLOWED_ANALYSIS_SUFFIXES = {".pdf", ".docx", ".pptx", ".txt", ".md", ".rtf", ".html", ".htm", ".csv", ".json"}
PRESIDIO_MODEL_NAME = "en_core_web_lg"
DOCLING_ARTIFACTS_RELATIVE_PATHS = (
    ("store", "docling", "models"),
    ("docling", "models"),
)
DOCLING_REQUIRED_MODEL_DIRS = (
    "docling-project--docling-layout-heron",
    "docling-project--docling-models",
    "RapidOcr",
)
_SAFE_LANGUAGE_RE = re.compile(r"^[a-z]{3}(?:\+[a-z]{3}){0,3}$", re.I)


class DocumentIntelligenceError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_text(path: Path, text: str) -> None:
    temporary = path.parent / f".{path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _version(package: str) -> str:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return "not_installed"


def _module_available(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def _bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        # Heavy offline engines are shipped beside the executable rather than
        # inside PyInstaller's ``_internal`` directory.
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _bundled_tesseract_root() -> Path:
    return _bundle_root() / "store" / "tesseract"


def _bundled_docling_artifacts_path() -> Path:
    configured = os.environ.get("MFL_DOCLING_ARTIFACTS_PATH", "").strip()
    if configured:
        return Path(configured).expanduser()
    root = _bundle_root()
    for parts in DOCLING_ARTIFACTS_RELATIVE_PATHS:
        candidate = root.joinpath(*parts)
        if candidate.exists():
            return candidate
    return root.joinpath(*DOCLING_ARTIFACTS_RELATIVE_PATHS[0])


def _bundled_presidio_model_available() -> bool:
    return _module_available(PRESIDIO_MODEL_NAME)


def _bundled_docling_artifacts_available(path: Path) -> bool:
    return path.is_dir() and all((path / name).is_dir() for name in DOCLING_REQUIRED_MODEL_DIRS)


@contextmanager
def _temporary_environment(updates: dict[str, str]):
    sentinel = object()
    previous: dict[str, Any] = {}
    try:
        for key, value in updates.items():
            previous[key] = os.environ.get(key, sentinel)
            os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is sentinel:
                os.environ.pop(key, None)
            else:
                os.environ[key] = str(value)


def _ocr_environment() -> dict[str, str]:
    env = dict(os.environ)
    tesseract_root = _bundled_tesseract_root()
    if tesseract_root.is_dir():
        env["PATH"] = os.pathsep.join(
            part for part in (str(tesseract_root), env.get("PATH", "")) if part
        )
        tessdata = tesseract_root / "tessdata"
        if tessdata.is_dir():
            env["TESSDATA_PREFIX"] = str(tessdata)
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    env["DOCLING_ALLOW_EXTERNAL_PLUGINS"] = "false"
    env["NO_PROXY"] = "*"
    env["no_proxy"] = "*"
    env["HTTP_PROXY"] = ""
    env["HTTPS_PROXY"] = ""
    env["ALL_PROXY"] = ""
    return env


def document_intelligence_status() -> dict[str, Any]:
    bundled_docling_artifacts = _bundled_docling_artifacts_path()
    ocr_engine = local_ocr_engine_status()
    statuses = [
        AdapterStatus(
            adapter_id="deterministic_baseline",
            available=True,
            version="built_in_v1",
            license="project_license",
            mode="in_process_bounded",
            capabilities=("pdf_native_text", "docx_paragraphs", "tables", "stable_blocks"),
            detail="Always available. Produces the fallback structured block report.",
        ),
        AdapterStatus(
            adapter_id="docling",
            available=_module_available("docling") and _bundled_docling_artifacts_available(bundled_docling_artifacts),
            version=_version("docling"),
            license="MIT; individual model licenses must be reviewed separately",
            mode="isolated_subprocess_offline",
            capabilities=("layout", "tables", "reading_order", "structured_blocks"),
            detail=f"Optional. Offline model artifacts expected at {bundled_docling_artifacts}.",
        ),
        AdapterStatus(
            adapter_id="presidio",
            available=_module_available("presidio_analyzer") and _bundled_presidio_model_available(),
            version=_version("presidio-analyzer"),
            license="MIT",
            mode="isolated_subprocess_offline",
            capabilities=("pii_detection", "recognizer_comparison"),
            detail=f"Optional secondary detector. Bundled spaCy model expected: {PRESIDIO_MODEL_NAME}.",
        ),
        AdapterStatus(
            adapter_id="ocrmypdf",
            available=_module_available("ocrmypdf")
            and bool(ocr_engine.get("available"))
            and bool(ocr_engine.get("pdf_ocr_available")),
            version=_version("ocrmypdf"),
            license="MPL-2.0",
            mode="isolated_subprocess_explicit_approval",
            capabilities=("searchable_pdf_copy", "sidecar_text", "deskew", "rotate_pages"),
            detail="Optional. Creates a separate derived PDF and never overwrites the original. Uses the bundled Tesseract tree when available.",
        ),
    ]
    return {
        "schema_version": "document_intelligence_status_v1",
        "status": "ready",
        "local_only": True,
        "network_used": False,
        "automatic_install": False,
        "adapters": [item.as_dict() for item in statuses],
        "review_required": True,
    }


def _safe_input(path: Path, *, case_root: Path) -> Path:
    if not case_root.exists() or case_root.is_symlink():
        raise DocumentIntelligenceError("case_root_invalid", "The active matter root is invalid.", status_code=409)
    resolved_root = case_root.resolve(strict=True)
    if path.is_symlink() or not path.is_file():
        raise DocumentIntelligenceError("document_source_invalid", "The source must be a regular file.", status_code=409)
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise DocumentIntelligenceError("document_source_outside_matter", "The source is outside the active matter.", status_code=409) from exc
    size = resolved.stat().st_size
    if size > MAX_SOURCE_BYTES:
        raise DocumentIntelligenceError("document_source_too_large", f"The source exceeds {MAX_SOURCE_BYTES} bytes.", status_code=413)
    return resolved


def _artifact_root(case_root: Path, source_hash: str) -> Path:
    root = case_root.resolve(strict=True) / "19_DOCUMENT_INTELLIGENCE" / source_hash
    if root.exists() and root.is_symlink():
        raise DocumentIntelligenceError("document_intelligence_output_unsafe", "The document-intelligence output path is unsafe.", status_code=409)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.resolve(strict=True).parent != case_root.resolve(strict=True) / "19_DOCUMENT_INTELLIGENCE":
        raise DocumentIntelligenceError("document_intelligence_output_unsafe", "The document-intelligence output path escaped the matter.", status_code=409)
    return root


def _offline_env() -> dict[str, str]:
    env = dict(os.environ)
    env.update({
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "DOCLING_ALLOW_EXTERNAL_PLUGINS": "false",
        "NO_PROXY": "*",
        "no_proxy": "*",
        "HTTP_PROXY": "",
        "HTTPS_PROXY": "",
        "ALL_PROXY": "",
        "DOCLING_ARTIFACTS_PATH": str(_bundled_docling_artifacts_path()),
    })
    return env


def _run_worker(adapter: str, path: Path, *, timeout: int) -> dict[str, Any]:
    started = time.monotonic()
    worker_output_path: Path | None = None
    if getattr(sys, "frozen", False):
        # A PyInstaller one-file executable is not a Python interpreter, so
        # invoking it with ``-m`` only relaunches the application entry point.
        # Route frozen worker jobs through an explicit internal command that
        # the Store entry point understands.
        with tempfile.NamedTemporaryFile(prefix="mfl-document-worker-", suffix=".json", delete=False) as handle:
            worker_output_path = Path(handle.name)
        command = [
            sys.executable,
            "--document-intelligence-worker",
            adapter,
            str(path),
            "--document-intelligence-output",
            str(worker_output_path),
        ]
    else:
        command = [sys.executable, "-m", "legal.document_intelligence.worker", adapter, str(path)]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            env=_offline_env(),
        )
    except subprocess.TimeoutExpired:
        if worker_output_path is not None:
            worker_output_path.unlink(missing_ok=True)
        return {"status": "timeout", "adapter": adapter, "duration_ms": round((time.monotonic() - started) * 1000), "review_required": True}
    if worker_output_path is not None:
        try:
            stdout = worker_output_path.read_text(encoding="utf-8")[:32 * 1024 * 1024]
        except OSError:
            stdout = ""
        finally:
            worker_output_path.unlink(missing_ok=True)
    else:
        stdout = (completed.stdout or "")[:32 * 1024 * 1024]
    try:
        payload = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError:
        payload = {"status": "failed", "adapter": adapter, "error": "worker_returned_invalid_json"}
    if not isinstance(payload, dict):
        payload = {"status": "failed", "adapter": adapter, "error": "worker_returned_invalid_payload"}
    def sanitize(value: Any) -> Any:
        if isinstance(value, str):
            cleaned = value.replace(str(path), path.name)
            try:
                cleaned = cleaned.replace(str(Path.cwd()), "[APPLICATION_ROOT]")
            except OSError:
                pass
            return cleaned
        if isinstance(value, list):
            return [sanitize(item) for item in value]
        if isinstance(value, dict):
            return {str(key): sanitize(item) for key, item in value.items()}
        return value

    payload = sanitize(payload)
    payload["duration_ms"] = round((time.monotonic() - started) * 1000)
    payload["return_code"] = completed.returncode
    payload["network_used"] = False
    payload["stderr_summary"] = sanitize((completed.stderr or "").strip()[:500])
    payload["review_required"] = True
    return payload


def _normalize_external_blocks(rows: Any, source_hash: str) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return output
    for index, raw in enumerate(rows[:20_000], start=1):
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text") or "")[:20_000]
        if not text.strip():
            continue
        kind = str(raw.get("kind") or "text")[:80]
        digest = hashlib.sha256(f"{source_hash}:{index}:{kind}:{text}".encode("utf-8", errors="replace")).hexdigest()
        row = {
            "block_id": f"blk_{digest[:20]}",
            "kind": kind,
            "text": text,
            "page_number": max(0, int(raw.get("page_number") or 0)),
            "order": index,
            "char_start": max(0, int(raw.get("char_start") or 0)),
            "char_end": max(0, int(raw.get("char_end") or 0)),
            "confidence": raw.get("confidence"),
            "bbox": raw.get("bbox"),
            "metadata": {"extractor": "docling", **(raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {})},
        }
        output.append(row)
    return output


def _source_text(data: bytes, suffix: str, baseline: dict[str, Any]) -> str:
    if suffix in {".txt", ".md", ".rtf", ".html", ".htm", ".csv", ".json"}:
        try:
            return data.decode("utf-8")[:MAX_TEXT_CHARS]
        except UnicodeDecodeError:
            return data.decode("latin-1", errors="replace")[:MAX_TEXT_CHARS]
    return "\n".join(str(row.get("text") or "") for row in baseline.get("blocks") or [])[:MAX_TEXT_CHARS]


def _normalize_for_compare(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _source_block_signature(block: dict[str, Any]) -> str:
    return "|".join(
        [
            str(block.get("kind") or "text"),
            str(int(block.get("page_number") or 0)),
            _normalize_for_compare(block.get("text") or "")[:240],
        ]
    )


def _compare_block_sets(baseline: list[dict[str, Any]], candidate: list[dict[str, Any]]) -> dict[str, Any]:
    baseline_signatures = [_source_block_signature(row) for row in baseline]
    candidate_signatures = [_source_block_signature(row) for row in candidate]
    baseline_set = set(baseline_signatures)
    candidate_set = set(candidate_signatures)
    shared = sorted(baseline_set & candidate_set)
    only_baseline = sorted(baseline_set - candidate_set)
    only_candidate = sorted(candidate_set - baseline_set)
    similarity = SequenceMatcher(None, "\n".join(baseline_signatures), "\n".join(candidate_signatures)).ratio()
    warnings: list[str] = []
    if only_baseline or only_candidate:
        warnings.append("structured_parser_differs_from_baseline")
    if similarity < 0.8 and (baseline_signatures or candidate_signatures):
        warnings.append("structured_parser_text_similarity_low")
    return {
        "schema_version": "document_intelligence_block_comparison_v1",
        "baseline_block_count": len(baseline_signatures),
        "candidate_block_count": len(candidate_signatures),
        "shared_block_count": len(shared),
        "baseline_only_block_count": len(only_baseline),
        "candidate_only_block_count": len(only_candidate),
        "similarity": round(similarity, 6),
        "warnings": warnings,
        "baseline_only_block_ids": [row.get("block_id") for row in baseline if _source_block_signature(row) in only_baseline][:200],
        "candidate_only_block_ids": [row.get("block_id") for row in candidate if _source_block_signature(row) in only_candidate][:200],
    }


def _build_receipt_payload(
    *,
    schema_version: str,
    artifact_type: str,
    source_sha256: str,
    output_sha256: str,
    component_id: str,
    component_version: str,
    component_license: str,
    configuration: dict[str, Any],
    warnings: list[str],
    review_required: bool = True,
    page_block_mapping: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": schema_version,
        "artifact_type": artifact_type,
        "status": "pass",
        "generated_at": _utc_now(),
        "source_sha256": source_sha256,
        "output_sha256": output_sha256,
        "component_id": component_id,
        "component_version": component_version,
        "component_license": component_license,
        "configuration_hash": hashlib.sha256(json.dumps(configuration, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
        "warnings": warnings,
        "review_required": review_required,
    }
    if page_block_mapping is not None:
        base["page_block_mapping"] = page_block_mapping
    if extra:
        base.update(extra)
    base["receipt_sha256"] = hashlib.sha256(json.dumps(base, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
    return base


def _apply_redactions(text: str, findings: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    ordered = sorted(
        [dict(row) for row in findings if isinstance(row, dict)],
        key=lambda row: (int(row.get("start") or 0), int(row.get("end") or 0), str(row.get("entity_type") or "")),
    )
    pieces: list[str] = []
    cursor = 0
    receipts: list[dict[str, Any]] = []
    for row in ordered:
        start = max(0, int(row.get("start") or 0))
        end = max(start, int(row.get("end") or 0))
        if start < cursor:
            continue
        replacement = str(row.get("replacement") or "[REDACTED]")
        pieces.append(text[cursor:start])
        pieces.append(replacement)
        receipts.append(
            {
                "span_start": start,
                "span_end": end,
                "rule": str(row.get("entity_type") or "unknown"),
                "replacement": replacement,
                "recognizer": str(row.get("recognizer") or "deterministic"),
                "score": row.get("score"),
            }
        )
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces), receipts


def _compare_text_views(source_text: str, output_text: str) -> dict[str, Any]:
    source_normalized = _normalize_for_compare(source_text)
    output_normalized = _normalize_for_compare(output_text)
    similarity = SequenceMatcher(None, source_normalized, output_normalized).ratio()
    source_lines = [line.strip() for line in source_text.splitlines() if line.strip()]
    output_lines = [line.strip() for line in output_text.splitlines() if line.strip()]
    source_set = set(source_lines)
    output_set = set(output_lines)
    added = sorted(output_set - source_set)
    removed = sorted(source_set - output_set)
    warnings: list[str] = []
    if source_text and output_text and abs(len(output_text) - len(source_text)) > max(500, len(source_text) * 0.75):
        warnings.append("suspicious_text_delta")
    if similarity < 0.75 and source_text and output_text:
        warnings.append("low_text_similarity")
    return {
        "schema_version": "document_text_comparison_v1",
        "source_text_length": len(source_text),
        "output_text_length": len(output_text),
        "similarity": round(similarity, 6),
        "added_line_count": len(added),
        "removed_line_count": len(removed),
        "added_lines": added[:200],
        "removed_lines": removed[:200],
        "warnings": warnings,
    }


def _immutable_copy(source: Path, target: Path, expected_hash: str) -> None:
    if target.exists():
        if target.is_symlink() or not target.is_file():
            raise DocumentIntelligenceError("derived_artifact_unsafe", "A derived artifact path is unsafe.", status_code=409)
        if _sha256_file(target) != expected_hash:
            raise DocumentIntelligenceError("derived_artifact_collision", "An immutable derived artifact collision was detected.", status_code=409)
        return
    temporary = target.parent / f".{target.name}.{secrets.token_hex(8)}.tmp"
    try:
        with source.open("rb") as incoming, temporary.open("xb") as outgoing:
            for chunk in iter(lambda: incoming.read(1024 * 1024), b""):
                outgoing.write(chunk)
            outgoing.flush()
            os.fsync(outgoing.fileno())
        if _sha256_file(temporary) != expected_hash:
            raise DocumentIntelligenceError("derived_artifact_copy_hash_mismatch", "A derived artifact copy failed verification.", status_code=409)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.parent / f".{path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def analyze_document(
    *,
    case_root: Path,
    source_path: Path,
    source_hash: str | None = None,
    run_docling: bool = True,
    run_presidio: bool = True,
) -> dict[str, Any]:
    source = _safe_input(source_path, case_root=case_root)
    data = source.read_bytes()
    actual_hash = _sha256_bytes(data)
    if source_hash and source_hash.lower() != actual_hash:
        raise DocumentIntelligenceError("document_source_hash_mismatch", "The source hash changed before analysis.", status_code=409)
    suffix = source.suffix.lower()
    if suffix not in ALLOWED_ANALYSIS_SUFFIXES:
        raise DocumentIntelligenceError("document_type_not_supported", "This file type is not supported by the document-intelligence pipeline.", status_code=415)

    baseline = extract_baseline_blocks(data, suffix, actual_hash)
    source_text = _source_text(data, suffix, baseline)
    deterministic = deterministic_privacy_review(source_text)
    status = document_intelligence_status()
    available = {row["adapter_id"]: bool(row["available"]) for row in status["adapters"]}

    docling_result: dict[str, Any] = {"status": "not_requested", "adapter": "docling"}
    if run_docling:
        docling_result = _run_worker("docling", source, timeout=420) if available.get("docling") else {"status": "unavailable", "adapter": "docling", "review_required": True}

    presidio_result: dict[str, Any] = {"status": "not_requested", "adapter": "presidio"}
    if run_presidio and source_text:
        if available.get("presidio"):
            with tempfile.TemporaryDirectory(prefix="mfl-presidio-") as temporary:
                text_path = Path(temporary) / "document.txt"
                text_path.write_text(source_text, encoding="utf-8")
                presidio_result = _run_worker("presidio", text_path, timeout=180)
        else:
            presidio_result = {"status": "unavailable", "adapter": "presidio", "review_required": True}

    privacy = merge_privacy_findings(deterministic, presidio_result)
    docling_blocks = _normalize_external_blocks(docling_result.get("blocks"), actual_hash)
    selected_blocks = docling_blocks if docling_result.get("status") == "pass" and docling_blocks else baseline.get("blocks")
    selected_extractor = "docling" if selected_blocks is docling_blocks else "deterministic_baseline"
    comparison = _compare_block_sets(list(baseline.get("blocks") or []), docling_blocks) if docling_blocks else {
        "schema_version": "document_intelligence_block_comparison_v1",
        "baseline_block_count": len(baseline.get("blocks") or []),
        "candidate_block_count": 0,
        "shared_block_count": 0,
        "baseline_only_block_count": len(baseline.get("blocks") or []),
        "candidate_only_block_count": 0,
        "similarity": 0.0,
        "warnings": ["docling_not_used"],
        "baseline_only_block_ids": [row.get("block_id") for row in baseline.get("blocks") or []][:200],
        "candidate_only_block_ids": [],
    }
    selection_reason = (
        "docling_passed_integrity_checks_and_was_selected"
        if selected_extractor == "docling"
        else "deterministic_baseline_selected_because_docling_was_unavailable_or_failed"
    )
    page_count = int(baseline.get("page_count") or 0)
    block_page_mapping = [
        {
            "block_id": row.get("block_id"),
            "page_number": int(row.get("page_number") or 0),
            "kind": row.get("kind"),
            "char_start": int(row.get("char_start") or 0),
            "char_end": int(row.get("char_end") or 0),
        }
        for row in list(selected_blocks or [])[:20_000]
    ]
    parser_history = [
        {
            "component_id": "deterministic_baseline",
            "component_version": "built_in_v1",
            "component_license": "project_license",
            "status": baseline.get("status"),
            "warnings": list(baseline.get("warnings") or []),
            "review_required": True,
        }
    ]
    if docling_result:
        parser_history.append(
            {
                "component_id": "docling",
                "component_version": str(docling_result.get("version") or "unknown"),
                "component_license": "MIT; individual model licenses must be reviewed separately",
                "status": docling_result.get("status"),
                "warnings": list(docling_result.get("warnings") or []),
                "review_required": True,
            }
        )
    integrity = {
        "schema_version": "document_record_integrity_v1",
        "record_id": actual_hash[:24],
        "matter_id": case_root.name,
        "safe_display_name": source.name[:240],
        "media_type": mimetypes.guess_type(source.name)[0] or "application/octet-stream",
        "original_byte_size": len(data),
        "page_count": page_count,
        "original_sha256": actual_hash,
        "import_timestamp": _utc_now(),
        "parser_status": baseline.get("status"),
        "ocr_status": "not_run",
        "text_availability_status": "available" if source_text else "unavailable",
        "confidentiality_labels": sorted({row.get("entity_type") for row in deterministic.get("findings") or [] if row.get("entity_type")}),
        "duplicate_group_id": actual_hash,
        "exact_duplicate": False,
        "near_duplicate_candidates": [],
        "source_classification": "document",
        "retention_status": "preserve_original",
        "immutable_original": True,
        "audit_history": [
            {
                "event_type": "document_imported",
                "timestamp": _utc_now(),
                "source_sha256": actual_hash,
            },
            {
                "event_type": "analysis_completed",
                "timestamp": _utc_now(),
                "selected_extractor": selected_extractor,
            },
        ],
    }
    report: dict[str, Any] = {
        "schema_version": "maine_document_intelligence_report_v1",
        "status": "review_required",
        "generated_at": _utc_now(),
        "local_only": True,
        "network_used": False,
        "integrity": integrity,
        "source": {
            "filename": source.name[:240],
            "extension": suffix,
            "size_bytes": len(data),
            "sha256": actual_hash,
            "original_modified": False,
        },
        "selected_extractor": selected_extractor,
        "selection_reason": selection_reason,
        "structured_document": {
            "block_count": len(selected_blocks or []),
            "blocks": list(selected_blocks or [])[:20_000],
            "baseline": {key: value for key, value in baseline.items() if key != "blocks"},
            "docling": {key: value for key, value in docling_result.items() if key not in {"blocks", "markdown_preview"}},
            "comparison": comparison,
            "selection_reason": selection_reason,
            "page_block_mapping": block_page_mapping,
        },
        "privacy_review": privacy,
        "provenance": {
            "schema_version": "document_provenance_v1",
            "source_sha256": actual_hash,
            "derived_artifacts": [],
            "parser_history": parser_history,
            "ocr_history": [],
            "block_selection_reason": selection_reason,
        },
        "adapter_status": status,
        "warnings": [
            "Document structure and privacy findings are review aids, not proof of authenticity, completeness, or legal significance.",
            "Optional model-backed parsers can make mistakes and cannot change application policy.",
        ],
        "review_required": True,
    }
    receipt_material = json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    report["receipt_sha256"] = hashlib.sha256(receipt_material).hexdigest()
    root = _artifact_root(case_root, actual_hash)
    report_path = root / f"analysis-{report['receipt_sha256'][:24]}.json"
    if report_path.exists() and (report_path.is_symlink() or not report_path.is_file()):
        raise DocumentIntelligenceError("analysis_artifact_unsafe", "The analysis artifact path is unsafe.", status_code=409)
    if not report_path.exists():
        _atomic_json(report_path, report)
    return {
        **report,
        "artifact": {
            "relative_path": report_path.relative_to(case_root.resolve(strict=True)).as_posix(),
            "sha256": _sha256_file(report_path),
            "size_bytes": report_path.stat().st_size,
            "artifact_type": "analysis_report",
            "receipt_relative_path": report_path.relative_to(case_root.resolve(strict=True)).as_posix(),
            "receipt_sha256": _sha256_file(report_path),
        },
    }


def create_ocr_preservation_copy(
    *,
    case_root: Path,
    source_path: Path,
    source_hash: str | None = None,
    approved: bool,
    language: str = "eng",
) -> dict[str, Any]:
    if approved is not True:
        raise DocumentIntelligenceError("ocr_preservation_consent_required", "Explicit approval is required before OCR.", status_code=409)
    source = _safe_input(source_path, case_root=case_root)
    if source.suffix.lower() != ".pdf":
        raise DocumentIntelligenceError("ocr_preservation_pdf_required", "OCR preservation copies are available only for PDF sources.", status_code=415)
    if not _SAFE_LANGUAGE_RE.fullmatch(language):
        raise DocumentIntelligenceError("ocr_language_invalid", "OCR language must be a bounded Tesseract language code.")
    actual_hash = _sha256_file(source)
    if source_hash and source_hash.lower() != actual_hash:
        raise DocumentIntelligenceError("document_source_hash_mismatch", "The source hash changed before OCR.", status_code=409)
    ocr_engine = local_ocr_engine_status()
    if not (_module_available("ocrmypdf") and ocr_engine.get("available") and ocr_engine.get("pdf_ocr_available")):
        return {
            "status": "blocked",
            "blockers": ["ocrmypdf_not_installed"],
            "source_sha256": actual_hash,
            "original_modified": False,
            "review_required": True,
        }

    root = _artifact_root(case_root, actual_hash)
    with tempfile.TemporaryDirectory(prefix="mfl-ocrmypdf-") as temporary:
        temporary_root = Path(temporary)
        temp_output = temporary_root / "output.pdf"
        temp_sidecar = temporary_root / "output.txt"
        started = time.monotonic()
        try:
            from ocrmypdf.api import ocr as run_ocrmypdf

            with _temporary_environment(_ocr_environment()):
                exit_code = run_ocrmypdf(
                    source,
                    temp_output,
                    language=[language],
                    sidecar=temp_sidecar,
                    output_type="pdf",
                    optimize=0,
                    skip_text=True,
                    deskew=True,
                    rotate_pages=True,
                    rasterizer="pypdfium",
                    jobs=1,
                    progress_bar=False,
                )
        except Exception as exc:
            return {
                "status": "blocked",
                "blockers": ["ocrmypdf_failed"],
                "error_summary": f"{exc.__class__.__name__}: {exc}"[:1000],
                "source_sha256": actual_hash,
                "original_modified": False,
                "review_required": True,
            }
        if int(getattr(exit_code, "value", exit_code)) != 0 or not temp_output.is_file():
            return {
                "status": "blocked",
                "blockers": ["ocrmypdf_failed"],
                "error_summary": "ocrmypdf_failed",
                "source_sha256": actual_hash,
                "original_modified": False,
                "review_required": True,
            }
        if _sha256_file(source) != actual_hash:
            raise DocumentIntelligenceError("original_changed_during_ocr", "The original changed during OCR and the output was refused.", status_code=409)
        output_hash = _sha256_file(temp_output)
        sidecar_hash = _sha256_file(temp_sidecar) if temp_sidecar.is_file() else None
        source_baseline = extract_baseline_blocks(source.read_bytes(), source.suffix.lower(), actual_hash)
        source_text = _source_text(source.read_bytes(), source.suffix.lower(), source_baseline)
        output_text = temp_sidecar.read_text(encoding="utf-8", errors="replace") if temp_sidecar.is_file() else ""
        comparison = _compare_text_views(source_text, output_text)
        source_page_count = int(source_baseline.get("page_count") or 0)
        try:
            output_page_count = len(PdfReader(str(temp_output)).pages)
        except Exception:
            output_page_count = 0
        if source_page_count and output_page_count and source_page_count != output_page_count:
            comparison["warnings"].append("page_count_mismatch")
        output = root / f"searchable-preservation-{output_hash[:24]}.pdf"
        sidecar = root / f"searchable-preservation-{sidecar_hash[:24]}.txt" if sidecar_hash else root / "unused-sidecar.txt"
        _immutable_copy(temp_output, output, output_hash)
        if temp_sidecar.is_file() and sidecar_hash:
            _immutable_copy(temp_sidecar, sidecar, sidecar_hash)
        try:
            os.chmod(output, 0o600)
            if sidecar.exists():
                os.chmod(sidecar, 0o600)
        except OSError:
            pass
        page_block_mapping = [
            {
                "page_number": int(row.get("page_number") or 0),
                "block_id": row.get("block_id"),
                "kind": row.get("kind"),
                "char_start": int(row.get("char_start") or 0),
                "char_end": int(row.get("char_end") or 0),
            }
            for row in list(source_baseline.get("blocks") or [])[:20_000]
        ]
        receipt: dict[str, Any] = {
            "schema_version": "ocr_preservation_receipt_v1",
            "status": "pass",
            "generated_at": _utc_now(),
            "engine": "ocrmypdf",
            "engine_version": _version("ocrmypdf"),
            "language": language,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "source_sha256": actual_hash,
            "source_size_bytes": source.stat().st_size,
            "output_sha256": _sha256_file(output),
            "output_size_bytes": output.stat().st_size,
            "sidecar_sha256": _sha256_file(sidecar) if sidecar.exists() else None,
            "sidecar_size_bytes": sidecar.stat().st_size if sidecar.exists() else 0,
            "source_page_count": source_page_count,
            "output_page_count": output_page_count,
            "comparison": comparison,
            "page_block_mapping": page_block_mapping,
            "original_modified": False,
            "network_used": False,
            "review_required": True,
            "warnings": ["OCR text may contain errors. Compare the searchable copy with the verified original before relying on any passage."],
        }
        receipt["receipt_sha256"] = hashlib.sha256(json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        receipt_path = root / f"ocr-preservation-receipt-{receipt['receipt_sha256'][:24]}.json"
        if receipt_path.exists() and (receipt_path.is_symlink() or not receipt_path.is_file()):
            raise DocumentIntelligenceError("ocr_receipt_unsafe", "The OCR receipt path is unsafe.", status_code=409)
        if not receipt_path.exists():
            _atomic_json(receipt_path, receipt)
    return {
        **receipt,
        "artifacts": {
            "pdf": {
                "relative_path": output.relative_to(case_root.resolve(strict=True)).as_posix(),
                "sha256": _sha256_file(output),
                "size_bytes": output.stat().st_size,
                "artifact_type": "ocr_preservation_pdf",
                "receipt_relative_path": receipt_path.relative_to(case_root.resolve(strict=True)).as_posix(),
                "receipt_sha256": _sha256_file(receipt_path),
            },
            "sidecar": ({"relative_path": sidecar.relative_to(case_root.resolve(strict=True)).as_posix(), "sha256": _sha256_file(sidecar), "size_bytes": sidecar.stat().st_size, "artifact_type": "ocr_preservation_sidecar", "receipt_relative_path": receipt_path.relative_to(case_root.resolve(strict=True)).as_posix(), "receipt_sha256": _sha256_file(receipt_path)} if sidecar.exists() else None),
            "receipt": {"relative_path": receipt_path.relative_to(case_root.resolve(strict=True)).as_posix(), "sha256": _sha256_file(receipt_path), "size_bytes": receipt_path.stat().st_size, "artifact_type": "ocr_preservation_receipt", "receipt_relative_path": receipt_path.relative_to(case_root.resolve(strict=True)).as_posix(), "receipt_sha256": _sha256_file(receipt_path)},
        },
    }


def create_redacted_copy(
    *,
    case_root: Path,
    source_path: Path,
    source_hash: str | None = None,
    approved: bool,
    reviewer: str = "local_operator",
    run_presidio: bool = True,
) -> dict[str, Any]:
    if approved is not True:
        raise DocumentIntelligenceError("redaction_consent_required", "Explicit approval is required before creating a redacted copy.", status_code=409)
    source = _safe_input(source_path, case_root=case_root)
    actual_hash = _sha256_file(source)
    if source_hash and source_hash.lower() != actual_hash:
        raise DocumentIntelligenceError("document_source_hash_mismatch", "The source hash changed before redaction.", status_code=409)
    baseline = extract_baseline_blocks(source.read_bytes(), source.suffix.lower(), actual_hash)
    source_text = _source_text(source.read_bytes(), source.suffix.lower(), baseline)
    deterministic = deterministic_privacy_review(source_text)
    privacy = deterministic
    presidio_result: dict[str, Any] | None = None
    if run_presidio and source_text:
        status = document_intelligence_status()
        if any(item["adapter_id"] == "presidio" and item.get("available") for item in status.get("adapters", [])):
            with tempfile.TemporaryDirectory(prefix="mfl-presidio-") as temporary:
                text_path = Path(temporary) / "document.txt"
                text_path.write_text(source_text, encoding="utf-8")
                presidio_result = _run_worker("presidio", text_path, timeout=180)
    privacy = merge_privacy_findings(deterministic, presidio_result)
    redacted_text, redaction_receipts = _apply_redactions(source_text, list(privacy.get("findings") or []))
    output_hash = hashlib.sha256(redacted_text.encode("utf-8")).hexdigest()
    output_root = _artifact_root(case_root, actual_hash)
    redacted_path = output_root / f"redacted-copy-{output_hash[:24]}.txt"
    receipt_path = output_root / f"redaction-receipt-{output_hash[:24]}.json"
    if redacted_path.exists() and _sha256_file(redacted_path) != output_hash:
        raise DocumentIntelligenceError("redacted_copy_collision", "A redacted copy already exists with different content.", status_code=409)
    if not redacted_path.exists():
        _atomic_text(redacted_path, redacted_text)
    receipt = _build_receipt_payload(
        schema_version="redaction_receipt_v1",
        artifact_type="redacted_copy",
        source_sha256=actual_hash,
        output_sha256=output_hash,
        component_id="deterministic_privacy_review",
        component_version="built_in_v1",
        component_license="project_license",
        configuration={
            "run_presidio": bool(run_presidio),
            "reviewer": reviewer,
        },
        warnings=list(privacy.get("warning") and [str(privacy["warning"]) ] or []),
        page_block_mapping=[
            {
                "block_id": row.get("block_id"),
                "page_number": int(row.get("page_number") or 0),
                "kind": row.get("kind"),
                "char_start": int(row.get("char_start") or 0),
                "char_end": int(row.get("char_end") or 0),
            }
            for row in list(baseline.get("blocks") or [])[:20_000]
        ],
        extra={
            "reviewer": reviewer,
            "redaction_count": len(redaction_receipts),
            "redactions": [
                {**item, "source_sha256": actual_hash, "output_sha256": output_hash, "reviewer": reviewer, "timestamp": _utc_now()}
                for item in redaction_receipts
            ],
            "privacy_review": privacy,
        },
    )
    if not receipt_path.exists():
        _atomic_json(receipt_path, receipt)
    return {
        **receipt,
        "artifacts": {
            "redacted_copy": {
                "relative_path": redacted_path.relative_to(case_root.resolve(strict=True)).as_posix(),
                "sha256": output_hash,
                "size_bytes": redacted_path.stat().st_size,
                "artifact_type": "redacted_copy",
                "receipt_relative_path": receipt_path.relative_to(case_root.resolve(strict=True)).as_posix(),
                "receipt_sha256": _sha256_file(receipt_path),
            },
            "receipt": {
                "relative_path": receipt_path.relative_to(case_root.resolve(strict=True)).as_posix(),
                "sha256": _sha256_file(receipt_path),
                "size_bytes": receipt_path.stat().st_size,
                "artifact_type": "redaction_receipt",
                "receipt_relative_path": receipt_path.relative_to(case_root.resolve(strict=True)).as_posix(),
                "receipt_sha256": _sha256_file(receipt_path),
            },
        },
    }
