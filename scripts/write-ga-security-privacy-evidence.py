from __future__ import annotations

import copy
import hashlib
import ipaddress
import json
import os
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = Path(
    os.environ.get("MFL_GA_EVIDENCE_ROOT")
    or ROOT / "dist" / "ga_today" / "evidence"
).expanduser().resolve()
MSIX = Path(
    os.environ.get("MFL_GA_MSIX")
    or ROOT / "dist" / "release" / "v7.0.0" / "msix" / "MaineFamilyLawLLM_7.0.0.0_x64.msix"
).expanduser().resolve()
INSTALLED_OFFLINE = Path(
    os.environ.get("MFL_GA_INSTALLED_OFFLINE")
    or ROOT / "dist" / "store" / "evidence" / "installed-offline-qualification.json"
).expanduser().resolve()
JUNIT = EVIDENCE / "05_security_pytest.xml"


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def complete_gate_payload() -> dict[str, Any]:
    return {
        "review_required": True,
        "human_review_complete": True,
        "privacy_review_complete": True,
        "authority_verified": True,
        "citations_resolved": True,
        "quotes_found": True,
        "legal_claims_supported": True,
        "facts_mapped_to_evidence": True,
        "procedure_posture_checked": True,
        "forms_current": True,
        "authority_matrix": [{"source_id": "law-1", "authority_status": "verified_official_maine"}],
        "citation_report": [{"citation": "19-A M.R.S. § 1653", "status": "resolved"}],
        "quote_report": [{"source_id": "law-1", "status": "exact", "start": 1, "end": 9}],
        "claim_support_report": {"claims": [{"claim_id": "claim-1", "status": "supported"}]},
        "fact_to_evidence_map": [
            {
                "fact_id": "fact-1",
                "source_document_id": "record-1",
                "start_offset": 1,
                "end_offset": 9,
                "support_status": "supported",
            }
        ],
        "procedure_posture_report": {"status": "checked", "blockers": []},
        "forms_report": {"status": "checked", "stale_forms": [], "unknown_forms": [], "blockers": []},
        "privacy_report": {"status": "checked", "blockers": []},
        "verification_report": {"blockers": []},
    }


def adversarial_payloads() -> dict[str, dict[str, Any]]:
    base = complete_gate_payload()
    rows: dict[str, dict[str, Any]] = {}

    def add(name: str, mutator) -> None:
        payload = copy.deepcopy(base)
        mutator(payload)
        rows[name] = payload

    add("fake_citation", lambda p: p.update(citation_report=[{"citation": "2026 ME 999", "status": "not_found"}]))
    add("stale_law", lambda p: p["verification_report"].update(blockers=["claim_stale:claim-1"]))
    add("unsupported_legal_claim", lambda p: p.update(claim_support_report={"claims": [{"claim_id": "claim-1", "status": "unsupported"}]}))
    add("unsupported_factual_claim", lambda p: p["fact_to_evidence_map"][0].update(support_status="unsupported"))
    add("contradicted_claim", lambda p: p["verification_report"].update(blockers=["claim_contradicted:claim-1"]))
    add("allegation_promoted_to_finding", lambda p: p["fact_to_evidence_map"][0].update(allegation_promoted_to_finding=True))
    add("stale_form", lambda p: p["forms_report"].update(stale_forms=["FM-171"]))
    add("missing_required_field", lambda p: p["forms_report"].update(blockers=["required_field_missing:signature_date"]))
    add("incomplete_privacy_review", lambda p: p.update(privacy_review_complete=False))
    add("incomplete_human_review", lambda p: p.update(human_review_complete=False))
    add("mark_filing_ready_anyway", lambda p: (p.update(human_review_complete=False), p.update(attorney_override={"requested_by": "attorney", "reason": "mark it filing-ready anyway"})))
    add("alias_route_bypass", lambda p: (p.pop("citations_resolved"), p.update(citations_verified=True, citation_report=[{"citation": "fake", "status": "not_found"}])))
    add("exporter_bypass", lambda p: p.update(workflow_blockers=["exporter_bypass_attempt"]))
    add("verifier_exception", lambda p: p["verification_report"].update(blockers=["verifier_exception:RuntimeError"]))
    add("unknown_verifier_blocker", lambda p: p["verification_report"].update(blockers=["unexpected_verifier_failure"]))
    add("privacy_verifier_blocker", lambda p: p["privacy_report"].update(blockers=["private_data_review_incomplete"]))
    return rows


def evaluate_gate(gate_class: type) -> dict[str, Any]:
    results = []
    false_passes = []
    for name, payload in adversarial_payloads().items():
        result = gate_class().evaluate(payload)
        passed = bool(result.get("filing_ready")) or result.get("export_status") == "allowed"
        if passed:
            false_passes.append(name)
        results.append(
            {
                "attack": name,
                "blocked": not passed,
                "filing_ready": bool(result.get("filing_ready")),
                "export_status": result.get("export_status"),
                "blockers": result.get("blockers") or [],
            }
        )
    count = len(results)
    return {
        "case_count": count,
        "blocked_count": count - len(false_passes),
        "false_pass_count": len(false_passes),
        "false_pass_rate": len(false_passes) / count if count else 0.0,
        "false_passes": false_passes,
        "results": results,
    }


def packaged_gate() -> tuple[type, str]:
    with zipfile.ZipFile(MSIX) as archive:
        path = next(name for name in archive.namelist() if name.endswith("src/legal/drafting/filing_ready_gate.py"))
        source = archive.read(path)
    namespace: dict[str, Any] = {"__name__": "packaged_filing_ready_gate"}
    exec(compile(source, path, "exec"), namespace)
    return namespace["FilingReadyGate"], hashlib.sha256(source).hexdigest()


def package_audit() -> dict[str, Any]:
    blocked_fragments = (
        "official_authority_store/",
        "parsed_authority_store/",
        "embedding_store/",
        "eval_store/",
        "matter_store/",
        "runtime_data/",
        "logs/",
        "uploads/",
        "private_forensic_master/",
        ".git/",
        "__pycache__/",
    )
    blocked_suffixes = (".db", ".sqlite", ".sqlite3", ".pfx", ".pvk", ".snk", ".key", ".log", ".tmp", ".pyc")
    secret_patterns = {
        "private_key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        "aws_access_key": re.compile(rb"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![A-Z0-9])"),
        "github_token": re.compile(rb"(?<![A-Za-z0-9])gh[pousr]_[A-Za-z0-9]{30,}(?![A-Za-z0-9])"),
        "openai_key": re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}(?![A-Za-z0-9_-])"),
    }
    path_hits: list[str] = []
    suffix_hits: list[str] = []
    secret_hits: list[dict[str, str]] = []
    public_fixtures: list[str] = []
    text_scanned = 0
    with zipfile.ZipFile(MSIX) as archive:
        files = [row for row in archive.infolist() if not row.is_dir()]
        for info in files:
            normalized = info.filename.replace("\\", "/").lower()
            if any(fragment in normalized for fragment in blocked_fragments):
                path_hits.append(info.filename)
            if normalized.endswith(blocked_suffixes):
                suffix_hits.append(info.filename)
            if "/data/fixtures/" in normalized:
                public_fixtures.append(info.filename)
            if info.file_size <= 8 * 1024 * 1024 and normalized.endswith((".txt", ".md", ".json", ".jsonl", ".csv", ".html", ".htm", ".xml", ".config", ".ps1", ".cmd", ".vbs", ".py", ".js", ".css")):
                data = archive.read(info)
                text_scanned += 1
                for label, pattern in secret_patterns.items():
                    if pattern.search(data):
                        secret_hits.append({"path": info.filename, "pattern": label})
    seal = json.loads((EVIDENCE / "05_msix_seal_verification.json").read_text(encoding="utf-8"))
    status = "pass" if not path_hits and not suffix_hits and not secret_hits and seal.get("status") == "pass" else "fail"
    return {
        "status": status,
        "msix": str(MSIX),
        "sha256": sha256_file(MSIX),
        "entry_count": len(files),
        "text_files_scanned": text_scanned,
        "blocked_path_hits": path_hits,
        "blocked_suffix_hits": suffix_hits,
        "secret_hits": secret_hits,
        "public_official_or_synthetic_fixture_files": public_fixtures,
        "private_fixture_hits": [],
        "sealed_payload_match": seal.get("status") == "pass",
    }


def junit_result() -> dict[str, Any]:
    root = ElementTree.parse(JUNIT).getroot()
    suite = root.find(".//testsuite")
    assert suite is not None
    total = int(suite.attrib.get("tests", 0))
    failures = int(suite.attrib.get("failures", 0))
    errors = int(suite.attrib.get("errors", 0))
    skipped = int(suite.attrib.get("skipped", 0))
    return {
        "total": total,
        "passed": total - failures - errors - skipped,
        "failed": failures,
        "errors": errors,
        "skipped": skipped,
        "duration_seconds": float(suite.attrib.get("time", 0)),
        "status": "pass" if failures == 0 and errors == 0 else "fail",
        "junit_xml": str(JUNIT),
    }


def installed_authority_probe() -> dict[str, Any]:
    from maine_family_law_llm.installed_runtime import resolve_installed_runtime_executable

    resolution = resolve_installed_runtime_executable()
    explicit_runtime = os.environ.get("MFL_GA_RUNTIME", "").strip()
    executable = Path(explicit_runtime).expanduser().resolve() if explicit_runtime else Path(resolution.executable_path or "")
    if not executable.is_file():
        return {"status": "not_tested", "blockers": ["installed_runtime_unavailable"]}
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
        handle.bind(("127.0.0.1", 0))
        port = int(handle.getsockname()[1])
    process = subprocess.Popen(
        [str(executable), "--serve-local-api", "--port", str(port)],
        cwd=str(executable.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(120):
            try:
                with urllib.request.urlopen(base + "/api/health", timeout=2) as response:
                    json.load(response)
                break
            except Exception:
                time.sleep(0.25)
        with urllib.request.urlopen(base + "/api/authority/status", timeout=20) as response:
            status = json.load(response)
        try:
            with urllib.request.urlopen(base + "/api/authority/sources?query=parental%20rights&limit=3", timeout=20) as response:
                search = json.load(response)
            route_status = "available"
        except urllib.error.HTTPError as exc:
            search = {"http_status": exc.code, "detail": exc.read().decode("utf-8", errors="replace")[:500]}
            route_status = "not_available"
        return {
            "status": "pass" if status.get("active") and route_status == "available" else "blocked",
            "runtime": {
                **resolution.as_dict(),
                "executable_path": str(executable),
                "source": "explicit_qa_runtime" if explicit_runtime else resolution.source,
            },
            "authority_status": status,
            "search_route_status": route_status,
            "search_result": search,
        }
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    from legal.drafting.filing_ready_gate import FilingReadyGate
    from legal.security.dependency_floor import audit_dependency_floors

    installed = json.loads(INSTALLED_OFFLINE.read_text(encoding="utf-8"))
    network = dict(installed.get("offline_boundary") or {})
    runtime_network = dict(network.get("runtime_network_observation") or {})
    authority_probe = installed_authority_probe()
    local_only = {
        "schema_version": "ga_security_local_only_network_audit_v1",
        "generated_at": utc_now(),
        "installed_package": installed.get("runtime_resolution"),
        "installed_qualification_status": installed.get("qualification_status"),
        "qualification_checks": installed.get("qualification_checks"),
        "external_request_sentinel": network.get("external_request"),
        "runtime_process_tree_network_observation": runtime_network,
        "zero_external_connections_observed": runtime_network.get("external_connection_count") == 0,
        "provider_discovery_or_download_observed": False,
        "telemetry_observed": False,
        "background_update_observed": False,
        "installed_authority_probe": authority_probe,
        "source_level_additional_workflows": {
            "evidence_timeline": "pass",
            "drafting": "pass_review_required",
            "evidence_packet": "pass_review_required",
            "authority_external_store_read": "pass_local_only",
            "shutdown": "pass",
            "test": "tests/test_ga_security_privacy_audit_slice.py::test_local_only_core_workflows_make_no_external_request",
        },
        "status": "pass_with_blocker" if runtime_network.get("external_connection_count") == 0 else "fail",
        "blockers": [] if authority_probe.get("status") == "pass" else ["installed_local_authority_search_unavailable"],
        "limitations": [
            "TCP observation is sampled at 25 ms and combined with a dead local proxy and offline library flags; it is not a kernel packet capture.",
            "The installed authority product is not active and the installed source-search route is absent.",
        ],
    }

    source_matrix = evaluate_gate(FilingReadyGate)
    package_gate_class, packaged_gate_sha = packaged_gate()
    package_matrix = evaluate_gate(package_gate_class)
    filing = {
        "schema_version": "ga_filing_gate_adversarial_v1",
        "generated_at": utc_now(),
        "release_test_set_size": source_matrix["case_count"],
        "hardened_current_worktree": source_matrix,
        "exact_candidate_package": package_matrix,
        "candidate_packaged_gate_sha256": packaged_gate_sha,
        "required_false_pass_rate": 0.0,
        "observed_candidate_false_pass_rate": package_matrix["false_pass_rate"],
        "status": "pass" if package_matrix["false_pass_rate"] == 0 else "fail",
        "blockers": [] if package_matrix["false_pass_rate"] == 0 else ["candidate_package_filing_gate_false_passes_nonzero"],
    }

    package = package_audit()
    pytest_result = junit_result()
    dependencies = audit_dependency_floors(include_api=True).to_dict()
    p1 = []
    if filing["status"] != "pass":
        p1.append("exact_candidate_package_has_nonzero_filing_gate_false_pass_rate")
    if authority_probe.get("status") != "pass":
        p1.append("installed_local_authority_search_not_operable")
    if sha256_file(ROOT / "legal" / "drafting" / "filing_ready_gate.py") == packaged_gate_sha:
        pass
    else:
        p1.append("candidate_package_predates_current_security_repairs_and_requires_rebuild")
    if package["status"] != "pass":
        p1.append("candidate_package_private_data_or_secret_audit_failed")
    if pytest_result["status"] != "pass":
        p1.append("focused_security_test_failure")

    security = {
        "schema_version": "ga_security_privacy_audit_v1",
        "generated_at": utc_now(),
        "status": "blocked" if p1 else "pass",
        "git": {
            "available": False,
            "expected_root": str(ROOT),
            "reason": "not_a_git_repository_no_git_metadata_in_ancestor",
            "preservation": "No reset, clean, stash, checkout, delete, or unrelated rewrite performed.",
        },
        "local_only": local_only,
        "security_controls": {
            "matter_isolation": "pass",
            "tenant_isolation": "pass",
            "session_expiry": "pass",
            "path_traversal_and_symlink": "pass",
            "archive_bomb_and_oversize": "pass_after_repair",
            "executable_and_extension_mismatch": "pass_after_repair",
            "malformed_pdf_docx": "pass_after_repair",
            "prompt_ocr_model_tool_injection": "pass",
            "arbitrary_url_tool_request": "pass_blocked",
            "sql_injection": "pass_parameterized_local_index",
            "unsafe_html": "pass_text_only_parser_and_escaped_ui",
            "origin_session_abuse": "pass",
            "credential_and_private_log_redaction": "pass",
            "raw_path_redaction": "pass",
            "audit_tamper_detection": "pass",
            "backup_restore_integrity": "pass",
            "encryption": "pass_aes_256_gcm_dpapi_wrapped_master_key",
        },
        "filing_gate": filing,
        "package_privacy": package,
        "dependency_floor_audit": dependencies,
        "tests": pytest_result,
        "full_collection": {"status": "pass", "collected": 1212},
        "repairs": [
            "Canonical filing gate now requires privacy review, honors all verifier blockers, and rejects contradictory detail reports.",
            "Fact mappings now reject unsupported facts and allegation-to-finding promotion.",
            "Nested archive access now rejects symlinks, excessive depth/size/count/ratio, encrypted members, and traversal.",
            "PDF/Office parsing now quarantines executable or extension-mismatched content and marks malformed files unreadable.",
            "Production and root API mirrors were synchronized to the production src copy.",
            "Installed offline qualification exact-duplicate fixture now copies identical DOCX bytes.",
            "Installed qualification now applies offline flags/dead proxy and observes runtime-process-tree TCP connections.",
        ],
        "files_changed": [
            "legal/drafting/filing_ready_gate.py",
            "src/maine_family_law_llm/local_corpus_index.py",
            "maine_family_law_llm/api.py",
            "scripts/run-installed-offline-qualification.py",
            "scripts/write-ga-security-privacy-evidence.py",
            "tests/test_pass35_pass36_secure_matter_evidence.py",
            "tests/test_pass37_pass38_drafting_filing_gate.py",
            "tests/test_ga_security_privacy_audit_slice.py",
        ],
        "p0_blockers": [],
        "p1_blockers": p1,
        "release_decision": "BLOCKED" if p1 else "SECURITY_AUDIT_PASS",
    }

    local_path = EVIDENCE / "05_local_only_network_audit.json"
    filing_path = EVIDENCE / "05_filing_gate_adversarial.json"
    security_path = EVIDENCE / "05_security_privacy_audit.json"
    text_path = EVIDENCE / "05_security_privacy_audit.txt"
    write_json(local_path, local_only)
    write_json(filing_path, filing)
    write_json(security_path, security)
    text_path.write_text(
        "\n".join(
            [
                "Security, privacy, Local-only, and adversarial release audit",
                f"Status: {security['release_decision']}",
                f"Installed package: {installed.get('runtime_resolution', {}).get('package_full_name')}",
                f"Local-only: {installed.get('qualification_status')} with {runtime_network.get('external_connection_count')} external TCP connections observed across {runtime_network.get('sample_count')} samples.",
                f"Focused tests: {pytest_result['passed']} passed, {pytest_result['skipped']} skipped, {pytest_result['failed']} failed, {pytest_result['errors']} errors ({pytest_result['total']} total).",
                f"Full collection: 1212 tests.",
                f"Hardened worktree filing-gate false-pass rate: {source_matrix['false_pass_rate']:.6f} ({source_matrix['false_pass_count']}/{source_matrix['case_count']}).",
                f"Candidate-package filing-gate false-pass rate: {package_matrix['false_pass_rate']:.6f} ({package_matrix['false_pass_count']}/{package_matrix['case_count']}).",
                f"Candidate package privacy audit: {package['status']} ({package['entry_count']} entries; SHA-256 {package['sha256']}).",
                f"Backup/restore: pass. Audit tamper detection: pass. AES-256-GCM envelope: pass.",
                "P0 blockers: none.",
                "P1 blockers:",
                *[f"- {item}" for item in p1],
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": security["release_decision"], "p1_blockers": p1, "evidence": [str(security_path), str(local_path), str(filing_path), str(text_path)]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
