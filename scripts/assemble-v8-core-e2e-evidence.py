"""Assemble a current, hash-bound v8 core end-to-end evidence matrix.

The installed-offline qualification runner is the action-producing test: it
launches the exact frozen executable, creates a disposable fictional matter,
exercises canonical local APIs, observes the process tree, and writes a
machine-readable result.  This utility makes that result auditable as a set of
journeys without promoting untested workbench controls or external legal
evidence into an E2E claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


class EvidenceInputError(ValueError):
    """Raised when a purported qualification artifact cannot prove a journey."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceInputError(f"{label} is unreadable: {exc}") from exc
    if not isinstance(payload, dict):
        raise EvidenceInputError(f"{label} must contain a JSON object")
    return payload


def nested(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def require_passed_check(qualification: dict[str, Any], check: str) -> None:
    value = nested(qualification, "qualification_checks", check, "status")
    if value != "pass":
        raise EvidenceInputError(f"qualification check is not passed: {check}")


def portable(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def journey(
    journey_id: str,
    title: str,
    action: str,
    expected: str,
    actual: str,
    *,
    routes: list[str],
    evidence: list[str],
    test_level: str,
    status: str,
    limitation: str = "",
) -> dict[str, Any]:
    passed = status == "verified"
    return {
        "journey_id": journey_id,
        "title": title,
        "action": action,
        "expected_result": expected,
        "actual_result": actual,
        "api_routes": routes,
        "evidence_artifacts": evidence,
        "test_level": test_level,
        "status": status,
        "pass": passed,
        "review_required": True,
        "limitation": limitation,
    }


def build_matrix(
    *,
    qualification: dict[str, Any],
    qualification_path: Path,
    package: Path,
    package_evidence: dict[str, Any],
    package_evidence_path: Path,
    durable_restart: dict[str, Any] | None = None,
    durable_restart_path: Path | None = None,
    ui_navigation: dict[str, Any] | None = None,
    ui_navigation_path: Path | None = None,
) -> dict[str, Any]:
    if qualification.get("schema_version") != "installed_offline_qualification_v2":
        raise EvidenceInputError("qualification has an unsupported schema")
    if qualification.get("feature_check_status") != "pass" or qualification.get("feature_blockers"):
        raise EvidenceInputError("canonical API feature checks are not a clean pass")
    if (qualification.get("execution_level") != "frozen_runtime_canonical_http"
            or qualification.get("runtime_instance_verified") is not True
            or qualification.get("fictional_only") is not True):
        raise EvidenceInputError("qualification lacks fictional frozen-runtime execution provenance")
    observed_requests = {
        (event.get("method"), event.get("path"))
        for event in qualification.get("request_events", [])
        if isinstance(event, dict) and event.get("http_status") == 200
        and event.get("request_id") and not event.get("error_class")
    }
    for method, route in (
        ("POST", "/api/records/REC-DOCX/parse"),
        ("POST", "/api/records/REC-PII-TXT/privacy-scan"),
        ("POST", "/api/records/REC-PII-TXT/redacted-copy"),
        ("POST", "/api/records/REC-OCR/ocr"),
        ("GET", "/api/records/REC-DUP-A/duplicates"),
        ("POST", "/api/records/compare"),
    ):
        if (method, route) not in observed_requests:
            raise EvidenceInputError(f"canonical runtime action evidence missing: {method} {route}")

    for check in (
        "runtime_health",
        "workbench_root",
        "retrieval_status",
        "retrieval_search",
        "grounded_school_answer",
        "grounded_private_answer",
        "no_automatic_install",
        "no_document_network",
        "presidio_available",
        "deterministic_fallback",
        "docling_or_fallback",
        "privacy_worker",
        "redacted_copy",
        "ocr_status",
        "original_immutable",
        "duplicate_detection",
        "record_comparison",
        "changed_copy",
        "docling_engine",
        "redaction_receipt",
        "original_hash_unchanged",
    ):
        require_passed_check(qualification, check)

    package_hash = sha256_file(package)
    candidate_hash = nested(package_evidence, "candidate", "package_sha256")
    if candidate_hash != package_hash:
        raise EvidenceInputError("package SHA-256 does not match package qualification evidence")
    runtime = qualification.get("runtime_resolution") or {}
    runtime_path = Path(str(runtime.get("executable_path") or "")).resolve()
    expected_runtime = package.parent.parent / "runtime" / "MaineFamilyLawLLM.exe"
    if runtime_path != expected_runtime.resolve():
        raise EvidenceInputError("qualification executable is not the runtime paired with the supplied MSIX")
    runtime_hash = sha256_file(runtime_path)
    if qualification.get("runtime_sha256") != runtime_hash:
        raise EvidenceInputError("qualification executable SHA-256 is stale or missing")
    try:
        with zipfile.ZipFile(package) as archive:
            if archive.namelist().count("MaineFamilyLawLLM.exe") != 1:
                raise EvidenceInputError("package must contain exactly one canonical executable")
            with archive.open("MaineFamilyLawLLM.exe") as stream:
                packaged_runtime_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise EvidenceInputError("package executable cannot be verified") from exc
    if packaged_runtime_hash != runtime_hash:
        raise EvidenceInputError("tested executable does not match bytes in supplied MSIX")

    durable_restart_ref = ""
    if durable_restart is not None:
        if durable_restart_path is None:
            raise EvidenceInputError("durable restart evidence path is missing")
        if durable_restart.get("schema_version") != "mfl_v8_durable_restart_e2e_v2":
            raise EvidenceInputError("durable restart evidence has an unsupported schema")
        if durable_restart.get("decision") != "PASS" or durable_restart.get("blockers"):
            raise EvidenceInputError("durable restart evidence is not a clean pass")
        if durable_restart.get("package_sha256") != package_hash:
            raise EvidenceInputError("durable restart package SHA-256 does not match supplied MSIX")
        expected_runtime_hash = sha256_file(runtime_path)
        if durable_restart.get("runtime_sha256") != expected_runtime_hash:
            raise EvidenceInputError("durable restart runtime SHA-256 does not match paired executable")
        failed_restart_checks = [
            str(name)
            for name, status in dict(durable_restart.get("checks") or {}).items()
            if status != "pass"
        ]
        if failed_restart_checks:
            raise EvidenceInputError("durable restart contains failed checks")
        required_restart_checks = {
            "first_runtime_instance_bound", "second_runtime_instance_bound",
            "first_health", "first_activation", "draft_created_review_required",
            "revision_committed", "original_preserved", "audit_before_valid",
            "second_health", "second_activation", "same_document_reopened",
            "same_revision_reopened", "same_content_reopened",
            "review_required_after_restart", "audit_after_valid",
            "document_list_contains_reopened",
        }
        if not required_restart_checks.issubset(durable_restart.get("checks") or {}):
            raise EvidenceInputError("durable restart is missing required checks")
        if (durable_restart.get("fictional_data_only") is not True
                or durable_restart.get("execution_level") != "frozen_runtime_canonical_api"):
            raise EvidenceInputError("durable restart lacks execution provenance")
        durable_restart_ref = portable(durable_restart_path)

    ui_navigation_ref = ""
    if ui_navigation is not None:
        if ui_navigation_path is None:
            raise EvidenceInputError("isolated UI navigation evidence path is missing")
        if ui_navigation.get("schema_version") != "mfl_v8_isolated_ui_navigation_v1":
            raise EvidenceInputError("isolated UI navigation evidence has an unsupported schema")
        if ui_navigation.get("decision") != "ISOLATED_FROZEN_UI_NAVIGATION_VERIFIED":
            raise EvidenceInputError("isolated UI navigation evidence is not a verified navigation pass")
        if nested(ui_navigation, "candidate", "package_sha256") != package_hash:
            raise EvidenceInputError("isolated UI navigation package SHA-256 does not match supplied MSIX")
        if nested(ui_navigation, "environment", "existing_profile_data_used") is not False:
            raise EvidenceInputError("isolated UI navigation evidence must not use an existing profile")
        actions = ui_navigation.get("actions")
        if not isinstance(actions, list) or not actions:
            raise EvidenceInputError("isolated UI navigation evidence has no recorded actions")
        failed_navigation_actions = [action for action in actions
                                     if not isinstance(action, dict) or not action.get("action")
                                     or action.get("result") != "pass"]
        if failed_navigation_actions:
            raise EvidenceInputError("isolated UI navigation contains failed actions")
        ui_navigation_ref = portable(ui_navigation_path)

    qualification_ref = portable(qualification_path)
    package_evidence_ref = portable(package_evidence_path)
    package_ref = portable(package)
    source_refs = [qualification_ref, package_evidence_ref, package_ref]
    inventory = qualification.get("inventory_result") or {}
    records = int(inventory.get("records") or 0)
    if records <= 0:
        raise EvidenceInputError("qualification did not record a fictional record inventory")
    sample_count = int(nested(qualification, "offline_boundary", "runtime_network_observation", "sample_count") or 0)
    external_connections = int(
        nested(qualification, "offline_boundary", "runtime_network_observation", "external_connection_count") or 0
    )
    if (sample_count <= 0 or external_connections != 0
            or nested(qualification, "offline_boundary", "runtime_network_observation", "errors")):
        raise EvidenceInputError("runtime TCP observations are missing, incomplete, or include external connections")

    journeys = [
        journey(
            "core-01",
            "Launch exact frozen runtime",
            "Launch the executable paired with the hash-checked MSIX and request local health.",
            "The loopback runtime health check passes.",
            "The exact paired frozen runtime launched and passed its local health check.",
            routes=["GET /api/health", "GET /api/version"],
            evidence=source_refs,
            test_level="frozen_runtime_canonical_api",
            status="verified",
        ),
        journey(
            "core-02",
            "Reach the production workbench",
            "Request the workbench root served by the exact frozen runtime.",
            "The shipped production workbench HTML is returned.",
            "The frozen runtime served the production workbench HTML; this HTTP check alone does not prove rendering or interaction.",
            routes=["GET /"],
            evidence=source_refs,
            test_level="frozen_runtime_production_ui_entry",
            status="verified",
        ),
        journey(
            "core-03",
            "Activate a fictional matter",
            "Create and activate the disposable fictional qualification matter.",
            "The active local corpus is accepted without using a real matter.",
            f"The exact runtime activated a disposable fictional matter with {records} records.",
            routes=["POST /api/activate-corpus", "GET /api/corpus-inventory"],
            evidence=[qualification_ref],
            test_level="frozen_runtime_canonical_api",
            status="verified",
        ),
        journey(
            "core-04",
            "Index and search fictional records",
            "Rebuild the local corpus index and search the private-record lane.",
            "Local retrieval returns source-bound private records without authority claims.",
            "The local index, retrieval-status endpoint, and source-card search checks passed.",
            routes=["POST /api/corpus-rebuild-index", "POST /api/retrieval-workbench/search"],
            evidence=[qualification_ref],
            test_level="frozen_runtime_canonical_api",
            status="verified",
        ),
        journey(
            "core-05",
            "Ask against fictional private records",
            "Ask private-record questions through the canonical local answer route.",
            "Answers expose source cards and remain review-required.",
            "Both private-record source-card answer checks passed; no legal-authority conclusion was asserted.",
            routes=["POST /ask"],
            evidence=[qualification_ref],
            test_level="frozen_runtime_canonical_api",
            status="verified",
        ),
        journey(
            "core-06",
            "Inspect document intelligence",
            "Run the admitted local parser path and deterministic fallback on fictional files.",
            "Parser selection and the no-network boundary are visible and fail closed.",
            "The parser/fallback and document-network checks passed on the exact frozen runtime.",
            routes=["GET /api/document-intelligence/status", "POST /api/records/{record_id}/parse"],
            evidence=[qualification_ref],
            test_level="frozen_runtime_local_worker",
            status="verified",
        ),
        journey(
            "core-07",
            "Create a privacy-reviewed derivative",
            "Run local privacy review and create a review-required redacted derivative.",
            "The original is preserved and the derivative remains review-required.",
            "Privacy-adapter availability, privacy worker behavior, and the redacted derivative check passed.",
            routes=["POST /api/records/{record_id}/privacy-scan", "POST /api/records/{record_id}/redacted-copy", "GET /api/artifacts/{artifact_id}/receipt"],
            evidence=[qualification_ref],
            test_level="frozen_runtime_local_worker",
            status="verified",
        ),
        journey(
            "core-08",
            "Preserve a scanned original through OCR",
            "Run the local OCR-preservation path on a fictional image-only PDF.",
            "The OCR result is recorded while the original remains immutable.",
            "OCR status and original-immutability checks passed.",
            routes=["POST /api/records/{record_id}/ocr", "GET /api/document-intelligence/artifacts/{token}"],
            evidence=[qualification_ref],
            test_level="frozen_runtime_local_worker",
            status="verified",
        ),
        journey(
            "core-09",
            "Detect exact duplicates and changed copies",
            "Compare fictional records through the local evidence pipeline.",
            "Exact duplicates are identified without conflating changed copies.",
            "Duplicate detection and record comparison checks passed.",
            routes=["GET /api/records/{record_id}/duplicates", "POST /api/records/compare"],
            evidence=[qualification_ref],
            test_level="frozen_runtime_canonical_api",
            status="verified",
        ),
        journey(
            "core-10",
            "Qualify the Local-only zero-network boundary",
            "Observe runtime TCP connections; separately run a socket guard in the test driver.",
            "Installed runtime makes zero external requests under an OS-enforced boundary.",
            f"{sample_count} TCP samples observed no external connections. The driver socket guard does not constrain native runtime traffic; OS-enforced proof was not executed.",
            routes=[],
            evidence=[qualification_ref],
            test_level="driver_guard_and_best_effort_runtime_tcp_observation",
            status="not_evaluated",
            limitation="Polling may miss short-lived connections, DNS and UDP. This is not an installed offline or zero-network certificate.",
        ),
        journey(
            "core-11",
            "Navigate the isolated frozen workbench",
            "Execute the actions individually recorded in the separate frozen production-UI report.",
            "The recorded actions pass without using an existing profile.",
            (
                "The separate report records passing actions against the isolated frozen UI; only its named actions are covered."
                if ui_navigation_ref
                else "Not evaluated by this core runner."
            ),
            routes=["GET /"],
            evidence=[ui_navigation_ref] if ui_navigation_ref else [],
            test_level="isolated_frozen_runtime_production_ui" if ui_navigation_ref else "not_evaluated",
            status="verified" if ui_navigation_ref else "not_evaluated",
            limitation=(
                "This proves listed navigation reachability only; specialized feature controls remain separately unproven."
                if ui_navigation_ref
                else "Requires an isolated-profile production UI navigation run."
            ),
        ),
        journey(
            "scope-01",
            "Current admitted-authority question",
            "Ask a current Maine-law question with exact official source proof.",
            "An active admitted authority build resolves the citation and source span.",
            "Not exercised because this package qualification intentionally contains no active external authority product.",
            routes=["POST /ask"],
            evidence=[qualification_ref],
            test_level="not_evaluated",
            status="not_evaluated",
            limitation="Requires separately admitted, current authority data and verifier evidence.",
        ),
        journey(
            "scope-02",
            "Broader workbench interaction",
            "Operate each visible specialized workbench control through the production desktop UI.",
            "Every feature has an observed UI action, source drill-down, and review state.",
            "Not evaluated by this core runner; it verifies the current production-UI entry only.",
            routes=[],
            evidence=[package_evidence_ref],
            test_level="not_evaluated",
            status="not_evaluated",
            limitation="Feature-specific browser/native desktop E2E journeys remain separate work.",
        ),
        journey(
            "scope-03",
            "Restart and persistent-work review",
            "Create a fictional durable work product, restart, reopen the same fictional matter, and verify the draft plus audit chain.",
            "The same reviewed artifact and history remain reachable after restart.",
            (
                "The paired frozen runtime preserved the fictional draft identifier, committed revision, content hash, review-required state, and valid audit chain across two launches."
                if durable_restart_ref
                else "Not evaluated by this core runner."
            ),
            routes=[
                "POST /api/document-workspace/documents",
                "POST /api/document-workspace/documents/{document_id}/proposals",
                "POST /api/document-workspace/documents/{document_id}/commit",
                "GET /api/document-workspace/documents/{document_id}",
                "GET /api/document-workspace/audit/verify",
            ],
            evidence=[durable_restart_ref] if durable_restart_ref else [],
            test_level="frozen_runtime_canonical_api" if durable_restart_ref else "not_evaluated",
            status="verified" if durable_restart_ref else "not_evaluated",
            limitation="Owned process termination/restart through the canonical API; not native UI quit or installed-package evidence." if durable_restart_ref else "Requires a separate durable-matter fixture and restart journey.",
        ),
    ]
    verified = sum(row["status"] == "verified" for row in journeys)
    not_evaluated = len(journeys) - verified
    artifacts = [
        {"path": qualification_ref, "sha256": sha256_file(qualification_path), "bytes": qualification_path.stat().st_size},
        {"path": package_evidence_ref, "sha256": sha256_file(package_evidence_path), "bytes": package_evidence_path.stat().st_size},
        {"path": package_ref, "sha256": package_hash, "bytes": package.stat().st_size},
    ]
    if durable_restart_ref and durable_restart_path is not None:
        artifacts.append(
            {
                "path": durable_restart_ref,
                "sha256": sha256_file(durable_restart_path),
                "bytes": durable_restart_path.stat().st_size,
            }
        )
    if ui_navigation_ref and ui_navigation_path is not None:
        artifacts.append(
            {
                "path": ui_navigation_ref,
                "sha256": sha256_file(ui_navigation_path),
                "bytes": ui_navigation_path.stat().st_size,
            }
        )
    return {
        "schema_version": "mfl_v8_core_e2e_matrix_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "CORE_API_VERIFIED_WITH_LIMITATIONS",
        "scope": "hash-bound core local workflow qualification; not a certification of every roadmap feature, current law, Store GA, or Enterprise GA",
        "fictional_data": {
            "classification": "disposable deterministic software fixture",
            "real_matter_data_used": False,
            "record_count": records,
        },
        "candidate": {
            "package": package_ref,
            "package_sha256": package_hash,
            "runtime_executable": str(runtime_path),
            "runtime_sha256": runtime_hash,
            "installed_msix": qualification.get("installed_msix") is True,
        },
        "journey_summary": {"total": len(journeys), "verified": verified, "not_evaluated": not_evaluated},
        "journeys": journeys,
        "artifact_hashes": artifacts,
        "remaining_blockers": [
            row["journey_id"] for row in journeys if row["status"] != "verified"
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qualification-json", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--package-evidence-json", required=True, type=Path)
    parser.add_argument("--durable-restart-json", type=Path)
    parser.add_argument("--ui-navigation-json", type=Path)
    parser.add_argument(
        "--output-json",
        type=Path,
        default=ROOT / "dist" / "ga_today" / "evidence" / "08_v8_core_e2e_matrix.json",
    )
    parser.add_argument(
        "--output-text",
        type=Path,
        default=ROOT / "dist" / "ga_today" / "evidence" / "08_v8_core_e2e_summary.txt",
    )
    args = parser.parse_args(argv)
    try:
        qualification_path = args.qualification_json.resolve(strict=True)
        package = args.package.resolve(strict=True)
        package_evidence_path = args.package_evidence_json.resolve(strict=True)
        durable_restart_path = args.durable_restart_json.resolve(strict=True) if args.durable_restart_json else None
        ui_navigation_path = args.ui_navigation_json.resolve(strict=True) if args.ui_navigation_json else None
        if not package.is_file():
            raise EvidenceInputError("package is not a regular file")
        matrix = build_matrix(
            qualification=load_object(qualification_path, label="qualification JSON"),
            qualification_path=qualification_path,
            package=package,
            package_evidence=load_object(package_evidence_path, label="package evidence JSON"),
            package_evidence_path=package_evidence_path,
            durable_restart=(load_object(durable_restart_path, label="durable restart JSON") if durable_restart_path else None),
            durable_restart_path=durable_restart_path,
            ui_navigation=(load_object(ui_navigation_path, label="isolated UI navigation JSON") if ui_navigation_path else None),
            ui_navigation_path=ui_navigation_path,
        )
    except EvidenceInputError as exc:
        print(f"Evidence assembly blocked: {exc}", file=sys.stderr)
        return 2

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_text.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "V8 CORE END-TO-END SUMMARY",
        "",
        f"Decision: {matrix['decision']}",
        f"Verified journeys: {matrix['journey_summary']['verified']}/{matrix['journey_summary']['total']}",
        f"Package SHA-256: {matrix['candidate']['package_sha256']}",
        "",
        "Verified journeys:",
    ]
    lines.extend(f"- {row['journey_id']}: {row['title']}" for row in matrix["journeys"] if row["status"] == "verified")
    lines.extend(["", "Not evaluated:"])
    lines.extend(
        f"- {row['journey_id']}: {row['title']} — {row['limitation']}"
        for row in matrix["journeys"]
        if row["status"] != "verified"
    )
    args.output_text.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"matrix": str(args.output_json), "summary": str(args.output_text), "decision": matrix["decision"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
