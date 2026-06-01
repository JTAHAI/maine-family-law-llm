from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from legal.resources import (
    EnterpriseResourceAuditor,
    EnterpriseResourceCollector,
    EnterpriseResourcePlanBuilder,
    load_enterprise_resource_catalog,
)


def tiny_catalog(url: str, required_count: int = 1) -> dict:
    return {
        "version": "test-catalog",
        "required_source_classes": {"test_class": required_count},
        "network_policy": {
            "respect_robots_txt": False,
            "default_delay_seconds": 0,
            "default_timeout_seconds": 5,
            "default_max_retries": 0,
        },
        "resources": [
            {
                "resource_id": "test-resource",
                "source_class": "test_class",
                "jurisdiction": "maine",
                "authority_level": "official_primary",
                "title": "Test Resource",
                "url": url,
                "expected_content_type": "text/plain",
                "required_for_enterprise": True,
                "parser_name": "plain_text",
            }
        ],
    }


def test_enterprise_catalog_has_windows_defaults_and_required_sources() -> None:
    catalog = load_enterprise_resource_catalog(Path(__file__).resolve().parents[1])
    assert catalog["default_windows_repo_root"] == r"C:\dev\ME_FM_LLM"
    assert catalog["default_windows_data_root"] == r"C:\dev\ME_FM_LLM_data"
    assert catalog["required_source_classes"]["maine_statute_title_index"] >= 8
    assert any(item["resource_id"] == "me-statutes-title-19a-index" for item in catalog["resources"])
    assert any(item["resource_id"] == "me-law-court-opinions-current" for item in catalog["resources"])


def test_enterprise_resource_collector_dry_run_writes_planned_manifest(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    data_root = tmp_path / "external-data"
    report = EnterpriseResourceCollector(
        project_root=project_root,
        data_root=data_root,
        catalog=tiny_catalog("https://example.test/resource"),
        respect_robots_txt=False,
    ).collect(dry_run=True)
    assert report.status == "pass"
    assert report.dry_run is True
    assert report.production_ready is False
    manifest = json.loads((data_root / "research_resources" / "resource_manifest.json").read_text())
    assert manifest[0]["status"] == "planned"
    assert "dry_run_no_resources_downloaded" in report.blockers


def test_enterprise_resource_collector_refuses_repo_data_root() -> None:
    project_root = Path(__file__).resolve().parents[1]
    with pytest.raises(ValueError):
        EnterpriseResourceCollector(
            project_root=project_root,
            data_root=project_root / "research_resources",
            catalog=tiny_catalog("https://example.test/resource"),
        ).collect(dry_run=True)


def test_enterprise_resource_auditor_validates_snapshot_hash_and_coverage(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    data_root = tmp_path / "external-data"
    root = data_root / "research_resources"
    snapshot = root / "snapshots" / "test_class" / "test-resource" / "snapshot.txt"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text("official text", encoding="utf-8")
    digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    manifest = [
        {
            "resource_id": "test-resource",
            "source_class": "test_class",
            "jurisdiction": "maine",
            "authority_level": "official_primary",
            "title": "Test Resource",
            "url": "file:///test-resource.txt",
            "required_for_enterprise": True,
            "status": "downloaded",
            "snapshot_path": str(snapshot),
            "sha256": digest,
            "bytes": len(snapshot.read_bytes()),
            "content_type": "text/plain",
            "retrieved_at": "2026-05-16T00:00:00+00:00",
            "parser_name": "plain_text",
        }
    ]
    root.mkdir(parents=True, exist_ok=True)
    (root / "resource_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    report = EnterpriseResourceAuditor(
        project_root=project_root,
        data_root=data_root,
        catalog=tiny_catalog("file:///test-resource.txt"),
    ).audit()
    assert report.production_ready is True
    assert report.successful_resources == 1
    assert report.coverage[0].status == "pass"


def test_enterprise_resource_plan_points_to_external_windows_data_root() -> None:
    project_root = Path(__file__).resolve().parents[1]
    plan = EnterpriseResourcePlanBuilder(project_root=project_root).build(
        repo_root=Path(r"C:\dev\ME_FM_LLM"),
        data_root=Path(r"C:\dev\ME_FM_LLM_data"),
    )
    assert plan["status"] == "pass"
    assert "C:" in plan["data_root"] or plan["data_root"].startswith("C")
    assert any("collect-enterprise-resources.py" in command for command in plan["commands"])
    assert "Do not commit" in plan["data_boundary"]


def test_enterprise_resource_catalog_has_redundant_court_rule_sources() -> None:
    catalog = load_enterprise_resource_catalog(Path(__file__).resolve().parents[1])
    rule_resources = [item for item in catalog["resources"] if item.get("source_class") == "maine_court_rules"]
    resource_ids = {item["resource_id"] for item in rule_resources}

    assert catalog["required_source_classes"]["maine_court_rules"] == 4
    assert len(rule_resources) >= 7
    assert "me-rules-appellate-plus-pdf" in resource_ids
    assert "me-rules-evidence-plus-pdf" in resource_ids
    assert "me-rules-probate-only-pdf" in resource_ids
    assert "me-rules-electronic-court-systems-pdf" in resource_ids
