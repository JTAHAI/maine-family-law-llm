from __future__ import annotations

import json
import shutil
from pathlib import Path

from legal.ops import EnterpriseAcceptanceAuditor, ReleaseLockfileBuilder
from legal.ops.enterprise_acceptance import run_final_local_acceptance

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
    (repo / ".mfl_work" / "cache").mkdir(parents=True, exist_ok=True)
    (repo / ".mfl_work" / "cache" / "fixture.metadata.json").write_text(
        "{}",
        encoding="utf-8",
    )
    (repo / "official_authority_store").mkdir()
    (repo / "official_authority_store" / "source_manifest.json").write_text("[]", encoding="utf-8")
    (repo / "docs" / "sample-evidence" / "source_release_lock.json").write_text(
        "{}",
        encoding="utf-8",
    )

    lock = ReleaseLockfileBuilder(repo).build()
    paths = {item["path"] for item in lock.artifacts}

    assert "runtime/private.db" not in paths
    assert ".mfl_work/cache/fixture.metadata.json" not in paths
    assert "official_authority_store/source_manifest.json" not in paths
    assert "docs/sample-evidence/source_release_lock.json" not in paths
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


def test_final_local_acceptance_writes_generated_artifacts_under_docs_sample_evidence(
    monkeypatch, tmp_path: Path
) -> None:
    calls: dict[str, Path] = {}

    class _DummyLock:
        status = "pass"

        def as_dict(self) -> dict[str, str]:
            return {"status": "pass"}

    class _DummyAudit(_DummyLock):
        pass

    class _DummyAcceptance(_DummyLock):
        production_legal_ready = False

    class _DummyConversation:
        def as_dict(self) -> dict[str, object]:
            return {"status": "pass"}

    def _record_lock_write(self, path):
        calls["lock_write"] = Path(path)
        return _DummyLock()

    def _record_lock_audit(self, path):
        calls["lock_audit"] = Path(path)
        return _DummyAudit()

    def _init_acceptance(self, project_root=".") -> None:
        self.project_root = Path(project_root).resolve()
        self.policy_path = self.project_root / "configs" / "maine_enterprise_acceptance_policy.json"
        self.policy = {}

    def _record_acceptance_write(self, path):
        calls["acceptance_write"] = Path(path)
        return _DummyAcceptance()

    monkeypatch.setattr(
        "legal.ops.enterprise_acceptance.run_command",
        lambda command, cwd: {"command": " ".join(command), "returncode": 0, "stdout": "", "stderr": ""},
    )
    monkeypatch.setattr(
        "legal.ops.enterprise_acceptance.ReleaseLockfileBuilder.write",
        _record_lock_write,
    )
    monkeypatch.setattr(
        "legal.ops.enterprise_acceptance.ReleaseLockfileBuilder.audit",
        _record_lock_audit,
    )
    monkeypatch.setattr(
        "legal.ops.enterprise_acceptance.EnterpriseAcceptanceAuditor.__init__",
        _init_acceptance,
    )
    monkeypatch.setattr(
        "legal.ops.enterprise_acceptance.EnterpriseAcceptanceAuditor.write",
        _record_acceptance_write,
    )
    monkeypatch.setattr(
        "legal.evals.conversation_eval.ConversationEvalRunner.run",
        lambda self, output_path=None: _DummyConversation(),
    )
    monkeypatch.setattr(
        "legal.conversation.internal_passes.ConversationPilotReadinessAuditor.write",
        lambda self, output_path, run_tests=False: _DummyConversation(),
    )

    report = run_final_local_acceptance(tmp_path)
    sample_dir = tmp_path / "docs" / "sample-evidence"

    assert report["status"] == "pass"
    assert calls["lock_write"] == sample_dir / "source_release_lock.json"
    assert calls["lock_audit"] == sample_dir / "source_release_lock.json"
    assert calls["acceptance_write"] == sample_dir / "enterprise_acceptance_evidence.json"
