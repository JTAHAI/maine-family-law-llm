from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from legal.production.followup_targets import AuthorityFollowupTargetBuilder


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def _parsed_index_fixture(tmp_path: Path) -> Path:
    data_root = tmp_path / "external_data"
    parsed = data_root / "parsed_authority_store"
    base = {
        "source_id": "index-source",
        "source_hash": "hash",
        "jurisdiction": "maine",
        "freshness_status": "fresh",
        "parser_status": "parsed",
        "source_span": {"start_offset": 0, "end_offset": 120},
        "source_url_or_path": "https://www.courts.maine.gov/forms/index.html",
    }
    _write_jsonl(
        parsed / "statutes" / "statute_title_indexes.jsonl",
        [
            {
                **base,
                "authority_kind": "statute_section_reference",
                "record_id": "statute-19a-1653",
                "title": "Parental rights and responsibilities",
                "title_number": "19-A",
                "section_number": "1653",
                "href": "https://legislature.maine.gov/statutes/19-a/title19-Asec1653.html",
            }
        ],
    )
    _write_jsonl(
        parsed / "rules" / "rules_index.jsonl",
        [
            {
                **base,
                "authority_kind": "court_rule_reference",
                "record_id": "rule-120",
                "citation": "M.R. Civ. P. 120",
                "rule_number": "120",
                "href": "https://www.courts.maine.gov/rules/text/mr_civ_p_120_standing_order_2023-03-09.pdf",
            }
        ],
    )
    _write_jsonl(
        parsed / "forms" / "forms_index.jsonl",
        [
            {
                **base,
                "authority_kind": "court_form_reference",
                "record_id": "form-fm-001",
                "citation": "FM-001",
                "form_id": "FM-001",
                "href": "https://www.courts.maine.gov/forms/fm-001.pdf",
            }
        ],
    )
    _write_jsonl(
        parsed / "opinions" / "opinion_index.jsonl",
        [
            {
                **base,
                "authority_kind": "law_court_opinion_reference",
                "record_id": "opinion-2026-me-1",
                "citation": "2026 ME 1",
                "href": "https://www.courts.maine.gov/courts/sjc/lawcourt/2026/26me001.pdf",
            }
        ],
    )
    return data_root


def test_followup_target_builder_derives_second_wave_catalog(tmp_path: Path) -> None:
    data_root = _parsed_index_fixture(tmp_path)

    report = AuthorityFollowupTargetBuilder(data_root=data_root).build(write=True)

    assert report.status == "pass"
    assert report.target_count == 4
    assert report.counts_by_source_class == {
        "court_form_pdf": 1,
        "court_rule_pdf": 1,
        "law_court_opinion_pdf": 1,
        "statute_section": 1,
    }
    catalog = json.loads((data_root / "official_authority_store" / "derived_authority_targets.json").read_text(encoding="utf-8"))
    target_by_class = {row["source_class"]: row for row in catalog["targets"]}
    assert target_by_class["statute_section"]["parser_name"] == "maine_revisor_section"
    assert target_by_class["court_form_pdf"]["parser_name"] == "maine_form_pdf"
    assert target_by_class["law_court_opinion_pdf"]["expected_content_type"] == "application/pdf"


def test_ingest_script_accepts_generated_target_catalog_in_dry_run(tmp_path: Path) -> None:
    data_root = _parsed_index_fixture(tmp_path)
    AuthorityFollowupTargetBuilder(data_root=data_root).build(write=True)
    catalog = data_root / "official_authority_store" / "derived_authority_targets.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/ingest-maine-authority.py",
            "--data-root",
            str(data_root),
            "--target-catalog",
            str(catalog),
            "--dry-run",
            "--max-targets",
            "2",
        ],
        text=True,
        capture_output=True,
        timeout=45,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "pass"
    assert payload["target_count"] == 2
    assert payload["target_ids"][0].startswith("me-")


def test_followup_target_builder_adds_core_title_19a_section_when_title_index_has_no_section_links(tmp_path: Path) -> None:
    data_root = tmp_path / "external_data"
    parsed = data_root / "parsed_authority_store"
    _write_jsonl(
        parsed / "statutes" / "statute_title_indexes.jsonl",
        [
            {
                "authority_kind": "statute_title_index",
                "record_id": "statute-title-19-a",
                "source_id": "title-19a-index",
                "source_hash": "hash",
                "jurisdiction": "maine",
                "freshness_status": "fresh",
                "parser_status": "parsed",
                "source_span": {"start_offset": 0, "end_offset": 120},
                "source_url_or_path": "https://legislature.maine.gov/statutes/19-a/title19-Ach0sec0.html",
                "title_number": "19-A",
            }
        ],
    )

    report = AuthorityFollowupTargetBuilder(data_root=data_root).build(write=True)

    assert report.status == "pass"
    catalog = json.loads((data_root / "official_authority_store" / "derived_authority_targets.json").read_text(encoding="utf-8"))
    targets = {row["target_id"]: row for row in catalog["targets"]}
    assert targets["me-revisor-section-19-a-1653"]["source_class"] == "statute_section"
    assert targets["me-revisor-section-19-a-1653"]["parser_name"] == "maine_revisor_section"


def test_followup_target_builder_percent_encodes_spaces_in_pdf_hrefs(tmp_path: Path) -> None:
    data_root = tmp_path / "external_data"
    parsed = data_root / "parsed_authority_store"
    _write_jsonl(
        parsed / "rules" / "rules_index.jsonl",
        [
            {
                "authority_kind": "court_rule_reference",
                "record_id": "rule-space-url",
                "source_id": "rules-index",
                "source_hash": "hash",
                "jurisdiction": "maine",
                "freshness_status": "fresh",
                "parser_status": "parsed",
                "source_span": {"start_offset": 0, "end_offset": 120},
                "source_url_or_path": "https://www.courts.maine.gov/rules/index.html",
                "rule_number": "MRScP",
                "href": "/rules/text/mrscp 2024-11-01.pdf",
            }
        ],
    )

    AuthorityFollowupTargetBuilder(data_root=data_root).build(write=True)

    catalog = json.loads((data_root / "official_authority_store" / "derived_authority_targets.json").read_text(encoding="utf-8"))
    assert catalog["targets"][0]["url"] == "https://www.courts.maine.gov/rules/text/mrscp%202024-11-01.pdf"


def test_followup_target_builder_corrects_fm171_download_identifier(tmp_path: Path) -> None:
    data_root = tmp_path / "external_data"
    parsed = data_root / "parsed_authority_store"
    _write_jsonl(
        parsed / "forms" / "forms_index.jsonl",
        [
            {
                "authority_kind": "court_form_reference",
                "record_id": "form-fm-171",
                "source_id": "forms-index",
                "source_hash": "hash",
                "jurisdiction": "maine",
                "freshness_status": "fresh",
                "parser_status": "parsed",
                "source_span": {"start_offset": 0, "end_offset": 120},
                "source_url_or_path": "https://www.courts.maine.gov/forms/index.html",
                "form_id": "FM-171",
                "href": "https://mjbportal.courts.maine.gov/CourtForms/FormsLists/DownloadForm?strFormNumber=FM-261",
            }
        ],
    )

    report = AuthorityFollowupTargetBuilder(data_root=data_root).build(write=True)

    catalog = json.loads((data_root / "official_authority_store" / "derived_authority_targets.json").read_text(encoding="utf-8"))
    assert catalog["targets"][0]["url"].endswith("strFormNumber=FM-171")
    assert catalog["targets"][0]["source_class"] == "court_form_pdf"
    assert catalog["targets"][0]["parser_name"] == "maine_form_pdf"
    assert any(item.code == "corrected_form_download_identifier" for item in report.findings)
