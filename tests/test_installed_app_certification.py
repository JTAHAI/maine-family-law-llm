import hashlib
import json
from pathlib import Path

from legal.release.installed_certification import InstalledAppCertifier


def write(root: Path, name: str, value: dict):
    (root / name).write_text(json.dumps(value), encoding="utf-8")


def evidence(tmp_path: Path) -> tuple[Path, Path, str]:
    package = tmp_path / "app.msix"
    package.write_bytes(b"synthetic-msix")
    package_hash = hashlib.sha256(package.read_bytes()).hexdigest()
    root = tmp_path / "evidence"
    root.mkdir()
    write(
        root,
        "store-build-smoke.json",
        {
            "launch_result": "pass",
            "api_health_result": True,
            "answer_grounded": True,
            "external_data_boundary_verification": True,
        },
    )
    write(
        root,
        "installed-offline-qualification.json",
        {"qualification_status": "pass", "blockers": []},
    )
    write(root, "sealed-msix-archive-audit.json", {"status": "pass"})
    write(root, "private-data-audit.json", {"status": "pass"})
    write(
        root,
        "store-preflight.json",
        {
            "final_readiness_state": "PASS",
            "package": {"sha256": package_hash},
            "blockers": [],
        },
    )
    write(
        root,
        "installed-lifecycle.json",
        {
            "package_sha256": package_hash,
            "install_passed": True,
            "launch_passed": True,
            "ui_load_passed": True,
            "uninstall_passed": True,
            "reinstall_passed": True,
            "data_retention_choice_verified": True,
            "wack_status": "pass",
        },
    )
    return package, root, package_hash


def test_certifier_passes_only_complete_hash_bound_lifecycle(tmp_path: Path):
    package, root, package_hash = evidence(tmp_path)
    report = InstalledAppCertifier(package, root).run()
    assert report["status"] == "pass"
    assert report["package_sha256"] == package_hash
    assert report["store_submission_eligible"] is True


def test_certifier_fails_closed_when_wack_or_lifecycle_is_missing(tmp_path: Path):
    package, root, _package_hash = evidence(tmp_path)
    (root / "installed-lifecycle.json").unlink()
    report = InstalledAppCertifier(package, root).run()
    assert report["status"] == "blocked"
    assert "install_uninstall_reinstall:evidence_missing" in report["blockers"]


def test_certifier_detects_evidence_bound_to_a_different_package(tmp_path: Path):
    package, root, _package_hash = evidence(tmp_path)
    lifecycle = json.loads((root / "installed-lifecycle.json").read_text(encoding="utf-8"))
    lifecycle["package_sha256"] = "f" * 64
    write(root, "installed-lifecycle.json", lifecycle)
    report = InstalledAppCertifier(package, root).run()
    assert "artifact_identity:evidence_package_hash_mismatch" in report["blockers"]
