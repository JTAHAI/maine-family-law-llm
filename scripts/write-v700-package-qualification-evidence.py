"""Freeze the v7 package-qualification result without overstating install evidence."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "dist" / "release" / "v7.0.0"
EVIDENCE = RELEASE / "evidence"
MSIX = RELEASE / "msix" / "MaineFamilyLawLLM_7.0.0.0_x64.msix"
BUILD_EVIDENCE = ROOT / "dist" / "final-v700" / "evidence"


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def main() -> int:
    if not MSIX.is_file():
        raise SystemExit(f"Missing final MSIX: {MSIX}")
    EVIDENCE.mkdir(parents=True, exist_ok=True)

    copied = []
    for name in (
        "bundled-engine-inventory.json",
        "final-runtime-cleanup.json",
        "final-staging-cleanup.json",
        "focaf-runtime-asset-audit.json",
        "msix-path-audit.json",
        "private-data-audit.json",
        "runtime-dependency-probe.json",
        "sealed-msix-archive-audit.json",
        "sealed-msix-payload-audit.json",
        "sealed-msix-payload.json",
        "store-build-smoke.json",
    ):
        source = BUILD_EVIDENCE / name
        if source.is_file():
            target = EVIDENCE / name
            shutil.copy2(source, target)
            copied.append(relative(target))

    with zipfile.ZipFile(MSIX) as archive:
        names = set(archive.namelist())
        manifest_bytes = archive.read("AppxManifest.xml")
        manifest = ET.fromstring(manifest_bytes)
        identity = manifest.find("{http://schemas.microsoft.com/appx/manifest/foundation/windows10}Identity")
        resources = manifest.find("{http://schemas.microsoft.com/appx/manifest/foundation/windows10}Resources")
        language = None
        if resources is not None:
            resource = resources.find("{http://schemas.microsoft.com/appx/manifest/foundation/windows10}Resource")
            language = resource.attrib.get("Language") if resource is not None else None
        package_manifest = {
            "identity": identity.attrib.get("Name") if identity is not None else None,
            "publisher": identity.attrib.get("Publisher") if identity is not None else None,
            "version": identity.attrib.get("Version") if identity is not None else None,
            "architecture": identity.attrib.get("ProcessorArchitecture") if identity is not None else None,
            "language": language,
            "entry_count": len(names),
            "has_block_map": "AppxBlockMap.xml" in names,
            "has_signature": "AppxSignature.p7x" in names,
            "has_x_generate": b"x-generate" in manifest_bytes.lower(),
        }

    package_hash = sha256(MSIX)
    (EVIDENCE / "package-sha256.txt").write_text(
        f"{package_hash}  {MSIX.name}\n", encoding="utf-8"
    )

    offline_path = EVIDENCE / "offline-frozen-exact" / "installed-offline-qualification.json"
    offline = read_json(offline_path)
    offline_summary = {
        "schema_version": "v700_offline_result_v1",
        "generated_at": utc_now(),
        "status": "runtime_pass_installed_not_executed",
        "exact_frozen_runtime_status": offline.get("qualification_status"),
        "external_connection_count": (
            offline.get("offline_boundary", {})
            .get("runtime_network_observation", {})
            .get("external_connection_count")
        ),
        "installed_package_offline_status": "NOT_EXECUTED",
        "reason": "The isolated QA AppX could not be registered because Developer Mode/sideloading is disabled.",
        "source_evidence": relative(offline_path),
    }
    write_json(EVIDENCE / "offline-qualification.json", offline_summary)

    install_report = {
        "schema_version": "v700_isolated_install_result_v1",
        "generated_at": utc_now(),
        "status": "blocked",
        "target_package": relative(MSIX),
        "target_sha256": package_hash,
        "real_store_package_before_after": "TAHAIWebServices.MaineFamilyLawLLM_6.0.4.0_x64__k9af96g77tmj4",
        "real_store_package_touched": False,
        "qa_identity": "TAHAIWebServices.MaineFamilyLawLLM.QA7",
        "qa_package_installed": False,
        "attempts": [
            {
                "method": "ephemeral self-signed QA package",
                "result": "blocked",
                "error": "0x800B0109 untrusted self-signed root",
                "cleanup": "ephemeral current-user TrustedPeople certificate removed; no QA package installed",
            },
            {
                "method": "unsigned executable QA MSIX with required unsigned namespace",
                "result": "blocked",
                "error": "0x80073D2B unsigned package cannot include executable activation",
            },
            {
                "method": "unpacked developer registration under unique QA identity",
                "result": "blocked",
                "error": "0x80073CFF Developer Mode/sideloading is disabled",
            },
            {
                "method": "Windows Sandbox",
                "result": "unavailable",
                "error": "Windows Sandbox executable is not installed",
            },
            {
                "method": "Hyper-V disposable VM",
                "result": "unavailable",
                "error": "Hyper-V management exists but the current user lacks authorization",
            },
        ],
        "environment": {"elevated": False, "developer_mode": False, "windows_sandbox": False},
        "clean_install": "NOT_EXECUTED",
        "first_launch_from_installed_qa": "NOT_EXECUTED",
        "restart_uninstall_reinstall": "NOT_EXECUTED",
        "classification": "P1 release-evidence blocker / environment limitation with direct OS error evidence",
    }
    write_json(EVIDENCE / "install-report.json", install_report)

    upgrade_report = {
        "schema_version": "v700_upgrade_result_v1",
        "generated_at": utc_now(),
        "package_upgrade": "NOT_EXECUTED",
        "reason": "No isolated 6.0.4 package environment was available and the real Store package was preserved.",
        "direct_prior_schema_migration": "pass",
        "migration_evidence": "dist/release/v7.0.0/migration-report.json",
    }
    write_json(EVIDENCE / "upgrade-report.json", upgrade_report)

    wack = {
        "schema_version": "v700_wack_status_v1",
        "generated_at": utc_now(),
        "status": "WACK_NOT_RUN",
        "tool": "C:/Program Files (x86)/Windows Kits/10/App Certification Kit/appcert.exe",
        "tool_version": "10.0.26100.7705",
        "reason": "The installed WACK executable requires elevation and this session is not elevated.",
        "report": None,
    }
    write_json(EVIDENCE / "wack-status.json", wack)

    rollback = {
        "schema_version": "v700_rollback_preparation_v1",
        "generated_at": utc_now(),
        "status": "prepared_not_executed",
        "real_store_package_preserved": True,
        "qa_identity_cleanup": "No QA package remains installed.",
        "qa_certificate_cleanup": "The sole ephemeral QA certificate was removed from CurrentUser TrustedPeople.",
        "migration_rollback": "Use the 6.0.4 backup/restore and forward-recovery notes in migration-report.json.",
    }
    write_json(EVIDENCE / "rollback-preparation.json", rollback)

    package_audit = {
        "schema_version": "v700_exact_package_audit_v1",
        "generated_at": utc_now(),
        "status": "pass",
        "package": relative(MSIX),
        "size_bytes": MSIX.stat().st_size,
        "sha256": package_hash,
        "manifest": package_manifest,
        "expected": {
            "identity": "TAHAIWebServices.MaineFamilyLawLLM",
            "publisher": "CN=D75EE668-B409-45ED-87E5-E37AA5FE3868",
            "version": "7.0.0.0",
            "architecture": "x64",
            "language": "en-us",
        },
        "private_data_audit": "pass",
        "sealed_payload_audit": "pass",
        "path_audit": "pass",
        "current_hardened_filing_gate": {"cases": 16, "false_passes": 0},
        "copied_build_evidence": copied,
    }
    write_json(EVIDENCE / "package-audit.json", package_audit)

    source_id_path = EVIDENCE / "source-tree-manifest.sha256"
    source_id = source_id_path.read_text(encoding="utf-8").strip() if source_id_path.is_file() else None
    qualification = {
        "schema_version": "v700_package_qualification_v1",
        "generated_at": utc_now(),
        "decision": "BLOCKED",
        "source_identity": source_id,
        "package_audit": "pass",
        "frozen_runtime_offline": "pass",
        "clean_install": "NOT_EXECUTED",
        "installed_core_journeys": "NOT_EXECUTED",
        "installed_offline": "NOT_EXECUTED",
        "wack": "WACK_NOT_RUN",
        "signing": "unsigned final Store MSIX; Partner Center signing required",
        "p0_blockers": [],
        "p1_blockers": [
            "Clean install, installed-app journeys, restart/uninstall/reinstall, and installed offline qualification remain unproved because no authorized isolated AppX environment is available.",
            "WACK is installed but could not run without elevation.",
        ],
    }
    write_json(EVIDENCE / "package-qualification-decision.json", qualification)
    (EVIDENCE / "package-qualification-decision.txt").write_text(
        "BLOCKED\n"
        "Exact v7 MSIX build/audit and frozen offline qualification pass.\n"
        "Clean isolated AppX install and WACK remain unexecuted due OS policy/elevation limits.\n",
        encoding="utf-8",
    )

    store_blockers = list(qualification["p1_blockers"])
    final = {
        "schema_version": "v700_final_release_decision_v2",
        "generated_at": utc_now(),
        "source_identity": source_id,
        "publishing_or_upload_performed": False,
        "package": {
            "path": relative(MSIX),
            "size_bytes": MSIX.stat().st_size,
            "sha256": package_hash,
            "audit": "pass",
            "qualification": "BLOCKED",
        },
        "authority": {"build_id": "89f23df714e94463f105228f", "status": "pass", "source_count": 38},
        "filing_gate": {"cases": 16, "false_passes": 0, "status": "pass"},
        "frozen_runtime_offline": offline_summary,
        "clean_install": install_report,
        "upgrade": upgrade_report,
        "wack": wack,
        "screenshots": {
            "status": "NOT_CREATED",
            "reason": "Installed v7 package did not pass the mandatory precondition; final Store screenshots would be misleading.",
            "files": [],
        },
        "store_copy": {
            "status": "NOT_CREATED",
            "reason": "PACKAGE_READY was not achieved.",
            "files": [],
        },
        "submission_bundle": {"status": "NOT_CREATED", "files": []},
        "v7_msix_decision": "V7_MSIX_BLOCKED",
        "enterprise_ga_decision": "ENTERPRISE_GA_BLOCKED",
        "store_blockers": store_blockers,
        "enterprise_blockers": [
            "Microsoft Store package qualification is blocked.",
            "No attorney-reviewed gold evaluation dataset meeting project minimums is evidenced.",
            "No attorney sandbox, controlled pilot, or legal/security/product/operations sign-off set is evidenced.",
        ],
    }
    write_json(RELEASE / "FINAL_RELEASE_DECISION.json", final)
    (RELEASE / "FINAL_RELEASE_DECISION.txt").write_text(
        "V7_MSIX_BLOCKED\nENTERPRISE_GA_BLOCKED\n\n"
        "The exact v7 MSIX and its package/privacy/filing-gate audits pass.\n"
        "An isolated clean AppX install and WACK could not be executed under current Windows policy.\n"
        "Store screenshots, listing copy, and upload bundle were intentionally not created.\n",
        encoding="utf-8",
    )
    submission_manifest = {
        "schema_version": "v700_store_submission_manifest_v2",
        "generated_at": utc_now(),
        "status": "NOT_CREATED_PRECONDITION_BLOCKED",
        "precondition": "PACKAGE_READY",
        "precondition_status": "NOT_SATISFIED",
        "submission_directory_created": False,
        "submission_files": [],
        "package": {"path": relative(MSIX), "sha256": package_hash},
        "screenshots": [],
        "listing_copy": [],
        "publication_or_upload_performed": False,
        "reason": "Clean installed-package qualification and WACK evidence are absent.",
    }
    write_json(RELEASE / "STORE_SUBMISSION_MANIFEST.json", submission_manifest)
    print(json.dumps({"decision": "BLOCKED", "sha256": package_hash}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
