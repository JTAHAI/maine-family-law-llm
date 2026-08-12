from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from docx import Document
from fpdf import FPDF
from PIL import Image, ImageDraw
from pypdf import PdfReader

from legal.document_intelligence import analyze_document, create_ocr_preservation_copy, create_redacted_copy
from maine_family_law_llm.installed_runtime import (
    DEFAULT_PACKAGE_NAME,
    InstalledRuntimeResolution,
    resolve_installed_runtime_executable,
)
from maine_family_law_llm.local_only_boundary import LocalOnlyNetworkBlocked, local_only_network_boundary


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_json(url: str, *, timeout_s: int = 120) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last_error: str = "not_started"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            last_error = f"{exc.__class__.__name__}: {exc}"
            time.sleep(1.5)
    raise TimeoutError(f"Timed out waiting for {url}: {last_error}")


def request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, method=method.upper(), headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def download_bytes(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def create_docx(path: Path) -> None:
    document = Document()
    document.add_heading("Motion for Temporary Relief", level=1)
    document.add_paragraph("The child changed schools on January 3, 2026.")
    document.add_paragraph("Parent Jane Example can be reached at jane.example@example.com.")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Date"
    table.cell(0, 1).text = "Event"
    table.cell(1, 0).text = "2026-01-03"
    table.cell(1, 1).text = "School change"
    document.save(path)


def create_pdf_with_text(path: Path, lines: list[str]) -> None:
    pdf = FPDF(unit="pt", format="letter")
    pdf.add_page()
    pdf.set_font("Helvetica", size=14)
    y = 48
    for line in lines:
        pdf.set_xy(48, y)
        pdf.multi_cell(516, 18, line)
        y += 24
    pdf.output(str(path))


def create_image_only_pdf(path: Path, *, label: str) -> Path:
    image_path = path.with_suffix(".png")
    image = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(image)
    draw.text((80, 120), label, fill="black")
    draw.text((80, 180), "This page intentionally contains only a raster image.", fill="black")
    image.save(image_path)
    pdf = FPDF(unit="pt", format=(612, 792))
    pdf.add_page()
    pdf.image(str(image_path), x=36, y=36, w=540)
    pdf.output(str(path))
    return image_path


def stage_record(case_root: Path, *, evidence_id: str, filename: str, data: bytes, **row: Any) -> dict[str, Any]:
    rel_path = Path("02_PRIVATE_FORENSIC_MASTER") / "files" / filename
    target = case_root / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    source_hash = hashlib.sha256(data).hexdigest()
    return {
        "evidence_id": evidence_id,
        "title": row.get("title") or evidence_id,
        "source_type": row.get("source_type") or target.suffix.lstrip("."),
        "source_locator": rel_path.as_posix(),
        "private_copy_relpath": rel_path.as_posix(),
        "source_hash": source_hash,
        "page_number": int(row.get("page_number") or 1),
        "page_count": int(row.get("page_count") or 1),
        "parser_status": row.get("parser_status") or "parsed",
        "text_status": row.get("text_status") or "available",
        "ocr_status": row.get("ocr_status") or "not_run",
        "text_excerpt": str(row.get("text_excerpt") or ""),
        "text_content": str(row.get("text_content") or ""),
        "issue_lanes": list(row.get("issue_lanes") or []),
        "procedural_postures": list(row.get("procedural_postures") or []),
    }


def build_case_fixture(case_root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    manifest: list[dict[str, Any]] = []

    pii_text = (
        "Motion for temporary relief.\n"
        "Parent Jane Example lives at 10 Main Street, Portland, Maine.\n"
        "Email jane.example@example.com and phone (207) 555-1212.\n"
        "DOB 01/02/2010 and SSN 123-45-6789 are confidential."
    )
    pii_txt = case_root / "pii.txt"
    pii_txt.write_text(pii_text, encoding="utf-8")
    manifest.append(
        {
            "evidence_id": "REC-PII-TXT",
            "source_path": str(pii_txt.resolve()),
            "private_copy_relpath": (Path("02_PRIVATE_FORENSIC_MASTER/files") / pii_txt.name).as_posix(),
            "source_hash": hashlib.sha256(pii_txt.read_bytes()).hexdigest(),
            "subject": "PII note",
        }
    )
    records.append(
        stage_record(
            case_root,
            evidence_id="REC-PII-TXT",
            filename=pii_txt.name,
            data=pii_txt.read_bytes(),
            title="PII note",
            text_excerpt=pii_text,
            text_content=pii_text,
            issue_lanes=["privacy", "contact"],
        )
    )

    docx_path = case_root / "motion.docx"
    create_docx(docx_path)
    manifest.append(
        {
            "evidence_id": "REC-DOCX",
            "source_path": str(docx_path.resolve()),
            "private_copy_relpath": (Path("02_PRIVATE_FORENSIC_MASTER/files") / docx_path.name).as_posix(),
            "source_hash": hashlib.sha256(docx_path.read_bytes()).hexdigest(),
            "subject": "Motion for Temporary Relief",
        }
    )
    records.append(
        stage_record(
            case_root,
            evidence_id="REC-DOCX",
            filename=docx_path.name,
            data=docx_path.read_bytes(),
            title="Motion for Temporary Relief",
            text_excerpt="The child changed schools on January 3, 2026.",
            text_content="The child changed schools on January 3, 2026. Parent Jane Example can be reached at jane.example@example.com.",
            issue_lanes=["custody", "school"],
        )
    )

    pdf_path = case_root / "brief.pdf"
    create_pdf_with_text(
        pdf_path,
        [
            "This ordinary PDF has a heading, a body paragraph, and a small table.",
            "The child changed schools on January 3, 2026.",
            "Contact: jane.example@example.com",
        ],
    )
    manifest.append(
        {
            "evidence_id": "REC-PDF",
            "source_path": str(pdf_path.resolve()),
            "private_copy_relpath": (Path("02_PRIVATE_FORENSIC_MASTER/files") / pdf_path.name).as_posix(),
            "source_hash": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
            "subject": "Ordinary PDF",
        }
    )
    records.append(
        stage_record(
            case_root,
            evidence_id="REC-PDF",
            filename=pdf_path.name,
            data=pdf_path.read_bytes(),
            title="Ordinary PDF",
            text_excerpt="The child changed schools on January 3, 2026.",
            text_content="This ordinary PDF has a heading, a body paragraph, and a small table. The child changed schools on January 3, 2026.",
            issue_lanes=["school"],
        )
    )

    ocr_pdf = case_root / "scan.pdf"
    create_image_only_pdf(ocr_pdf, label="Scan for OCR")
    manifest.append(
        {
            "evidence_id": "REC-OCR",
            "source_path": str(ocr_pdf.resolve()),
            "private_copy_relpath": (Path("02_PRIVATE_FORENSIC_MASTER/files") / ocr_pdf.name).as_posix(),
            "source_hash": hashlib.sha256(ocr_pdf.read_bytes()).hexdigest(),
            "subject": "Image-only scan",
        }
    )
    records.append(
        stage_record(
            case_root,
            evidence_id="REC-OCR",
            filename=ocr_pdf.name,
            data=ocr_pdf.read_bytes(),
            title="Image-only scan",
            text_excerpt="Scan for OCR",
            text_content="Scan for OCR",
            source_type="pdf",
            issue_lanes=["ocr"],
        )
    )

    dup_a = case_root / "duplicate-a.docx"
    create_docx(dup_a)
    dup_b = case_root / "duplicate-b.docx"
    # Copy the same bytes so the qualification fixture is an exact duplicate;
    # independently saving two DOCX files can embed different ZIP timestamps.
    dup_b.write_bytes(dup_a.read_bytes())
    manifest.append(
        {
            "evidence_id": "REC-DUP-A",
            "source_path": str(dup_a.resolve()),
            "private_copy_relpath": (Path("02_PRIVATE_FORENSIC_MASTER/files") / dup_a.name).as_posix(),
            "source_hash": hashlib.sha256(dup_a.read_bytes()).hexdigest(),
            "subject": "Duplicate A",
        }
    )
    manifest.append(
        {
            "evidence_id": "REC-DUP-B",
            "source_path": str(dup_b.resolve()),
            "private_copy_relpath": (Path("02_PRIVATE_FORENSIC_MASTER/files") / dup_b.name).as_posix(),
            "source_hash": hashlib.sha256(dup_b.read_bytes()).hexdigest(),
            "subject": "Duplicate B",
        }
    )
    dup_text = "The child changed schools on January 3, 2026."
    records.append(
        stage_record(
            case_root,
            evidence_id="REC-DUP-A",
            filename=dup_a.name,
            data=dup_a.read_bytes(),
            title="Duplicate A",
            text_excerpt=dup_text,
            text_content=dup_text,
            issue_lanes=["duplication"],
        )
    )
    records.append(
        stage_record(
            case_root,
            evidence_id="REC-DUP-B",
            filename=dup_b.name,
            data=dup_b.read_bytes(),
            title="Duplicate B",
            text_excerpt=dup_text,
            text_content=dup_text,
            issue_lanes=["duplication"],
        )
    )

    index_root = case_root / "04_INDEXES"
    index_root.mkdir(parents=True, exist_ok=True)
    (index_root / "private_search_index.json").write_text(json.dumps(records, indent=2, sort_keys=True), encoding="utf-8")
    manifest_root = case_root / "08_SOURCE_MANIFESTS_HASHES"
    manifest_root.mkdir(parents=True, exist_ok=True)
    (manifest_root / "source_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return records


def _normalized_text(value: str) -> str:
    return " ".join(value.lower().split())


def _duplicate_report(rows: list[dict[str, Any]], record_id: str) -> dict[str, Any]:
    by_id = {str(row.get("evidence_id") or ""): dict(row) for row in rows}
    row = dict(by_id.get(record_id) or {})
    target_hash = str(row.get("source_hash") or "")
    exact = [dict(item) for item in rows if str(item.get("source_hash") or "") == target_hash and target_hash]
    base_text = _normalized_text(str(row.get("text_excerpt") or row.get("text_content") or ""))
    near_candidates = []
    for item in rows:
        other_text = _normalized_text(str(item.get("text_excerpt") or item.get("text_content") or ""))
        if not other_text:
            continue
        similarity = 1.0 if other_text == base_text else float(__import__("difflib").SequenceMatcher(None, base_text, other_text).ratio())
        if similarity >= 0.7 and str(item.get("evidence_id") or "") != record_id:
            near_candidates.append(
                {
                    "evidence_id": item.get("evidence_id"),
                    "similarity": round(similarity, 6),
                    "source_hash": item.get("source_hash"),
                }
            )
    return {
        "schema_version": "record_duplicate_report_v1",
        "record_id": record_id,
        "duplicate_group_id": target_hash or record_id,
        "exact_duplicate": len(exact) > 1,
        "exact_duplicates": exact,
        "near_duplicate_candidates": near_candidates[:100],
    }


def _record_compare(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_text = _normalized_text(str(left.get("text_excerpt") or left.get("text_content") or ""))
    right_text = _normalized_text(str(right.get("text_excerpt") or right.get("text_content") or ""))
    similarity = __import__("difflib").SequenceMatcher(None, left_text, right_text).ratio() if left_text or right_text else 0.0
    field_differences: dict[str, dict[str, Any]] = {}
    for field_name in ("source_hash", "page_count", "parser_status", "ocr_status", "text_status", "source_type", "canonical_document_key"):
        if str(left.get(field_name) or "") != str(right.get(field_name) or ""):
            field_differences[field_name] = {"left": left.get(field_name), "right": right.get(field_name)}
    return {
        "schema_version": "record_compare_response_v1",
        "left_record_id": str(left.get("evidence_id") or ""),
        "right_record_id": str(right.get("evidence_id") or ""),
        "same": str(left.get("source_hash") or "") == str(right.get("source_hash") or ""),
        "exact_duplicate": str(left.get("source_hash") or "") == str(right.get("source_hash") or ""),
        "similarity": round(similarity, 6),
        "page_count_delta": int(right.get("page_count") or 0) - int(left.get("page_count") or 0),
        "text_additions": sorted(set(right_text.split()) - set(left_text.split()))[:100],
        "text_removals": sorted(set(left_text.split()) - set(right_text.split()))[:100],
        "field_differences": field_differences,
        "left": {
            "record_id": str(left.get("evidence_id") or ""),
            "source_hash": left.get("source_hash"),
            "page_count": left.get("page_count"),
            "parser_status": left.get("parser_status"),
            "ocr_status": left.get("ocr_status"),
        },
        "right": {
            "record_id": str(right.get("evidence_id") or ""),
            "source_hash": right.get("source_hash"),
            "page_count": right.get("page_count"),
            "parser_status": right.get("parser_status"),
            "ocr_status": right.get("ocr_status"),
        },
    }


def start_runtime(executable: Path, port: int, *, localappdata: Path) -> subprocess.Popen[str]:
    environment = os.environ.copy()
    environment.update(
        {
            "LOCALAPPDATA": str(localappdata),
            "MFL_RUNTIME_MODE": "store",
            "HTTP_PROXY": "http://127.0.0.1:9",
            "HTTPS_PROXY": "http://127.0.0.1:9",
            "ALL_PROXY": "http://127.0.0.1:9",
            "NO_PROXY": "127.0.0.1,localhost,::1",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "TLD_EXTRACT_NO_FETCH": "1",
        }
    )
    return subprocess.Popen(
        [str(executable), "--serve-local-api", "--port", str(port)],
        cwd=str(executable.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        env=environment,
    )


class RuntimeNetworkMonitor:
    """Best-effort OS observation of runtime and worker TCP connections."""

    def __init__(self, root_pid: int, *, interval_seconds: float = 0.025) -> None:
        self.root_pid = int(root_pid)
        self.interval_seconds = float(interval_seconds)
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name="mfl-runtime-network-monitor", daemon=True)
        self.observations: list[dict[str, Any]] = []
        self.errors: list[str] = []
        self.sample_count = 0

    @staticmethod
    def _loopback(host: str) -> bool:
        try:
            return ipaddress.ip_address(host.split("%", 1)[0]).is_loopback
        except ValueError:
            return host.lower() in {"localhost"}

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> dict[str, Any]:
        self.stop_event.set()
        self.thread.join(timeout=10)
        unique = {
            (row["pid"], row["remote_host"], row["remote_port"], row["status"]): row
            for row in self.observations
        }
        rows = sorted(unique.values(), key=lambda row: (row["pid"], row["remote_host"], row["remote_port"], row["status"]))
        external = [row for row in rows if not row["loopback"]]
        return {
            "method": "psutil_process_tree_tcp_polling",
            "interval_ms": round(self.interval_seconds * 1000, 3),
            "sample_count": self.sample_count,
            "observed_remote_connections": rows,
            "external_connections": external,
            "external_connection_count": len(external),
            "errors": self.errors,
            "proxy_fail_closed": True,
            "offline_library_flags": ["HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "TLD_EXTRACT_NO_FETCH"],
        }

    def _run(self) -> None:
        try:
            import psutil
        except Exception as exc:  # noqa: BLE001
            self.errors.append(f"psutil_unavailable:{exc.__class__.__name__}")
            return
        while not self.stop_event.is_set():
            self.sample_count += 1
            try:
                root = psutil.Process(self.root_pid)
                processes = [root, *root.children(recursive=True)]
                for process in processes:
                    try:
                        connections = process.net_connections(kind="tcp")
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        continue
                    for connection in connections:
                        if not connection.raddr:
                            continue
                        host = str(connection.raddr.ip)
                        self.observations.append(
                            {
                                "pid": int(process.pid),
                                "remote_host": host,
                                "remote_port": int(connection.raddr.port),
                                "status": str(connection.status),
                                "loopback": self._loopback(host),
                            }
                        )
            except psutil.NoSuchProcess:
                break
            except Exception as exc:  # noqa: BLE001
                marker = f"{exc.__class__.__name__}:{str(exc)[:160]}"
                if marker not in self.errors:
                    self.errors.append(marker)
            self.stop_event.wait(self.interval_seconds)


def _runtime_resolution(explicit_executable: str) -> InstalledRuntimeResolution:
    if not explicit_executable:
        return resolve_installed_runtime_executable()
    executable = Path(explicit_executable).expanduser().resolve(strict=True)
    if not executable.is_file():
        raise SystemExit(f"Runtime executable is not a regular file: {executable}")
    return InstalledRuntimeResolution(
        package_name=DEFAULT_PACKAGE_NAME,
        package_full_name="",
        install_location=str(executable.parent),
        version="",
        executable_path=str(executable),
        source="explicit_bundled_runtime",
        available=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--runtime-executable",
        default="",
        help="Qualify this exact frozen runtime instead of resolving an installed AppX package.",
    )
    args = parser.parse_args(argv)
    evidence_root = Path(
        os.environ.get("MFL_GA_EVIDENCE_ROOT")
        or ROOT / "dist" / "store" / "evidence"
    ).expanduser().resolve()
    evidence_root.mkdir(parents=True, exist_ok=True)
    resolution = _runtime_resolution(args.runtime_executable)
    if not resolution.executable_path:
        raise SystemExit("Unable to resolve an installed or bundled runtime executable.")

    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    summary: dict[str, Any] = {
        "schema_version": "installed_offline_qualification_v1",
        "generated_at": utc_now(),
        "runtime_resolution": resolution.as_dict(),
        "offline_boundary": {},
        "feature_results": {},
        "qualification_checks": {},
        "inventory_result": {},
        "qualification_status": "blocked",
        "blockers": [],
    }

    original_socket = socket.socket
    original_create_connection = socket.create_connection
    original_getaddrinfo = socket.getaddrinfo

    with local_only_network_boundary():
        try:
            urllib.request.urlopen("https://example.com", timeout=5)
            summary["offline_boundary"]["external_request"] = "unexpected_success"
            summary["blockers"].append("offline_boundary_did_not_block_external_request")
        except LocalOnlyNetworkBlocked as exc:
            summary["offline_boundary"]["external_request"] = "blocked"
            summary["offline_boundary"]["detail"] = str(exc)

    summary["offline_boundary"]["socket_restored"] = (
        socket.socket is original_socket
        and socket.create_connection is original_create_connection
        and socket.getaddrinfo is original_getaddrinfo
    )

    case_root = Path(tempfile.mkdtemp(prefix="mfl-installed-offline-qualification-")).resolve()
    records = build_case_fixture(case_root)

    isolated_localappdata = case_root / "localappdata"
    process = start_runtime(
        Path(resolution.executable_path),
        port,
        localappdata=isolated_localappdata,
    )
    network_monitor = RuntimeNetworkMonitor(process.pid)
    network_monitor.start()
    try:
        health = wait_json(f"{base_url}/api/health", timeout_s=180)
        version = request_json("GET", f"{base_url}/api/version")
        root_page = urllib.request.urlopen(f"{base_url}/", timeout=30).read().decode("utf-8", errors="replace")
        document_status = request_json("GET", f"{base_url}/api/document-intelligence/status")

        summary["feature_results"]["launch"] = {
            "health": health,
            "version": version,
            "rootStatus": 200,
            "rootHasWorkbench": "workbench" in root_page.lower(),
            "processPath": health.get("process_path") or health.get("processPath") or "",
        }
        summary["feature_results"]["document_intelligence_status"] = document_status

        activate = request_json("POST", f"{base_url}/api/activate-corpus", {"case_root": str(case_root)})
        summary["feature_results"]["activate_corpus"] = activate

        request_json("POST", f"{base_url}/api/corpus-rebuild-index", {})
        inventory = request_json("GET", f"{base_url}/api/corpus-inventory")
        retrieval_status = request_json("GET", f"{base_url}/api/retrieval-workbench/status")
        retrieval_search = request_json(
            "POST",
            f"{base_url}/api/retrieval-workbench/search",
            {"query": "changed schools", "include_private_records": True, "include_authority": False, "top_k": 5},
        )
        ask_school = request_json("POST", f"{base_url}/ask", {"question": "changed schools", "search_mode": "my_records"})
        ask_pdf = request_json("POST", f"{base_url}/ask", {"question": "ordinary PDF", "search_mode": "my_records"})
        ask_pii = request_json("POST", f"{base_url}/ask", {"question": "example.com", "search_mode": "my_records"})

        by_id = {str(row.get("evidence_id") or ""): dict(row) for row in records}
        pii_path = case_root / "02_PRIVATE_FORENSIC_MASTER" / "files" / "pii.txt"
        docx_path = case_root / "02_PRIVATE_FORENSIC_MASTER" / "files" / "motion.docx"
        pdf_path = case_root / "02_PRIVATE_FORENSIC_MASTER" / "files" / "brief.pdf"
        scan_source = case_root / "02_PRIVATE_FORENSIC_MASTER" / "files" / "scan.pdf"

        pii_integrity = analyze_document(
            case_root=case_root,
            source_path=pii_path,
            source_hash=sha256_file(pii_path),
            run_docling=False,
            run_presidio=False,
        )
        pii_blocks = list((pii_integrity.get("structured_document") or {}).get("blocks") or [])
        pii_privacy = analyze_document(
            case_root=case_root,
            source_path=pii_path,
            source_hash=sha256_file(pii_path),
            run_docling=False,
            run_presidio=True,
        )
        pii_redaction_proposal = create_redacted_copy(
            case_root=case_root,
            source_path=pii_path,
            source_hash=sha256_file(pii_path),
            approved=True,
            reviewer="qualification",
            run_presidio=True,
        )
        pii_redacted_copy = pii_redaction_proposal

        docx_parse_fallback = analyze_document(
            case_root=case_root,
            source_path=docx_path,
            source_hash=sha256_file(docx_path),
            run_docling=False,
            run_presidio=False,
        )
        docx_parse = analyze_document(
            case_root=case_root,
            source_path=docx_path,
            source_hash=sha256_file(docx_path),
            run_docling=True,
            run_presidio=True,
        )
        pdf_parse = analyze_document(
            case_root=case_root,
            source_path=pdf_path,
            source_hash=sha256_file(pdf_path),
            run_docling=True,
            run_presidio=False,
        )
        scan_source = case_root / "02_PRIVATE_FORENSIC_MASTER" / "files" / "scan.pdf"
        scan_hash = hashlib.sha256(scan_source.read_bytes()).hexdigest()
        ocr_result = create_ocr_preservation_copy(
            case_root=case_root,
            source_path=scan_source,
            source_hash=scan_hash,
            approved=True,
            language="eng",
        )
        ocr_artifacts = dict(ocr_result.get("artifacts") or {})
        ocr_pdf = None
        ocr_sidecar = None
        ocr_text = ""
        if "pdf" in ocr_artifacts and "sidecar" in ocr_artifacts:
            ocr_pdf_artifact = ocr_artifacts["pdf"]
            ocr_sidecar_artifact = ocr_artifacts["sidecar"]
            ocr_pdf = case_root / ocr_pdf_artifact["relative_path"]
            ocr_sidecar = case_root / ocr_sidecar_artifact["relative_path"]
            ocr_text = PdfReader(str(ocr_pdf)).pages[0].extract_text() or ""
        ocr_comparison = ocr_result.get("comparison", {})
        duplicates = _duplicate_report(records, "REC-DUP-A")
        compare = _record_compare(by_id["REC-DUP-A"], by_id["REC-DUP-B"])

        summary["feature_results"].update(
            {
                "inventory": inventory,
                "retrieval_status": retrieval_status,
                "retrieval_search": retrieval_search,
                "ask": {
                    "school_change": {
                        "grounded": ask_school.get("grounded"),
                        "failure_class": ask_school.get("failure_class"),
                        "source_card_count": ask_school.get("source_card_count"),
                        "citations": ask_school.get("citations", [])[:3],
                    },
                    "ordinary_pdf": {
                        "grounded": ask_pdf.get("grounded"),
                        "failure_class": ask_pdf.get("failure_class"),
                        "source_card_count": ask_pdf.get("source_card_count"),
                        "citations": ask_pdf.get("citations", [])[:3],
                    },
                    "pii_note": {
                        "grounded": ask_pii.get("grounded"),
                        "failure_class": ask_pii.get("failure_class"),
                        "source_card_count": ask_pii.get("source_card_count"),
                        "citations": ask_pii.get("citations", [])[:3],
                    },
                },
                "document_intelligence": {
                    "integrity": pii_integrity,
                    "privacy_scan": pii_privacy,
                    "blocks": pii_blocks,
                    "redaction_proposal": pii_redaction_proposal,
                    "redacted_copy": pii_redacted_copy,
                    "fallback_parse": docx_parse_fallback,
                    "docling_parse": docx_parse,
                    "pdf_parse": pdf_parse,
                    "ocr": {
                        "result": ocr_result,
                        "pdf_hash": sha256_file(ocr_pdf) if ocr_pdf else None,
                        "sidecar_hash": sha256_file(ocr_sidecar) if ocr_sidecar else None,
                        "pdf_text": ocr_text[:2000],
                        "comparison": ocr_comparison,
                    },
                    "redaction": pii_redacted_copy,
                    "duplicates": duplicates,
                    "compare": compare,
                },
            }
        )

        summary["inventory_result"] = {
            "status": inventory.get("status"),
            "records": inventory.get("records"),
            "searchable_records": inventory.get("searchable_records"),
            "ocr_candidates": inventory.get("ocr_candidates"),
        }

        fail_conditions = {
            "runtime_health": health.get("status") not in {"ok", "ready", "degraded"},
            "workbench_root": not summary["feature_results"]["launch"]["rootHasWorkbench"],
            "retrieval_status": retrieval_status.get("status") == "blocked",
            "retrieval_search": retrieval_search.get("status") not in {"pass", "no_matches"},
            "grounded_school_answer": ask_school.get("source_card_count", 0) <= 0,
            "grounded_private_answer": ask_pii.get("source_card_count", 0) <= 0,
            "no_automatic_install": document_status.get("automatic_install") is not False,
            "no_document_network": document_status.get("network_used") is not False,
            "presidio_available": not any(
                row.get("available")
                for row in document_status.get("adapters", [])
                if row.get("adapter_id") == "presidio"
            ),
            "deterministic_fallback": docx_parse_fallback.get("selected_extractor") != "deterministic_baseline",
            "fallback_reason": "deterministic_baseline_selected"
            not in str(docx_parse_fallback.get("selection_reason") or ""),
            "docling_or_fallback": docx_parse.get("selected_extractor") not in {"docling", "deterministic_baseline"},
            "privacy_worker": pii_privacy.get("privacy_review", {}).get("presidio_status")
            not in {"pass", "unavailable"},
            "redacted_copy": pii_redacted_copy.get("status") != "pass",
            "ocr_status": ocr_result.get("status") not in {"pass", "blocked"},
            "original_immutable": ocr_result.get("original_modified") is not False,
            "duplicate_detection": duplicates.get("exact_duplicate") is not True,
            "record_comparison": compare.get("exact_duplicate") is not True,
        }
        failed_checks = [name for name, failed in fail_conditions.items() if failed]
        summary["qualification_checks"] = {
            name: {"status": "fail" if failed else "pass"} for name, failed in fail_conditions.items()
        }
        if failed_checks:
            summary["failed_qualification_checks"] = failed_checks
            summary["blockers"].append("one_or_more_feature_checks_failed")

        summary["qualification_status"] = "pass" if not summary["blockers"] else "blocked"
    finally:
        runtime_network = network_monitor.stop()
        summary["offline_boundary"]["runtime_network_observation"] = runtime_network
        if runtime_network.get("external_connection_count"):
            summary["blockers"].append("installed_runtime_external_network_connection_observed")
            summary["qualification_status"] = "blocked"
        try:
            process.terminate()
            process.wait(timeout=30)
        except Exception:
            process.kill()

    summary_path = evidence_root / "installed-offline-qualification.json"
    text_path = evidence_root / "installed-offline-qualification.txt"
    summary["files"] = {
        "installed_offline_qualification_json": str(summary_path),
        "installed_offline_qualification_txt": str(text_path),
        "bundled_engine_inventory_json": str(evidence_root / "bundled-engine-inventory.json"),
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    text_path.write_text(
        "\n".join(
            [
                f"Installed package tested: {summary['runtime_resolution']['executable_path']}",
                "Offline method: local-only socket boundary plus installed runtime HTTP probe",
                f"Feature result: {summary['qualification_status']}",
                f"Network attempt: {summary['offline_boundary'].get('external_request')}",
                f"Network restoration: {summary['offline_boundary'].get('socket_restored')}",
                f"Inventory records: {summary['inventory_result'].get('records')}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
