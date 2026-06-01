from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from legal.authority_store import ParsedAuthorityStoreAuditor, ParsedAuthorityStoreBuilder
from legal.connectors.base import RetrievedSource, SourceTarget
from legal.connectors.http_fetcher import OfficialSourceFetchError
from legal.connectors.ingest_pipeline import OfficialAuthorityIngestor
from legal.production import SourceUpdateEngine


class MultiStaticFetcher:
    def __init__(self, bodies: dict[str, bytes], failures: set[str] | None = None) -> None:
        self.bodies = bodies
        self.failures = failures or set()

    def fetch(self, target: SourceTarget) -> RetrievedSource:
        if target.target_id in self.failures:
            raise OfficialSourceFetchError(
                target=target,
                code="fixture_network_down",
                message="fixture failure",
            )
        return RetrievedSource(
            target=target,
            content=self.bodies[target.target_id],
            retrieved_at=datetime.now(timezone.utc),
            content_type=target.expected_content_type,
            status_code=200,
            final_url=target.url,
        )


def _targets() -> list[SourceTarget]:
    return [
        SourceTarget(
            target_id="statute",
            source_class="statute_title_index",
            jurisdiction="maine",
            url="https://legislature.maine.gov/statutes/19-a/title19-Ach0sec0.html",
            parser_name="maine_revisor_title_index",
        ),
        SourceTarget(
            target_id="statute_pdf",
            source_class="statute_title_pdf",
            jurisdiction="maine",
            url="https://legislature.maine.gov/statutes/19-a/title19-A.pdf",
            parser_name="pdf_snapshot",
            expected_content_type="application/pdf",
        ),
        SourceTarget(
            target_id="rules",
            source_class="court_rules_index",
            jurisdiction="maine",
            url="https://www.courts.maine.gov/rules/rules-civil.html",
            parser_name="maine_rules_index",
        ),
        SourceTarget(
            target_id="forms",
            source_class="court_forms_index",
            jurisdiction="maine",
            url="https://www.courts.maine.gov/forms/index.html",
            parser_name="maine_forms_index",
        ),
        SourceTarget(
            target_id="opinions",
            source_class="law_court_opinion_index",
            jurisdiction="maine",
            url="https://www.courts.maine.gov/courts/sjc/lawcourt/2026/index.html",
            parser_name="maine_law_court_opinion_index",
        ),
    ]


def _bodies() -> dict[str, bytes]:
    return {
        "statute": b"""
        <html><body><h1>Title 19-A: DOMESTIC RELATIONS</h1>
        <a href="title19-Asec1653.html">\xc2\xa71653. Parental rights and responsibilities</a>
        <p>Data for this page extracted on 10/20/2025 14:32:56.</p></body></html>
        """,
        "statute_pdf": b"%PDF-1.4 fixture title 19-A pdf bytes",
        "rules": b"""
        <html><body><a href="/rules/text/MRCP_100.pdf">Rule 100. Family Division</a></body></html>
        """,
        "forms": b"""
        <html><body><a href="/forms/fm-001.pdf">FM-001 Family Matter Summons</a></body></html>
        """,
        "opinions": b"""
        <html><body><a href="/courts/sjc/lawcourt/2026/26me001.pdf">2026 ME 1 Test v. Test</a></body></html>
        """,
    }


def _build_fixture_authority_store(tmp_path: Path) -> Path:
    data_root = tmp_path / "external_data"
    official_store = data_root / "official_authority_store"
    ingestor = OfficialAuthorityIngestor(
        fetcher=MultiStaticFetcher(_bodies()),
        snapshot_base_dir=official_store,
    )
    ingested = ingestor.ingest_all(_targets())
    ingestor.write_manifest(ingested)
    return data_root


def test_pass19_ingestor_continues_and_writes_failed_source_report(tmp_path):
    data_root = tmp_path / "external_data"
    ingestor = OfficialAuthorityIngestor(
        fetcher=MultiStaticFetcher(_bodies(), failures={"forms"}),
        snapshot_base_dir=data_root / "official_authority_store",
    )

    ingested = ingestor.ingest_all(_targets(), continue_on_error=True)
    manifest_path = ingestor.write_manifest(ingested)
    failure_report = ingestor.write_failure_report()
    run_report = ingestor.write_ingest_run_report(ingested=ingested, manifest_path=manifest_path)

    assert len(ingested) == 4
    assert len(ingestor.failed) == 1
    assert json.loads(failure_report.read_text(encoding="utf-8"))["failed_count"] == 1
    assert json.loads(run_report.read_text(encoding="utf-8"))["failed_count"] == 1
    assert json.loads(manifest_path.read_text(encoding="utf-8"))[1]["freshness_status"] == "retrieved_timestamp_known"


def test_pass20_parsed_authority_store_builds_structured_jsonl(tmp_path):
    data_root = _build_fixture_authority_store(tmp_path)

    report = ParsedAuthorityStoreBuilder(data_root=data_root).build()
    audit = ParsedAuthorityStoreAuditor(data_root=data_root).run()

    assert report.status == "pass"
    assert report.parsed_record_count >= 5
    assert (data_root / "parsed_authority_store" / "statutes" / "statute_title_indexes.jsonl").exists()
    assert (data_root / "parsed_authority_store" / "rules" / "rules_index.jsonl").exists()
    assert (data_root / "parsed_authority_store" / "forms" / "forms_index.jsonl").exists()
    assert (data_root / "parsed_authority_store" / "opinions" / "opinion_index.jsonl").exists()
    assert audit["status"] == "pass"


def test_pass21_source_update_report_measures_freshness_and_diffs(tmp_path):
    data_root = _build_fixture_authority_store(tmp_path)
    manifest_path = data_root / "official_authority_store" / "source_manifest.json"
    current = json.loads(manifest_path.read_text(encoding="utf-8"))
    previous = [dict(row) for row in current[:-1]]
    previous[0]["hash"] = "previoushash"
    previous_path = tmp_path / "previous_manifest.json"
    previous_path.write_text(json.dumps(previous), encoding="utf-8")

    report = SourceUpdateEngine(
        data_root=data_root,
        previous_manifest=previous_path,
        max_age_days=999999,
    ).run(write_report=True)

    assert report.status == "pass"
    assert report.freshness_counts["fresh"] == len(current)
    assert current[-1]["source_id"] in report.changed_since_last_build["added"]
    assert current[0]["source_id"] in report.changed_since_last_build["hash_changed"]
    assert (data_root / "source_update_report.json").exists()


def test_pass21_source_update_report_allows_court_form_retrieved_timestamp_fallback(tmp_path):
    data_root = tmp_path / "external_data"
    official_store = data_root / "official_authority_store"
    official_store.mkdir(parents=True)
    now = datetime.now(timezone.utc).isoformat()
    manifest = [
        {
            "source_id": "court-form-pdf-no-version",
            "source_class": "court_form_pdf",
            "jurisdiction": "maine",
            "retrieved_at": now,
            "hash": "hash-form",
            "parser_status": "parsed",
            "freshness_status": "unknown",
            "data_class": "official_public_authority",
            "source_url_or_path": "https://www.courts.maine.gov/forms/fm-088.pdf",
            "metadata": {"freshness_strategy": "form_version_or_retrieved_timestamp"},
        }
    ]
    (official_store / "source_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    report = SourceUpdateEngine(data_root=data_root, max_age_days=999999).run(write_report=True)

    assert report.status == "pass"
    assert report.freshness_counts["fresh"] == 1
    assert report.freshness_counts["unknown"] == 0
    assert any(finding.code == "freshness_retrieved_timestamp_fallback" for finding in report.findings)
