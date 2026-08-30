"""Non-destructive Windows build-containment checks; never run a package build."""

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/store-build-workspace.ps1"
pytestmark = pytest.mark.skipif(os.name != "nt", reason="PowerShell Windows build guards")


def ps(code: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            f"$ErrorActionPreference='Stop'; . '{HELPER}'; {code}",
        ],
        capture_output=True,
        text=True,
        timeout=15,
        cwd=ROOT,
    )


@pytest.mark.parametrize(
    "candidate",
    [
        "C:\\",
        "C:\\mfl-new-stage",
        str(ROOT),
        str(ROOT / "dist"),
        str(ROOT / "dist-elsewhere/stage"),
        str(ROOT / "dist/../source"),
    ],
)
def test_external_or_broad_paths_are_rejected_without_writes(candidate):
    result = ps(f"Resolve-RepoBuildDirectory '{candidate}' '{ROOT}'")
    assert result.returncode != 0
    assert "dedicated children of repository dist" in result.stderr


def test_valid_repo_build_path_is_resolved_without_creating_it():
    path = ROOT / "dist/guard-proof/nonexistent-stage"
    existed = path.exists()
    result = ps(f"Resolve-RepoBuildDirectory '{path}' '{ROOT}'")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(path)
    assert path.exists() == existed


def test_overlapping_build_paths_rejected_and_sibling_prefix_allowed():
    parent = ROOT / "dist/stage"
    for child in (parent, parent / "output"):
        result = ps(f"Assert-SeparateBuildDirectories '{parent}' '{child}'")
        assert result.returncode != 0
    sibling = ROOT / "dist/stage-other"
    assert ps(f"Assert-SeparateBuildDirectories '{parent}' '{sibling}'").returncode == 0


def test_disk_guard_fails_before_any_build_for_impossible_budget():
    result = ps(f"Assert-StoreBuildDiskSpace '{ROOT}' 9000000000000000000")
    assert result.returncode != 0
    assert "existing artifacts preserved" in result.stderr


def test_all_entry_scripts_parse_and_use_shared_containment():
    for name in ("build-msix.ps1", "build-store-runtime.ps1", "provision-whisper-engine.ps1"):
        path = ROOT / "scripts" / name
        source = path.read_text(encoding="utf-8")
        assert "store-build-workspace.ps1" in source
        assert "Resolve-RepoBuildDirectory" in source
        result = ps(
            f"$tokens=$null; $errors=$null; "
            f"[System.Management.Automation.Language.Parser]::ParseFile('{path}', "
            "[ref]$tokens, [ref]$errors) | Out-Null; "
            "if ($errors.Count) { $errors | Out-String | Write-Error }"
        )
        assert result.returncode == 0, result.stderr
    build = (ROOT / "scripts/build-msix.ps1").read_text(encoding="utf-8")
    assert '$PackagingRoot = "C:\\mfl6"' not in build
    assert "Move-Item -LiteralPath $shortMsixPath" in build
    helper = HELPER.read_text(encoding="utf-8")
    assert "$env:PYINSTALLER_CONFIG_DIR = Join-Path $tempRoot 'pyinstaller'" in helper
