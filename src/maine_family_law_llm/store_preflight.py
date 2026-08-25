from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

EXPECTED_PACKAGE_NAME = "TAHAIWebServices.MaineFamilyLawLLM"
EXPECTED_PUBLISHER = "CN=D75EE668-B409-45ED-87E5-E37AA5FE3868"
DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MSIX_PATH = DEFAULT_REPO_ROOT / "dist" / "release" / "v8.0.0" / "msix" / "MaineFamilyLawLLM_8.0.0.0_x64.msix"
DEFAULT_EVIDENCE_ROOT = DEFAULT_REPO_ROOT / "dist" / "store" / "evidence"
DEFAULT_WACK_RESULT = DEFAULT_EVIDENCE_ROOT / "wack" / "wack-result.json"

APPX_NS = "http://schemas.microsoft.com/appx/manifest/foundation/windows10"
UAP_NS = "http://schemas.microsoft.com/appx/manifest/uap/windows10"
DESKTOP_NS = "http://schemas.microsoft.com/appx/manifest/desktop/windows10"
RESCAP_NS = "http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"

REQUIRED_TOP_LEVEL_FILES = {"AppxManifest.xml", "AppxBlockMap.xml", "[Content_Types].xml", "AppxSignature.p7x"}
REQUIRED_NOTICE_PATTERNS = ("license", "licenses/")
FORBIDDEN_EXACT_BASENAMES = {
    "store-preflight.json",
    "store-preflight.txt",
    "installed-offline-qualification.json",
    "installed-offline-qualification.txt",
    "private-data-audit.json",
    "bundled-engine-inventory.json",
    "msix-path-audit.json",
    "sealed-msix-payload.json",
    "sealed-msix-payload-audit.json",
    "sealed-msix-archive-audit.json",
    "msix-staging-manifest.json",
    "package-file-manifest.json",
    "runtime-dependency-probe.json",
    "store-build-smoke.json",
    "final-runtime-cleanup.json",
    "final-staging-cleanup.json",
    "bytecode-regeneration-trace.json",
    "test-summary.txt",
    "wack-result.json",
    "source_manifest.json",
    "private_search_index.json",
}
FORBIDDEN_PREFIXES = (
    "dist/",
    "build/",
    "out/",
    "temp/",
    "tmp/",
    "logs/",
    "log/",
    "tests/",
    "test/",
    "eval_data/",
    "store/evidence/",
    "case_",
    "matter_",
)
FORBIDDEN_SEGMENTS = {"__pycache__", ".pytest_cache", "tests"}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _canonical_path(name: str) -> str:
    return name.replace("\\", "/").lstrip("/")


def _parse_manifest(msix_path: Path) -> tuple[str, ET.Element]:
    with zipfile.ZipFile(msix_path) as archive:
        manifest_bytes = archive.read("AppxManifest.xml")
    manifest_text = manifest_bytes.decode("utf-8-sig")
    return manifest_text, ET.fromstring(manifest_text)


def _qname(namespace: str, local_name: str) -> str:
    return f"{{{namespace}}}{local_name}"


def _child_text(parent: ET.Element | None, namespace: str, local_name: str) -> str:
    if parent is None:
        return ""
    return (parent.findtext(_qname(namespace, local_name)) or "").strip()


def _find_sdk_tool(tool_name: str) -> str | None:
    kit_root = Path(r"C:\Program Files (x86)\Windows Kits\10\bin")
    if not kit_root.exists():
        return None
    candidates = sorted(
        (path for path in kit_root.rglob(tool_name) if "\\x64\\" in str(path).lower()),
        key=lambda path: str(path).lower(),
    )
    return str(candidates[0]) if candidates else None


def _parse_wack_result(wack_result_path: Path) -> dict[str, Any]:
    if not wack_result_path.exists():
        return {
            "status": "not_run",
            "reason": "wack_result_not_found",
            "package_path": str(DEFAULT_MSIX_PATH),
            "artifact_path": str(wack_result_path),
        }
    payload = _read_json(wack_result_path)
    status = str(payload.get("status") or "not_run")
    return {
        "status": status,
        "reason": payload.get("reason") or payload.get("detail") or "",
        "package_path": payload.get("package_path") or str(DEFAULT_MSIX_PATH),
        "artifact_path": str(wack_result_path),
    }


def audit_manifest(msix_path: Path, expected_version: str) -> dict[str, Any]:
    manifest_text, root = _parse_manifest(msix_path)
    ns = {"a": APPX_NS, "uap": UAP_NS, "desktop": DESKTOP_NS, "rescap": RESCAP_NS}
    identity = root.find("a:Identity", ns)
    properties = root.find("a:Properties", ns)
    resources = root.find("a:Resources", ns)
    application = root.find("a:Applications/a:Application", ns)
    visual_elements = root.find("a:Applications/a:Application/uap:VisualElements", ns)
    default_tile = root.find("a:Applications/a:Application/uap:VisualElements/uap:DefaultTile", ns)
    splash_screen = root.find("a:Applications/a:Application/uap:VisualElements/uap:SplashScreen", ns)
    dependencies = root.findall("a:Dependencies/*", ns)
    capabilities = root.findall("a:Capabilities/*", ns)
    extension_nodes = root.findall("a:Applications/a:Application/a:Extensions/*", ns)

    issues: list[str] = []
    if identity is None:
        issues.append("missing_identity")
    else:
        identity_name = identity.attrib.get("Name", "")
        identity_publisher = identity.attrib.get("Publisher", "")
        identity_version = identity.attrib.get("Version", "")
        architecture = identity.attrib.get("ProcessorArchitecture", "")
        if identity_name != EXPECTED_PACKAGE_NAME:
            issues.append("identity_name_mismatch")
        if identity_publisher != EXPECTED_PUBLISHER:
            issues.append("publisher_mismatch")
        if identity_version != expected_version:
            issues.append("version_mismatch")
        if architecture.lower() != "x64":
            issues.append("processor_architecture_mismatch")
    if properties is None:
        issues.append("missing_properties")
    else:
        display_name = _child_text(properties, APPX_NS, "DisplayName")
        description = _child_text(properties, APPX_NS, "Description")
        if not display_name:
            issues.append("missing_display_name")
        if not description:
            issues.append("missing_description")
    if resources is None or not any((resource.attrib.get("Language") or "").lower() == "en-us" for resource in resources):
        issues.append("missing_en_us_resource")
    if application is None:
        issues.append("missing_application")
    else:
        if application.attrib.get("Executable") != "MaineFamilyLawLLM.exe":
            issues.append("executable_mismatch")
        if application.attrib.get("EntryPoint") != "Windows.FullTrustApplication":
            issues.append("entry_point_mismatch")
    if visual_elements is None:
        issues.append("missing_visual_elements")
    else:
        for asset in ("Square150x150Logo", "Square44x44Logo"):
            if not visual_elements.attrib.get(asset):
                issues.append(f"missing_visual_asset:{asset}")
        if default_tile is None:
            issues.append("missing_default_tile")
        else:
            for asset in ("Wide310x150Logo", "Square310x310Logo"):
                if not default_tile.attrib.get(asset):
                    issues.append(f"missing_visual_asset:{asset}")
        if splash_screen is None or not splash_screen.attrib.get("Image"):
            issues.append("missing_visual_asset:Image")
        if not (visual_elements.attrib.get("DisplayName") or "").strip():
            issues.append("missing_visual_display_name")
        if not (visual_elements.attrib.get("Description") or "").strip():
            issues.append("missing_visual_description")
    if not dependencies:
        issues.append("missing_target_device_family")
    else:
        allowed_dependencies = {
            ("Windows.Desktop", "10.0.19041.0", "10.0.26100.0"),
        }
        dep_key = tuple(dependencies[0].attrib.get(key, "") for key in ("Name", "MinVersion", "MaxVersionTested"))
        if dep_key not in allowed_dependencies:
            issues.append("target_device_family_mismatch")
    capability_names = [node.attrib.get("Name", "") for node in capabilities]
    if capability_names != ["runFullTrust"]:
        issues.append("capability_mismatch")
    if extension_nodes:
        if any(node.tag != _qname(DESKTOP_NS, "Extension") for node in extension_nodes):
            issues.append("unsupported_extension_namespace")
        if any(node.attrib.get("Category") != "windows.fullTrustProcess" for node in extension_nodes):
            issues.append("unsupported_extension_category")
    if "x-generate" in manifest_text.lower():
        issues.append("x_generate_present")

    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "identity": identity.attrib if identity is not None else {},
        "properties": {
            "display_name": _child_text(properties, APPX_NS, "DisplayName"),
            "publisher_display_name": _child_text(properties, APPX_NS, "PublisherDisplayName"),
            "description": _child_text(properties, APPX_NS, "Description"),
        },
        "resources": [resource.attrib for resource in resources] if resources is not None else [],
        "application": application.attrib if application is not None else {},
        "visual_elements": visual_elements.attrib if visual_elements is not None else {},
        "default_tile": default_tile.attrib if default_tile is not None else {},
        "splash_screen": splash_screen.attrib if splash_screen is not None else {},
        "dependencies": [node.attrib for node in dependencies],
        "capabilities": capability_names,
        "extensions": [node.attrib for node in extension_nodes],
    }


def audit_archive(msix_path: Path) -> dict[str, Any]:
    issues: list[str] = []
    with zipfile.ZipFile(msix_path) as archive:
        names = [_canonical_path(info.filename) for info in archive.infolist() if not info.is_dir()]
        normalized = [name.lower() for name in names]
        duplicate_counts = Counter(normalized)
        duplicate_paths = sorted(path for path, count in duplicate_counts.items() if count > 1)
        if duplicate_paths:
            issues.append("duplicate_destination_path")
        traversal_hits = [name for name in names if name.startswith("/") or name.startswith("\\") or ".." in Path(name).parts or ":" in name]
        if traversal_hits:
            issues.append("path_traversal_or_ads")
        required_missing = sorted(path for path in REQUIRED_TOP_LEVEL_FILES if path not in names)
        if required_missing:
            issues.append("missing_required_package_files")
        notice_hits = [name for name in names if any(pattern in name.lower() for pattern in REQUIRED_NOTICE_PATTERNS)]
        if not notice_hits:
            issues.append("third_party_notices_missing")

        forbidden_hits = []
        for name in names:
            lower = name.lower()
            basename = Path(name).name.lower()
            if any(lower.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
                forbidden_hits.append(name)
                continue
            if basename in FORBIDDEN_EXACT_BASENAMES:
                forbidden_hits.append(name)
                continue
            if any(segment in FORBIDDEN_SEGMENTS for segment in Path(name).parts):
                forbidden_hits.append(name)
                continue
        if forbidden_hits:
            issues.append("forbidden_package_entries")

        signature_state = "unsigned"
        signature_tool = _find_sdk_tool("signtool.exe")
        signature_details = {"tool_path": signature_tool or "", "exit_code": None, "stdout": "", "stderr": ""}
        if signature_tool:
            completed = subprocess.run(
                [signature_tool, "verify", "/pa", "/v", str(msix_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            signature_details.update(
                {
                    "exit_code": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                }
            )
            if completed.returncode == 0:
                signature_state = "signed_verified"
            elif "not trusted" in f"{completed.stdout}\n{completed.stderr}".lower():
                signature_state = "signed_untrusted_chain"
            else:
                signature_state = "verify_failed"
                issues.append("signature_verification_failed")
        else:
            signature_state = "signtool_not_found"
            issues.append("signtool_not_found")

    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "signature_state": signature_state,
        "signature_details": signature_details,
        "duplicate_destination_paths": duplicate_paths,
        "traversal_hits": traversal_hits,
        "required_missing": required_missing,
        "notice_hits": notice_hits,
        "forbidden_hits": forbidden_hits,
        "required_top_level_files": sorted(REQUIRED_TOP_LEVEL_FILES),
        "entry_count": len(names),
    }


def audit_evidence(repo_root: Path, msix_path: Path, evidence_root: Path) -> dict[str, Any]:
    evidence_paths = {
        "bundled_engine_inventory": evidence_root / "bundled-engine-inventory.json",
        "private_data_audit": evidence_root / "private-data-audit.json",
        "installed_offline_qualification": evidence_root / "installed-offline-qualification.json",
        "sealed_msix_payload": evidence_root / "sealed-msix-payload.json",
        "sealed_msix_payload_audit": evidence_root / "sealed-msix-payload-audit.json",
        "sealed_msix_archive_audit": evidence_root / "sealed-msix-archive-audit.json",
        "msix_path_audit": evidence_root / "msix-path-audit.json",
        "package_file_manifest": evidence_root / "package-file-manifest.json",
        "store_build_smoke": evidence_root / "store-build-smoke.json",
    }
    statuses: dict[str, Any] = {}
    issues: list[str] = []
    for name, path in evidence_paths.items():
        if not path.exists():
            statuses[name] = {"status": "missing", "path": str(path)}
            issues.append(f"missing_{name}")
            continue
        payload = _read_json(path)
        if isinstance(payload, list):
            statuses[name] = {
                "status": "present",
                "generated_at": None,
                "path": str(path),
                "entry_count": len(payload),
            }
            continue
        statuses[name] = {
            "status": payload.get("status") or payload.get("qualification_status") or "unknown",
            "generated_at": payload.get("generated_at"),
            "path": str(path),
        }
    inventory = _read_json(evidence_paths["bundled_engine_inventory"])
    private_audit = _read_json(evidence_paths["private_data_audit"])
    installed_offline = _read_json(evidence_paths["installed_offline_qualification"])
    archive_audit = _read_json(evidence_paths["sealed_msix_archive_audit"])
    payload_audit = _read_json(evidence_paths["sealed_msix_payload_audit"])
    package_file_manifest = _read_json(evidence_paths["package_file_manifest"]) if evidence_paths["package_file_manifest"].exists() else []
    msix_path_audit = _read_json(evidence_paths["msix_path_audit"]) if evidence_paths["msix_path_audit"].exists() else {}

    if inventory.get("status") != "pass" or inventory.get("failures"):
        issues.append("bundled_engine_inventory_failed")
    if private_audit.get("status") != "pass":
        issues.append("private_data_audit_failed")
    if installed_offline.get("qualification_status") != "pass" or installed_offline.get("blockers"):
        issues.append("installed_offline_qualification_failed")
    if payload_audit.get("status") != "pass":
        issues.append("sealed_msix_payload_audit_failed")
    if archive_audit.get("status") != "pass":
        issues.append("sealed_msix_archive_audit_failed")
    if msix_path_audit and msix_path_audit.get("status") != "pass":
        issues.append("msix_path_audit_failed")
    if not package_file_manifest:
        issues.append("package_file_manifest_missing")
    if archive_audit.get("msix_path") and Path(str(archive_audit["msix_path"])) != msix_path:
        issues.append("archive_audit_package_path_mismatch")
    if installed_offline.get("files", {}).get("installed_offline_qualification_json"):
        if Path(installed_offline["files"]["installed_offline_qualification_json"]) != evidence_paths["installed_offline_qualification"]:
            issues.append("installed_offline_qualification_path_mismatch")

    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "package_file_manifest_count": len(package_file_manifest),
        "evidence_files": statuses,
        "bundled_engine_inventory": {
            "status": inventory.get("status"),
            "package_count": inventory.get("package_count"),
            "failures": inventory.get("failures") or [],
        },
        "private_data_audit": {
            "status": private_audit.get("status"),
            "blocked_paths": private_audit.get("blocked_paths") or [],
            "blocked_files": private_audit.get("blocked_files") or [],
        },
        "installed_offline_qualification": {
            "status": installed_offline.get("qualification_status"),
            "blockers": installed_offline.get("blockers") or [],
        },
        "sealed_msix_payload_audit": {
            "status": payload_audit.get("status"),
        },
        "sealed_msix_archive_audit": {
            "status": archive_audit.get("status"),
            "msix_path": archive_audit.get("msix_path"),
        },
        "msix_path_audit": msix_path_audit,
    }


def build_preflight_report(repo_root: Path, msix_path: Path, evidence_root: Path, wack_result_path: Path) -> dict[str, Any]:
    identity_spec = _read_json(repo_root / "store" / "msix" / "identity.example.json")
    package_sha256 = sha256_file(msix_path)
    manifest_audit = audit_manifest(msix_path, str(identity_spec.get("package_version") or ""))
    archive_audit = audit_archive(msix_path)
    evidence_audit = audit_evidence(repo_root, msix_path, evidence_root)
    wack_result = _parse_wack_result(wack_result_path)

    manifest_ok = manifest_audit["status"] == "pass"
    archive_ok = archive_audit["status"] == "pass"
    evidence_ok = evidence_audit["status"] == "pass"
    wack_ok = wack_result["status"] in {"completed", "pass"}
    final_readiness_state = "READY_FOR_PARTNER_CENTER_UPLOAD" if manifest_ok and archive_ok and evidence_ok and wack_ok else "BLOCKED"

    blockers: list[str] = []
    if not manifest_ok:
        blockers.extend(f"manifest:{issue}" for issue in manifest_audit["issues"])
    if not archive_ok:
        blockers.extend(f"archive:{issue}" for issue in archive_audit["issues"])
    if not evidence_ok:
        blockers.extend(f"evidence:{issue}" for issue in evidence_audit["issues"])
    if not wack_ok:
        blockers.append(f"wack:{wack_result['status']}")
        if wack_result.get("reason"):
            blockers.append(f"wack_reason:{wack_result['reason']}")

    return {
        "schema_version": "store_preflight_v1",
        "generated_at": utc_now(),
        "package": {
            "path": str(msix_path),
            "sha256": package_sha256,
            "size_bytes": msix_path.stat().st_size,
        },
        "expected_identity": identity_spec,
        "manifest_audit": manifest_audit,
        "content_audit": archive_audit,
        "evidence_audit": evidence_audit,
        "wack": wack_result,
        "final_readiness_state": final_readiness_state,
        "blockers": blockers,
        "package_hash_tied_evidence": {
            "msix_path_audit": str(evidence_root / "msix-path-audit.json"),
            "sealed_msix_archive_audit": str(evidence_root / "sealed-msix-archive-audit.json"),
            "sealed_msix_payload_audit": str(evidence_root / "sealed-msix-payload-audit.json"),
            "installed_offline_qualification": str(evidence_root / "installed-offline-qualification.json"),
            "private_data_audit": str(evidence_root / "private-data-audit.json"),
            "bundled_engine_inventory": str(evidence_root / "bundled-engine-inventory.json"),
        },
    }


def write_outputs(report: dict[str, Any], json_path: Path, txt_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        f"Package: {report['package']['path']}",
        f"Package SHA-256: {report['package']['sha256']}",
        f"Package identity: {report['manifest_audit']['identity'].get('Name', '')}",
        f"Manifest audit: {report['manifest_audit']['status']}",
        f"Content audit: {report['content_audit']['status']}",
        f"Evidence audit: {report['evidence_audit']['status']}",
        f"Bundled engine inventory: {report['evidence_audit']['bundled_engine_inventory']['status']}",
        f"Private-data audit: {report['evidence_audit']['private_data_audit']['status']}",
        f"Installed-offline qualification: {report['evidence_audit']['installed_offline_qualification']['status']}",
        f"WACK: {report['wack']['status']}",
        f"Final readiness: {report['final_readiness_state']}",
    ]
    if report["wack"].get("reason"):
        lines.append(f"WACK reason: {report['wack']['reason']}")
    if report["blockers"]:
        lines.append("Blockers:")
        lines.extend(f"- {blocker}" for blocker in report["blockers"])
    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Store package-compliance preflight slice.")
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT))
    parser.add_argument("--msix-path", default=str(DEFAULT_MSIX_PATH))
    parser.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT))
    parser.add_argument("--wack-result", default=str(DEFAULT_WACK_RESULT))
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-txt", default="")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    msix_path = Path(args.msix_path).resolve()
    evidence_root = Path(args.evidence_root).resolve()
    wack_result = Path(args.wack_result).resolve()
    output_json = Path(args.output_json).resolve() if args.output_json else evidence_root / "store-preflight.json"
    output_txt = Path(args.output_txt).resolve() if args.output_txt else evidence_root / "store-preflight.txt"

    report = build_preflight_report(repo_root, msix_path, evidence_root, wack_result)
    write_outputs(report, output_json, output_txt)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
