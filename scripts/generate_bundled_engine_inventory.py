from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata as metadata
import json
import os
import sqlite3
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pypdf import PdfWriter


@dataclass(frozen=True)
class EngineDefinition:
    package_name: str
    module_name: str
    smoke_group: str
    required_paths: tuple[str, ...] = ()
    path_markers: tuple[str, ...] = ()


ENGINE_DEFINITIONS: tuple[EngineDefinition, ...] = (
    EngineDefinition(
        package_name="presidio-analyzer",
        module_name="presidio_analyzer",
        smoke_group="presidio_stack",
        path_markers=("presidio_analyzer",),
    ),
    EngineDefinition(
        package_name="en-core-web-lg",
        module_name="en_core_web_lg",
        smoke_group="presidio_stack",
        required_paths=("_internal/en_core_web_lg",),
        path_markers=("en_core_web_lg", "spacy", "presidio"),
    ),
    EngineDefinition(
        package_name="spacy",
        module_name="spacy",
        smoke_group="presidio_stack",
        path_markers=("spacy",),
    ),
    EngineDefinition(
        package_name="sqlite-vec",
        module_name="sqlite_vec",
        smoke_group="sqlite_vec",
        path_markers=("sqlite_vec",),
    ),
    EngineDefinition(
        package_name="docling",
        module_name="docling",
        smoke_group="docling",
        required_paths=("store/docling/models",),
        path_markers=("docling",),
    ),
    EngineDefinition(
        package_name="ocrmypdf",
        module_name="ocrmypdf",
        smoke_group="ocr_stack",
        required_paths=("store/tesseract",),
        path_markers=("ocrmypdf", "tesseract", "pypdfium2", "pikepdf", "fpdf2", "uharfbuzz"),
    ),
    EngineDefinition(
        package_name="pypdfium2",
        module_name="pypdfium2",
        smoke_group="pdfium_stack",
        path_markers=("pypdfium2",),
    ),
    EngineDefinition(
        package_name="pikepdf",
        module_name="pikepdf",
        smoke_group="ocr_stack",
        path_markers=("pikepdf",),
    ),
    EngineDefinition(
        package_name="fpdf2",
        module_name="fpdf",
        smoke_group="ocr_stack",
        path_markers=("fpdf2",),
    ),
    EngineDefinition(
        package_name="uharfbuzz",
        module_name="uharfbuzz",
        smoke_group="ocr_stack",
        path_markers=("uharfbuzz",),
    ),
    EngineDefinition(
        package_name="qdrant-client",
        module_name="qdrant_client",
        smoke_group="qdrant_client",
        path_markers=("qdrant_client",),
    ),
)
ESSENTIAL_ENGINE_PACKAGES = {"pypdfium2"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_path(value: str) -> str:
    return value.replace("\\", "/").lstrip("./")


def _distribution_license(package_name: str) -> str:
    try:
        dist = metadata.distribution(package_name)
    except metadata.PackageNotFoundError:
        return "not_installed"
    license_text = str(dist.metadata.get("License") or "").strip()
    if license_text:
        return license_text
    classifiers = [value for key, value in dist.metadata.items() if key == "Classifier"]
    license_classifiers = [value for value in classifiers if str(value).startswith("License :: ")]
    return license_classifiers[0] if license_classifiers else "unknown"


def _distribution_version(package_name: str) -> str:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return "not_installed"


def _distribution_files_size(package_name: str) -> int:
    try:
        dist = metadata.distribution(package_name)
    except metadata.PackageNotFoundError:
        return 0
    location = Path(dist.locate_file(""))
    total = 0
    for file in dist.files or ():
        candidate = location / file
        if candidate.is_file():
            total += candidate.stat().st_size
    return total


def _collect_runtime_files(runtime_root: Path, markers: tuple[str, ...]) -> list[dict[str, Any]]:
    if not markers:
        return []
    runtime_root = runtime_root.resolve()
    results: list[dict[str, Any]] = []
    for path in sorted(p for p in runtime_root.rglob("*") if p.is_file()):
        rel = _normalize_path(str(path.relative_to(runtime_root)))
        rel_lower = rel.lower()
        if any(marker.lower() in rel_lower for marker in markers):
            results.append(
                {
                    "path": rel,
                    "size": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    return results


def _ensure_required_paths(runtime_root: Path, paths: tuple[str, ...]) -> None:
    for relative in paths:
        candidate = runtime_root / relative
        if not candidate.exists():
            raise RuntimeError(f"Required bundled path is missing: {relative}")


def _measure_import(module_name: str) -> tuple[bool, int, str]:
    started = time.perf_counter()
    try:
        importlib.import_module(module_name)
        return True, round((time.perf_counter() - started) * 1000), "pass"
    except Exception as exc:
        return (
            False,
            round((time.perf_counter() - started) * 1000),
            f"{exc.__class__.__name__}: {exc}",
        )


def _write_minimal_pdf(path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with path.open("wb") as handle:
        writer.write(handle)


def _smoke_presidio_stack(runtime_root: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="mfl-presidio-frozen-") as temporary:
        sample = Path(temporary) / "sample.txt"
        sample.write_text(
            "John Smith lives at 11 Main Street in Portland, Maine. Email john.smith@example.com.",
            encoding="utf-8",
        )
        result = _run_frozen_document_worker(runtime_root, "presidio", sample, timeout=240)
    return {
        "status": "pass",
        "findings": int(result.get("finding_count") or 0),
        "detail": "The frozen Presidio worker completed offline against the bundled spaCy model.",
    }


def _smoke_docling(runtime_root: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="mfl-docling-") as temporary:
        sample_pdf = Path(temporary) / "sample.pdf"
        _write_minimal_pdf(sample_pdf)
        result = _run_frozen_document_worker(runtime_root, "docling", sample_pdf, timeout=480)
        return {
            "status": "pass",
            "blocks": int(result.get("block_count") or 0),
            "detail": (
                "The frozen Docling worker converted a local PDF using bundled offline artifacts."
            ),
        }


def _run_frozen_document_worker(
    runtime_root: Path, adapter: str, input_path: Path, *, timeout: int
) -> dict[str, Any]:
    executable = runtime_root / "MaineFamilyLawLLM.exe"
    if not executable.is_file():
        raise RuntimeError("Frozen runtime executable is missing.")
    output_path = input_path.parent / f"{adapter}-worker-result.json"
    env = dict(os.environ)
    env.update(
        {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "DOCLING_ALLOW_EXTERNAL_PLUGINS": "false",
            "NO_PROXY": "*",
            "no_proxy": "*",
            "HTTP_PROXY": "",
            "HTTPS_PROXY": "",
            "ALL_PROXY": "",
        }
    )
    completed = subprocess.run(
        [
            str(executable),
            "--document-intelligence-worker",
            adapter,
            str(input_path),
            "--document-intelligence-output",
            str(output_path),
        ],
        cwd=str(runtime_root),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
        env=env,
    )
    if not output_path.is_file():
        raise RuntimeError(
            f"Frozen {adapter} worker did not create a result (exit {completed.returncode})."
        )
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("status") != "pass":
        detail = (
            str(payload.get("error") or payload.get("status") or "invalid_result")
            if isinstance(payload, dict)
            else "invalid_result"
        )
        raise RuntimeError(f"Frozen {adapter} worker failed: {detail[:500]}")
    return payload


def _smoke_sqlite_vec(runtime_root: Path) -> dict[str, Any]:
    import sqlite_vec

    with sqlite3.connect(":memory:") as db:
        db.enable_load_extension(True)
        try:
            sqlite_vec.load(db)
        finally:
            db.enable_load_extension(False)
        db.execute("CREATE VIRTUAL TABLE docs_vec USING vec0(embedding float[4])")
    return {
        "status": "pass",
        "detail": "sqlite_vec loaded into an in-memory SQLite database.",
    }


def _smoke_ocr_stack(runtime_root: Path) -> dict[str, Any]:
    from ocrmypdf.api import ocr

    tesseract_root = runtime_root / "store" / "tesseract"
    env = dict(os.environ)
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

    previous = dict(os.environ)
    try:
        os.environ.clear()
        os.environ.update(env)
        with tempfile.TemporaryDirectory(prefix="mfl-ocr-") as temporary:
            input_pdf = Path(temporary) / "input.pdf"
            output_pdf = Path(temporary) / "output.pdf"
            _write_minimal_pdf(input_pdf)
            exit_code = ocr(
                input_pdf,
                output_pdf,
                language=["eng"],
                force_ocr=True,
                output_type="pdf",
                jobs=1,
                # Keep the smoke in-process so OCRmyPDF's built-in plugin
                # namespace registration remains visible during the run.
                use_threads=True,
                optimize=0,
                progress_bar=False,
            )
            if int(exit_code) != 0:
                raise RuntimeError(f"ocrmypdf exited with code {exit_code}")
            if not output_pdf.is_file() or output_pdf.stat().st_size == 0:
                raise RuntimeError("ocrmypdf did not create an output PDF")
    finally:
        os.environ.clear()
        os.environ.update(previous)

    return {
        "status": "pass",
        "detail": "OCRmyPDF generated a searchable-copy output with the bundled Tesseract tree.",
    }


def _smoke_pdfium_stack(runtime_root: Path) -> dict[str, Any]:
    import pypdfium2

    with tempfile.TemporaryDirectory(prefix="mfl-pdfium-") as temporary:
        input_pdf = Path(temporary) / "input.pdf"
        _write_minimal_pdf(input_pdf)
        document = pypdfium2.PdfDocument(str(input_pdf))
        try:
            if len(document) != 1:
                raise RuntimeError("pypdfium2 did not open the one-page smoke PDF")
            bitmap = document[0].render(scale=0.25)
            if bitmap.width <= 0 or bitmap.height <= 0:
                raise RuntimeError("pypdfium2 rendered an empty bitmap")
        finally:
            document.close()
    return {
        "status": "pass",
        "detail": "pypdfium2 opened and rendered a deterministic one-page local PDF.",
    }


def _smoke_qdrant_client(runtime_root: Path) -> dict[str, Any]:
    import qdrant_client

    client = qdrant_client.QdrantClient(url="http://127.0.0.1:6333", prefer_grpc=False)
    parsed_url = urlparse(getattr(client._client, "rest_uri", ""))
    admitted = (
        parsed_url.scheme in {"http", "https"}
        and (parsed_url.hostname or "").lower() in {"127.0.0.1", "localhost", "::1"}
        and parsed_url.username is None
        and parsed_url.password is None
    )
    if not admitted:
        raise RuntimeError("Loopback Qdrant URL was not admitted.")
    return {
        "status": "pass",
        "detail": "qdrant-client imported and loopback admission stayed local-only.",
    }


def _native_whisper_inventory(runtime_root: Path) -> dict[str, Any]:
    whisper_root = runtime_root / "store" / "whisper"
    executable = whisper_root / "whisper-cli.exe"
    model = whisper_root / "ggml-tiny.en-q5_1.bin"
    manifest_path = whisper_root / "engine-manifest.json"
    for required in (executable, model, manifest_path):
        if not required.is_file() or required.is_symlink():
            raise RuntimeError(f"Required whisper.cpp payload is missing: {required.name}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    executable_hash = sha256_file(executable)
    model_hash = sha256_file(model)
    if executable_hash != str(manifest.get("executable_sha256") or ""):
        raise RuntimeError("whisper.cpp executable hash mismatch")
    if model_hash != str(manifest.get("model_sha256") or ""):
        raise RuntimeError("whisper.cpp model hash mismatch")
    started = time.perf_counter()
    completed = subprocess.run(
        [str(executable), "--version"],
        cwd=str(whisper_root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    duration_ms = round((time.perf_counter() - started) * 1000)
    if completed.returncode != 0 or str(manifest.get("version") or "") not in (completed.stdout + completed.stderr):
        raise RuntimeError("whisper.cpp native launch/version smoke failed")
    runtime_files = _collect_runtime_files(runtime_root, ("store/whisper",))
    return {
        "package_name": "whisper.cpp",
        "version": str(manifest.get("version") or "unknown"),
        "license": "MIT",
        "module_name": "native_executable",
        "required_bundle_paths": ["store/whisper"],
        "binary_model_files": runtime_files,
        "sha256": hashlib.sha256(
            json.dumps(runtime_files, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "runtime_import_check": {
            "status": "pass",
            "duration_ms": 0,
            "detail": "Native executable; Python import is not applicable.",
        },
        "offline_functional_smoke_result": {
            "status": "pass",
            "duration_ms": duration_ms,
            "detail": "Pinned CPU executable launched offline and reported the admitted version; audio E2E is recorded separately.",
        },
        "startup_cost_ms": duration_ms,
        "package_size_contribution_bytes": sum(int(row["size"]) for row in runtime_files),
    }


SMOKE_HANDLERS: dict[str, Callable[[Path], dict[str, Any]]] = {
    "presidio_stack": _smoke_presidio_stack,
    "sqlite_vec": _smoke_sqlite_vec,
    "docling": _smoke_docling,
    "ocr_stack": _smoke_ocr_stack,
    "pdfium_stack": _smoke_pdfium_stack,
    "qdrant_client": _smoke_qdrant_client,
}


def build_inventory(runtime_root: Path, *, feature_tier: str | None = None) -> list[dict[str, Any]]:
    runtime_root = runtime_root.resolve()
    tier = str(feature_tier or os.environ.get("MFL_STORE_FEATURE_TIER") or "full").lower()
    if tier not in {"essential", "full"}:
        raise ValueError(f"unsupported feature tier: {tier}")
    definitions = (
        tuple(
            definition
            for definition in ENGINE_DEFINITIONS
            if definition.package_name in ESSENTIAL_ENGINE_PACKAGES
        )
        if tier == "essential"
        else ENGINE_DEFINITIONS
    )
    inventory: list[dict[str, Any]] = []
    smoke_results: dict[str, dict[str, Any]] = {}
    for definition in definitions:
        _ensure_required_paths(runtime_root, definition.required_paths)
        runtime_files = _collect_runtime_files(runtime_root, definition.path_markers)
        runtime_import_ok, import_cost_ms, import_detail = _measure_import(definition.module_name)
        if definition.smoke_group not in smoke_results:
            smoke_handler = SMOKE_HANDLERS[definition.smoke_group]
            started = time.perf_counter()
            result = smoke_handler(runtime_root)
            result["duration_ms"] = round((time.perf_counter() - started) * 1000)
            smoke_results[definition.smoke_group] = result
        smoke = smoke_results[definition.smoke_group]
        package_size_contribution = _distribution_files_size(definition.package_name) + sum(
            int(row["size"]) for row in runtime_files
        )
        inventory.append(
            {
                "package_name": definition.package_name,
                "version": _distribution_version(definition.package_name),
                "license": _distribution_license(definition.package_name),
                "module_name": definition.module_name,
                "required_bundle_paths": list(definition.required_paths),
                "binary_model_files": runtime_files,
                "sha256": hashlib.sha256(
                    json.dumps(
                        runtime_files, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                    ).encode("utf-8")
                ).hexdigest(),
                "runtime_import_check": {
                    "status": "pass" if runtime_import_ok else "fail",
                    "duration_ms": import_cost_ms,
                    "detail": import_detail,
                },
                "offline_functional_smoke_result": smoke,
                "startup_cost_ms": import_cost_ms,
                "package_size_contribution_bytes": package_size_contribution,
            }
        )
    inventory.append(_native_whisper_inventory(runtime_root))
    return inventory


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    runtime_root = Path(args.runtime_root)
    if not runtime_root.exists():
        raise SystemExit(f"Runtime root does not exist: {runtime_root}")

    inventory = build_inventory(runtime_root)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "bundled_engine_inventory_v1",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "runtime_root": str(runtime_root),
        "package_count": len(inventory),
        "packages": inventory,
        "feature_tier": str(os.environ.get("MFL_STORE_FEATURE_TIER") or "full").lower(),
    }

    failures = []
    for row in inventory:
        if row["runtime_import_check"]["status"] != "pass":
            failures.append(f"{row['package_name']}: import check failed")
        if row["offline_functional_smoke_result"]["status"] != "pass":
            failures.append(f"{row['package_name']}: smoke check failed")
        if (
            payload["feature_tier"] == "full"
            and not row["binary_model_files"]
            and row["package_name"] in {"en-core-web-lg", "docling", "ocrmypdf"}
        ):
            failures.append(f"{row['package_name']}: required bundled files not found")
    payload["status"] = "pass" if not failures else "fail"
    payload["failures"] = failures
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if failures:
        raise SystemExit(2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
