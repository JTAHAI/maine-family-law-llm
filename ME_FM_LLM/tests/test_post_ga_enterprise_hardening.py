from __future__ import annotations

import json
from pathlib import Path

from legal.ops import EnterprisePreflightRunner, ReleaseProvenanceBuilder
from legal.release import PublicRepoReadinessAuditor
from legal.resources import OfflineValidationPackBuilder


def test_public_repo_readiness_enforces_single_pass_txt_and_ci() -> None:
    root = Path(__file__).resolve().parents[1]
    report = PublicRepoReadinessAuditor(project_root=root).audit()
    assert report.status == "pass"
    assert report.public_source_ready is True
    assert report.production_legal_ready is False
    assert report.only_one_txt_file is True
    assert report.github_ci_present is True


def test_enterprise_preflight_creates_external_layout_and_reports_commands(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    data_root = tmp_path / "ME_FM_LLM_data"
    report = EnterprisePreflightRunner(repo_root=root, data_root=data_root).run(create_external_dirs=True)
    assert report.status == "pass"
    assert report.source_preflight_ready is True
    assert report.networked_data_ready is False
    for required in ["research_resources", "official_authority_store", "parsed_authority_store", "embedding_store", "eval_store", "release_evidence"]:
        assert (data_root / required).is_dir()
    assert any("collect-enterprise-resources.py" in command for command in report.next_commands)


def test_offline_validation_pack_is_external_and_fixture_only(tmp_path: Path) -> None:
    data_root = tmp_path / "external"
    report = OfflineValidationPackBuilder(data_root=data_root).build()
    assert report.status == "pass"
    assert report.fixture_only is True
    manifest = json.loads((data_root / "official_authority_store" / "source_manifest.json").read_text())
    assert manifest[0]["fixture_only_not_legal_authority"] is True
    assert (data_root / "parsed_authority_store" / "statutes" / "offline_fixture_statutes.jsonl").is_file()
    assert (data_root / "release_evidence" / "offline_validation_pack_evidence.json").is_file()


def test_release_provenance_hashes_source_tree_without_runtime_dirs(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    report = ReleaseProvenanceBuilder(project_root=root).build()
    assert report.status == "pass"
    assert report.file_count > 100
    assert len(report.source_tree_hash) == 64
    paths = {item["path"] for item in report.artifacts}
    assert "PASS_CHANGES.txt" in paths
    assert not any(path.startswith("official_authority_store/") for path in paths)
