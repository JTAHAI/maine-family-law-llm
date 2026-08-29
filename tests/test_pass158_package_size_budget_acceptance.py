from __future__ import annotations

import json
import zipfile
from pathlib import Path

from legal.release.package_size_budget import analyze_msix_package


def _config(path: Path) -> None:
    path.write_text(json.dumps({"policy": {"runtime_downloads_allowed": False, "tier_change_requires_new_signed_package": True}, "tiers": {"essential": {"maximum_package_bytes": 1000000, "excluded_archive_prefixes": ["store/docling/models/", "_internal/en_core_web_lg/", "_internal/torch/"]}, "full": {"maximum_package_bytes": 1000000, "required_archive_prefixes": ["store/docling/models/", "_internal/en_core_web_lg/"]}}}), encoding="utf-8")


def test_pass158_accepts_hash_bound_offline_full_tier_and_reports_heavy_groups(tmp_path: Path) -> None:
    package = tmp_path / "full.msix"; config = tmp_path / "tiers.json"; _config(config)
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("store/docling/models/fake.bin", b"a" * 200)
        archive.writestr("_internal/en_core_web_lg/vectors", b"b" * 150)
        archive.writestr("_internal/torch/lib/torch_cpu.dll", b"c" * 100)
    report = analyze_msix_package(package=package, tier_config=config, requested_tier="full")
    assert report["status"] == "pass" and report["tier"]["runtime_downloads_allowed"] is False
    assert report["optimization"]["essential_edition_available_only_as_separate_build"] is True
    assert report["size_groups"][0]["group"] == "docling_models"


def test_pass158_blocks_excluded_essential_payload_and_budget_excess(tmp_path: Path) -> None:
    package = tmp_path / "essential.msix"; config = tmp_path / "tiers.json"; _config(config)
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("store/docling/models/fake.bin", b"a" * 20)
    report = analyze_msix_package(package=package, tier_config=config, requested_tier="essential")
    assert report["status"] == "blocked" and "excluded_tier_payload_present:store/docling/models/" in report["blockers"]
