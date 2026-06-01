from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ROOT_EVIDENCE_FILENAMES = {
    "enterprise_acceptance_evidence.json",
    "enterprise_local_build_plan.json",
    "enterprise_local_hardening_evidence.json",
    "enterprise_preflight_report.json",
    "final_local_acceptance_evidence.json",
    "full_ga_workbench_report.json",
    "local_smoke_report.json",
    "local_test_readiness_report.json",
    "networked_source_gate_report.json",
    "offline_validation_pack_report.json",
    "operator_handoff_bundle.json",
    "operator_test_battery_evidence.json",
    "post_ga_repo_review_build_path.json",
    "production_promotion_gate_report.json",
    "public_attribution_kit_report.json",
    "public_release_readiness.json",
    "reboot_recovery_healthcheck.json",
    "release_provenance.json",
    "source_release_lock.json",
    "source_sbom.json",
}

ALLOWED_POLICY_SCRIPTS = {
    "clean-local-artifacts.py",
    "doctor-local-repo.py",
    "audit-release-artifacts.py",
    "package-release.sh",
    "package-release.ps1",
}


def _is_generated_evidence_line(line: str) -> bool:
    if "smoke_evidence" in line and ".json" in line:
        return True
    return any(name in line for name in ROOT_EVIDENCE_FILENAMES)


def test_operator_scripts_default_generated_evidence_to_sample_folder() -> None:
    offenders: list[str] = []
    for path in sorted((ROOT / "scripts").glob("*")):
        if path.name in ALLOWED_POLICY_SCRIPTS or path.suffix not in {".py", ".ps1"}:
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not _is_generated_evidence_line(line):
                continue
            if ("docs" in line and "sample-evidence" in line) or "SAMPLE_EVIDENCE_DIR" in line:
                continue
            if "GENERATED_ROOT_JSON" in line or "ROOT_GENERATED_JSON" in line:
                continue
            offenders.append(f"{path.relative_to(ROOT)}:{line_number}:{line.strip()}")
    assert offenders == []


def test_sample_evidence_manifest_has_no_missing_files() -> None:
    sample_dir = ROOT / "docs" / "sample-evidence"
    manifest = sample_dir / "manifest.json"
    listed = set()
    if manifest.exists():
        import json

        listed = set(json.loads(manifest.read_text(encoding="utf-8")).get("files", []))
    actual = {p.name for p in sample_dir.glob("*.json") if p.name != "manifest.json"}
    assert actual <= listed
