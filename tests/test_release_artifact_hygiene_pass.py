from __future__ import annotations

import json
from pathlib import Path
import stat
import subprocess
import sys
import zipfile

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


def test_source_archive_keeps_runtime_modules_and_only_the_pinned_binary_fixture(tmp_path: Path) -> None:
    source = tmp_path / "source"
    runtime_module = "legal/runtime/idempotency.py"
    fixture = "data/fixtures/parser_regression/malformed_download_v1.bin"
    private_runtime = "legal/runtime/cache/private.py"
    private_root = "runtime/private.py"
    files = (
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
        runtime_module,
        fixture,
    )
    for relative in files:
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    for relative in (private_runtime, private_root, "data/fixtures/parser_regression/extra.bin"):
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"not public")

    archive = tmp_path / "source.zip"
    subprocess.run([
        sys.executable, "-S", str(ROOT / "scripts/build-deterministic-source-release.py"),
        "--repo-root", str(source), "--output", str(archive),
    ], check=True, capture_output=True, timeout=30)
    with zipfile.ZipFile(archive) as zf:
        assert zf.read(f"ME_FM_LLM/{runtime_module}") == (ROOT / runtime_module).read_bytes()
        assert zf.read(f"ME_FM_LLM/{fixture}") == (ROOT / fixture).read_bytes()
        assert f"ME_FM_LLM/{private_runtime}" not in zf.namelist()
        assert f"ME_FM_LLM/{private_root}" not in zf.namelist()
        assert "ME_FM_LLM/data/fixtures/parser_regression/extra.bin" not in zf.namelist()

    audit = [sys.executable, "-S", str(ROOT / "scripts/audit-source-zip-contents.py")]
    subprocess.run([*audit, str(archive)], check=True, capture_output=True, timeout=30)
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(archive) as clean, zipfile.ZipFile(tampered, "w") as bad:
        for name in clean.namelist():
            bad.writestr(name, b"not the pinned fixture" if name == f"ME_FM_LLM/{fixture}" else clean.read(name))
        bad.writestr(f"ME_FM_LLM/{private_runtime}", b"not public")
        bad.writestr("ME_FM_LLM/legal/runtime/private.dll", b"not public")
        bad.writestr("ME_FM_LLM/legal/runtime/../escape.py", b"not public")
        bad.writestr("ME_FM_LLM!legal!runtime!escape.py", b"not public")
        link = zipfile.ZipInfo("ME_FM_LLM/legal/runtime/link.py")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        bad.writestr(link, "../../private.py")
        bad.writestr(f"{runtime_module.upper()}", b"case-fold collision")
    # ZipInfo normalizes backslashes at write time on Windows. Put the original
    # member name in both ZIP headers to exercise the actual hostile wire bytes.
    tampered.write_bytes(tampered.read_bytes().replace(
        b"ME_FM_LLM!legal!runtime!escape.py", b"ME_FM_LLM\\legal\\runtime\\escape.py",
    ))
    result = subprocess.run([*audit, str(tampered)], capture_output=True, timeout=30)
    assert result.returncode == 1
    blockers = json.loads(result.stdout)["blockers"]
    assert f"prohibited_release_zip_entry:{fixture}" in blockers
    assert f"prohibited_release_zip_entry:{private_runtime}" in blockers
    assert "prohibited_release_zip_entry:legal/runtime/private.dll" in blockers
    assert blockers.count("unsafe_release_zip_path") == 3
    assert "duplicate_release_zip_path" in blockers
