"""Installed-app certification gate bound to one immutable MSIX artifact."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.security.durable_io import atomic_write_bytes


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class InstalledAppCertifier:
    """Refuse GA unless build, package, install lifecycle, and WACK all pass."""

    def __init__(self, package_path: str | Path, evidence_root: str | Path):
        self.package_path = Path(package_path).expanduser().resolve()
        self.evidence_root = Path(evidence_root).expanduser().resolve()

    def run(self) -> dict[str, Any]:
        package_hash = _sha256(self.package_path) if self.package_path.is_file() else ""
        gates = [
            self._gate("frozen_runtime_smoke", "store-build-smoke.json", self._smoke),
            self._gate(
                "installed_offline_qualification",
                "installed-offline-qualification.json",
                lambda value: (
                    value.get("qualification_status") == "pass" and not value.get("blockers")
                ),
            ),
            self._gate(
                "sealed_archive",
                "sealed-msix-archive-audit.json",
                lambda value: value.get("status") == "pass",
            ),
            self._gate(
                "private_data_audit",
                "private-data-audit.json",
                lambda value: value.get("status") == "pass",
            ),
            self._gate(
                "package_preflight",
                "store-preflight.json",
                lambda value: value.get("final_readiness_state") == "PASS",
            ),
            self._gate(
                "install_uninstall_reinstall",
                "installed-lifecycle.json",
                self._lifecycle,
            ),
        ]
        tied_hashes = {
            str(gate.get("package_sha256") or "") for gate in gates if gate.get("package_sha256")
        }
        if tied_hashes and tied_hashes != {package_hash}:
            gates.append(
                {
                    "gate": "artifact_identity",
                    "status": "blocked",
                    "blockers": ["evidence_package_hash_mismatch"],
                }
            )
        elif not package_hash:
            gates.append(
                {
                    "gate": "artifact_identity",
                    "status": "blocked",
                    "blockers": ["msix_package_unavailable"],
                }
            )
        else:
            gates.append({"gate": "artifact_identity", "status": "pass", "blockers": []})
        blockers = [
            f"{gate['gate']}:{blocker}" for gate in gates for blocker in gate.get("blockers", [])
        ]
        report = {
            "schema_version": "installed_app_certification_v1",
            "status": "pass" if not blockers else "blocked",
            "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "package_filename": self.package_path.name,
            "package_sha256": package_hash,
            "package_size_bytes": self.package_path.stat().st_size
            if self.package_path.is_file()
            else 0,
            "gates": gates,
            "blockers": blockers,
            "store_submission_eligible": not blockers,
            "external_wack_required": True,
            "review_required": True,
        }
        report["report_sha256"] = hashlib.sha256(
            json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return report

    def write(self, output: str | Path) -> dict[str, Any]:
        report = self.run()
        atomic_write_bytes(
            output,
            (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8"),
            mode=0o600,
        )
        return report

    def _gate(
        self,
        name: str,
        filename: str,
        predicate: Callable[[dict[str, Any]], bool],
    ) -> dict[str, Any]:
        path = self.evidence_root / filename
        if not path.is_file() or path.is_symlink():
            return {
                "gate": name,
                "status": "blocked",
                "evidence_file": filename,
                "blockers": ["evidence_missing"],
            }
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {
                "gate": name,
                "status": "blocked",
                "evidence_file": filename,
                "blockers": ["evidence_invalid"],
            }
        passed = predicate(value)
        package_hash = self._find_package_hash(value)
        return {
            "gate": name,
            "status": "pass" if passed else "blocked",
            "evidence_file": filename,
            "evidence_sha256": _sha256(path),
            "package_sha256": package_hash,
            "blockers": [] if passed else self._evidence_blockers(value),
        }

    @staticmethod
    def _smoke(value: dict[str, Any]) -> bool:
        return all(
            (
                value.get("launch_result") == "pass",
                value.get("api_health_result") is True,
                value.get("answer_grounded") is True,
                value.get("external_data_boundary_verification") is True,
            )
        )

    @staticmethod
    def _lifecycle(value: dict[str, Any]) -> bool:
        return (
            all(
                value.get(key) is True
                for key in (
                    "install_passed",
                    "launch_passed",
                    "ui_load_passed",
                    "uninstall_passed",
                    "reinstall_passed",
                    "data_retention_choice_verified",
                )
            )
            and value.get("wack_status") == "pass"
        )

    @staticmethod
    def _find_package_hash(value: Any) -> str:
        if isinstance(value, dict):
            for key in ("package_sha256", "msix_sha256"):
                candidate = str(value.get(key) or "").casefold()
                if len(candidate) == 64:
                    return candidate
            for key in ("package", "msix", "package_hash_tied_evidence"):
                item = value.get(key)
                if not isinstance(item, (dict, list)):
                    continue
                if isinstance(item, dict):
                    candidate = str(item.get("sha256") or "").casefold()
                    if len(candidate) == 64:
                        return candidate
                found = InstalledAppCertifier._find_package_hash(item)
                if found:
                    return found
        return ""

    @staticmethod
    def _evidence_blockers(value: dict[str, Any]) -> list[str]:
        blockers = [str(item) for item in value.get("blockers", []) if str(item)]
        return blockers or ["gate_predicate_failed"]


__all__ = ["InstalledAppCertifier"]
