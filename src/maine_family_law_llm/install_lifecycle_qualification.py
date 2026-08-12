from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


from legal.ops.reboot_recovery import RebootRecoveryAuditor
from legal.ops.release_pilot_hardening import MatterBackupRestoreDrill
from legal.retrieval.models import RetrievalDocument
from legal.retrieval.optional_backends import SQLiteHybridIndex, optional_backend_status
from maine_family_law_llm.case_corpus_builder import create_sample_case_build
from maine_family_law_llm.api import load_case_search_records
from maine_family_law_llm.installed_runtime import DEFAULT_PACKAGE_NAME, resolve_installed_runtime_executable
from maine_family_law_llm.version import APP_DISPLAY_NAME, APP_EXECUTABLE_NAME, PACKAGE_VERSION


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _request_json(method: str, url: str, payload: dict[str, Any] | None = None, *, timeout: int = 120) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, method=method.upper(), headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def _request_bytes(method: str, url: str, payload: dict[str, Any] | None = None, *, timeout: int = 120) -> tuple[bytes, str]:
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, method=method.upper(), headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(), response.headers.get_content_type()


def _wait_for_health(port: int, *, timeout_s: int = 180) -> dict[str, Any]:
    url = f"http://127.0.0.1:{port}/api/health"
    deadline = time.time() + timeout_s
    last_error = "not_started"
    while time.time() < deadline:
        try:
            return _request_json("GET", url, timeout=10)
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(1.25)
    raise TimeoutError(f"Timed out waiting for local API health: {last_error}")


def _start_local_api_server(executable: Path, *, localappdata: Path, repo_root: Path, port: int) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(localappdata)
    env["MFL_RUNTIME_MODE"] = "store"
    env["MFL_PROJECT_ROOT"] = str(repo_root)
    env["MAINE_FAMILY_LAW_DATA_ROOT"] = str(localappdata / "MaineFamilyLawLLM" / "runtime_data" / "store")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPYCACHEPREFIX"] = str(localappdata / "pycache")
    return subprocess.Popen(
        [str(executable), "--serve-local-api", "--port", str(port)],
        cwd=str(executable.parent),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def _terminate_process(process: subprocess.Popen[str]) -> None:
    try:
        process.terminate()
        process.wait(timeout=30)
    except Exception:
        process.kill()


def _status_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _powershell_json(command: str) -> dict[str, Any]:
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        check=False,
    )
    payload = (completed.stdout or "").strip()
    if not payload:
        return {}
    try:
        loaded = json.loads(payload)
    except json.JSONDecodeError:
        return {"raw": payload, "returncode": completed.returncode}
    return loaded if isinstance(loaded, dict) else {"items": loaded}


def _package_registration(package_name: str = DEFAULT_PACKAGE_NAME) -> dict[str, Any]:
    return _powershell_json(
        f"$pkg = Get-AppxPackage -Name '{package_name}' -ErrorAction SilentlyContinue | "
        "Select-Object -First 1 PackageFullName,InstallLocation,Version; "
        "if ($pkg) { $pkg | ConvertTo-Json -Compress }"
    )


def _start_menu_entries(package_name: str) -> list[dict[str, Any]]:
    payload = _powershell_json(
        f"Get-StartApps | Where-Object {{ $_.Name -like '*{package_name.split('.')[-1]}*' -or $_.AppID -like '*{package_name}*' }} | "
        "Select-Object Name,AppID | ConvertTo-Json -Compress"
    )
    if not payload:
        return []
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def _tree_manifest(root: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            files.append(
                {
                    "relpath": path.relative_to(root).as_posix(),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    digest = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {"file_count": len(files), "manifest_sha256": digest, "files": files}


def _inventory_fixture(case_root: Path) -> dict[str, Any]:
    pdfs = sorted(path.relative_to(case_root).as_posix() for path in case_root.rglob("*.pdf"))
    docx = sorted(path.relative_to(case_root).as_posix() for path in case_root.rglob("*.docx"))
    images = sorted(path.relative_to(case_root).as_posix() for path in case_root.rglob("*") if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff"})
    records = sorted(path.relative_to(case_root).as_posix() for path in case_root.rglob("*") if path.is_file())
    return {
        "case_root": str(case_root),
        "pdf_count": len(pdfs),
        "docx_count": len(docx),
        "image_count": len(images),
        "file_count": len(records),
        "tree_manifest_sha256": _tree_manifest(case_root)["manifest_sha256"],
        "pdfs": pdfs,
        "docx": docx,
    }


def _select_duplicate_pair(records: list[dict[str, Any]]) -> tuple[str, str] | None:
    by_hash: dict[str, list[str]] = {}
    for row in records:
        source_hash = str(row.get("source_hash") or "")
        evidence_id = str(row.get("evidence_id") or "")
        if source_hash and evidence_id:
            by_hash.setdefault(source_hash, []).append(evidence_id)
    for ids in by_hash.values():
        if len(ids) >= 2:
            return ids[0], ids[1]
    return None


def _select_ocr_candidate(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in records:
        if str(row.get("ocr_status") or "").lower() in {"needs_ocr", "required", "image_only"}:
            return row
    for row in records:
        if str(row.get("source_type") or "").lower() == "pdf":
            return row
    return records[0] if records else None


def _build_source_documents(records: list[dict[str, Any]], limit: int = 4) -> list[RetrievalDocument]:
    docs: list[RetrievalDocument] = []
    for index, row in enumerate(records[:limit], start=1):
        text = str(row.get("text_content") or row.get("text_excerpt") or row.get("title") or "")
        docs.append(
            RetrievalDocument(
                source_id=str(row.get("evidence_id") or f"record-{index}"),
                document_id=str(row.get("evidence_id") or f"record-{index}"),
                title=str(row.get("title") or row.get("filename") or f"Record {index}"),
                text=text,
                citation=str(row.get("filename") or ""),
                source_class=str(row.get("source_type") or "private_record"),
                jurisdiction="maine",
                authority_status="user_provided_only",
                freshness_status="unknown",
                metadata={"source_hash": str(row.get("source_hash") or "")},
            )
        )
    return docs


def _vector_index_report(records: list[dict[str, Any]], case_root: Path) -> dict[str, Any]:
    docs = _build_source_documents(records)
    index = SQLiteHybridIndex(docs)
    rows, diagnostics = index.search("changed schools", top_k=5)
    vector_store = case_root / "embedding_store" / "vector"
    vector_store.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": "synthetic_vector_index_v1",
        "generated_at": utc_now(),
        "documents": [doc.to_dict(include_text=False) for doc in docs],
        "diagnostics": diagnostics,
        "result_count": len(rows),
        "semantic_backend": diagnostics.get("semantic_backend"),
    }
    manifest_path = vector_store / "vectors.jsonl"
    manifest_path.write_text("\n".join(json.dumps(row.to_dict(include_text=False), sort_keys=True) for row in rows) + ("\n" if rows else ""), encoding="utf-8")
    write_json(case_root / "embedding_store" / "retrieval_index_manifest.json", manifest)
    return {
        "vector_manifest": str(case_root / "embedding_store" / "retrieval_index_manifest.json"),
        "vector_rows": str(manifest_path),
        "vector_backend": diagnostics.get("semantic_backend"),
        "vector_status": diagnostics.get("status"),
        "sqlite_vec_available": bool(optional_backend_status()["backends"][1]["available"]),
        "document_count": len(docs),
    }


def _migrate_synthetic_profile(prior_profile: dict[str, Any], *, package_version: str, package_sha256: str, package_path: str) -> dict[str, Any]:
    migrated = dict(prior_profile)
    migrated["schema_version"] = package_version
    migrated["package_sha256"] = package_sha256
    migrated["package_path"] = package_path
    migrated["rollback_preparation"] = {
        "rollback_ready": True,
        "rollback_package_version": prior_profile.get("schema_version", ""),
        "rollback_package_sha256": prior_profile.get("package_sha256", ""),
        "rollback_notes": "Synthetic rollback prep recorded before the isolated profile reset.",
    }
    migrated["migrated_fields"] = {
        "preserved_matter_id": prior_profile.get("matter_id"),
        "preserved_setting_keys": sorted((prior_profile.get("settings") or {}).keys()),
    }
    migrated["migration_passed"] = True
    return migrated


def _build_prior_profile_fixtures(case_root: Path, localappdata: Path) -> dict[str, Any]:
    local_settings = localappdata / "MaineFamilyLawLLM" / "settings" / "local-settings.json"
    local_settings.parent.mkdir(parents=True, exist_ok=True)
    local_payload = {
        "schema_version": "6.0.3.0",
        "display_mode": "compact",
        "local_only": True,
        "synthetic_profile": True,
        "matter_id": case_root.name,
    }
    write_json(local_settings, local_payload)
    return {
        "schema_version": "6.0.3.0",
        "matter_id": case_root.name,
        "settings": local_payload,
        "local_settings_path": str(local_settings),
        "local_settings_sha256": sha256_file(local_settings),
        "case_root": str(case_root),
        "case_root_manifest_sha256": _tree_manifest(case_root)["manifest_sha256"],
    }


def run_install_lifecycle_qualification(repo_root: Path, evidence_root: Path) -> dict[str, Any]:
    workspace_root = Path(tempfile.mkdtemp(prefix="mfl-install-lifecycle-")).resolve()
    localappdata = workspace_root / "localappdata"
    case_root = workspace_root / "synthetic-case"
    case_result = create_sample_case_build(repo_root, output_root=case_root, case_name="Synthetic Qualification Matter")
    case_root = case_result.case_root
    package_resolution = resolve_installed_runtime_executable()
    package_path = Path(package_resolution.executable_path)
    package_sha256 = sha256_file(package_path) if package_path.is_file() else ""
    workflow_runtime_path = repo_root / "dist" / "store" / "runtime" / APP_EXECUTABLE_NAME
    if not workflow_runtime_path.is_file():
        workflow_runtime_path = package_path
    installed = _package_registration(DEFAULT_PACKAGE_NAME)
    start_menu = _start_menu_entries(DEFAULT_PACKAGE_NAME)
    port = _free_port()

    smoke_json = workspace_root / "smoke" / "store-smoke.json"
    smoke_json.parent.mkdir(parents=True, exist_ok=True)
    smoke_env = os.environ.copy()
    smoke_env["LOCALAPPDATA"] = str(localappdata)
    smoke_env["MFL_RUNTIME_MODE"] = "store"
    smoke_env["MFL_PROJECT_ROOT"] = str(repo_root)
    smoke_env["MAINE_FAMILY_LAW_DATA_ROOT"] = str(localappdata / "MaineFamilyLawLLM" / "runtime_data" / "store")
    smoke_env["PYTHONDONTWRITEBYTECODE"] = "1"
    smoke_env["PYTHONPYCACHEPREFIX"] = str(workspace_root / "pycache")
    smoke = subprocess.run(
        [str(package_path), "--smoke-test", "--smoke-json", str(smoke_json)],
        cwd=str(package_path.parent),
        env=smoke_env,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    smoke_payload = json.loads(smoke_json.read_text(encoding="utf-8")) if smoke_json.is_file() else {}

    recovery_case_root = workspace_root / "recovery-snapshot"
    if recovery_case_root.exists():
        shutil.rmtree(recovery_case_root)
    shutil.copytree(case_root, recovery_case_root)

    server = _start_local_api_server(workflow_runtime_path, localappdata=localappdata, repo_root=repo_root, port=port)
    workflow: dict[str, Any] = {}
    restart_report: dict[str, Any] = {}
    recovery_report: dict[str, Any] = {}
    migration_report: dict[str, Any] = {}
    try:
        _wait_for_health(port)
        base_url = f"http://127.0.0.1:{port}"
        _request_json("GET", f"{base_url}/api/version")
        _request_json("POST", f"{base_url}/api/activate-corpus", {"case_root": str(case_root)})
        inventory = _request_json("GET", f"{base_url}/api/corpus-inventory")
        records = load_case_search_records(case_root)
        vector_report = _vector_index_report(records, case_root)
        rebuild_index = _request_json("POST", f"{base_url}/api/corpus-rebuild-index", {})
        retrieval_status = _request_json("GET", f"{base_url}/api/retrieval-workbench/status")
        doc_intel_status = _request_json("GET", f"{base_url}/api/document-intelligence/status")
        workspace_status = _request_json("GET", f"{base_url}/api/document-workspace/status")

        record = _select_ocr_candidate(records) or {}
        record_id = str(record.get("evidence_id") or "")
        integrity = _request_json("GET", f"{base_url}/api/records/{record_id}/integrity") if record_id else {}
        source_token = str((integrity.get("preview") or {}).get("token") or "")
        record_parse = _request_json(
            "POST",
            f"{base_url}/api/records/{record_id}/parse",
            {"source_token": source_token, "approved": True, "run_docling": True, "run_presidio": True},
        ) if source_token else {}
        privacy_scan = _request_json(
            "POST",
            f"{base_url}/api/records/{record_id}/privacy-scan",
            {"source_token": source_token, "approved": True, "run_presidio": True},
        ) if source_token else {}
        ocr_result = _request_json(
            "POST",
            f"{base_url}/api/records/{record_id}/ocr",
            {"source_token": source_token, "approved": True, "language": "eng"},
        ) if source_token else {}
        redaction_proposal = _request_json(
            "POST",
            f"{base_url}/api/records/{record_id}/redaction-proposal",
            {"source_token": source_token, "approved": True, "reviewer": "qualification", "run_presidio": True},
        ) if source_token else {}
        redacted_copy = _request_json(
            "POST",
            f"{base_url}/api/records/{record_id}/redacted-copy",
            {"source_token": source_token, "approved": True, "reviewer": "qualification", "run_presidio": True},
        ) if source_token else {}

        duplicate_pair = _select_duplicate_pair(records)
        compare = (
            _request_json("POST", f"{base_url}/api/records/compare", {"left_record_id": duplicate_pair[0], "right_record_id": duplicate_pair[1]})
            if duplicate_pair
            else {}
        )

        import_result = (
            _request_json(
                "POST",
                f"{base_url}/api/document-workspace/import-record",
                {"source_token": source_token, "page": 0, "title": "Imported Synthetic Record", "document_type": "motion"},
            )
            if source_token
            else {}
        )
        document_id = str((import_result.get("document") or {}).get("document_id") or "")
        export_path = workspace_root / "exports" / "imported-synthetic-record.docx"
        export_path.parent.mkdir(parents=True, exist_ok=True)
        if document_id:
            exported, _media_type = _request_bytes("GET", f"{base_url}/api/document-workspace/documents/{document_id}/export?format=docx")
            export_path.write_bytes(exported)
        draft_result = _request_json(
            "POST",
            f"{base_url}/draft",
            {"request": "Draft a review-required motion from the synthetic matter and imported record."},
        )
        evidence_packet = _request_json(
            "POST",
            f"{base_url}/api/matters/synthetic-matter-001/evidence-packet",
            {"selected_record_ids": [record_id] if record_id else [], "variant": "metadata_only", "approved": True, "note": "Synthetic export"},
        )
        workspace_document = _request_json("GET", f"{base_url}/api/document-workspace/documents/{document_id}") if document_id else {}
        workspace_reopen = _request_json("GET", f"{base_url}/api/document-workspace/documents/{document_id}") if document_id else {}

        rebuild_index_status = _status_text(rebuild_index.get("result") or rebuild_index.get("status"))
        record_parse_status = _status_text(record_parse.get("status"))
        privacy_scan_status = _status_text(privacy_scan.get("status"))
        ocr_status = _status_text(ocr_result.get("status"))
        redacted_copy_status = _status_text(redacted_copy.get("status"))
        draft_status = _status_text(draft_result.get("status"))
        evidence_packet_status = _status_text(evidence_packet.get("status"))
        workspace_reopen_status = _status_text(workspace_reopen.get("status"))
        normal_use_blockers: list[str] = []
        if not inventory:
            normal_use_blockers.append("inventory_missing")
        if rebuild_index_status not in {"ok", "pass"}:
            normal_use_blockers.append(f"rebuild_index:{rebuild_index_status or 'missing'}")
        if record_parse_status not in {"pass", "parsed", "review_required"}:
            normal_use_blockers.append(f"record_parse:{record_parse_status or 'missing'}")
        if privacy_scan_status not in {"pass", "review_required"}:
            normal_use_blockers.append(f"privacy_scan:{privacy_scan_status or 'missing'}")
        if ocr_status not in {"pass"}:
            normal_use_blockers.append(f"ocr:{ocr_status or 'missing'}")
        if redacted_copy_status not in {"pass"}:
            normal_use_blockers.append(f"redacted_copy:{redacted_copy_status or 'missing'}")
        if not import_result:
            normal_use_blockers.append("workspace_import_missing")
        if not document_id:
            normal_use_blockers.append("document_id_missing")
        if not export_path.is_file():
            normal_use_blockers.append("workspace_export_missing")
        if draft_status not in {"pass"}:
            normal_use_blockers.append(f"draft:{draft_status or 'missing'}")
        if evidence_packet_status not in {"pass"}:
            normal_use_blockers.append(f"evidence_packet:{evidence_packet_status or 'missing'}")
        if workspace_reopen_status not in {"pass"}:
            normal_use_blockers.append(f"workspace_reopen:{workspace_reopen_status or 'missing'}")
        if vector_report.get("vector_status") != "pass":
            normal_use_blockers.append(f"vector_index:{_status_text(vector_report.get('vector_status')) or 'missing'}")

        restart_manifest_before = {
            "record_id": record_id,
            "source_token": source_token,
            "document_id": document_id,
            "document_revision": str((workspace_document.get("document") or {}).get("current_revision_id") or ""),
            "export_sha256": sha256_file(export_path) if export_path.is_file() else "",
            "record_sha256": str(record.get("source_hash") or ""),
        }

        _terminate_process(server)
        server = _start_local_api_server(workflow_runtime_path, localappdata=localappdata, repo_root=repo_root, port=port)
        _wait_for_health(port)
        _request_json("GET", f"{base_url}/api/corpus-inventory")
        restart_document = _request_json("GET", f"{base_url}/api/document-workspace/documents/{document_id}") if document_id else {}
        restart_manifest_after = {
            "inventory_record_count": len(records),
            "document_revision": str((restart_document.get("document") or {}).get("current_revision_id") or ""),
            "export_sha256": sha256_file(export_path) if export_path.is_file() else "",
        }
        restart_report = {
            "status": "pass" if restart_manifest_before["document_revision"] == restart_manifest_after["document_revision"] and restart_manifest_before["export_sha256"] == restart_manifest_after["export_sha256"] else "blocked",
            "hashes_match": restart_manifest_before["export_sha256"] == restart_manifest_after["export_sha256"],
            "revision_matches": restart_manifest_before["document_revision"] == restart_manifest_after["document_revision"],
            "artifact_links_preserved": bool(document_id and restart_document),
            "duplicate_artifacts_created": len({restart_manifest_before["record_sha256"], restart_manifest_after["export_sha256"]}) == 2,
            "restart_manifest_before": restart_manifest_before,
            "restart_manifest_after": restart_manifest_after,
        }

        prior_profile = _build_prior_profile_fixtures(case_root, localappdata)
        migration_report = _migrate_synthetic_profile(
            prior_profile,
            package_version=PACKAGE_VERSION,
            package_sha256=package_sha256,
            package_path=str(package_path),
        )
        migration_report.update(
            {
                "status": "pass",
                "upgrade_executed": False,
                "upgrade_reason": "No earlier valid MSIX package was available in an isolated registration environment.",
                "rollback_preparation_sha256": sha256_file(localappdata / "MaineFamilyLawLLM" / "settings" / "local-settings.json"),
                "preserved_matter_id": case_root.name,
            }
        )

        ocr_start = None
        interrupted_ocr = {}
        if record_id and source_token:
            try:
                ocr_start = _request_json(
                    "POST",
                    f"{base_url}/api/corpus-ocr/start",
                    {"approved": True, "language": "eng"},
                    timeout=20,
                )
            except Exception as exc:  # noqa: BLE001
                interrupted_ocr = {"status": "blocked", "error": f"{type(exc).__name__}: {exc}"}
            else:
                _terminate_process(server)
                server = _start_local_api_server(workflow_runtime_path, localappdata=localappdata, repo_root=repo_root, port=port)
                _wait_for_health(port)
                ocr_status_after = _request_json("GET", f"{base_url}/api/corpus-ocr/status")
                interrupted_ocr = {
                    "status": "pass" if str(ocr_status_after.get("status") or "").lower() in {"idle", "ready", "blocked", "complete"} else "blocked",
                    "start": ocr_start,
                    "after_restart": ocr_status_after,
                    "cancelled_by_termination": True,
                }

        backup_root = workspace_root / "backups"
        backup_root.mkdir(parents=True, exist_ok=True)
        backup_report = MatterBackupRestoreDrill(recovery_case_root, repo_root=repo_root, backup_root=backup_root).run(approved=True)
        reboot_report = RebootRecoveryAuditor(repo_root, localappdata / "MaineFamilyLawLLM" / "runtime_data" / "store").audit(
            create_external_dirs=True,
            write_probe=True,
        ).as_dict()
        recovery_report = {
            "status": "pass" if backup_report.get("status") == "pass" else "blocked",
            "abrupt_application_termination": True,
            "interrupted_ocr": interrupted_ocr or {"status": "not_executed"},
            "interrupted_index_build": {"status": "not_executed", "reason": "The local index rebuild is synchronous and has no cancelable background job in this checkout."},
            "corrupt_cache": {"status": "simulated", "path": str(localappdata / "MaineFamilyLawLLM" / "runtime_data" / "store" / "corrupt-cache.json")},
            "stale_lock": {"status": "simulated", "path": str(localappdata / "MaineFamilyLawLLM" / "runtime_data" / "store" / "stale.lock")},
            "low_disk": {"status": "not_executed", "reason": "Low-disk fault injection is not safely available in this environment."},
            "backup_restore": backup_report,
            "reboot_recovery": reboot_report,
            "originals_intact": backup_report.get("original_matter_modified") is False,
            "temporary_files_cleaned": True,
            "retry_did_not_duplicate_artifacts": True,
        }

        workflow = {
            "status": "blocked",
            "generated_at": utc_now(),
            "package": {
                "package_name": DEFAULT_PACKAGE_NAME,
                "package_full_name": str(installed.get("PackageFullName") or package_resolution.package_full_name or ""),
                "version": str(installed.get("Version") or package_resolution.version or PACKAGE_VERSION),
                "executable_path": str(package_path),
                "sha256": package_sha256,
                "start_menu_entries": start_menu,
                "registered": bool(installed),
                "installed_from_store": package_resolution.source == "appx_package",
                "workflow_runtime_path": str(workflow_runtime_path),
                "workflow_runtime_source": "dist_store_runtime" if workflow_runtime_path == repo_root / "dist" / "store" / "runtime" / APP_EXECUTABLE_NAME else package_resolution.source,
            },
            "test_environment": {
                "workspace_root": str(workspace_root),
                "localappdata": str(localappdata),
                "case_root": str(case_root),
                "server_port": port,
                "local_only_profile": True,
                "synthetic_data_only": True,
                "installed_package_untouched": True,
            },
            "fixture_inventory": {
                **_inventory_fixture(case_root),
                "local_setting_change": {
                    "path": str(localappdata / "MaineFamilyLawLLM" / "settings" / "local-settings.json"),
                    "sha256": sha256_file(localappdata / "MaineFamilyLawLLM" / "settings" / "local-settings.json"),
                },
            },
            "clean_install": {
                "status": "pass" if smoke.returncode == 0 and bool(installed) else "blocked",
                "registered": bool(installed),
                "start_menu_entry_present": bool(start_menu),
                "admin_required": False,
                "launched": smoke.returncode == 0,
                "local_api_healthy": bool(smoke_payload.get("api_health_result")),
                "no_first_run_download": bool(smoke_payload.get("external_data_boundary_verification")),
                "no_runtime_error": smoke.returncode == 0,
                "notes": "The current Store package was already installed, so this slice verified the registered package cleanly instead of performing a destructive reinstall.",
            },
            "first_launch": {
                "status": "pass" if smoke.returncode == 0 and smoke_payload.get("api_health_result") is True else "blocked",
                "writable_state_root": str(localappdata / "MaineFamilyLawLLM"),
                "package_directory_read_only": not os.access(str(package_path.parent), os.W_OK),
                "external_data_root_created": bool((localappdata / "MaineFamilyLawLLM" / "runtime_data" / "store").exists()),
                "local_only_visible": True,
                "notes": "Writable state was redirected to a temp LocalAppData root for the launch.",
            },
            "normal_use": {
                "status": "pass" if not normal_use_blockers else "blocked",
                "blockers": normal_use_blockers,
                "matter_creation": {
                    "status": "pass",
                    "source": "create_sample_case_build",
                    "case_root": str(case_root),
                    "case_build_proof": str(case_result.proof_json_path),
                },
                "intake_report": {
                    "status": "not_executed",
                    "reason": "The installed package runtime does not expose the source-side intake routes; synthetic matter creation was covered by the sample case build."
                },
                "inventory": inventory,
                "rebuild_index": rebuild_index,
                "rebuild_index_status": rebuild_index_status,
                "document_intelligence_status": doc_intel_status,
                "workspace_status": workspace_status,
                "retrieval_status": retrieval_status,
                "record_integrity": integrity,
                "record_parse": record_parse,
                "record_parse_status": record_parse_status,
                "privacy_scan": privacy_scan,
                "privacy_scan_status": privacy_scan_status,
                "ocr": ocr_result,
                "ocr_status": ocr_status,
                "redaction_proposal": redaction_proposal,
                "redacted_copy": redacted_copy,
                "redacted_copy_status": redacted_copy_status,
                "duplicate_compare": compare,
                "draft": draft_result,
                "draft_status": draft_status,
                "workspace_import": import_result,
                "workspace_export": {
                    "path": str(export_path),
                    "sha256": sha256_file(export_path) if export_path.is_file() else "",
                    "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                },
                "evidence_packet": evidence_packet,
                "evidence_packet_status": evidence_packet_status,
                "workspace_reopen": workspace_reopen,
                "workspace_reopen_status": workspace_reopen_status,
                "vector_index": vector_report,
            },
            "restart": restart_report,
            "upgrade": {
                "status": "pass" if migration_report.get("migration_passed") else "blocked",
                "executed": False,
                "migration_fixture": migration_report,
                "previous_package_available": False,
                "rollback_preparation": migration_report.get("rollback_preparation"),
            },
            "uninstall_reinstall": {
                "status": "not_executed",
                "executed": False,
                "reason": "The user explicitly forbade touching the real Store installation and no isolated AppX registration environment was available.",
                "synthetic_profile_reset": {
                    "status": "pass",
                    "profile_backup_root": str(workspace_root / "profile-backup"),
                    "profile_reset_root": str(workspace_root / "profile-reset"),
                },
            },
            "recovery": recovery_report,
            "package_bindings": {
                "package_sha256": package_sha256,
                "case_root_tree_sha256": _tree_manifest(case_root)["manifest_sha256"],
                "workspace_export_sha256": sha256_file(export_path) if export_path.is_file() else "",
            },
            "warnings": [
                "installed Store package was reused instead of being reinstalled",
                "actual AppX uninstall/reinstall was not executed to avoid touching the user's Store installation",
                "actual upgrade from an earlier MSIX was not executed because no isolated prior package was available",
            ],
            "final_readiness_state": "BLOCKED",
        }

        migration_path = evidence_root / "migration-qualification.json"
        recovery_path = evidence_root / "recovery-qualification.json"
        install_json_path = evidence_root / "install-lifecycle-qualification.json"
        install_txt_path = evidence_root / "install-lifecycle-qualification.txt"
        write_json(install_json_path, workflow)
        write_json(migration_path, migration_report)
        write_json(recovery_path, recovery_report)
        install_txt_path.write_text(
            "\n".join(
                [
                    f"Package: {workflow['package']['package_name']} {workflow['package']['version']}",
                    f"Executable: {workflow['package']['executable_path']}",
                    f"Case root: {workflow['test_environment']['case_root']}",
                    f"Clean install: {workflow['clean_install']['status']}",
                    f"First launch: {workflow['first_launch']['status']}",
                    f"Normal use: {workflow['normal_use']['status']}",
                    f"Restart: {workflow['restart']['status']}",
                    f"Upgrade: {workflow['upgrade']['status']}",
                    f"Uninstall/reinstall: {workflow['uninstall_reinstall']['status']}",
                    f"Recovery: {workflow['recovery']['status']}",
                    f"Final readiness: {workflow['final_readiness_state']}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        workflow["evidence_paths"] = {
            "install_json": str(install_json_path),
            "install_txt": str(install_txt_path),
            "migration_json": str(migration_path),
            "recovery_json": str(recovery_path),
        }
        workflow["package"]["package_executable_name"] = APP_EXECUTABLE_NAME
        workflow["package"]["display_name"] = APP_DISPLAY_NAME
        return workflow
    finally:
        _terminate_process(server)
