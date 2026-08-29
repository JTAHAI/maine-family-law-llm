"""Fail-closed planning and evidence validation for isolated MSIX upgrades.

This module intentionally cannot install, uninstall, or alter the user's Store
package.  An external isolated runner must be explicitly supplied for those
operations.  The planner validates exact package identity and produces a
hash-bound execution contract so a runner cannot silently substitute packages.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

_MSIX_NAME = re.compile(r"^[A-Za-z0-9._-]{1,180}\.msix$", re.IGNORECASE)


class MsixUpgradeQualificationError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _version(value: str) -> tuple[int, int, int, int]:
    parts = value.split(".")
    if len(parts) != 4 or any(not part.isdigit() for part in parts):
        raise MsixUpgradeQualificationError("msix_manifest_version_invalid")
    return tuple(int(part) for part in parts)  # type: ignore[return-value]


@dataclass(frozen=True)
class MsixIdentity:
    name: str
    publisher: str
    version: str
    architecture: str
    executable: str
    language: str

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "publisher": self.publisher, "version": self.version, "architecture": self.architecture, "executable": self.executable, "language": self.language}


def read_identity(package: str | Path) -> MsixIdentity:
    path = Path(package).resolve()
    if not path.is_file() or not _MSIX_NAME.fullmatch(path.name):
        raise MsixUpgradeQualificationError("msix_package_unavailable")
    try:
        with zipfile.ZipFile(path, "r") as archive:
            root = ElementTree.fromstring(archive.read("AppxManifest.xml"))
    except Exception as exc:
        raise MsixUpgradeQualificationError("msix_manifest_unreadable") from exc
    namespace = {"m": "http://schemas.microsoft.com/appx/manifest/foundation/windows10"}
    identity = root.find("m:Identity", namespace)
    application = root.find(".//m:Application", namespace)
    resource = root.find(".//m:Resources/m:Resource", namespace)
    if identity is None or application is None:
        raise MsixUpgradeQualificationError("msix_manifest_identity_missing")
    name = str(identity.attrib.get("Name") or "")
    publisher = str(identity.attrib.get("Publisher") or "")
    version = str(identity.attrib.get("Version") or "")
    architecture = str(identity.attrib.get("ProcessorArchitecture") or "")
    executable = str(application.attrib.get("Executable") or "")
    language = str((resource.attrib.get("Language") if resource is not None else "") or root.attrib.get("{http://www.w3.org/XML/1998/namespace}lang") or root.attrib.get("Language") or "")
    if not name or not publisher or not executable or architecture.lower() != "x64" or language.lower() != "en-us":
        raise MsixUpgradeQualificationError("msix_manifest_identity_invalid")
    _version(version)
    return MsixIdentity(name=name, publisher=publisher, version=version, architecture=architecture, executable=executable, language=language or "und")


def build_upgrade_execution_contract(prior_package: str | Path, candidate_package: str | Path) -> dict[str, Any]:
    prior_path = Path(prior_package).resolve()
    candidate_path = Path(candidate_package).resolve()
    prior = read_identity(prior_path)
    candidate = read_identity(candidate_path)
    blockers: list[str] = []
    if prior.name != candidate.name:
        blockers.append("package_identity_name_changed")
    if prior.publisher != candidate.publisher:
        blockers.append("package_identity_publisher_changed")
    if prior.architecture.lower() != candidate.architecture.lower():
        blockers.append("package_architecture_changed")
    if prior.executable != candidate.executable:
        blockers.append("package_executable_changed")
    if _version(candidate.version) <= _version(prior.version):
        blockers.append("candidate_version_not_greater_than_prior")
    return {
        "schema_version": "msix_upgrade_execution_contract_v1",
        "generated_at": _now(),
        "status": "blocked" if blockers else "ready_for_isolated_execution",
        "blockers": blockers,
        "prior": {"file_name": prior_path.name, "sha256": sha256_file(prior_path), "identity": prior.as_dict()},
        "candidate": {"file_name": candidate_path.name, "sha256": sha256_file(candidate_path), "identity": candidate.as_dict()},
        "required_isolated_steps": [
            "install_prior_package",
            "create_fictional_local_state",
            "capture_prior_state_hashes",
            "install_candidate_as_upgrade",
            "launch_and_verify_local_api_and_production_ui",
            "verify_fictional_matter_drafts_and_history_hashes",
            "restart_and_verify_state",
            "uninstall_and_reinstall_candidate",
            "verify_declared_data-retention_choice",
        ],
        "safety_boundary": {
            "requires_explicit_isolated_runner": True,
            "modifies_user_store_package": False,
            "synthetic_data_only": True,
            "network_required": False,
            "review_required": True,
        },
    }


def validate_runner_result(contract: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    required = {"install_prior_package", "create_fictional_local_state", "install_candidate_as_upgrade", "launch_and_verify_local_api_and_production_ui", "verify_fictional_matter_drafts_and_history_hashes", "restart_and_verify_state", "uninstall_and_reinstall_candidate", "verify_declared_data-retention_choice"}
    steps = result.get("steps") if isinstance(result, dict) else None
    completed = {str(row.get("id")) for row in steps if isinstance(row, dict) and row.get("status") == "pass"} if isinstance(steps, list) else set()
    blockers = list(contract.get("blockers") or [])
    if str(result.get("prior_sha256") or "") != str(((contract.get("prior") or {}).get("sha256") or "")):
        blockers.append("runner_prior_package_hash_mismatch")
    if str(result.get("candidate_sha256") or "") != str(((contract.get("candidate") or {}).get("sha256") or "")):
        blockers.append("runner_candidate_package_hash_mismatch")
    missing = sorted(required - completed)
    if missing:
        blockers.append("runner_required_steps_incomplete")
    return {"status": "pass" if not blockers else "blocked", "blockers": sorted(set(blockers)), "completed_steps": sorted(completed), "missing_steps": missing, "review_required": True, "store_or_enterprise_claim": "not_made"}


__all__ = ["MsixIdentity", "MsixUpgradeQualificationError", "build_upgrade_execution_contract", "read_identity", "sha256_file", "validate_runner_result"]
