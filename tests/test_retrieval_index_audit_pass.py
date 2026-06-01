from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from legal.production.retrieval_index_audit import RetrievalIndexAuditor
from legal.retrieval.index_builder import RetrievalIndexBuilder


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def _parsed_data_root(tmp_path: Path, *, direct: bool = True) -> Path:
    data_root = tmp_path / "external_data"
    parsed = data_root / "parsed_authority_store"
    base = {
        "source_id": "snapshot-1",
        "source_hash": "hash-1",
        "jurisdiction": "maine",
        "freshness_status": "fresh",
        "parser_status": "parsed",
        "source_span": {"start_offset": 0, "end_offset": 100},
        "source_url_or_path": "https://official.example/source",
    }
    if not direct:
        _write_jsonl(
            parsed / "misc" / "plain.jsonl",
            [
                {
                    **base,
                    "record_id": "plain-record",
                    "source_class": "secondary_reference",
                    "authority_kind": "plain_text_reference",
                    "title": "Plain record",
                    "text": "Maine family law background without parsed citation lookup metadata.",
                }
            ],
        )
        return data_root
    _write_jsonl(
        parsed / "statutes" / "statute_sections.jsonl",
        [
            {
                **base,
                "record_id": "statute-19a-1653",
                "source_class": "maine_statute_section",
                "authority_kind": "statute_section",
                "title": "Best interest of the child",
                "citation": "19-A M.R.S. § 1653",
                "section_number": "1653",
                "text": "Best interest factors govern parental rights and responsibilities.",
                "issue_labels": ["parental_rights_responsibilities"],
            }
        ],
    )
    _write_jsonl(
        parsed / "forms" / "forms.jsonl",
        [
            {
                **base,
                "record_id": "form-fm-002",
                "source_class": "court_form",
                "authority_kind": "court_form",
                "title": "Family Matter Summary Sheet",
                "citation": "FM-002",
                "form_id": "FM-002",
                "text": "Official Maine family matter summary sheet.",
                "issue_labels": ["divorce"],
            }
        ],
    )
    _write_jsonl(
        parsed / "opinions" / "opinions.jsonl",
        [
            {
                **base,
                "record_id": "case-2026-me-1",
                "source_class": "law_court_opinion",
                "authority_kind": "law_court_opinion",
                "title": "Test v. Test",
                "citation": "2026 ME 1",
                "text": "The Law Court discussed parental rights and Rule 52 findings.",
                "issue_labels": ["Rule_52_findings"],
            }
        ],
    )
    return data_root


def test_retrieval_index_audit_blocks_missing_artifacts(tmp_path: Path) -> None:
    report = RetrievalIndexAuditor(data_root=tmp_path / "external_data", repo_root=Path.cwd()).audit()

    assert report.status == "blocked"
    assert "manifest_missing" in report.blockers
    assert "required_index_file_missing" in report.blockers


def test_retrieval_index_audit_passes_built_external_indexes(tmp_path: Path) -> None:
    data_root = _parsed_data_root(tmp_path)
    RetrievalIndexBuilder(data_root=data_root, repo_root=Path.cwd()).build()

    report = RetrievalIndexAuditor(data_root=data_root, repo_root=Path.cwd()).audit(require_direct_lookups=True)

    assert report.status == "pass"
    assert report.readiness == "retrieval_indexes_ready"
    assert report.document_count == 3
    assert report.vector_count == 3
    assert report.lookup_counts["exact_citation"] >= 3
    assert report.lookup_counts["form_id"] >= 1
    assert report.lookup_counts["statute_section"] >= 1


def test_retrieval_index_audit_direct_lookup_gate_blocks_empty_lookups(tmp_path: Path) -> None:
    data_root = _parsed_data_root(tmp_path, direct=False)
    RetrievalIndexBuilder(data_root=data_root, repo_root=Path.cwd()).build()

    report = RetrievalIndexAuditor(data_root=data_root, repo_root=Path.cwd()).audit(require_direct_lookups=True)

    assert report.status == "blocked"
    assert "required_lookup_empty" in report.blockers


def test_audit_retrieval_indexes_cli_and_harness_plan_wire_direct_lookup_gate(tmp_path: Path) -> None:
    data_root = _parsed_data_root(tmp_path)
    RetrievalIndexBuilder(data_root=data_root, repo_root=Path.cwd()).build()
    result = subprocess.run(
        [
            sys.executable,
            "scripts/audit-retrieval-indexes.py",
            "--data-root",
            str(data_root),
            "--require-direct-lookups",
        ],
        text=True,
        capture_output=True,
        timeout=45,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "pass"

    plan = subprocess.run(
        [
            sys.executable,
            "scripts/run-authority-data-product.py",
            "--data-root",
            str(tmp_path / "external_plan_data"),
            "--plan-only",
            "--require-direct-authority",
        ],
        text=True,
        capture_output=True,
        timeout=45,
        check=False,
    )
    assert plan.returncode == 0, plan.stderr + plan.stdout
    plan_payload = json.loads(plan.stdout)
    audit_steps = [step for step in plan_payload["steps"] if step["name"] == "audit_retrieval_indexes"]
    assert audit_steps
    assert "--require-direct-lookups" in audit_steps[0]["command"]
