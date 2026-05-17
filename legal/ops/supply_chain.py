from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class SupplyChainFinding:
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
class SupplyChainReport:
    status: str
    production_legal_ready: bool
    project_root: str
    generated_at: str
    python_requires: str
    dependency_count: int
    optional_dependency_count: int
    script_count: int
    workflow_count: int
    sbom_path: str | None
    findings: list[SupplyChainFinding] = field(default_factory=list)
    sbom: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "production_legal_ready": self.production_legal_ready,
            "project_root": self.project_root,
            "generated_at": self.generated_at,
            "python_requires": self.python_requires,
            "dependency_count": self.dependency_count,
            "optional_dependency_count": self.optional_dependency_count,
            "script_count": self.script_count,
            "workflow_count": self.workflow_count,
            "sbom_path": self.sbom_path,
            "findings": [item.as_dict() for item in self.findings],
            "sbom": self.sbom,
        }


class SupplyChainAuditor:
    """Build a lightweight source SBOM and audit public-release supply-chain controls.

    This is intentionally dependency-light and does not call package registries. It checks the
    source tree, declared dependencies, scripts, CI workflow, and resource catalog wiring that an
    enterprise reviewer can inspect before publishing or local installation.
    """

    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()
        self.pyproject_path = self.project_root / "pyproject.toml"

    def _load_pyproject(self) -> dict[str, Any]:
        return tomllib.loads(self.pyproject_path.read_text(encoding="utf-8"))

    def _script_paths(self) -> list[Path]:
        scripts = self.project_root / "scripts"
        return sorted(path for path in scripts.rglob("*") if path.is_file() and path.suffix in {".py", ".ps1", ".sh"})

    def _workflow_paths(self) -> list[Path]:
        workflows = self.project_root / ".github" / "workflows"
        if not workflows.exists():
            return []
        return sorted(path for path in workflows.rglob("*.yml") if path.is_file()) + sorted(
            path for path in workflows.rglob("*.yaml") if path.is_file()
        )

    def _component(self, path: Path, kind: str) -> dict[str, Any]:
        rel = path.relative_to(self.project_root).as_posix()
        return {
            "type": kind,
            "path": rel,
            "sha256": _sha256_file(path),
            "bytes": path.stat().st_size,
        }

    def _build_sbom(
        self,
        project: dict[str, Any],
        scripts: list[Path],
        workflows: list[Path],
    ) -> dict[str, Any]:
        project_meta = project.get("project", {})
        optional = project_meta.get("optional-dependencies", {})
        dependencies = list(project_meta.get("dependencies", []))
        optional_dependencies = [dep for group in optional.values() for dep in group]
        components = [
            {
                "type": "python-project",
                "name": project_meta.get("name", "unknown"),
                "version": project_meta.get("version", "unknown"),
                "description_hash": _sha256_text(str(project_meta.get("description", ""))),
            },
            *[{"type": "dependency", "specifier": dep} for dep in dependencies],
            *[{"type": "optional-dependency", "specifier": dep} for dep in optional_dependencies],
            *[self._component(path, "script") for path in scripts],
            *[self._component(path, "github-workflow") for path in workflows],
        ]
        catalog = self.project_root / "configs" / "maine_enterprise_resource_catalog.json"
        if catalog.exists():
            payload = json.loads(catalog.read_text(encoding="utf-8"))
            components.append(
                {
                    "type": "enterprise-resource-catalog",
                    "path": catalog.relative_to(self.project_root).as_posix(),
                    "sha256": _sha256_file(catalog),
                    "resource_count": len(payload.get("resources", [])),
                    "catalog_version": payload.get("catalog_version") or payload.get("version"),
                }
            )
        return {
            "schema": "maine-family-law-llm-source-sbom-v1",
            "generated_at": _utc_now(),
            "project_name": project_meta.get("name", "unknown"),
            "project_version": project_meta.get("version", "unknown"),
            "source_only": True,
            "production_legal_ready": False,
            "components": components,
            "interpretation": "Source SBOM/provenance only; not proof that legal data, attorney-reviewed evals, or production signoffs exist.",
        }

    @staticmethod
    def _is_pinned_or_bounded(specifier: str) -> bool:
        return any(op in specifier for op in ["==", ">=", "~=", "==="])

    def audit(self, *, write_sbom: bool = False, output_path: str | Path | None = None) -> SupplyChainReport:
        findings: list[SupplyChainFinding] = []
        if not self.pyproject_path.is_file():
            findings.append(SupplyChainFinding("pyproject", "fail", "pyproject.toml missing", "pyproject.toml"))
            return SupplyChainReport(
                status="fail",
                production_legal_ready=False,
                project_root=str(self.project_root),
                generated_at=_utc_now(),
                python_requires="",
                dependency_count=0,
                optional_dependency_count=0,
                script_count=0,
                workflow_count=0,
                sbom_path=None,
                findings=findings,
            )
        project = self._load_pyproject()
        meta = project.get("project", {})
        scripts = self._script_paths()
        workflows = self._workflow_paths()
        dependencies = list(meta.get("dependencies", []))
        optional = meta.get("optional-dependencies", {})
        optional_dependencies = [dep for group in optional.values() for dep in group]
        python_requires = str(meta.get("requires-python", ""))
        if ">=3.11" not in python_requires:
            findings.append(
                SupplyChainFinding(
                    "python-version",
                    "fail",
                    "project should require Python >=3.11 for enterprise baseline consistency",
                    "pyproject.toml",
                )
            )
        unbounded = [dep for dep in [*dependencies, *optional_dependencies] if not self._is_pinned_or_bounded(str(dep))]
        for dep in unbounded:
            findings.append(
                SupplyChainFinding(
                    "dependency-bounds",
                    "fail",
                    f"dependency lacks a lower bound or exact pin: {dep}",
                    "pyproject.toml",
                )
            )
        if not workflows:
            findings.append(SupplyChainFinding("github-ci", "fail", "no GitHub workflow present", ".github/workflows"))
        else:
            ci_text = "\n".join(path.read_text(encoding="utf-8") for path in workflows)
            for required in ["pytest", "scripts/run-quality-checks.py", "actions/checkout", "actions/setup-python"]:
                if required not in ci_text:
                    findings.append(
                        SupplyChainFinding("github-ci", "fail", f"CI workflow missing required step marker: {required}", ".github/workflows")
                    )
        required_scripts = {
            "run-quality-checks.py",
            "collect-enterprise-resources.py",
            "run-enterprise-preflight.py",
            "prepare-public-github-release.py",
            "build-release-provenance.py",
            "build-release-lockfile.py",
            "audit-release-lockfile.py",
            "build-enterprise-acceptance-evidence.py",
            "run-final-local-acceptance.py",
        }
        present_scripts = {path.name for path in scripts}
        for required in sorted(required_scripts - present_scripts):
            findings.append(SupplyChainFinding("required-scripts", "fail", f"missing required script {required}", "scripts"))
        sbom = self._build_sbom(project, scripts, workflows)
        sbom_path: str | None = None
        if write_sbom:
            out = Path(output_path or self.project_root / "source_sbom.json")
            if not out.is_absolute():
                out = self.project_root / out
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(sbom, indent=2, sort_keys=True), encoding="utf-8")
            sbom_path = str(out)
        return SupplyChainReport(
            status="pass" if not findings else "fail",
            production_legal_ready=False,
            project_root=str(self.project_root),
            generated_at=_utc_now(),
            python_requires=python_requires,
            dependency_count=len(dependencies),
            optional_dependency_count=len(optional_dependencies),
            script_count=len(scripts),
            workflow_count=len(workflows),
            sbom_path=sbom_path,
            findings=findings,
            sbom=sbom,
        )

    def write(self, output_path: str | Path) -> SupplyChainReport:
        out = Path(output_path)
        if not out.is_absolute():
            out = self.project_root / out
        report = self.audit(write_sbom=False)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return report
