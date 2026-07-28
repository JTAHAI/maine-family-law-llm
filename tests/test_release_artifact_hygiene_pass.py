from __future__ import annotations

import json
from pathlib import Path
import subprocess

from legal.production.release_artifact_audit import ReleaseArtifactAudit

ROOT = Path(__file__).resolve().parents[1]


def test_root_generated_json_is_blocked(tmp_path: Path) -> None:
    (tmp_path / "smoke_evidence_pass99.json").write_text("{}", encoding="utf-8")
    report = ReleaseArtifactAudit(tmp_path).audit()
    assert report["status"] == "fail"
    assert report["safe_to_package"] is False
    assert report["blockers"] == [
        {"path": "smoke_evidence_pass99.json", "reason": "generated_evidence_json_at_repo_root"}
    ]


def test_docs_sample_evidence_is_warn_only(tmp_path: Path) -> None:
    sample = tmp_path / "docs" / "sample-evidence"
    sample.mkdir(parents=True)
    (sample / "smoke_evidence_pass1.json").write_text("{}", encoding="utf-8")
    report = ReleaseArtifactAudit(tmp_path).audit()
    assert report["status"] == "pass"
    assert report["warnings"] == [
        {"path": "docs/sample-evidence/smoke_evidence_pass1.json", "reason": "sample_only_not_release_evidence"}
    ]


def test_cleaner_removes_root_generated_json(tmp_path: Path) -> None:
    (tmp_path / "source_sbom.json").write_text("{}", encoding="utf-8")
    (tmp_path / "smoke_evidence_pass1.json").write_text("{}", encoding="utf-8")
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "sample.json").write_text("{}", encoding="utf-8")
    result = subprocess.run(
        ["python", str(ROOT / "scripts" / "clean-local-artifacts.py"), "--repo-root", str(tmp_path), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=45,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert sorted(payload["removed"]) == ["smoke_evidence_pass1.json", "source_sbom.json"]
    assert (tmp_path / "configs" / "sample.json").exists()


def test_current_release_tree_has_no_root_generated_json() -> None:
    report = ReleaseArtifactAudit(ROOT).audit()
    assert report["status"] == "pass"
    assert report["safe_to_package"] is True
    assert report["blockers"] == []


def test_package_scripts_run_release_artifact_audit_after_quality() -> None:
    sh = (ROOT / "scripts" / "package-release.sh").read_text(encoding="utf-8")
    ps1 = (ROOT / "scripts" / "package-release.ps1").read_text(encoding="utf-8")
    for text in (sh, ps1):
        assert "audit-release-artifacts.py" in text
        assert "doctor-local-repo.py" in text
        assert "source_sbom.json" in text
        assert "smoke_evidence*.json" in text
        assert "PYTHONDONTWRITEBYTECODE" in text


def test_package_scripts_verify_finished_zip_contains_required_ga_evidence() -> None:
    sh = (ROOT / "scripts" / "package-release.sh").read_text(encoding="utf-8")
    ps1 = (ROOT / "scripts" / "package-release.ps1").read_text(encoding="utf-8")
    for text in (sh, ps1):
        assert "audit-source-zip-contents.py" in text
        assert "*_report.json" not in text
        assert "*_evidence.json" not in text


def test_source_zip_content_audit_blocks_missing_required_evidence(tmp_path: Path) -> None:
    import zipfile

    zip_path = tmp_path / "source.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("ME_FM_LLM/openapi.json", "{}")
    completed = subprocess.run(
        ["python", str(ROOT / "scripts" / "audit-source-zip-contents.py"), str(zip_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["status"] == "fail"
    assert "missing_required_release_path:docs/model_registry_admission_report.json" in payload["blockers"]


def test_source_zip_content_audit_accepts_current_release_zip_shape(tmp_path: Path) -> None:
    import zipfile

    required_paths = [
        "openapi.json",
        "docs/api-contract-test-report.json",
        "docs/ui-completion-report.json",
        "docs/model_registry_admission_report.json",
        "docs/llm_injection_red_team_report.json",
        "docs/enterprise-security-test-report.json",
        "docs/governance-compliance-packet-report.json",
        "docs/sre-reliability-report.json",
        "configs/maine_true_ga_pass_tracker.json",
        "configs/maine_ga_pass_evidence_requirements.json",
    ]
    zip_path = tmp_path / "source.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for path in required_paths:
            zf.writestr(f"ME_FM_LLM/{path}", "{}")
    completed = subprocess.run(
        ["python", str(ROOT / "scripts" / "audit-source-zip-contents.py"), str(zip_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["status"] == "pass"


def test_source_zip_content_audit_accepts_hyphenated_title_case_archive_root(tmp_path: Path) -> None:
    import zipfile

    required_paths = [
        "openapi.json",
        "docs/api-contract-test-report.json",
        "docs/ui-completion-report.json",
        "docs/model_registry_admission_report.json",
        "docs/llm_injection_red_team_report.json",
        "docs/enterprise-security-test-report.json",
        "docs/governance-compliance-packet-report.json",
        "docs/sre-reliability-report.json",
        "configs/maine_true_ga_pass_tracker.json",
        "configs/maine_ga_pass_evidence_requirements.json",
    ]
    zip_path = tmp_path / "source.zip"
    archive_root = "Maine-Family-Law-LLM-v5.2.0"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for path in required_paths:
            zf.writestr(f"{archive_root}/{path}", "{}")
        zf.writestr(
            f"{archive_root}/src/maine_family_law_llm/resources/focaf/approved-public.pdf",
            b"%PDF-1.4\n",
        )
    completed = subprocess.run(
        ["python", str(ROOT / "scripts" / "audit-source-zip-contents.py"), str(zip_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["status"] == "pass"
    assert payload["allowed_public_pdf_count"] == 1
