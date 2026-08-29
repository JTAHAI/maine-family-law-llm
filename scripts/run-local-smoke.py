#!/usr/bin/env python3
"""Run a fast local operator smoke check without requiring external Maine corpora.

This script is intentionally source-only. It verifies that the checkout can import,
serve the API in-process, keep data roots external, and preserve release hygiene.
It does not certify production legal readiness.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

ALLOWED_TEXT_FILES = {
    "PASS_CHANGES.txt",
    "store/listing/features.txt",
    "store/listing/search-terms.txt",
    "store/listing/short-description.txt",
    "store/pyinstaller/requirements-store-build.txt",
}

GENERATED_PARTS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".eggs",
    ".proofs",
}
REQUIRED_SOURCE_FILES = [
    "Dockerfile",
    ".dockerignore",
    "docker-compose.yml",
    "PASS_CHANGES.txt",
    "pyproject.toml",
    "app/api/main.py",
    "legal/corpus/__init__.py",
    "legal/corpus/source_normalizer.py",
    "legal/corpus/source_registry.py",
    "legal/corpus/source_snapshotter.py",
    "legal/corpus/maine_source_manifest.schema.json",
    "scripts/run-tests.ps1",
    "scripts/install.ps1",
    "scripts/clean-local-artifacts.py",
]


@dataclass
class SmokeCheck:
    name: str
    status: str
    detail: Any = None


@dataclass
class SmokeReport:
    status: str
    repo_root: str
    data_root: str
    production_legal_ga: bool = False
    checks: list[SmokeCheck] = field(default_factory=list)
    api_endpoints: list[str] = field(default_factory=list)
    next_commands: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["checks"] = [asdict(check) for check in self.checks]
        return data


def _is_ignored(rel_path: Path) -> bool:
    """Return True for generated/runtime/cache paths that should not affect smoke hygiene."""
    parts = set(rel_path.parts)
    rel = rel_path.as_posix()

    if parts & GENERATED_PARTS:
        return True
    if rel.startswith(".local_tmp/"):
        return True
    # Deliberately inert parser fixtures are version-controlled source inputs,
    # not operator logs or matter records.  Their extensions are intentionally
    # broad so defensive parsers can be exercised.
    if rel.startswith(("data/fixtures/", "tests/fixtures/")):
        return True
    if rel == "tests/PASS_CHANGES.txt":
        return True

    return False


def _run(cmd: list[str], *, cwd: Path, timeout: int = 90) -> tuple[str, str, int]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return proc.stdout, proc.stderr, proc.returncode


def _check_api_import(repo_root: Path) -> SmokeCheck:
    try:
        from fastapi.testclient import TestClient
        from app.api.main import app

        client = TestClient(app)
        health = client.get("/api/health")
        version = client.get("/api/version")
        if health.status_code != 200 or version.status_code != 200:
            return SmokeCheck(
                "api_in_process",
                "fail",
                {"health_status": health.status_code, "version_status": version.status_code},
            )
        return SmokeCheck(
            "api_in_process",
            "pass",
            {"health": health.json(), "version": version.json()},
        )
    except Exception as exc:  # pragma: no cover - exercised by CLI operator failures
        return SmokeCheck("api_in_process", "fail", f"{type(exc).__name__}: {exc}")


def build_report(repo_root: Path, data_root: Path, *, run_pytest: bool = False) -> SmokeReport:
    repo_root = repo_root.resolve()
    data_root = data_root.resolve()
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)
    checks: list[SmokeCheck] = []

    missing = [rel for rel in REQUIRED_SOURCE_FILES if not (repo_root / rel).exists()]
    checks.append(SmokeCheck("required_source_files", "pass" if not missing else "fail", missing))

    txt_files = sorted(
        path.relative_to(repo_root).as_posix()
        for path in repo_root.rglob("*.txt")
        if not _is_ignored(path.relative_to(repo_root))
    )
    unexpected_txt = [path for path in txt_files if path not in ALLOWED_TEXT_FILES]
    checks.append(
        SmokeCheck(
            "single_running_txt_log",
            "pass" if not unexpected_txt and "PASS_CHANGES.txt" in txt_files else "fail",
            {"approved": sorted(ALLOWED_TEXT_FILES), "found": txt_files, "unexpected": unexpected_txt},
        )
    )

    data_external = data_root != repo_root and repo_root not in data_root.parents
    checks.append(
        SmokeCheck(
            "external_data_root",
            "pass" if data_external else "fail",
            {"repo_root": str(repo_root), "data_root": str(data_root)},
        )
    )

    forbidden_roots = [
        "official_authority_store",
        "parsed_authority_store",
        "embedding_store",
        "eval_store",
        "matter_store",
        "model_store",
        "model_registry",
        "audit_store",
        "runtime",
        "uploads",
        "ME_FM_LLM_data",
    ]
    present_forbidden = [name for name in forbidden_roots if (repo_root / name).exists()]
    checks.append(SmokeCheck("no_repo_local_external_stores", "pass" if not present_forbidden else "fail", present_forbidden))

    checks.append(_check_api_import(repo_root))

    if run_pytest:
        stdout, stderr, code = _run([sys.executable, "-m", "pytest", "-q"], cwd=repo_root, timeout=180)
        checks.append(
            SmokeCheck(
                "pytest",
                "pass" if code == 0 else "fail",
                {"returncode": code, "stdout_tail": stdout[-2000:], "stderr_tail": stderr[-2000:]},
            )
        )
    else:
        checks.append(SmokeCheck("pytest", "skipped", "Use --run-pytest for full local test run."))

    status = "pass" if all(check.status in {"pass", "skipped"} for check in checks) else "fail"
    return SmokeReport(
        status=status,
        repo_root=str(repo_root),
        data_root=str(data_root),
        checks=checks,
        api_endpoints=[
            "http://127.0.0.1:8000/api/health",
            "http://127.0.0.1:8000/api/version",
            "http://127.0.0.1:8000/docs",
        ],
        next_commands=[
            "powershell -ExecutionPolicy Bypass -File .\\scripts\\run-tests.ps1 -Install",
            "powershell -ExecutionPolicy Bypass -File .\\scripts\\run-local-api.ps1",
            "python .\\scripts\\collect-enterprise-resources.py --data-root C:\\dev\\ME_FM_LLM_data",
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local source-only smoke checks.")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--data-root", default=os.environ.get("MAINE_FAMILY_LAW_DATA_ROOT", "C:/dev/ME_FM_LLM_data"))
    parser.add_argument("--output", default=str(ROOT / "docs" / "sample-evidence" / "local_smoke_report.json"))
    parser.add_argument("--run-pytest", action="store_true")
    args = parser.parse_args()

    report = build_report(Path(args.repo_root), Path(args.data_root), run_pytest=args.run_pytest)
    output = Path(args.output)
    if not output.is_absolute():
        output = Path(args.repo_root) / output
    output.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
