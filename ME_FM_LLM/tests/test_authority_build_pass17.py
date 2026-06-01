from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from legal.connectors.base import RetrievedSource, SourceTarget
from legal.connectors.ingest_pipeline import OfficialAuthorityIngestor
from legal.production import AuthorityBuildAuditor


class StaticFetcher:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def fetch(self, target: SourceTarget) -> RetrievedSource:
        return RetrievedSource(
            target=target,
            content=self.body,
            retrieved_at=datetime(2026, 5, 16, tzinfo=timezone.utc),
            content_type="text/html",
            status_code=200,
            final_url=target.url,
        )


def _record(
    official_store: Path,
    *,
    source_id: str,
    source_class: str,
    parser_status: str = "parsed",
    freshness_status: str = "known_extracted_timestamp",
) -> dict:
    body = f"official source bytes for {source_id}".encode()
    digest = hashlib.sha256(body).hexdigest()
    path = official_store / f"{source_id}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return {
        "source_id": source_id,
        "source_class": source_class,
        "jurisdiction": "maine",
        "retrieved_at": "2026-05-16T00:00:00+00:00",
        "hash": digest,
        "parser_status": parser_status,
        "freshness_status": freshness_status,
        "data_class": "official_public_authority",
        "source_url_or_path": f"https://example.maine.gov/{source_id}",
        "parser_version": "test_v1",
        "snapshot_path": str(path),
        "parser_audit": {"status": parser_status, "parser_version": "test_v1"},
        "use_restrictions": {
            "training_allowed_by_default": True,
            "release_packaging_allowed": False,
            "requires_human_review": True,
        },
        "metadata": {},
    }


def test_pass17_authority_build_auditor_blocks_missing_external_manifest(tmp_path):
    report = AuthorityBuildAuditor(project_root=Path.cwd(), data_root=tmp_path).run()

    assert report.status == "pass"
    assert report.production_ready is False
    assert "manifest_missing" in report.blockers
    assert report.total_records == 0


def test_pass17_authority_build_auditor_accepts_valid_external_manifest(tmp_path):
    official_store = tmp_path / "official_authority_store"
    manifest = [
        _record(official_store, source_id="title19a", source_class="statute_title_index"),
        _record(
            official_store,
            source_id="title19a-pdf",
            source_class="statute_title_pdf",
            parser_status="snapshot_only",
            freshness_status="retrieved_pdf_metadata_known",
        ),
    ]
    (official_store / "source_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    policy = {
        "version": "test-pass17",
        "external_data_root_required": True,
        "official_store_name": "official_authority_store",
        "manifest_filename": "source_manifest.json",
        "minimum_ingested_targets": 2,
        "required_source_class_minimums": {
            "statute_title_index": 1,
            "statute_title_pdf": 1,
        },
        "acceptable_parser_statuses": ["parsed", "snapshot_only"],
        "parsed_status_required_for_classes": ["statute_title_index"],
        "snapshot_only_allowed_for_classes": ["statute_title_pdf"],
        "required_manifest_fields": [
            "source_id",
            "source_class",
            "jurisdiction",
            "retrieved_at",
            "hash",
            "parser_status",
            "freshness_status",
            "data_class",
            "source_url_or_path",
            "snapshot_path",
            "parser_audit",
        ],
        "minimum_snapshot_bytes": 1,
        "require_snapshot_files_exist": True,
        "require_manifest_hash_matches_snapshot": True,
    }

    report = AuthorityBuildAuditor(project_root=Path.cwd(), data_root=tmp_path, policy=policy).run()

    assert report.production_ready is True
    assert report.total_records == 2
    assert report.parsed_records == 1
    assert report.snapshot_only_records == 1
    assert not report.blockers


def test_pass17_ingest_manifest_includes_snapshot_path_and_parser_audit(tmp_path):
    target = SourceTarget(
        target_id="fixture-title-19a",
        source_class="statute_title_index",
        jurisdiction="maine",
        url="https://legislature.maine.gov/statutes/19-a/title19-Ach0sec0.html",
        parser_name="maine_revisor_title_index",
    )
    body = b"""
    <html><body><h1>Title 19-A: DOMESTIC RELATIONS</h1>
    <a href="title19-Asec1653.html">\xc2\xa71653. Parental rights and responsibilities</a>
    <p>Data for this page extracted on 10/20/2025 14:32:56.</p></body></html>
    """
    ingestor = OfficialAuthorityIngestor(fetcher=StaticFetcher(body), snapshot_base_dir=tmp_path)

    result = ingestor.ingest_target(target)
    manifest_path = ingestor.write_manifest([result])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest[0]["snapshot_path"] == result.snapshot_path
    assert manifest[0]["parser_audit"]["status"] == "parsed"
    assert Path(manifest[0]["snapshot_path"]).exists()


def test_pass17_authority_build_blocks_non_object_manifest_rows(tmp_path):
    official_store = tmp_path / "official_authority_store"
    official_store.mkdir(parents=True)
    (official_store / "source_manifest.json").write_text(json.dumps(["not-a-record"]), encoding="utf-8")
    policy = {
        "version": "test-non-object",
        "external_data_root_required": True,
        "official_store_name": "official_authority_store",
        "manifest_filename": "source_manifest.json",
        "minimum_ingested_targets": 0,
        "required_source_class_minimums": {},
        "acceptable_parser_statuses": ["parsed", "snapshot_only"],
        "parsed_status_required_for_classes": [],
        "snapshot_only_allowed_for_classes": [],
        "required_manifest_fields": [],
        "minimum_snapshot_bytes": 1,
        "require_snapshot_files_exist": False,
        "require_manifest_hash_matches_snapshot": False,
    }

    report = AuthorityBuildAuditor(project_root=Path.cwd(), data_root=tmp_path, policy=policy).run()

    assert report.production_ready is False
    assert "manifest_record_not_object" in report.blockers


def test_pass17_authority_build_blocks_duplicate_source_ids(tmp_path):
    official_store = tmp_path / "official_authority_store"
    manifest = [
        _record(official_store, source_id="duplicate", source_class="statute_title_index"),
        _record(official_store, source_id="duplicate", source_class="statute_title_index"),
    ]
    (official_store / "source_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    policy = {
        "version": "test-duplicate",
        "external_data_root_required": True,
        "official_store_name": "official_authority_store",
        "manifest_filename": "source_manifest.json",
        "minimum_ingested_targets": 2,
        "required_source_class_minimums": {"statute_title_index": 2},
        "acceptable_parser_statuses": ["parsed"],
        "parsed_status_required_for_classes": ["statute_title_index"],
        "snapshot_only_allowed_for_classes": [],
        "required_manifest_fields": [
            "source_id",
            "source_class",
            "jurisdiction",
            "retrieved_at",
            "hash",
            "parser_status",
            "freshness_status",
            "data_class",
            "source_url_or_path",
            "snapshot_path",
            "parser_audit",
        ],
        "minimum_snapshot_bytes": 1,
        "require_snapshot_files_exist": True,
        "require_manifest_hash_matches_snapshot": True,
    }

    report = AuthorityBuildAuditor(project_root=Path.cwd(), data_root=tmp_path, policy=policy).run()

    assert report.production_ready is False
    assert "duplicate_source_id" in report.blockers


def test_pass17_authority_build_blocks_snapshot_path_outside_official_store(tmp_path):
    official_store = tmp_path / "official_authority_store"
    outside = tmp_path / "elsewhere" / "snapshot.html"
    outside.parent.mkdir(parents=True)
    body = b"official bytes outside store"
    outside.write_bytes(body)
    manifest = [
        {
            **_record(official_store, source_id="title19a", source_class="statute_title_index"),
            "snapshot_path": str(outside),
            "hash": hashlib.sha256(body).hexdigest(),
        }
    ]
    (official_store / "source_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    policy = {
        "version": "test-snapshot-containment",
        "external_data_root_required": True,
        "official_store_name": "official_authority_store",
        "manifest_filename": "source_manifest.json",
        "minimum_ingested_targets": 1,
        "required_source_class_minimums": {"statute_title_index": 1},
        "acceptable_parser_statuses": ["parsed"],
        "parsed_status_required_for_classes": ["statute_title_index"],
        "snapshot_only_allowed_for_classes": [],
        "required_manifest_fields": [
            "source_id",
            "source_class",
            "jurisdiction",
            "retrieved_at",
            "hash",
            "parser_status",
            "freshness_status",
            "data_class",
            "source_url_or_path",
            "snapshot_path",
            "parser_audit",
        ],
        "minimum_snapshot_bytes": 1,
        "require_snapshot_files_exist": True,
        "require_manifest_hash_matches_snapshot": True,
    }

    report = AuthorityBuildAuditor(project_root=Path.cwd(), data_root=tmp_path, policy=policy).run()

    assert report.production_ready is False
    assert "snapshot_path_outside_official_store" in report.blockers


def test_pass17_authority_build_blocks_invalid_timestamp_and_parser_audit_mismatch(tmp_path):
    official_store = tmp_path / "official_authority_store"
    manifest = [
        {
            **_record(official_store, source_id="title19a", source_class="statute_title_index"),
            "retrieved_at": "not-a-timestamp",
            "parser_audit": {"status": "snapshot_only", "parser_version": "test_v1"},
        }
    ]
    (official_store / "source_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    policy = {
        "version": "test-timestamp-parser-audit",
        "external_data_root_required": True,
        "official_store_name": "official_authority_store",
        "manifest_filename": "source_manifest.json",
        "minimum_ingested_targets": 1,
        "required_source_class_minimums": {"statute_title_index": 1},
        "acceptable_parser_statuses": ["parsed"],
        "parsed_status_required_for_classes": ["statute_title_index"],
        "snapshot_only_allowed_for_classes": [],
        "required_manifest_fields": [
            "source_id",
            "source_class",
            "jurisdiction",
            "retrieved_at",
            "hash",
            "parser_status",
            "freshness_status",
            "data_class",
            "source_url_or_path",
            "snapshot_path",
            "parser_audit",
        ],
        "minimum_snapshot_bytes": 1,
        "require_snapshot_files_exist": True,
        "require_manifest_hash_matches_snapshot": True,
    }

    report = AuthorityBuildAuditor(project_root=Path.cwd(), data_root=tmp_path, policy=policy).run()

    assert report.production_ready is False
    assert "retrieved_timestamp_invalid" in report.blockers
    assert "parser_audit_status_mismatch" in report.blockers
