from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class EnterpriseAcceptanceFinding:
    check: str
    status: str
    message: str
    path: str | None = None
    severity: str = "blocker"

    def as_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "status": self.status,
            "message": self.message,
            "path": self.path,
            "severity": self.severity,
        }


@dataclass(frozen=True)
class EnterpriseAcceptanceReport:
    status: str
    public_source_ready: bool
    production_legal_ready: bool
    project_root: str
    expected_windows_repo_root: str
    expected_windows_data_root: str
    generated_at: str
    required_file_count: int
    evidence_file_count: int
    release_lock_present: bool
    only_one_txt_file: bool
    production_blockers: list[str] = field(default_factory=list)
    findings: list[EnterpriseAcceptanceFinding] = field(default_factory=list)
    source_hashes: dict[str, str] = field(default_factory=dict)
    interpretation: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "public_source_ready": self.public_source_ready,
            "production_legal_ready": self.production_legal_ready,
            "project_root": self.project_root,
            "expected_windows_repo_root": self.expected_windows_repo_root,
            "expected_windows_data_root": self.expected_windows_data_root,
            "generated_at": self.generated_at,
            "required_file_count": self.required_file_count,
            "evidence_file_count": self.evidence_file_count,
            "release_lock_present": self.release_lock_present,
            "only_one_txt_file": self.only_one_txt_file,
            "production_blockers": list(self.production_blockers),
            "findings": [finding.as_dict() for finding in self.findings],
            "source_hashes": dict(self.source_hashes),
            "interpretation": self.interpretation,
        }


class EnterpriseAcceptanceAuditor:
    """Final source-readiness auditor before local testing or public staging.

    This auditor intentionally returns production_legal_ready=False unless real external evidence
    markers are present. Its job is to make source readiness strong while preventing an accidental
    claim that fixture evidence equals a production legal data product.
    """

    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()
        self.policy_path = self.project_root / "configs" / "maine_enterprise_acceptance_policy.json"
        self.policy = _load_json(self.policy_path)

    def _iter_source_files(self) -> list[Path]:
        skipped = {
            ".git",
            ".pytest_cache",
            ".ruff_cache",
            ".venv",
            "venv",
            "__pycache__",
            "node_modules",
            "dist",
            "build",
            ".eggs",
            ".proofs",
        }
        files: list[Path] = []
        for path in sorted(self.project_root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(self.project_root)
            if any(part in skipped or part.endswith(".egg-info") for part in rel.parts):
                continue
            files.append(path)
        return files

    def audit(self) -> EnterpriseAcceptanceReport:
        findings: list[EnterpriseAcceptanceFinding] = []
        rel_files = {p.relative_to(self.project_root).as_posix() for p in self._iter_source_files()}
        required_paths = [
            *self.policy.get("required_root_files", []),
            *self.policy.get("required_docs", []),
            *self.policy.get("required_github_files", []),
            *self.policy.get("required_scripts", []),
        ]
        for rel in required_paths:
            if rel not in rel_files:
                findings.append(EnterpriseAcceptanceFinding("required-file", "fail", "missing required file", rel))

        txt_files = sorted(rel for rel in rel_files if rel.lower().endswith(".txt"))
        allowed_txt = self.policy.get("single_text_file_allowed", "PASS_CHANGES.txt")
        only_one_txt = txt_files == [allowed_txt]
        if not only_one_txt:
            findings.append(
                EnterpriseAcceptanceFinding(
                    "single-pass-log",
                    "fail",
                    f"expected exactly one .txt file: {allowed_txt}",
                    ";".join(txt_files) or "<none>",
                )
            )

        blocked_source_paths = set(self.policy.get("blocked_source_paths", []))
        for rel in rel_files:
            if any(part in blocked_source_paths for part in Path(rel).parts):
                findings.append(
                    EnterpriseAcceptanceFinding("source-boundary", "fail", "blocked runtime/external path is inside source tree", rel)
                )

        key_paths = [
            "README.md",
            "PASS_CHANGES.txt",
            "pyproject.toml",
            "configs/maine_enterprise_acceptance_policy.json",
            "configs/maine_public_release_policy.json",
            "scripts/run-quality-checks.py",
            "scripts/collect-enterprise-resources.py",
            "scripts/run-enterprise-preflight.py",
            "docs/enterprise-acceptance-and-github-publish.md",
        ]
        source_hashes = {
            rel: _sha256_file(self.project_root / rel)
            for rel in key_paths
            if (self.project_root / rel).is_file()
        }

        evidence_files = sorted(
            rel for rel in rel_files if rel.startswith("smoke_evidence") and rel.endswith(".json")
        )
        release_lock_present = "source_release_lock.json" in rel_files
        production_blockers = list(self.policy.get("required_external_evidence_markers", []))
        marker_path = self.project_root / "production_external_evidence_markers.json"
        if marker_path.is_file():
            try:
                markers = _load_json(marker_path)
                production_blockers = [
                    marker for marker in production_blockers if markers.get(marker) is not True
                ]
            except json.JSONDecodeError:
                findings.append(
                    EnterpriseAcceptanceFinding(
                        "external-evidence-markers",
                        "fail",
                        "production external evidence marker file is not valid JSON",
                        "production_external_evidence_markers.json",
                    )
                )

        public_ready = not findings and only_one_txt
        production_ready = public_ready and not production_blockers
        return EnterpriseAcceptanceReport(
            status="pass" if public_ready else "fail",
            public_source_ready=public_ready,
            production_legal_ready=production_ready,
            project_root=str(self.project_root),
            expected_windows_repo_root=str(self.policy.get("expected_windows_repo_root", "C:\\dev\\ME_FM_LLM")),
            expected_windows_data_root=str(self.policy.get("expected_windows_data_root", "C:\\dev\\ME_FM_LLM_data")),
            generated_at=_utc_now(),
            required_file_count=len(required_paths),
            evidence_file_count=len(evidence_files),
            release_lock_present=release_lock_present,
            only_one_txt_file=only_one_txt,
            production_blockers=production_blockers,
            findings=findings,
            source_hashes=source_hashes,
            interpretation=(
                "Source acceptance is separate from production legal readiness. A public/source-ready tree "
                "still cannot be used as a production legal product until every external evidence marker is satisfied."
            ),
        )

    def write(self, output_path: str | Path) -> EnterpriseAcceptanceReport:
        report = self.audit()
        out = Path(output_path)
        if not out.is_absolute():
            out = self.project_root / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return report


@dataclass(frozen=True)
class ReleaseLockReport:
    status: str
    project_root: str
    generated_at: str
    file_count: int
    source_tree_hash: str
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    excluded_dirs: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "project_root": self.project_root,
            "generated_at": self.generated_at,
            "file_count": self.file_count,
            "source_tree_hash": self.source_tree_hash,
            "artifacts": list(self.artifacts),
            "excluded_dirs": list(self.excluded_dirs),
        }


@dataclass(frozen=True)
class ReleaseLockAuditReport:
    status: str
    project_root: str
    generated_at: str
    expected_file_count: int
    actual_file_count: int
    expected_source_tree_hash: str
    actual_source_tree_hash: str
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "project_root": self.project_root,
            "generated_at": self.generated_at,
            "expected_file_count": self.expected_file_count,
            "actual_file_count": self.actual_file_count,
            "expected_source_tree_hash": self.expected_source_tree_hash,
            "actual_source_tree_hash": self.actual_source_tree_hash,
            "added": list(self.added),
            "removed": list(self.removed),
            "changed": list(self.changed),
        }


class ReleaseLockfileBuilder:
    excluded_parts = {
        ".git",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "node_modules",
        "dist",
        ".proofs",
        "runtime",
        "uploads",
        "corpora",
        "vectorstores",
        "official_authority_store",
        "parsed_authority_store",
        "embedding_store",
        "eval_store",
        "matter_store",
        "model_store",
        "model_registry",
        "audit_store",
        "ME_FM_LLM_data",
    }
    excluded_files = {
        "source_release_lock.json",
        "enterprise_acceptance_evidence.json",
        "release_lock_audit.json",
    }

    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()

    def _artifacts(self) -> list[dict[str, Any]]:
        artifacts: list[dict[str, Any]] = []
        for path in sorted(self.project_root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(self.project_root)
            rel_posix = rel.as_posix()
            if rel_posix in self.excluded_files:
                continue
            if any(part in self.excluded_parts for part in rel.parts):
                continue
            artifacts.append(
                {
                    "path": rel_posix,
                    "sha256": _sha256_file(path),
                    "bytes": path.stat().st_size,
                }
            )
        return artifacts

    @staticmethod
    def _tree_hash(artifacts: list[dict[str, Any]]) -> str:
        basis = "\n".join(f"{item['path']} {item['sha256']} {item['bytes']}" for item in artifacts)
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()

    def build(self) -> ReleaseLockReport:
        artifacts = self._artifacts()
        return ReleaseLockReport(
            status="pass",
            project_root=str(self.project_root),
            generated_at=_utc_now(),
            file_count=len(artifacts),
            source_tree_hash=self._tree_hash(artifacts),
            artifacts=artifacts,
            excluded_dirs=sorted(self.excluded_parts),
        )

    def write(self, output_path: str | Path) -> ReleaseLockReport:
        report = self.build()
        out = Path(output_path)
        if not out.is_absolute():
            out = self.project_root / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return report

    def audit(self, lockfile: str | Path) -> ReleaseLockAuditReport:
        lock_path = Path(lockfile)
        if not lock_path.is_absolute():
            lock_path = self.project_root / lock_path
        expected = _load_json(lock_path)
        actual = self.build().as_dict()
        expected_artifacts = {item["path"]: item for item in expected.get("artifacts", [])}
        actual_artifacts = {item["path"]: item for item in actual.get("artifacts", [])}
        added = sorted(set(actual_artifacts) - set(expected_artifacts))
        removed = sorted(set(expected_artifacts) - set(actual_artifacts))
        changed = sorted(
            path
            for path in set(expected_artifacts) & set(actual_artifacts)
            if expected_artifacts[path].get("sha256") != actual_artifacts[path].get("sha256")
            or expected_artifacts[path].get("bytes") != actual_artifacts[path].get("bytes")
        )
        status = "pass" if not added and not removed and not changed else "fail"
        return ReleaseLockAuditReport(
            status=status,
            project_root=str(self.project_root),
            generated_at=_utc_now(),
            expected_file_count=int(expected.get("file_count", 0)),
            actual_file_count=int(actual.get("file_count", 0)),
            expected_source_tree_hash=str(expected.get("source_tree_hash", "")),
            actual_source_tree_hash=str(actual.get("source_tree_hash", "")),
            added=added,
            removed=removed,
            changed=changed,
        )


def run_command(command: list[str], cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    return {
        "command": " ".join(command),
        "returncode": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def run_final_local_acceptance(project_root: str | Path = ".") -> dict[str, Any]:
    root = Path(project_root).resolve()
    pytest_result = run_command([sys.executable, "-m", "pytest", "-q"], root)
    quality_result = run_command([sys.executable, "scripts/run-quality-checks.py"], root)
    lock_report = ReleaseLockfileBuilder(root).write(root / "source_release_lock.json")
    lock_audit = ReleaseLockfileBuilder(root).audit(root / "source_release_lock.json")
    acceptance = EnterpriseAcceptanceAuditor(root).write(root / "enterprise_acceptance_evidence.json")
    status = "pass" if (
        pytest_result["returncode"] == 0
        and quality_result["returncode"] == 0
        and lock_report.status == "pass"
        and lock_audit.status == "pass"
        and acceptance.status == "pass"
    ) else "fail"
    return {
        "status": status,
        "generated_at": _utc_now(),
        "pytest": pytest_result,
        "quality_checks": quality_result,
        "release_lock": lock_report.as_dict(),
        "release_lock_audit": lock_audit.as_dict(),
        "enterprise_acceptance": acceptance.as_dict(),
        "production_legal_ready": acceptance.production_legal_ready,
        "interpretation": "Passing final local acceptance proves source/test readiness only, not production legal readiness.",
    }
