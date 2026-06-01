from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from legal.authority_store import ParsedAuthorityStoreAuditor


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def _base() -> dict:
    return {
        "source_id": "snapshot-1",
        "source_hash": "hash-1",
        "jurisdiction": "maine",
        "freshness_status": "fresh",
        "parser_status": "parsed",
        "source_span": {"start_offset": 0, "end_offset": 100},
        "source_url_or_path": "https://official.example/source",
    }


def _write_first_wave_indexes(data_root: Path) -> None:
    parsed = data_root / "parsed_authority_store"
    base = _base()
    _write_jsonl(
        parsed / "statutes" / "statute_title_indexes.jsonl",
        [
            {
                **base,
                "authority_kind": "statute_section_reference",
                "record_id": "statute-19a-1653-ref",
                "title": "Parental rights and responsibilities",
                "citation": "19-A M.R.S. § 1653",
                "href": "title19-Asec1653.html",
            }
        ],
    )
    _write_jsonl(
        parsed / "rules" / "rules_index.jsonl",
        [
            {
                **base,
                "authority_kind": "court_rule_reference",
                "record_id": "rule-120-ref",
                "title": "Rule 120",
                "citation": "M.R. Civ. P. 120",
                "href": "rules/text/rule120.pdf",
            }
        ],
    )
    _write_jsonl(
        parsed / "forms" / "forms_index.jsonl",
        [
            {
                **base,
                "authority_kind": "court_form_reference",
                "record_id": "fm-001-ref",
                "title": "Family Matter Summons",
                "citation": "FM-001",
                "form_id": "FM-001",
                "href": "forms/fm-001.pdf",
            }
        ],
    )
    _write_jsonl(
        parsed / "opinions" / "opinion_index.jsonl",
        [
            {
                **base,
                "authority_kind": "law_court_opinion_reference",
                "record_id": "2026-me-1-ref",
                "title": "Test v. Test",
                "citation": "2026 ME 1",
                "href": "lawcourt/2026/26me001.pdf",
            }
        ],
    )


def _write_direct_authority(data_root: Path) -> None:
    parsed = data_root / "parsed_authority_store"
    base = _base()
    _write_jsonl(
        parsed / "statutes" / "statute_sections.jsonl",
        [
            {
                **base,
                "authority_kind": "statute_section",
                "record_id": "statute-19a-1653",
                "title": "19-A § 1653",
                "citation": "19-A M.R.S. § 1653",
                "title_number": "19-A",
                "section_number": "1653",
                "text": "Best interest and parental rights text.",
            }
        ],
    )
    _write_jsonl(
        parsed / "forms" / "forms.jsonl",
        [
            {
                **base,
                "authority_kind": "court_form",
                "record_id": "form-fm-001",
                "title": "Family Matter Summons",
                "citation": "FM-001",
                "form_id": "FM-001",
                "text": "Official form instructions.",
            }
        ],
    )
    _write_jsonl(
        parsed / "opinions" / "opinions.jsonl",
        [
            {
                **base,
                "authority_kind": "law_court_opinion",
                "record_id": "case-2026-me-1",
                "title": "Test v. Test",
                "citation": "2026 ME 1",
                "text": "The Law Court applied 19-A M.R.S. § 1653.",
            }
        ],
    )


def test_parsed_audit_reports_index_only_readiness_without_blocking_first_wave(tmp_path: Path) -> None:
    data_root = tmp_path / "external_data"
    _write_first_wave_indexes(data_root)

    report = ParsedAuthorityStoreAuditor(data_root=data_root).run()

    assert report["status"] == "pass"
    assert report["readiness"] == "index_only"
    assert report["direct_authority"]["reference_record_count"] == 4


def test_parsed_audit_blocks_direct_handoff_when_direct_authority_missing(tmp_path: Path) -> None:
    data_root = tmp_path / "external_data"
    _write_first_wave_indexes(data_root)

    report = ParsedAuthorityStoreAuditor(
        data_root=data_root,
        require_direct_authority=True,
    ).run()

    assert report["status"] == "blocked"
    codes = {finding["code"] for finding in report["findings"]}
    assert "missing_direct_authority_collection" in codes
    assert "direct_authority_kind_missing" in codes


def test_parsed_audit_passes_direct_handoff_with_full_text_records(tmp_path: Path) -> None:
    data_root = tmp_path / "external_data"
    _write_first_wave_indexes(data_root)
    _write_direct_authority(data_root)

    report = ParsedAuthorityStoreAuditor(
        data_root=data_root,
        require_direct_authority=True,
    ).run()

    assert report["status"] == "pass"
    assert report["readiness"] == "direct_authority_ready"
    assert report["direct_authority"]["full_text_record_count"] == 3
    assert report["direct_authority"]["counts_by_kind"] == {
        "court_form": 1,
        "law_court_opinion": 1,
        "statute_section": 1,
    }


def test_parsed_audit_script_exposes_require_direct_authority_flag(tmp_path: Path) -> None:
    data_root = tmp_path / "external_data"
    _write_first_wave_indexes(data_root)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/audit-parsed-authority-store.py",
            "--data-root",
            str(data_root),
            "--require-direct-authority",
        ],
        text=True,
        capture_output=True,
        timeout=45,
        check=False,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert payload["require_direct_authority"] is True
