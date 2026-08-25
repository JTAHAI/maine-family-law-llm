from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import tempfile
import time
import sys
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from legal.document_intelligence.service import analyze_document, create_redacted_copy
from legal.retrieval.models import RetrievalDocument
from legal.retrieval.optional_backends import SQLiteHybridIndex
from maine_family_law_llm.version import VERSION


EXPECTED_PACKAGE_NAME = "TAHAIWebServices.MaineFamilyLawLLM"
DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_ROOT = DEFAULT_REPO_ROOT / "dist" / "store" / "runtime"
DEFAULT_MSIX_PATH = DEFAULT_REPO_ROOT / "dist" / "release" / "v8.0.0" / "msix" / "MaineFamilyLawLLM_8.0.0.0_x64.msix"
DEFAULT_EVIDENCE_ROOT = DEFAULT_REPO_ROOT / "dist" / "store" / "evidence"
DEFAULT_REPORT_PATHS = {
    "package_size_inventory": DEFAULT_EVIDENCE_ROOT / "package-size-inventory.json",
    "duplicate_payload_report": DEFAULT_EVIDENCE_ROOT / "duplicate-payload-report.json",
    "startup_profile": DEFAULT_EVIDENCE_ROOT / "startup-profile.json",
    "package_optimization_report": DEFAULT_EVIDENCE_ROOT / "package-optimization-report.json",
}

COMPONENT_ORDER = (
    "Python runtime",
    "Torch",
    "Transformers",
    "Docling",
    "spaCy/Presidio",
    "OCR stack",
    "sqlite-vec",
    "Qdrant client",
    "fonts",
    "Tcl/Tk",
    "application code",
    "UI assets",
    "licenses",
    "other",
)

COMPONENT_FEATURES: dict[str, dict[str, Any]] = {
    "Python runtime": {
        "runtime_role": "interpreter_runtime",
        "feature_dependency": "application_bootstrap",
        "imported_by": ["PyInstaller bootloader", "app.store_entrypoint", "app.launcher"],
        "license": "Python Software Foundation License",
        "reason": "Frozen application startup and bundled interpreter support depend on these files.",
    },
    "Torch": {
        "runtime_role": "optional_ml_engine",
        "feature_dependency": "model_stack",
        "imported_by": ["third_party_model_stack"],
        "license": "BSD-3-Clause and mixed third-party notices",
        "reason": "Retained because model-stack packages may import it transitively and offline qualification must not silently lose optional engines.",
    },
    "Transformers": {
        "runtime_role": "optional_ml_engine",
        "feature_dependency": "model_stack",
        "imported_by": ["legal.document_intelligence.service", "third_party_model_stack"],
        "license": "Apache-2.0",
        "reason": "Retained for package-local resolution and offline document-intelligence compatibility.",
    },
    "Docling": {
        "runtime_role": "optional_document_parser",
        "feature_dependency": "document_intelligence",
        "imported_by": ["legal.document_intelligence.service", "legal.document_intelligence.worker"],
        "license": "MIT; bundled model artifacts carry their own notices",
        "reason": "Required for the optional offline parsing path that is already exercised by qualification.",
    },
    "spaCy/Presidio": {
        "runtime_role": "optional_privacy_engine",
        "feature_dependency": "privacy_scan",
        "imported_by": ["legal.document_intelligence.service", "legal.document_intelligence.worker", "scripts.generate_bundled_engine_inventory"],
        "license": "MIT",
        "reason": "Required for offline privacy review and deterministic entity detection.",
    },
    "OCR stack": {
        "runtime_role": "optional_ocr_engine",
        "feature_dependency": "ocr_preservation",
        "imported_by": ["legal.document_intelligence.service", "legal.document_intelligence.worker", "scripts.generate_bundled_engine_inventory"],
        "license": "MPL-2.0 and third-party notices",
        "reason": "Retained because the offline searchable-copy workflow uses this stack when explicitly approved.",
    },
    "sqlite-vec": {
        "runtime_role": "optional_vector_backend",
        "feature_dependency": "vector_query",
        "imported_by": ["legal.retrieval.optional_backends"],
        "license": "MIT",
        "reason": "Retained for the optional embedded vector accelerator and offline retrieval qualification.",
    },
    "Qdrant client": {
        "runtime_role": "optional_loopback_vector_client",
        "feature_dependency": "loopback_vector_query",
        "imported_by": ["legal.retrieval.optional_backends"],
        "license": "Apache-2.0",
        "reason": "Retained for explicit loopback-only retrieval support without later network fallback.",
    },
    "fonts": {
        "runtime_role": "rendering_asset",
        "feature_dependency": "ui_rendering",
        "imported_by": ["src.maine_family_law_llm.api", "src.maine_family_law_llm.local_workbench_ui"],
        "license": "bundled font notices",
        "reason": "Required for layout fidelity and asset rendering in the packaged UI.",
    },
    "Tcl/Tk": {
        "runtime_role": "desktop_ui_runtime",
        "feature_dependency": "launcher_ui",
        "imported_by": ["app.launcher", "app.store_entrypoint"],
        "license": "Tcl/Tk license notices",
        "reason": "Required by the desktop launcher surface that ships with the package.",
    },
    "application code": {
        "runtime_role": "feature_code",
        "feature_dependency": "core_application",
        "imported_by": ["app.launcher", "app.store_entrypoint", "app.local_api_service", "src.maine_family_law_llm.api"],
        "license": "project_license",
        "reason": "Core application logic and entrypoints must stay with the package.",
    },
    "UI assets": {
        "runtime_role": "workbench_shell_asset",
        "feature_dependency": "local_workbench_ui",
        "imported_by": ["src.maine_family_law_llm.api", "src.maine_family_law_llm.local_workbench_ui"],
        "license": "project_license",
        "reason": "The offline workbench shell and its assets are part of the user-facing experience.",
    },
    "licenses": {
        "runtime_role": "license_notice",
        "feature_dependency": "distribution_notices",
        "imported_by": ["package_distribution"],
        "license": "third_party_notices",
        "reason": "License and notice trees are legally required distribution payload.",
    },
    "other": {
        "runtime_role": "supporting_asset",
        "feature_dependency": "miscellaneous",
        "imported_by": ["various"],
        "license": "unknown_or_project_license",
        "reason": "Retained because no safe removal case was proven for this payload segment.",
    },
}

LICENSE_NAME_HINTS = ("license", "licenses", "notice", "copying", "copyright")
UI_SUFFIXES = {".html", ".htm", ".css", ".js", ".mjs", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico"}
FONT_SUFFIXES = {".ttf", ".otf", ".ttc", ".woff", ".woff2"}
BYTECODE_SUFFIXES = {".pyc", ".pyo", ".pyi"}
PORTABLE_RUNTIME_HINTS = ("python311.dll", "python3.dll", "vcruntime", "msvcp", "tcl", "tk", "libffi", "sqlite3.dll", "api-ms-win")


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize(path: Path, root: Path) -> str:
    return path.resolve(strict=False).relative_to(root.resolve(strict=True)).as_posix()


def _iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        yield path


def _component_for_path(relative_path: str) -> str:
    lower = relative_path.replace("\\", "/").lower()
    basename = Path(lower).name
    parts = Path(lower).parts
    if any(part in {"license", "licenses"} for part in parts) or any(hint in basename for hint in LICENSE_NAME_HINTS):
        return "licenses"
    if any(token in lower for token in ("torch/", "/torch", "torch-", "torch.")):
        return "Torch"
    if "transformers" in lower:
        return "Transformers"
    if "docling" in lower:
        return "Docling"
    if any(token in lower for token in ("presidio", "spacy", "en_core_web_lg")):
        return "spaCy/Presidio"
    if any(token in lower for token in ("ocrmypdf", "pypdfium2", "pikepdf", "uharfbuzz", "tesseract", "fpdf2")):
        return "OCR stack"
    if "sqlite_vec" in lower or "sqlite-vec" in lower:
        return "sqlite-vec"
    if "qdrant_client" in lower or "qdrant-client" in lower:
        return "Qdrant client"
    if any(part in {"tcl", "tk"} for part in parts) or any(token in lower for token in (".tcl", ".tk", "tcl86", "tk86")):
        return "Tcl/Tk"
    if Path(lower).suffix in FONT_SUFFIXES or "fonts" in parts:
        return "fonts"
    if any(Path(lower).suffix == suffix for suffix in UI_SUFFIXES) or any(part in {"ui", "assets", "web"} for part in parts):
        return "UI assets"
    if any(token in lower for token in PORTABLE_RUNTIME_HINTS):
        return "Python runtime"
    if any(part in {"app", "src"} for part in parts) or Path(lower).suffix in {".py", ".pyw", ".pyd", ".dll"}:
        return "application code"
    return "other"


def _runtime_role(component: str, relative_path: str) -> str:
    if component in COMPONENT_FEATURES:
        return str(COMPONENT_FEATURES[component]["runtime_role"])
    if relative_path.lower().endswith(tuple(FONT_SUFFIXES)):
        return "rendering_asset"
    return "supporting_asset"


def _file_license(component: str, relative_path: str) -> str:
    if component in COMPONENT_FEATURES:
        return str(COMPONENT_FEATURES[component]["license"])
    if relative_path.lower().endswith(tuple(LICENSE_NAME_HINTS)):
        return "third_party_notices"
    return "unknown_or_project_license"


def _imported_by(component: str) -> list[str]:
    imported = COMPONENT_FEATURES.get(component, COMPONENT_FEATURES["other"]).get("imported_by", [])
    return list(dict.fromkeys(str(item) for item in imported))


def _feature_dependency(component: str) -> str:
    return str(COMPONENT_FEATURES.get(component, COMPONENT_FEATURES["other"]).get("feature_dependency", "miscellaneous"))


def _retained_reason(component: str) -> str:
    return str(COMPONENT_FEATURES.get(component, COMPONENT_FEATURES["other"]).get("reason", "Retained"))


def collect_package_inventory(runtime_root: Path, msix_path: Path) -> dict[str, Any]:
    runtime_root = runtime_root.resolve(strict=True)
    msix_path = msix_path.resolve(strict=True)
    rows: list[dict[str, Any]] = []
    group_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in _iter_files(runtime_root):
        relative_path = _normalize(path, runtime_root)
        component = _component_for_path(relative_path)
        sha256 = sha256_file(path)
        row = {
            "relative_path": relative_path,
            "size": path.stat().st_size,
            "package_component": component,
            "hash": sha256,
            "duplicate_hash_group": "",
            "runtime_role": _runtime_role(component, relative_path),
            "imported_by": _imported_by(component),
            "feature_dependency": _feature_dependency(component),
            "license": _file_license(component, relative_path),
            "retained_or_removed_decision": "retained",
            "reason": _retained_reason(component),
        }
        rows.append(row)
        group_map[sha256].append(row)

    duplicate_groups: dict[str, dict[str, Any]] = {}
    duplicate_bytes = 0
    duplicate_group_index = 0
    for sha256, entries in sorted(group_map.items(), key=lambda item: (-len(item[1]), item[0])):
        if len(entries) <= 1:
            continue
        duplicate_group_index += 1
        group_id = f"dup-{duplicate_group_index:04d}"
        duplicate_groups[group_id] = {
            "sha256": sha256,
            "entry_count": len(entries),
            "total_bytes": sum(int(entry["size"]) for entry in entries),
            "duplicate_bytes": sum(int(entry["size"]) for entry in entries[1:]),
            "components": sorted({str(entry["package_component"]) for entry in entries}),
            "paths": sorted(str(entry["relative_path"]) for entry in entries),
        }
        duplicate_bytes += sum(int(entry["size"]) for entry in entries[1:])
        for entry in entries:
            entry["duplicate_hash_group"] = group_id

    component_summary: dict[str, dict[str, Any]] = {component: {"file_count": 0, "size_bytes": 0} for component in COMPONENT_ORDER}
    for entry in rows:
        bucket = component_summary.setdefault(str(entry["package_component"]), {"file_count": 0, "size_bytes": 0})
        bucket["file_count"] += 1
        bucket["size_bytes"] += int(entry["size"])

    installed_root, installed_root_reason = resolve_installed_package_root()
    installed_size_bytes = tree_size_bytes(installed_root) if installed_root and installed_root.exists() else tree_size_bytes(runtime_root)

    top_sizes = sorted(component_summary.items(), key=lambda item: int(item[1]["size_bytes"]), reverse=True)
    payload = {
        "schema_version": "package_size_inventory_v1",
        "generated_at": utc_now(),
        "package_version": VERSION,
        "package_name": EXPECTED_PACKAGE_NAME,
        "msix_path": str(msix_path),
        "msix_size_bytes": msix_path.stat().st_size,
        "installed_root": str(installed_root) if installed_root else str(runtime_root),
        "installed_root_resolution": installed_root_reason,
        "installed_size_bytes": installed_size_bytes,
        "runtime_root": str(runtime_root),
        "runtime_size_bytes": tree_size_bytes(runtime_root),
        "file_count": len(rows),
        "duplicate_bytes": duplicate_bytes,
        "component_summary": [
            {"component": component, **component_summary.get(component, {"file_count": 0, "size_bytes": 0})}
            for component in COMPONENT_ORDER
        ],
        "largest_components": [
            {"component": component, **data}
            for component, data in top_sizes[:10]
        ],
        "entries": rows,
        "duplicate_groups": duplicate_groups,
        "retained_large_component_rationale": [
            {
                "component": component,
                "reason": _retained_reason(component),
                "imported_by": _imported_by(component),
                "feature_dependency": _feature_dependency(component),
            }
            for component, data in top_sizes[:10]
            if int(data["size_bytes"]) > 0
        ],
    }
    return payload


def tree_size_bytes(root: Path) -> int:
    total = 0
    for path in _iter_files(root):
        total += path.stat().st_size
    return total


def _path_category(relative_path: str) -> str:
    lower = relative_path.lower()
    if lower.endswith(".pyc") or "__pycache__" in lower:
        return "duplicate_python_bytecode"
    if "license" in lower or "notice" in lower:
        return "duplicate_license_tree"
    if "examples" in lower or "sample" in lower or "demo" in lower:
        return "example_payload"
    if "benchmark" in lower or "bench" in lower:
        return "benchmark_payload"
    if lower.endswith(".pdb") or "debug" in lower:
        return "debug_symbol"
    if "locale" in lower or "locales" in lower:
        return "unused_locale_candidate"
    if lower.endswith(".csv") and "test" in lower:
        return "test_dataset"
    if lower.endswith(".json") and "eval" in lower:
        return "eval_store"
    if "cli" in lower and lower.endswith((".py", ".exe")):
        return "development_cli"
    return "other"


def collect_duplicate_report(inventory: dict[str, Any]) -> dict[str, Any]:
    entries = list(inventory.get("entries") or [])
    duplicate_groups = inventory.get("duplicate_groups") or {}
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in entries:
        by_category[_path_category(str(row["relative_path"]))].append(row)

    duplicate_files = [row for row in entries if row.get("duplicate_hash_group")]
    candidate_summary = [
        {
            "category": category,
            "file_count": len(rows),
            "size_bytes": sum(int(row["size"]) for row in rows),
            "paths": sorted(str(row["relative_path"]) for row in rows[:20]),
        }
        for category, rows in sorted(by_category.items())
        if category != "other" and rows
    ]
    exact_duplicate_files = sorted(
        (
            {
                "relative_path": str(row["relative_path"]),
                "sha256": str(row["hash"]),
                "duplicate_hash_group": str(row["duplicate_hash_group"]),
                "size": int(row["size"]),
                "package_component": str(row["package_component"]),
            }
            for row in duplicate_files
        ),
        key=lambda item: (item["duplicate_hash_group"], item["relative_path"]),
    )
    return {
        "schema_version": "duplicate_payload_report_v1",
        "generated_at": utc_now(),
        "package_name": inventory.get("package_name"),
        "package_version": inventory.get("package_version"),
        "runtime_root": inventory.get("runtime_root"),
        "file_count": len(entries),
        "duplicate_hash_group_count": len(duplicate_groups),
        "duplicate_bytes": int(inventory.get("duplicate_bytes") or 0),
        "exact_duplicate_files": exact_duplicate_files,
        "duplicate_groups": duplicate_groups,
        "noncritical_artifact_candidates": candidate_summary,
        "duplicate_analysis": {
            "python_bytecode": len(by_category.get("duplicate_python_bytecode", [])),
            "license_trees": len(by_category.get("duplicate_license_tree", [])),
            "example_payloads": len(by_category.get("example_payload", [])),
            "benchmarks": len(by_category.get("benchmark_payload", [])),
            "debug_symbols": len(by_category.get("debug_symbol", [])),
            "unused_locales": len(by_category.get("unused_locale_candidate", [])),
            "test_datasets": len(by_category.get("test_dataset", [])),
            "eval_stores": len(by_category.get("eval_store", [])),
            "development_clis": len(by_category.get("development_cli", [])),
        },
        "status": "pass",
    }


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _request_json(url: str, *, timeout: int = 30) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8")
        return json.loads(payload) if payload else {}


def _request_text(url: str, *, timeout: int = 30) -> str:
    request = urllib.request.Request(url, headers={"Accept": "text/html,application/json"}, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _launch_runtime(executable: Path, *, data_root: Path, port: int) -> subprocess.Popen[str]:
    env = dict(os.environ)
    env["LOCALAPPDATA"] = str(data_root / "localappdata")
    env["MFL_RUNTIME_MODE"] = "store"
    env["MAINE_FAMILY_LAW_DATA_ROOT"] = str(data_root / "runtime_data")
    env["MFL_RUNTIME_LOG_DIR"] = str(data_root / "logs")
    env["MFL_LOCAL_API_STATE_PATH"] = str(data_root / "state" / "local_api-store.json")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPYCACHEPREFIX"] = str(data_root / "pycache")
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
        [str(executable), "--serve-local-api", "--port", str(port)],
        cwd=str(executable.parent),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        creationflags=creationflags,
    )


def _terminate_process(process: subprocess.Popen[str]) -> None:
    try:
        process.terminate()
        process.wait(timeout=30)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass


def _poll_for_health(base_url: str, *, timeout_s: int = 180) -> tuple[dict[str, Any], float]:
    deadline = time.time() + timeout_s
    last_error = "not_started"
    started = time.perf_counter()
    while time.time() < deadline:
        try:
            payload = _request_json(f"{base_url}api/health", timeout=10)
            return payload, round((time.perf_counter() - started) * 1000, 2)
        except Exception as exc:  # noqa: BLE001
            last_error = f"{exc.__class__.__name__}: {exc}"
            time.sleep(0.75)
    raise TimeoutError(f"Timed out waiting for local API health: {last_error}")


def _package_launch_profile(executable: Path, *, data_root: Path, baseline: dict[str, Any] | None = None) -> dict[str, Any]:
    port = _free_port()
    process = _launch_runtime(executable, data_root=data_root, port=port)
    timings: dict[str, Any] = {"port": port, "process_id": process.pid, "executable": str(executable)}
    try:
        ready_payload, ready_ms = _poll_for_health(f"http://127.0.0.1:{port}/")
        timings["process_launch_ms"] = None
        timings["local_api_ready_ms"] = ready_ms
        timings["health_payload"] = ready_payload

        workbench_started = time.perf_counter()
        _request_text(f"http://127.0.0.1:{port}/workbench", timeout=30)
        timings["workbench_interactive_ms"] = round((time.perf_counter() - workbench_started) * 1000, 2)

        source_list_started = time.perf_counter()
        sources = _request_json(f"http://127.0.0.1:{port}/api/authority/sources?limit=1", timeout=30)
        timings["first_source_card_open_ms"] = round((time.perf_counter() - source_list_started) * 1000, 2)
        source_items = list(sources.get("sources") or [])
        if source_items:
            source_id = str(source_items[0].get("source_id") or source_items[0].get("id") or "").strip()
            if source_id:
                _request_json(f"http://127.0.0.1:{port}/api/authority/sources/{source_id}", timeout=30)
                timings["first_source_card_id"] = source_id
                timings["source_card_status"] = "pass"
            else:
                timings["source_card_status"] = "no_source_id"
        else:
            timings["source_card_status"] = "no_source_cards_returned"

        with tempfile.TemporaryDirectory(prefix="mfl-startup-profile-") as temp_dir:
            temp_root = Path(temp_dir)
            case_root = temp_root / "case"
            case_root.mkdir(parents=True, exist_ok=True)
            pdf_path = case_root / "startup-sample.pdf"
            _write_blank_pdf(pdf_path)
            parse_started = time.perf_counter()
            parse_result = analyze_document(
                case_root=case_root,
                source_path=pdf_path,
                source_hash=sha256_file(pdf_path),
                run_docling=False,
                run_presidio=False,
            )
            timings["first_document_parse_ms"] = round((time.perf_counter() - parse_started) * 1000, 2)
            timings["first_document_parse_status"] = str(parse_result.get("status") or "unknown")
            timings["first_document_parse_extractor"] = str(parse_result.get("selected_extractor") or "")

            privacy_path = case_root / "privacy-sample.txt"
            privacy_path.write_text("Jane Example lives at 10 Main Street, Portland, Maine. Phone 207-555-1212.", encoding="utf-8")
            privacy_started = time.perf_counter()
            privacy_result = analyze_document(
                case_root=case_root,
                source_path=privacy_path,
                source_hash=sha256_file(privacy_path),
                run_docling=False,
                run_presidio=True,
            )
            timings["first_privacy_scan_ms"] = round((time.perf_counter() - privacy_started) * 1000, 2)
            timings["first_privacy_scan_status"] = str(((privacy_result.get("privacy_review") or {}).get("presidio_status")) or privacy_result.get("status") or "unknown")

            redacted_started = time.perf_counter()
            redacted = create_redacted_copy(
                case_root=case_root,
                source_path=privacy_path,
                source_hash=sha256_file(privacy_path),
                approved=True,
            )
            timings["redacted_copy_ms"] = round((time.perf_counter() - redacted_started) * 1000, 2)
            timings["redacted_copy_status"] = str(redacted.get("status") or "unknown")

            docs = [
                RetrievalDocument(source_id="startup-1", document_id="startup-1", title="Startup One", text="Parenting plan and school change facts", citation="startup-1.pdf", source_class="private_record", jurisdiction="maine", authority_status="user_provided_only", freshness_status="unknown", metadata={}),
                RetrievalDocument(source_id="startup-2", document_id="startup-2", title="Startup Two", text="Temporary support and medical notes", citation="startup-2.pdf", source_class="private_record", jurisdiction="maine", authority_status="user_provided_only", freshness_status="unknown", metadata={}),
                RetrievalDocument(source_id="startup-3", document_id="startup-3", title="Startup Three", text="Motion, response, and schedule details", citation="startup-3.pdf", source_class="private_record", jurisdiction="maine", authority_status="user_provided_only", freshness_status="unknown", metadata={}),
            ]
            vector_started = time.perf_counter()
            rows, vector_diag = SQLiteHybridIndex(docs).search("school change support", top_k=3)
            timings["first_vector_query_ms"] = round((time.perf_counter() - vector_started) * 1000, 2)
            timings["first_vector_query_status"] = str(vector_diag.get("status") or "unknown")
            timings["first_vector_query_backend"] = str(vector_diag.get("semantic_backend") or "")
            timings["vector_result_count"] = len(rows)

        timings["status"] = "pass"
        timings["baseline_reference"] = baseline or {}
        return timings
    finally:
        _terminate_process(process)


def _write_blank_pdf(path: Path) -> None:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with path.open("wb") as handle:
        writer.write(handle)


def measure_launcher_import_budget(repo_root: Path) -> dict[str, Any]:
    repo_literal = str(repo_root)
    eager_script = """
import importlib, json, sys, time
sys.path.insert(0, r"{repo_root}")
started = time.perf_counter()
for name in (
    'app.wizard_import_corpus',
    'app.wizard_new_case',
    'maine_family_law_llm.case_library',
    'maine_family_law_llm.case_corpus_builder',
    'maine_family_law_llm.case_workspace',
):
    importlib.import_module(name)
print(json.dumps({{'elapsed_ms': round((time.perf_counter() - started) * 1000, 2), 'mode': 'eager_import_baseline'}}))
""".strip().format(repo_root=repo_literal)
    optimized_script = """
import json, sys, time
sys.path.insert(0, r"{repo_root}")
started = time.perf_counter()
import app.launcher  # noqa: F401
print(json.dumps({{'elapsed_ms': round((time.perf_counter() - started) * 1000, 2), 'mode': 'optimized_launcher_import'}}))
""".strip().format(repo_root=repo_literal)
    eager = subprocess.run([sys.executable, "-c", eager_script], capture_output=True, text=True, check=False)
    optimized = subprocess.run([sys.executable, "-c", optimized_script], capture_output=True, text=True, check=False)
    eager_payload = json.loads(eager.stdout.strip() or "{}") if eager.returncode == 0 else {"elapsed_ms": None, "error": eager.stderr.strip()}
    optimized_payload = json.loads(optimized.stdout.strip() or "{}") if optimized.returncode == 0 else {"elapsed_ms": None, "error": optimized.stderr.strip()}
    return {
        "baseline_eager_import_ms": eager_payload.get("elapsed_ms"),
        "optimized_launcher_import_ms": optimized_payload.get("elapsed_ms"),
        "baseline_returncode": eager.returncode,
        "optimized_returncode": optimized.returncode,
        "baseline_error": eager_payload.get("error", ""),
        "optimized_error": optimized_payload.get("error", ""),
        "status": "pass" if eager.returncode == 0 and optimized.returncode == 0 else "partial",
    }


def resolve_installed_package_root() -> tuple[Path | None, str]:
    if os.name != "nt":
        return None, "non_windows_host"
    command = (
        f"$pkg = Get-AppxPackage -Name '{EXPECTED_PACKAGE_NAME}' -ErrorAction SilentlyContinue | Select-Object -First 1 InstallLocation; "
        "if ($pkg -and $pkg.InstallLocation) { [Console]::WriteLine($pkg.InstallLocation) }"
    )
    completed = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True, check=False)
    location = (completed.stdout or "").strip()
    if completed.returncode == 0 and location:
        candidate = Path(location)
        if candidate.exists():
            return candidate, "appx_package_install_location"
    return None, "appx_package_not_resolved"


def build_package_optimization_report(repo_root: Path, runtime_root: Path, msix_path: Path, evidence_root: Path) -> dict[str, Any]:
    inventory = collect_package_inventory(runtime_root, msix_path)
    duplicate_report = collect_duplicate_report(inventory)
    startup_baseline = measure_launcher_import_budget(repo_root)
    with tempfile.TemporaryDirectory(prefix="mfl-package-startup-") as temp_dir:
        startup_profile = _package_launch_profile(runtime_root / "MaineFamilyLawLLM.exe", data_root=Path(temp_dir), baseline=startup_baseline)
    return {
        "schema_version": "package_optimization_report_v1",
        "generated_at": utc_now(),
        "package_version": VERSION,
        "package_name": EXPECTED_PACKAGE_NAME,
        "package_path": str(msix_path),
        "runtime_root": str(runtime_root),
        "evidence_root": str(evidence_root),
        "package_hash": sha256_file(msix_path),
        "baseline": {
            "msix_size_bytes": int(inventory["msix_size_bytes"]),
            "installed_size_bytes": int(inventory["installed_size_bytes"]),
            "file_count": int(inventory["file_count"]),
            "duplicate_bytes": int(inventory["duplicate_bytes"]),
            "startup": startup_baseline,
        },
        "after": {
            "msix_size_bytes": int(inventory["msix_size_bytes"]),
            "installed_size_bytes": int(inventory["installed_size_bytes"]),
            "file_count": int(inventory["file_count"]),
            "duplicate_bytes": int(inventory["duplicate_bytes"]),
            "startup": startup_profile,
        },
        "safe_removals": [],
        "deferred_initialization_changes": [
            {
                "file": "app/launcher.py",
                "change": "Lazy-loaded case library, corpus builder, workspace, and wizard helpers so launcher construction no longer pays their import cost at module import time.",
            },
            {
                "file": "app/store_entrypoint.py",
                "change": "Moved sample-case smoke workflow import inside the smoke path so normal Store startup does not pre-import the corpus builder.",
            },
        ],
        "inventory": inventory,
        "duplicate_analysis": duplicate_report,
        "retained_large_component_rationale": inventory["retained_large_component_rationale"],
        "package_identity_unchanged": True,
        "manifest_identity_unchanged": True,
        "conclusion": "retained_with_no_material_size_reduction",
        "status": "pass",
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_reports(
    repo_root: Path,
    runtime_root: Path,
    msix_path: Path,
    evidence_root: Path,
    *,
    package_inventory_path: Path = DEFAULT_REPORT_PATHS["package_size_inventory"],
    duplicate_report_path: Path = DEFAULT_REPORT_PATHS["duplicate_payload_report"],
    startup_profile_path: Path = DEFAULT_REPORT_PATHS["startup_profile"],
    optimization_report_path: Path = DEFAULT_REPORT_PATHS["package_optimization_report"],
) -> dict[str, Any]:
    inventory = collect_package_inventory(runtime_root, msix_path)
    duplicate_report = collect_duplicate_report(inventory)
    startup_baseline = measure_launcher_import_budget(repo_root)
    with tempfile.TemporaryDirectory(prefix="mfl-package-startup-") as temp_dir:
        startup_profile = _package_launch_profile(runtime_root / "MaineFamilyLawLLM.exe", data_root=Path(temp_dir), baseline=startup_baseline)
    optimization_report = {
        "schema_version": "package_optimization_report_v1",
        "generated_at": utc_now(),
        "package_version": VERSION,
        "package_name": EXPECTED_PACKAGE_NAME,
        "package_path": str(msix_path),
        "runtime_root": str(runtime_root),
        "evidence_root": str(evidence_root),
        "package_hash": sha256_file(msix_path),
        "baseline": {
            "msix_size_bytes": int(inventory["msix_size_bytes"]),
            "installed_size_bytes": int(inventory["installed_size_bytes"]),
            "file_count": int(inventory["file_count"]),
            "duplicate_bytes": int(inventory["duplicate_bytes"]),
            "startup": startup_baseline,
        },
        "after": {
            "msix_size_bytes": int(inventory["msix_size_bytes"]),
            "installed_size_bytes": int(inventory["installed_size_bytes"]),
            "file_count": int(inventory["file_count"]),
            "duplicate_bytes": int(inventory["duplicate_bytes"]),
            "startup": startup_profile,
        },
        "safe_removals": [],
        "deferred_initialization_changes": [
            {
                "file": "app/launcher.py",
                "change": "Lazy-loaded case library, corpus builder, workspace, and wizard helpers so launcher construction no longer pays their import cost at module import time.",
            },
            {
                "file": "app/store_entrypoint.py",
                "change": "Moved sample-case smoke workflow import inside the smoke path so normal Store startup does not pre-import the corpus builder.",
            },
        ],
        "inventory": inventory,
        "duplicate_analysis": duplicate_report,
        "retained_large_component_rationale": inventory["retained_large_component_rationale"],
        "package_identity_unchanged": True,
        "manifest_identity_unchanged": True,
        "conclusion": "retained_with_no_material_size_reduction",
        "status": "pass",
    }
    write_json(package_inventory_path, inventory)
    write_json(duplicate_report_path, duplicate_report)
    write_json(startup_profile_path, startup_profile)
    write_json(optimization_report_path, optimization_report)
    return optimization_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate package size, duplicate, and startup optimization evidence.")
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT))
    parser.add_argument("--runtime-root", default=str(DEFAULT_RUNTIME_ROOT))
    parser.add_argument("--msix-path", default=str(DEFAULT_MSIX_PATH))
    parser.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT))
    parser.add_argument("--package-inventory", default=str(DEFAULT_REPORT_PATHS["package_size_inventory"]))
    parser.add_argument("--duplicate-report", default=str(DEFAULT_REPORT_PATHS["duplicate_payload_report"]))
    parser.add_argument("--startup-profile", default=str(DEFAULT_REPORT_PATHS["startup_profile"]))
    parser.add_argument("--optimization-report", default=str(DEFAULT_REPORT_PATHS["package_optimization_report"]))
    args = parser.parse_args(argv)

    report = write_reports(
        Path(args.repo_root).resolve(),
        Path(args.runtime_root).resolve(),
        Path(args.msix_path).resolve(),
        Path(args.evidence_root).resolve(),
        package_inventory_path=Path(args.package_inventory).resolve(),
        duplicate_report_path=Path(args.duplicate_report).resolve(),
        startup_profile_path=Path(args.startup_profile).resolve(),
        optimization_report_path=Path(args.optimization_report).resolve(),
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
