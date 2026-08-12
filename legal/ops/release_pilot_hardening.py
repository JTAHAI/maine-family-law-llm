"""Release, backup, observability, and attorney-sandbox hardening controls.

This module deliberately distinguishes an operational control from evidence that a
control actually passed.  It never fabricates a signed package, WACK result,
vulnerability scan, attorney identity, pilot session, or GA approval.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from legal.data_boundaries.storage_layout import is_inside_project_repo

MAX_JSON_BYTES = 25 * 1024 * 1024
MAX_METRIC_ROWS = 10_000
MAX_METRIC_BYTES = 5 * 1024 * 1024
MAX_BACKUP_FILES = 20_000
MAX_BACKUP_BYTES = 4 * 1024 * 1024 * 1024
MAX_PILOT_ROWS = 20_000
_HASH_RE = re.compile(r"[a-f0-9]{64}")
_SAFE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
_WINDOWS_ABS_RE = re.compile(r"(?i)\b[A-Z]:[\\/]")
_EMAIL_RE = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_OBSERVABILITY_LOCK = threading.RLock()
_BACKUP_LOCK = threading.RLock()
_PILOT_LOCK = threading.RLock()


class ReleasePilotHardeningError(RuntimeError):
    def __init__(self, code: str, *, status_code: int = 400) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    tmp.write_bytes(json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n")
    os.replace(tmp, path)


def _read_json(path: Path) -> Any:
    if not path.is_file() or path.is_symlink():
        raise ReleasePilotHardeningError("evidence_file_unavailable", status_code=404)
    if path.stat().st_size > MAX_JSON_BYTES:
        raise ReleasePilotHardeningError("evidence_file_too_large", status_code=413)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleasePilotHardeningError("evidence_file_invalid_json", status_code=409) from exc


def _safe_external_root(
    configured: str | Path | None,
    *,
    repo_root: Path,
    forbidden_roots: Iterable[Path] = (),
    create: bool = False,
) -> Path | None:
    if configured is None or not str(configured).strip():
        return None
    root = Path(configured).expanduser()
    if root.exists() and root.is_symlink():
        raise ReleasePilotHardeningError("external_root_symlink_refused", status_code=409)
    root = root.resolve()
    if is_inside_project_repo(root, repo_root):
        raise ReleasePilotHardeningError("external_root_inside_source_repo", status_code=409)
    for forbidden in forbidden_roots:
        candidate = Path(forbidden).resolve()
        try:
            root.relative_to(candidate)
        except ValueError:
            pass
        else:
            raise ReleasePilotHardeningError("external_root_inside_forbidden_root", status_code=409)
        try:
            candidate.relative_to(root)
        except ValueError:
            pass
        else:
            raise ReleasePilotHardeningError("external_root_contains_forbidden_root", status_code=409)
    if create:
        root.mkdir(parents=True, exist_ok=True)
    return root


def find_source_root(start: str | Path) -> Path:
    current = Path(start).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "legal").is_dir():
            return candidate
    return current


@dataclass(frozen=True)
class EvidenceFileResult:
    filename: str
    present: bool
    sha256: str = ""
    size_bytes: int = 0
    status: str = "missing"
    blockers: tuple[str, ...] = ()
    summary: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "present": self.present,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "status": self.status,
            "blockers": list(self.blockers),
            "summary": dict(self.summary or {}),
        }


class ReleaseEvidenceAuditor:
    """Audit externally generated supply-chain and signed-MSIX evidence."""

    EXPECTED = (
        "sbom.cyclonedx.json",
        "sbom.spdx.json",
        "grype.json",
        "pip-audit.json",
        "semgrep.json",
        "msix-qualification.json",
        "backup-restore.json",
    )

    TOOL_NAMES = {
        "syft": ("syft",),
        "grype": ("grype",),
        "semgrep": ("semgrep",),
        "pip_audit": ("pip-audit",),
        "makeappx": ("makeappx", "makeappx.exe"),
        "signtool": ("signtool", "signtool.exe"),
        "wack": ("appcert", "appcert.exe"),
    }

    def __init__(self, repo_root: str | Path, evidence_root: str | Path | None = None) -> None:
        self.repo_root = find_source_root(repo_root)
        configured = evidence_root or os.environ.get("MAINE_FAMILY_LAW_RELEASE_EVIDENCE_ROOT")
        self.evidence_root = _safe_external_root(configured, repo_root=self.repo_root)

    def tool_status(self) -> dict[str, Any]:
        tools: dict[str, Any] = {}
        for label, names in self.TOOL_NAMES.items():
            found = next((shutil.which(name) for name in names if shutil.which(name)), None)
            tools[label] = {"available": bool(found), "executable": Path(found).name if found else ""}
        return tools

    @staticmethod
    def _severity(value: Any) -> str:
        return str(value or "").strip().casefold()

    def _audit_cyclonedx(self, path: Path, payload: Any) -> EvidenceFileResult:
        blockers: list[str] = []
        if not isinstance(payload, dict) or str(payload.get("bomFormat") or "") != "CycloneDX":
            blockers.append("cyclonedx_format_invalid")
        components = payload.get("components") if isinstance(payload, dict) else None
        if not isinstance(components, list):
            blockers.append("cyclonedx_components_missing")
        return self._result(path, blockers, {"component_count": len(components or [])})

    def _audit_spdx(self, path: Path, payload: Any) -> EvidenceFileResult:
        blockers: list[str] = []
        if not isinstance(payload, dict) or not str(payload.get("spdxVersion") or "").startswith("SPDX-"):
            blockers.append("spdx_format_invalid")
        packages = payload.get("packages") if isinstance(payload, dict) else None
        if not isinstance(packages, list):
            blockers.append("spdx_packages_missing")
        return self._result(path, blockers, {"package_count": len(packages or [])})

    def _audit_grype(self, path: Path, payload: Any) -> EvidenceFileResult:
        matches = payload.get("matches") if isinstance(payload, dict) else None
        blockers: list[str] = []
        if not isinstance(matches, list):
            blockers.append("grype_matches_missing")
            matches = []
        critical = 0
        high = 0
        for match in matches:
            vulnerability = match.get("vulnerability") if isinstance(match, dict) else {}
            severity = self._severity((vulnerability or {}).get("severity"))
            if severity == "critical":
                critical += 1
            elif severity == "high":
                high += 1
        if critical:
            blockers.append("grype_critical_findings")
        if high:
            blockers.append("grype_high_findings")
        return self._result(path, blockers, {"match_count": len(matches), "critical": critical, "high": high})

    def _audit_pip(self, path: Path, payload: Any) -> EvidenceFileResult:
        dependencies = payload.get("dependencies") if isinstance(payload, dict) else payload
        blockers: list[str] = []
        if not isinstance(dependencies, list):
            blockers.append("pip_audit_dependencies_missing")
            dependencies = []
        vulnerabilities = 0
        for dependency in dependencies:
            vulns = dependency.get("vulns") if isinstance(dependency, dict) else None
            if isinstance(vulns, list):
                vulnerabilities += len(vulns)
        if vulnerabilities:
            blockers.append("pip_audit_vulnerabilities_found")
        return self._result(path, blockers, {"dependency_count": len(dependencies), "vulnerability_count": vulnerabilities})

    def _audit_semgrep(self, path: Path, payload: Any) -> EvidenceFileResult:
        blockers: list[str] = []
        results = payload.get("results") if isinstance(payload, dict) else None
        errors = payload.get("errors") if isinstance(payload, dict) else None
        if not isinstance(results, list):
            blockers.append("semgrep_results_missing")
            results = []
        if not isinstance(errors, list):
            errors = []
        blocking_results = 0
        for result in results:
            extra = result.get("extra") if isinstance(result, dict) else {}
            severity = self._severity((extra or {}).get("severity"))
            if severity in {"error", "critical", "high"}:
                blocking_results += 1
        if errors:
            blockers.append("semgrep_execution_errors")
        if blocking_results:
            blockers.append("semgrep_blocking_findings")
        return self._result(path, blockers, {"finding_count": len(results), "blocking_findings": blocking_results, "error_count": len(errors)})

    @staticmethod
    def _verify_referenced_file(
        root: Path,
        payload: dict[str, Any],
        *,
        filename_field: str,
        hash_field: str,
        blocker_prefix: str,
    ) -> tuple[str, str, list[str]]:
        blockers: list[str] = []
        filename = str(payload.get(filename_field) or "").strip()
        expected_hash = str(payload.get(hash_field) or "").strip().casefold()
        if not filename or Path(filename).name != filename or "/" in filename or "\\" in filename:
            blockers.append(f"{blocker_prefix}_filename_missing_or_unsafe")
            return filename, expected_hash, blockers
        if not _HASH_RE.fullmatch(expected_hash):
            blockers.append(f"{blocker_prefix}_hash_missing")
        target = root / filename
        if not target.is_file() or target.is_symlink():
            blockers.append(f"{blocker_prefix}_file_missing")
        elif _HASH_RE.fullmatch(expected_hash) and _sha_file(target) != expected_hash:
            blockers.append(f"{blocker_prefix}_hash_mismatch")
        return filename, expected_hash, blockers


    def _audit_msix(self, path: Path, payload: Any) -> EvidenceFileResult:
        blockers: list[str] = []
        if not isinstance(payload, dict):
            payload = {}
            blockers.append("msix_qualification_invalid")
        package_hash = str(payload.get("package_sha256") or "").casefold()
        if not _HASH_RE.fullmatch(package_hash):
            blockers.append("msix_package_hash_missing")
        required_true = (
            "signed",
            "signature_verified",
            "install_passed",
            "launch_passed",
            "api_health_passed",
            "ui_load_passed",
            "uninstall_passed",
            "reinstall_passed",
        )
        for field in required_true:
            if payload.get(field) is not True:
                blockers.append(f"msix_{field}_required")
        if str(payload.get("architecture") or "").casefold() not in {"x64", "amd64"}:
            blockers.append("msix_x64_architecture_required")
        if str(payload.get("wack_status") or "").casefold() != "pass":
            blockers.append("wack_pass_required")
        package_filename, _package_hash, package_blockers = self._verify_referenced_file(
            path.parent,
            payload,
            filename_field="package_filename",
            hash_field="package_sha256",
            blocker_prefix="msix_package",
        )
        signature_filename, _signature_hash, signature_blockers = self._verify_referenced_file(
            path.parent,
            payload,
            filename_field="signature_report_filename",
            hash_field="signature_report_sha256",
            blocker_prefix="msix_signature_report",
        )
        smoke_filename, _smoke_hash, smoke_blockers = self._verify_referenced_file(
            path.parent,
            payload,
            filename_field="install_smoke_filename",
            hash_field="install_smoke_sha256",
            blocker_prefix="msix_install_smoke",
        )
        wack_filename, _wack_hash, wack_blockers = self._verify_referenced_file(
            path.parent,
            payload,
            filename_field="wack_report_filename",
            hash_field="wack_report_sha256",
            blocker_prefix="wack_report",
        )
        blockers.extend(package_blockers)
        blockers.extend(signature_blockers)
        blockers.extend(smoke_blockers)
        blockers.extend(wack_blockers)
        return self._result(path, blockers, {
            "package_version": str(payload.get("package_version") or ""),
            "architecture": str(payload.get("architecture") or ""),
            "signed": payload.get("signed") is True,
            "wack_status": str(payload.get("wack_status") or "unknown"),
            "package_filename": package_filename,
            "signature_report_filename": signature_filename,
            "install_smoke_filename": smoke_filename,
            "wack_report_filename": wack_filename,
        })

    def _audit_backup(self, path: Path, payload: Any) -> EvidenceFileResult:
        blockers: list[str] = []
        if not isinstance(payload, dict):
            payload = {}
            blockers.append("backup_restore_report_invalid")
        if payload.get("status") != "pass":
            blockers.append("backup_restore_drill_not_passed")
        if payload.get("backup_verified") is not True:
            blockers.append("backup_verification_required")
        if payload.get("restore_rehearsal_verified") is not True:
            blockers.append("restore_rehearsal_required")
        if not _HASH_RE.fullmatch(str(payload.get("backup_sha256") or "").casefold()):
            blockers.append("backup_hash_missing")
        return self._result(path, blockers, {
            "file_count": int(payload.get("file_count") or 0),
            "backup_verified": payload.get("backup_verified") is True,
            "restore_rehearsal_verified": payload.get("restore_rehearsal_verified") is True,
        })

    @staticmethod
    def _result(path: Path, blockers: list[str], summary: dict[str, Any]) -> EvidenceFileResult:
        return EvidenceFileResult(
            filename=path.name,
            present=True,
            sha256=_sha_file(path),
            size_bytes=path.stat().st_size,
            status="pass" if not blockers else "blocked",
            blockers=tuple(sorted(set(blockers))),
            summary=summary,
        )

    def _audit_path(self, filename: str) -> EvidenceFileResult:
        if self.evidence_root is None:
            return EvidenceFileResult(filename=filename, present=False, blockers=("release_evidence_root_not_configured",))
        path = self.evidence_root / filename
        if not path.is_file() or path.is_symlink():
            return EvidenceFileResult(filename=filename, present=False, blockers=(f"missing:{filename}",))
        try:
            payload = _read_json(path)
            if filename == "sbom.cyclonedx.json":
                return self._audit_cyclonedx(path, payload)
            if filename == "sbom.spdx.json":
                return self._audit_spdx(path, payload)
            if filename == "grype.json":
                return self._audit_grype(path, payload)
            if filename == "pip-audit.json":
                return self._audit_pip(path, payload)
            if filename == "semgrep.json":
                return self._audit_semgrep(path, payload)
            if filename == "msix-qualification.json":
                return self._audit_msix(path, payload)
            if filename == "backup-restore.json":
                return self._audit_backup(path, payload)
        except ReleasePilotHardeningError as exc:
            return EvidenceFileResult(filename=filename, present=True, status="blocked", blockers=(exc.code,))
        return EvidenceFileResult(filename=filename, present=True, status="blocked", blockers=("unsupported_evidence_file",))

    def audit(self) -> dict[str, Any]:
        files = [self._audit_path(name) for name in self.EXPECTED]
        blockers = sorted({blocker for row in files for blocker in row.blockers})
        return {
            "schema_version": "release_supply_chain_evidence_v1",
            "status": "pass" if not blockers else "blocked",
            "files": [row.as_dict() for row in files],
            "blockers": blockers,
            "tool_status": self.tool_status(),
            "store_package_qualified": not blockers,
            "legal_ga_ready": False,
            "legal_ga_blockers": [
                "attorney_sandbox_external_audit_required",
                "limited_real_matter_pilot_evidence_required",
                "legal_product_ops_signoff_required",
            ],
            "external_root_configured": self.evidence_root is not None,
            "review_required": True,
        }


class OpenTelemetryLocalBridge:
    """Optional in-memory OpenTelemetry bridge with no exporter or private payloads."""

    def __init__(self) -> None:
        self._available = False
        self._error = ""
        self._meter = None
        self._reader = None
        self._instruments: dict[tuple[str, str], Any] = {}
        try:
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.metrics.export import InMemoryMetricReader

            self._reader = InMemoryMetricReader()
            provider = MeterProvider(metric_readers=[self._reader])
            self._meter = provider.get_meter("maine-family-law-llm", "5.13.0")
            self._available = True
        except Exception as exc:  # optional developer/runtime dependency
            self._error = type(exc).__name__

    def status(self) -> dict[str, Any]:
        return {
            "available": self._available,
            "mode": "in_memory_only" if self._available else "unavailable",
            "remote_exporters_enabled": False,
            "private_attributes_allowed": False,
            "error_class": self._error,
        }

    def emit(self, event: str, metrics: dict[str, float | int], labels: dict[str, str]) -> bool:
        if not self._available or self._meter is None:
            return False
        attributes = {"event": event, **labels}
        try:
            for key, value in metrics.items():
                instrument_key = (key, "histogram" if key == "duration_ms" else "counter")
                instrument = self._instruments.get(instrument_key)
                if instrument is None:
                    name = f"mfl.{key}"
                    if key == "duration_ms":
                        instrument = self._meter.create_histogram(name, unit="ms")
                    else:
                        instrument = self._meter.create_counter(name)
                    self._instruments[instrument_key] = instrument
                if key == "duration_ms":
                    instrument.record(value, attributes)
                else:
                    instrument.add(value, attributes)
            return True
        except Exception:
            return False


_OTEL_BRIDGE = OpenTelemetryLocalBridge()


class PrivacySafeObservabilityStore:
    """Bounded hash-chained local metrics that refuse private prose and paths."""

    ALLOWED_EVENTS = {
        "parser",
        "ocr",
        "retrieval",
        "model_generation",
        "verifier",
        "review_queue",
        "document_commit",
        "source_inspector",
        "backup_restore",
        "api_request",
        "cancellation",
        "timeout",
        "error",
        "self_test",
    }
    ALLOWED_METRICS = {"duration_ms", "count", "bytes", "queue_depth", "result_count", "error_count"}
    ALLOWED_LABELS = {"status", "component", "operation", "error_class", "mode"}

    def __init__(self, case_root: str | Path) -> None:
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / ".mfl_work" / "observability"
        self.path = self.root / "metrics.jsonl"

    @staticmethod
    def _safe_label(value: Any) -> str:
        text = str(value or "").strip()[:80]
        if not text:
            return ""
        if _EMAIL_RE.search(text) or _SSN_RE.search(text) or _WINDOWS_ABS_RE.search(text) or "/" in text or "\\" in text:
            raise ReleasePilotHardeningError("observability_private_or_path_label_refused", status_code=409)
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", text):
            raise ReleasePilotHardeningError("observability_label_invalid", status_code=409)
        return text

    def _read_rows(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        if self.path.is_symlink() or self.path.stat().st_size > MAX_METRIC_BYTES:
            raise ReleasePilotHardeningError("observability_store_invalid", status_code=409)
        rows: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ReleasePilotHardeningError("observability_store_invalid_json", status_code=409) from exc
            if not isinstance(row, dict):
                raise ReleasePilotHardeningError("observability_store_invalid_row", status_code=409)
            rows.append(row)
            if len(rows) > MAX_METRIC_ROWS:
                raise ReleasePilotHardeningError("observability_store_row_limit_exceeded", status_code=409)
        return rows

    def record(self, event: str, *, metrics: dict[str, Any] | None = None, labels: dict[str, Any] | None = None) -> dict[str, Any]:
        event = str(event or "").strip().casefold()
        if event not in self.ALLOWED_EVENTS:
            raise ReleasePilotHardeningError("observability_event_not_allowed", status_code=409)
        safe_metrics: dict[str, float | int] = {}
        for key, value in dict(metrics or {}).items():
            if key not in self.ALLOWED_METRICS or isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ReleasePilotHardeningError("observability_metric_not_allowed", status_code=409)
            if value < 0 or value > 10**15:
                raise ReleasePilotHardeningError("observability_metric_out_of_range", status_code=409)
            safe_metrics[key] = value
        safe_labels: dict[str, str] = {}
        for key, value in dict(labels or {}).items():
            if key not in self.ALLOWED_LABELS:
                raise ReleasePilotHardeningError("observability_label_not_allowed", status_code=409)
            safe_labels[key] = self._safe_label(value)
        with _OBSERVABILITY_LOCK:
            rows = self._read_rows()
            previous = str(rows[-1].get("record_sha256") or "") if rows else "0" * 64
            sequence = len(rows) + 1
            body = {
                "schema_version": "privacy_safe_metric_v1",
                "sequence": sequence,
                "recorded_at": _now_iso(),
                "event": event,
                "metrics": safe_metrics,
                "labels": safe_labels,
                "previous_sha256": previous,
                "contains_user_text": False,
                "contains_document_text": False,
                "contains_paths": False,
            }
            body["record_sha256"] = _sha_bytes(_canonical_json(body))
            self.root.mkdir(parents=True, exist_ok=True)
            if self.path.exists() and self.path.is_symlink():
                raise ReleasePilotHardeningError("observability_store_symlink_refused", status_code=409)
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n")
            _OTEL_BRIDGE.emit(event, safe_metrics, safe_labels)
            return body

    def verify(self) -> dict[str, Any]:
        rows = self._read_rows()
        previous = "0" * 64
        blockers: list[str] = []
        for index, row in enumerate(rows, start=1):
            if int(row.get("sequence") or 0) != index:
                blockers.append(f"sequence_mismatch:{index}")
            if row.get("previous_sha256") != previous:
                blockers.append(f"chain_mismatch:{index}")
            supplied = str(row.get("record_sha256") or "")
            body = dict(row)
            body.pop("record_sha256", None)
            actual = _sha_bytes(_canonical_json(body))
            if supplied != actual:
                blockers.append(f"hash_mismatch:{index}")
            previous = supplied
        counts: dict[str, int] = {}
        for row in rows:
            event = str(row.get("event") or "unknown")
            counts[event] = counts.get(event, 0) + 1
        return {
            "schema_version": "privacy_safe_observability_status_v1",
            "status": "pass" if not blockers else "blocked",
            "row_count": len(rows),
            "event_counts": counts,
            "latest_record_sha256": previous if rows else "",
            "blockers": blockers,
            "local_only": True,
            "remote_exporters_enabled": False,
            "private_payload_logging_enabled": False,
            "opentelemetry": _OTEL_BRIDGE.status(),
        }


class MatterBackupRestoreDrill:
    """Create and verify a private, external, content-addressed matter backup."""

    EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".ruff_cache", "dist", "build"}
    EXCLUDED_SUFFIXES = {".tmp", ".bak", ".log"}

    def __init__(
        self,
        case_root: str | Path,
        *,
        repo_root: str | Path,
        backup_root: str | Path | None = None,
        release_evidence_root: str | Path | None = None,
    ) -> None:
        self.case_root = Path(case_root).resolve()
        self.repo_root = find_source_root(repo_root)
        configured = backup_root or os.environ.get("MAINE_FAMILY_LAW_BACKUP_ROOT")
        self.backup_root = _safe_external_root(
            configured,
            repo_root=self.repo_root,
            forbidden_roots=(self.case_root,),
            create=bool(configured),
        )
        evidence_configured = release_evidence_root or os.environ.get("MAINE_FAMILY_LAW_RELEASE_EVIDENCE_ROOT")
        self.release_evidence_root = _safe_external_root(
            evidence_configured,
            repo_root=self.repo_root,
            forbidden_roots=(self.case_root,),
            create=False,
        )

    def status(self) -> dict[str, Any]:
        blockers = [] if self.backup_root is not None else ["backup_root_not_configured"]
        return {
            "status": "ready" if not blockers else "blocked",
            "blockers": blockers,
            "backup_root_configured": self.backup_root is not None,
            "release_evidence_root_configured": self.release_evidence_root is not None,
            "active_matter_available": self.case_root.is_dir(),
            "restore_mode": "isolated_rehearsal_only",
            "review_required": True,
        }

    def _files(self) -> list[tuple[str, Path, int, str]]:
        if not self.case_root.is_dir() or self.case_root.is_symlink():
            raise ReleasePilotHardeningError("active_matter_unavailable", status_code=404)
        rows: list[tuple[str, Path, int, str]] = []
        total = 0
        for path in sorted(self.case_root.rglob("*"), key=lambda item: item.as_posix().casefold()):
            relative = path.relative_to(self.case_root)
            if any(part in self.EXCLUDED_PARTS for part in relative.parts):
                continue
            if path.is_symlink():
                raise ReleasePilotHardeningError("backup_symlink_refused", status_code=409)
            if not path.is_file() or path.suffix.casefold() in self.EXCLUDED_SUFFIXES:
                continue
            size = path.stat().st_size
            total += size
            if len(rows) >= MAX_BACKUP_FILES:
                raise ReleasePilotHardeningError("backup_file_limit_exceeded", status_code=413)
            if total > MAX_BACKUP_BYTES:
                raise ReleasePilotHardeningError("backup_byte_limit_exceeded", status_code=413)
            rows.append((relative.as_posix(), path, size, _sha_file(path)))
        return rows

    @staticmethod
    def _zip_info(name: str) -> zipfile.ZipInfo:
        info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o600 << 16
        return info

    @staticmethod
    def _safe_zip_name(name: str) -> bool:
        path = PurePosixPath(name)
        return bool(name) and not path.is_absolute() and ".." not in path.parts and "\\" not in name

    def run(self, *, approved: bool) -> dict[str, Any]:
        with _BACKUP_LOCK:
            if approved is not True:
                raise ReleasePilotHardeningError("backup_restore_approval_required", status_code=409)
            if self.backup_root is None:
                raise ReleasePilotHardeningError("backup_root_not_configured", status_code=409)
            files = self._files()
            manifest_basis = {
                "schema_version": "matter_backup_manifest_v1",
                "case_scope_sha256": _sha_bytes(str(self.case_root).encode("utf-8")),
                "files": [{"path": rel, "size": size, "sha256": sha} for rel, _path, size, sha in files],
            }
            backup_id = _sha_bytes(_canonical_json(manifest_basis))
            generation = self.backup_root / "matter-backups" / backup_id
            generation.mkdir(parents=True, exist_ok=True)
            archive = generation / f"matter-backup-{backup_id[:16]}.zip"
            manifest = {**manifest_basis, "backup_id": backup_id}
            manifest_bytes = json.dumps(manifest, sort_keys=True, indent=2).encode("utf-8") + b"\n"
            if archive.exists() and archive.is_symlink():
                raise ReleasePilotHardeningError("backup_archive_symlink_refused", status_code=409)
            if not archive.exists():
                temp_archive = archive.with_suffix(".tmp")
                with zipfile.ZipFile(temp_archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
                    output.writestr(self._zip_info("backup-manifest.json"), manifest_bytes)
                    for relative, path, _size, _sha in files:
                        output.writestr(self._zip_info(f"matter/{relative}"), path.read_bytes())
                os.replace(temp_archive, archive)
            archive_sha = _sha_file(archive)
            verification = self.verify_archive(archive, expected_manifest=manifest)
            rehearsal = self.restore_rehearsal(archive, expected_manifest=manifest)
            report = {
                "schema_version": "matter_backup_restore_drill_v1",
                "status": "pass" if verification["status"] == "pass" and rehearsal["status"] == "pass" else "blocked",
                "backup_id": backup_id,
                "backup_filename": archive.name,
                "backup_sha256": archive_sha,
                "file_count": len(files),
                "total_bytes": sum(size for _rel, _path, size, _sha in files),
                "backup_verified": verification["status"] == "pass",
                "restore_rehearsal_verified": rehearsal["status"] == "pass",
                "verification": verification,
                "restore_rehearsal": rehearsal,
                "original_matter_modified": False,
                "restore_mode": "isolated_temporary_rehearsal",
                "completed_at": _now_iso(),
                "review_required": True,
            }
            _write_json(generation / "backup-restore.json", report)
            if self.release_evidence_root is not None:
                _write_json(self.release_evidence_root / "backup-restore.json", report)
            return report


    def verify_archive(self, archive: Path, *, expected_manifest: dict[str, Any] | None = None) -> dict[str, Any]:
        blockers: list[str] = []
        if not archive.is_file() or archive.is_symlink():
            return {"status": "blocked", "blockers": ["backup_archive_unavailable"]}
        seen: set[str] = set()
        with zipfile.ZipFile(archive, "r") as source:
            infos = source.infolist()
            for info in infos:
                if info.filename in seen:
                    blockers.append(f"duplicate_zip_entry:{info.filename}")
                seen.add(info.filename)
                if not self._safe_zip_name(info.filename):
                    blockers.append(f"unsafe_zip_entry:{info.filename}")
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    blockers.append(f"symlink_zip_entry:{info.filename}")
            try:
                manifest = json.loads(source.read("backup-manifest.json").decode("utf-8"))
            except Exception:
                manifest = {}
                blockers.append("backup_manifest_unavailable")
            if expected_manifest is not None and manifest != expected_manifest:
                blockers.append("backup_manifest_mismatch")
            entries = manifest.get("files") if isinstance(manifest, dict) else None
            if not isinstance(entries, list):
                entries = []
                blockers.append("backup_manifest_files_missing")
            expected_names = {"backup-manifest.json", *(f"matter/{row.get('path')}" for row in entries if isinstance(row, dict))}
            if seen != expected_names:
                blockers.append("backup_entry_set_mismatch")
            for row in entries:
                if not isinstance(row, dict):
                    blockers.append("backup_manifest_row_invalid")
                    continue
                name = f"matter/{row.get('path')}"
                try:
                    data = source.read(name)
                except KeyError:
                    blockers.append(f"backup_entry_missing:{name}")
                    continue
                if len(data) != int(row.get("size") or -1):
                    blockers.append(f"backup_size_mismatch:{name}")
                if _sha_bytes(data) != str(row.get("sha256") or ""):
                    blockers.append(f"backup_hash_mismatch:{name}")
        return {"status": "pass" if not blockers else "blocked", "blockers": blockers, "entry_count": len(seen)}

    def restore_rehearsal(self, archive: Path, *, expected_manifest: dict[str, Any]) -> dict[str, Any]:
        blockers: list[str] = []
        with tempfile.TemporaryDirectory(prefix="mfl-restore-rehearsal-", dir=self.backup_root) as temp:
            target = Path(temp)
            with zipfile.ZipFile(archive, "r") as source:
                for row in expected_manifest.get("files", []):
                    relative = str(row.get("path") or "")
                    name = f"matter/{relative}"
                    if not self._safe_zip_name(name):
                        blockers.append(f"unsafe_restore_entry:{name}")
                        continue
                    destination = target / "matter" / PurePosixPath(relative)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(source.read(name))
                    if destination.stat().st_size != int(row.get("size") or -1):
                        blockers.append(f"restore_size_mismatch:{relative}")
                    if _sha_file(destination) != str(row.get("sha256") or ""):
                        blockers.append(f"restore_hash_mismatch:{relative}")
        return {
            "status": "pass" if not blockers else "blocked",
            "blockers": blockers,
            "restored_file_count": len(expected_manifest.get("files", [])),
            "temporary_copy_deleted": True,
            "active_matter_modified": False,
        }


class AttorneySandboxStore:
    """Append-only, external attorney-sandbox operations without private matters."""

    REQUIRED_TRAINING = {
        "data_boundaries",
        "source_grounding",
        "citation_quote_verification",
        "review_required_exports",
        "feedback_and_error_reporting",
    }
    DATA_CLASSES = {"synthetic", "public_authority"}
    SEVERITIES = {"low", "medium", "high", "critical"}
    CATEGORIES = {"legal_accuracy", "citation", "retrieval", "workflow", "privacy", "security", "accessibility", "other"}

    def __init__(self, repo_root: str | Path, pilot_root: str | Path | None = None) -> None:
        self.repo_root = find_source_root(repo_root)
        configured = pilot_root or os.environ.get("MAINE_FAMILY_LAW_PILOT_ROOT")
        self.root = _safe_external_root(configured, repo_root=self.repo_root, create=bool(configured))
        if self.root is not None:
            self.ledger_path = self.root / "attorney-sandbox-ledger.jsonl"
        else:
            self.ledger_path = None

    @staticmethod
    def _safe_id(value: Any, code: str) -> str:
        text = str(value or "").strip()
        if not _SAFE_ID_RE.fullmatch(text):
            raise ReleasePilotHardeningError(code, status_code=409)
        return text

    @staticmethod
    def _safe_description(value: Any) -> str:
        text = str(value or "").strip()[:2_000]
        if not text:
            raise ReleasePilotHardeningError("pilot_feedback_description_required", status_code=409)
        if _EMAIL_RE.search(text) or _SSN_RE.search(text) or _WINDOWS_ABS_RE.search(text):
            raise ReleasePilotHardeningError("pilot_feedback_private_data_refused", status_code=409)
        return text

    def _rows(self) -> list[dict[str, Any]]:
        if self.ledger_path is None or not self.ledger_path.exists():
            return []
        if self.ledger_path.is_symlink() or self.ledger_path.stat().st_size > MAX_JSON_BYTES:
            raise ReleasePilotHardeningError("pilot_ledger_invalid", status_code=409)
        rows = []
        for line in self.ledger_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ReleasePilotHardeningError("pilot_ledger_invalid_json", status_code=409) from exc
            if not isinstance(row, dict):
                raise ReleasePilotHardeningError("pilot_ledger_invalid_row", status_code=409)
            rows.append(row)
            if len(rows) > MAX_PILOT_ROWS:
                raise ReleasePilotHardeningError("pilot_ledger_row_limit_exceeded", status_code=409)
        return rows

    def _append(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self.root is None or self.ledger_path is None:
            raise ReleasePilotHardeningError("pilot_root_not_configured", status_code=409)
        with _PILOT_LOCK:
            rows = self._rows()
            previous = str(rows[-1].get("record_sha256") or "") if rows else "0" * 64
            body = {
                "schema_version": "attorney_sandbox_event_v1",
                "sequence": len(rows) + 1,
                "event_type": event_type,
                "recorded_at": _now_iso(),
                "previous_sha256": previous,
                **payload,
            }
            body["record_sha256"] = _sha_bytes(_canonical_json(body))
            self.root.mkdir(parents=True, exist_ok=True)
            if self.ledger_path.exists() and self.ledger_path.is_symlink():
                raise ReleasePilotHardeningError("pilot_ledger_symlink_refused", status_code=409)
            with self.ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n")
            return body

    def register_participant(
        self,
        *,
        participant_id: str,
        role: str,
        bar_status_verified: bool,
        verification_reference_sha256: str,
        terms_accepted: bool,
        training_modules: list[str],
    ) -> dict[str, Any]:
        participant_id = self._safe_id(participant_id, "pilot_participant_id_invalid")
        role = self._safe_id(role, "pilot_role_invalid")
        verification_reference_sha256 = str(verification_reference_sha256 or "").casefold()
        if bar_status_verified and not _HASH_RE.fullmatch(verification_reference_sha256):
            raise ReleasePilotHardeningError("pilot_bar_verification_reference_required", status_code=409)
        completed = {str(item or "").strip() for item in training_modules}
        missing = sorted(self.REQUIRED_TRAINING - completed)
        eligible = bool(bar_status_verified and terms_accepted and not missing)
        return self._append("participant_registered", {
            "participant_id": participant_id,
            "role": role,
            "bar_status_verified": bool(bar_status_verified),
            "verification_reference_sha256": verification_reference_sha256 if bar_status_verified else "",
            "terms_accepted": bool(terms_accepted),
            "training_modules": sorted(completed & self.REQUIRED_TRAINING),
            "missing_training_modules": missing,
            "sandbox_eligible": eligible,
            "identity_independently_verified_by_application": False,
            "allowed_data": sorted(self.DATA_CLASSES),
            "real_matter_allowed": False,
        })

    def _latest_participant(self, participant_id: str) -> dict[str, Any] | None:
        matches = [row for row in self._rows() if row.get("event_type") == "participant_registered" and row.get("participant_id") == participant_id]
        return matches[-1] if matches else None

    def start_session(self, *, participant_id: str, data_classification: str, approved: bool) -> dict[str, Any]:
        if approved is not True:
            raise ReleasePilotHardeningError("pilot_session_approval_required", status_code=409)
        participant_id = self._safe_id(participant_id, "pilot_participant_id_invalid")
        data_classification = str(data_classification or "").strip().casefold()
        if data_classification not in self.DATA_CLASSES:
            raise ReleasePilotHardeningError("pilot_private_or_unsupported_data_refused", status_code=409)
        participant = self._latest_participant(participant_id)
        if not participant or participant.get("sandbox_eligible") is not True:
            raise ReleasePilotHardeningError("pilot_participant_not_eligible", status_code=409)
        session_nonce = f"{participant_id}\0{time.time_ns()}"
        session_id = f"sandbox-{_sha_bytes(session_nonce.encode())[:20]}"
        return self._append("session_started", {
            "session_id": session_id,
            "participant_id": participant_id,
            "data_classification": data_classification,
            "real_matter_allowed": False,
            "exports_review_required": True,
            "private_data_allowed_for_training": False,
        })

    def add_feedback(
        self,
        *,
        participant_id: str,
        session_id: str,
        category: str,
        severity: str,
        description: str,
    ) -> dict[str, Any]:
        participant_id = self._safe_id(participant_id, "pilot_participant_id_invalid")
        session_id = self._safe_id(session_id, "pilot_session_id_invalid")
        category = str(category or "").strip().casefold()
        severity = str(severity or "").strip().casefold()
        if category not in self.CATEGORIES:
            raise ReleasePilotHardeningError("pilot_feedback_category_invalid", status_code=409)
        if severity not in self.SEVERITIES:
            raise ReleasePilotHardeningError("pilot_feedback_severity_invalid", status_code=409)
        sessions = [row for row in self._rows() if row.get("event_type") == "session_started" and row.get("session_id") == session_id]
        if not sessions or sessions[-1].get("participant_id") != participant_id:
            raise ReleasePilotHardeningError("pilot_session_not_available", status_code=404)
        feedback_nonce = f"{participant_id}\0{session_id}\0{time.time_ns()}"
        feedback_id = f"feedback-{_sha_bytes(feedback_nonce.encode())[:20]}"
        return self._append("feedback_recorded", {
            "feedback_id": feedback_id,
            "participant_id": participant_id,
            "session_id": session_id,
            "category": category,
            "severity": severity,
            "description": self._safe_description(description),
            "creates_eval_candidate": True,
            "may_be_counted_as_gold": False,
            "private_data_allowed_for_training": False,
            "blocks_release": severity in {"critical", "high"},
            "status": "open",
        })

    def verify(self) -> dict[str, Any]:
        rows = self._rows()
        previous = "0" * 64
        blockers: list[str] = []
        for index, row in enumerate(rows, start=1):
            if int(row.get("sequence") or 0) != index:
                blockers.append(f"sequence_mismatch:{index}")
            if row.get("previous_sha256") != previous:
                blockers.append(f"chain_mismatch:{index}")
            supplied = str(row.get("record_sha256") or "")
            body = dict(row)
            body.pop("record_sha256", None)
            if supplied != _sha_bytes(_canonical_json(body)):
                blockers.append(f"hash_mismatch:{index}")
            previous = supplied
        return {"status": "pass" if not blockers else "blocked", "row_count": len(rows), "blockers": blockers, "latest_record_sha256": previous if rows else ""}

    def dashboard(self) -> dict[str, Any]:
        rows = self._rows()
        participants = [row for row in rows if row.get("event_type") == "participant_registered"]
        latest_by_id: dict[str, dict[str, Any]] = {}
        for row in participants:
            latest_by_id[str(row.get("participant_id") or "")] = row
        eligible = [row for row in latest_by_id.values() if row.get("sandbox_eligible") is True]
        sessions = [row for row in rows if row.get("event_type") == "session_started"]
        feedback = [row for row in rows if row.get("event_type") == "feedback_recorded"]
        blockers = [str(row.get("feedback_id") or "") for row in feedback if row.get("blocks_release") is True and row.get("status") != "closed"]
        verification = self.verify()
        return {
            "schema_version": "attorney_sandbox_dashboard_v1",
            "status": "operational" if eligible and sessions and verification["status"] == "pass" else "blocked",
            "root_configured": self.root is not None,
            "participant_count": len(latest_by_id),
            "eligible_participant_count": len(eligible),
            "session_count": len(sessions),
            "feedback_count": len(feedback),
            "open_release_blockers": blockers,
            "verification": verification,
            "allowed_data": sorted(self.DATA_CLASSES),
            "real_matter_allowed": False,
            "may_be_counted_as_ga_attorney_pilot_evidence": False,
            "external_identity_and_pilot_audit_required": True,
            "review_required": True,
        }


class ReleasePilotHardeningService:
    def __init__(self, repo_root: str | Path, case_root: str | Path | None = None) -> None:
        self.repo_root = find_source_root(repo_root)
        self.case_root = Path(case_root).resolve() if case_root else None

    def status(self) -> dict[str, Any]:
        service_blockers: list[str] = []
        try:
            evidence = ReleaseEvidenceAuditor(self.repo_root).audit()
        except ReleasePilotHardeningError as exc:
            evidence = {"status": "blocked", "blockers": [exc.code], "store_package_qualified": False}
            service_blockers.append(exc.code)
        try:
            pilot = AttorneySandboxStore(self.repo_root).dashboard()
        except ReleasePilotHardeningError as exc:
            pilot = {"status": "blocked", "blockers": [exc.code], "may_be_counted_as_ga_attorney_pilot_evidence": False}
            service_blockers.append(exc.code)
        if self.case_root is not None:
            try:
                observability = PrivacySafeObservabilityStore(self.case_root).verify()
            except ReleasePilotHardeningError as exc:
                observability = {"status": "blocked", "blockers": [exc.code], "local_only": True}
                service_blockers.append(exc.code)
            try:
                backup = MatterBackupRestoreDrill(self.case_root, repo_root=self.repo_root).status()
            except ReleasePilotHardeningError as exc:
                backup = {"status": "blocked", "blockers": [exc.code]}
                service_blockers.append(exc.code)
        else:
            observability = {"status": "blocked", "blockers": ["active_matter_unavailable"], "local_only": True}
            backup = {"status": "blocked", "blockers": ["active_matter_unavailable"]}
        blockers = sorted({
            *service_blockers,
            *list(evidence.get("blockers") or []),
            *list(observability.get("blockers") or []),
            *list(backup.get("blockers") or []),
            *(["attorney_sandbox_not_operational"] if pilot.get("status") != "operational" else []),
        })
        return {
            "schema_version": "release_pilot_hardening_status_v1",
            "status": "pass" if not blockers else "blocked",
            "supply_chain_and_msix": evidence,
            "observability": observability,
            "backup_restore": backup,
            "attorney_sandbox": pilot,
            "blockers": blockers,
            "source_release_qualified_by_this_status": False,
            "store_submission_ready": evidence.get("store_package_qualified") is True,
            "legal_ga_ready": False,
            "review_required": True,
        }
