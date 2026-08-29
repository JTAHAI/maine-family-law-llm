from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal.release.release_manifest import ReleaseManifest


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_policy(project_root: Path) -> dict[str, Any]:
    return json.loads((project_root / "configs" / "maine_public_release_policy.json").read_text(encoding="utf-8"))




def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

SECRET_VALUE_RE = re.compile(
    r"(?i)(?:api[_-]?key|secret[_-]?key|client[_-]?secret|password|token)\s*[:=]\s*['\"][^'\"]{12,}['\"]"
)


@dataclass(frozen=True)
class PublicReleaseFinding:
    path: str
    reason: str
    severity: str = "blocker"

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "reason": self.reason, "severity": self.severity}


@dataclass(frozen=True)
class PublicRepoReadinessReport:
    status: str
    public_source_ready: bool
    production_legal_ready: bool
    project_root: str
    generated_at: str
    checked_files: int
    only_one_txt_file: bool
    pass_log_present: bool
    github_ci_present: bool
    release_manifest_clean: bool
    required_docs_present: bool
    findings: list[PublicReleaseFinding] = field(default_factory=list)
    interpretation: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "public_source_ready": self.public_source_ready,
            "production_legal_ready": self.production_legal_ready,
            "project_root": self.project_root,
            "generated_at": self.generated_at,
            "checked_files": self.checked_files,
            "only_one_txt_file": self.only_one_txt_file,
            "pass_log_present": self.pass_log_present,
            "github_ci_present": self.github_ci_present,
            "release_manifest_clean": self.release_manifest_clean,
            "required_docs_present": self.required_docs_present,
            "findings": [finding.as_dict() for finding in self.findings],
            "interpretation": self.interpretation,
        }


class PublicRepoReadinessAuditor:
    """Audit whether the source tree is safe to stage for a public GitHub repo.

    This is intentionally not a legal-product certification. It checks source hygiene,
    public-release docs, CI, pass-log discipline, and absence of private/runtime artifacts.
    """

    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()
        self.policy = _load_policy(self.project_root)

    def _iter_files(self) -> list[Path]:
        skipped_parts = {
            ".git",
            ".pytest_cache",
            ".ruff_cache",
            ".venv",
            "venv",
            ".mfl_work",
            "__pycache__",
            "node_modules",
            "dist",
            "build",
            ".eggs",
            ".proofs",
        }
        files: list[Path] = []
        # Prune massive generated release/runtime trees before walking into
        # them.  Filtering after ``rglob`` still descends into every bundled
        # dependency and made a local source-readiness check needlessly slow.
        for directory, dirnames, filenames in os.walk(self.project_root):
            current = Path(directory)
            rel_dir = current.relative_to(self.project_root)
            dirnames[:] = [
                name
                for name in dirnames
                if name not in skipped_parts and not name.endswith(".egg-info")
            ]
            if any(part in skipped_parts or part.endswith(".egg-info") for part in rel_dir.parts):
                continue
            for name in filenames:
                files.append(current / name)
        return files

    @staticmethod
    def _is_public_fixture(rel: str) -> bool:
        path = Path(rel)
        return path.parts[:2] in {("data", "fixtures"), ("tests", "fixtures")}

    @staticmethod
    def _is_public_runtime_source(rel: str) -> bool:
        return Path(rel).parts[:2] == ("legal", "runtime")

    def _public_binary_inventory(self, root_rel: str) -> dict[str, str]:
        inventory_path = self.project_root / root_rel / "focaf_inventory.json"
        if not inventory_path.is_file():
            return {}
        try:
            payload = json.loads(inventory_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return {
            str(row.get("original_filename") or ""): str(row.get("source_hash") or "").lower()
            for row in payload.get("documents", [])
            if str(row.get("original_filename") or "") and str(row.get("source_hash") or "")
        }

    def _allowed_public_binary(self, rel: str, path: Path) -> bool:
        suffixes = {str(value).lower() for value in self.policy.get("allowed_public_binary_suffixes", [])}
        if path.suffix.lower() not in suffixes:
            return False
        rel_path = Path(rel)
        for root_rel in self.policy.get("allowed_public_binary_roots", []):
            root_path = Path(str(root_rel))
            try:
                within = rel_path.relative_to(root_path)
            except ValueError:
                continue
            if len(within.parts) != 1:
                return False
            expected = self._public_binary_inventory(str(root_rel)).get(within.name, "")
            if not expected:
                return False
            try:
                if path.read_bytes()[:5] != b"%PDF-":
                    return False
                return _sha256(path).lower() == expected
            except OSError:
                return False
        return False

    def audit(self) -> PublicRepoReadinessReport:
        findings: list[PublicReleaseFinding] = []
        files = self._iter_files()
        rel_files = [p.relative_to(self.project_root).as_posix() for p in files]
        rel_set = set(rel_files)

        txt_files = sorted(
            path for path in rel_files if path.lower().endswith(".txt") and not self._is_public_fixture(path)
        )
        allowed_txt = self.policy.get("single_text_file_allowed", "PASS_CHANGES.txt")
        allowed_text_files = sorted(self.policy.get("allowed_text_files", [allowed_txt]))
        only_one_txt_file = txt_files == allowed_text_files
        if not only_one_txt_file:
            findings.append(
                PublicReleaseFinding(
                    path=";".join(txt_files) or "<none>",
                    reason=f"public source tree text files must exactly match: {', '.join(allowed_text_files)}",
                )
            )

        for required in self.policy.get("required_root_files", []):
            if required not in rel_set:
                findings.append(PublicReleaseFinding(path=required, reason="missing required root file"))
        for required_doc in self.policy.get("required_docs", []):
            if required_doc not in rel_set:
                findings.append(PublicReleaseFinding(path=required_doc, reason="missing required public release doc"))
        for required_workflow in self.policy.get("required_github_workflows", []):
            if required_workflow not in rel_set:
                findings.append(PublicReleaseFinding(path=required_workflow, reason="missing required CI workflow"))

        blocked_paths = set(self.policy.get("blocked_paths", []))
        blocked_suffixes = {str(s).lower() for s in self.policy.get("blocked_suffixes", [])}
        for rel in rel_files:
            path = Path(rel)
            if self._is_public_fixture(rel):
                continue
            if not self._is_public_runtime_source(rel) and any(part in blocked_paths for part in path.parts):
                findings.append(PublicReleaseFinding(path=rel, reason="blocked runtime/private path present"))
            if path.suffix.lower() in blocked_suffixes and not self._allowed_public_binary(rel, self.project_root / rel):
                findings.append(PublicReleaseFinding(path=rel, reason="blocked runtime/private/binary suffix present"))

        text_suffixes = {".py", ".ps1", ".sh", ".md", ".json", ".jsonl", ".yaml", ".yml", ".toml"}
        for path in files:
            if path.suffix.lower() not in text_suffixes:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if SECRET_VALUE_RE.search(text):
                findings.append(
                    PublicReleaseFinding(
                        path=path.relative_to(self.project_root).as_posix(),
                        reason="possible literal secret value detected",
                    )
                )

        manifest = ReleaseManifest(project_root=self.project_root).generate()
        release_manifest_clean = manifest["data_boundary_status"] == "pass"
        if not release_manifest_clean:
            for finding in manifest.get("private_or_runtime_artifacts", []):
                findings.append(PublicReleaseFinding(path=finding["path"], reason=finding["reason"]))

        required_docs_present = all(doc in rel_set for doc in self.policy.get("required_docs", []))
        github_ci_present = all(flow in rel_set for flow in self.policy.get("required_github_workflows", []))
        pass_log_present = allowed_txt in rel_set
        public_ready = not findings and only_one_txt_file and pass_log_present and github_ci_present and required_docs_present
        return PublicRepoReadinessReport(
            status="pass" if public_ready else "fail",
            public_source_ready=public_ready,
            production_legal_ready=False,
            project_root=str(self.project_root),
            generated_at=_utc_now(),
            checked_files=len(files),
            only_one_txt_file=only_one_txt_file,
            pass_log_present=pass_log_present,
            github_ci_present=github_ci_present,
            release_manifest_clean=release_manifest_clean,
            required_docs_present=required_docs_present,
            findings=findings,
            interpretation=(
                "Public source readiness only. Production legal readiness still requires external official authority, "
                "attorney-reviewed evals, measured metrics, security/pilot evidence, and owner signoffs."
            ),
        )

    def write(self, output_path: str | Path) -> PublicRepoReadinessReport:
        report = self.audit()
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return report
