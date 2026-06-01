from __future__ import annotations

import json
import shutil
from pathlib import Path

from legal.ops import EnterpriseAcceptanceAuditor, ReleaseLockfileBuilder

ROOT = Path(__file__).resolve().parents[1]


def test_enterprise_acceptance_is_source_ready_but_not_legal_production_ready() -> None:
    report = EnterpriseAcceptanceAuditor(ROOT).audit()

    assert report.status == "pass"
    assert report.public_source_ready is True
    assert report.production_legal_ready is False
    assert report.only_one_txt_file is True
    assert report.expected_windows_repo_root == r"C:\dev\ME_FM_LLM"
    assert report.expected_windows_data_root == r"C:\dev\ME_FM_LLM_data"
    assert "external_data_manifest_attached" in report.production_blockers
    assert "PASS_CHANGES.txt" in report.source_hashes


def test_release_lockfile_audit_passes_then_detects_source_drift(tmp_path: Path) -> None:
    lock_path = tmp_path / "source_release_lock.json"
    builder = ReleaseLockfileBuilder(ROOT)
    lock = builder.write(lock_path)
    audit = builder.audit(lock_path)

    assert lock.status == "pass"
    assert audit.status == "pass"
    assert lock.file_count == audit.actual_file_count

    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    first_artifact = payload["artifacts"][0]
    first_artifact["sha256"] = "0" * 64
    lock_path.write_text(json.dumps(payload), encoding="utf-8")

    drift = builder.audit(lock_path)
    assert drift.status == "fail"
    assert drift.changed


def test_release_lockfile_excludes_runtime_external_artifacts(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".pytest_cache", "__pycache__"))
    (repo / "runtime").mkdir()
    (repo / "runtime" / "private.db").write_text("runtime database", encoding="utf-8")
    (repo / "official_authority_store").mkdir()
    (repo / "official_authority_store" / "source_manifest.json").write_text("[]", encoding="utf-8")

    lock = ReleaseLockfileBuilder(repo).build()
    paths = {item["path"] for item in lock.artifacts}

    assert "runtime/private.db" not in paths
    assert "official_authority_store/source_manifest.json" not in paths
    assert "PASS_CHANGES.txt" in paths


def test_github_public_hygiene_files_are_present() -> None:
    required = [
        "SECURITY.md",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "SUPPORT.md",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/config.yml",
        ".github/PULL_REQUEST_TEMPLATE.md",
        "docs/enterprise-acceptance-and-github-publish.md",
    ]
    for rel in required:
        assert (ROOT / rel).is_file(), rel
