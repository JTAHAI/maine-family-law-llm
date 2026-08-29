from __future__ import annotations

import json
from pathlib import Path

from legal.authority_store import ParsedAuthorityStoreBuilder
from legal.authority_store import parsed_store as parsed_store_module


def _write_manifest(data_root: Path, records: list[dict]) -> None:
    official = data_root / "official_authority_store"
    official.mkdir(parents=True, exist_ok=True)
    (official / "source_manifest.json").write_text(json.dumps(records), encoding="utf-8")


def _record(data_root: Path, *, source_id: str, source_class: str, url: str, parser_name: str) -> dict:
    snapshot = data_root / "official_authority_store" / f"{source_id}.pdf"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_bytes(b"%PDF-1.4 fixture")
    return {
        "source_id": source_id,
        "source_class": source_class,
        "jurisdiction": "maine",
        "hash": f"hash-{source_id}",
        "snapshot_path": str(snapshot),
        "source_url_or_path": url,
        "retrieved_at": "2026-05-31T00:00:00+00:00",
        "freshness_status": "retrieved_timestamp_known",
        "parser_status": "parsed",
        "parser_audit": {"parser_name": parser_name, "metadata": {}},
    }


def test_form_pdf_builder_falls_back_to_official_url_form_identifier(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "external"
    record = _record(
        data_root,
        source_id="court-form-pdf-aa",
        source_class="court_form_pdf",
        url="https://www.courts.maine.gov/forms/fm-088.pdf",
        parser_name="maine_form_pdf",
    )
    _write_manifest(data_root, [record])
    monkeypatch.setattr(
        parsed_store_module,
        "extract_pdf_text",
        lambda _content: "Motion to Modify Parental Rights and Responsibilities",
    )

    report = ParsedAuthorityStoreBuilder(data_root=data_root).build()
    rows = (data_root / "parsed_authority_store" / "forms" / "forms.jsonl").read_text(encoding="utf-8").splitlines()
    parsed = json.loads(rows[0])

    assert report.status == "pass"
    assert parsed["form_id"] == "FM-088"
    assert parsed["form_id_source"] == "source_url"
    assert parsed["text"]


def test_builder_excludes_explicitly_quarantined_source_before_parsing(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "external"
    record = _record(
        data_root,
        source_id="court-form-pdf-quarantined",
        source_class="court_form_pdf",
        url="https://www.courts.maine.gov/forms/fm-088.pdf",
        parser_name="maine_form_pdf",
    )
    record["metadata"] = {"retrieval_admission": "quarantined"}
    _write_manifest(data_root, [record])
    monkeypatch.setattr(parsed_store_module, "extract_pdf_text", lambda _content: (_ for _ in ()).throw(AssertionError("must not parse quarantined source")))

    report = ParsedAuthorityStoreBuilder(data_root=data_root).build()

    assert report.status == "blocked"
    assert any(finding.code == "source_quarantined_from_retrieval" for finding in report.findings)


def test_opinion_pdf_builder_quarantines_empty_text_without_failing_build(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "external"
    empty = _record(
        data_root,
        source_id="law-court-opinion-pdf-empty",
        source_class="law_court_opinion_pdf",
        url="https://www.courts.maine.gov/courts/sjc/lawcourt/2020/20me001.pdf",
        parser_name="maine_law_court_opinion_pdf",
    )
    good = _record(
        data_root,
        source_id="law-court-opinion-pdf-good",
        source_class="law_court_opinion_pdf",
        url="https://www.courts.maine.gov/courts/sjc/lawcourt/2020/20me002.pdf",
        parser_name="maine_law_court_opinion_pdf",
    )
    _write_manifest(data_root, [empty, good])

    def fake_extract(content: bytes) -> str:
        return "" if content == b"%PDF-1.4 fixture" else "unused"

    # Use snapshot filenames to make one record empty and one valid while still avoiding real PDF parsing.
    empty_path = Path(empty["snapshot_path"])
    good_path = Path(good["snapshot_path"])
    empty_path.write_bytes(b"empty")
    good_path.write_bytes(b"good")
    monkeypatch.setattr(
        parsed_store_module,
        "extract_pdf_text",
        lambda content: "" if content == b"empty" else "MAINE SUPREME JUDICIAL COURT Decision: 2020 ME 2 Decided: January 1, 2020 Full text.",
    )

    report = ParsedAuthorityStoreBuilder(data_root=data_root).build()
    rows = (data_root / "parsed_authority_store" / "opinions" / "opinions.jsonl").read_text(encoding="utf-8").splitlines()

    assert report.status == "pass"
    assert len(rows) == 1
    assert json.loads(rows[0])["citation"] == "2020 ME 2"
    assert any(finding.code == "direct_authority_row_quarantined" for finding in report.findings)


def test_form_text_builder_falls_back_to_official_url_slug_when_form_id_absent(tmp_path: Path) -> None:
    data_root = tmp_path / "external"
    official = data_root / "official_authority_store"
    official.mkdir(parents=True, exist_ok=True)
    snapshot = official / "court-form-text-aa.html"
    snapshot.write_text(
        "Maine Judicial Branch family matter packet instructions. Use this official court form packet.",
        encoding="utf-8",
    )
    record = {
        "source_id": "court-form-text-aa",
        "source_class": "court_form_text",
        "jurisdiction": "maine",
        "hash": "hash-form-text-aa",
        "snapshot_path": str(snapshot),
        "source_url_or_path": "https://www.courts.maine.gov/forms/family-matter-packet.html",
        "retrieved_at": "2026-05-31T00:00:00+00:00",
        "freshness_status": "retrieved_timestamp_known",
        "parser_status": "parsed",
        "parser_audit": {"parser_name": "maine_form_text", "metadata": {}},
    }
    _write_manifest(data_root, [record])

    report = ParsedAuthorityStoreBuilder(data_root=data_root).build()
    rows = (data_root / "parsed_authority_store" / "forms" / "forms.jsonl").read_text(encoding="utf-8").splitlines()
    parsed = json.loads(rows[0])

    assert report.status == "pass"
    assert parsed["form_id"] == "OFFICIAL-FORM-FAMILY-MATTER-PACKET"
    assert parsed["form_id_source"] == "source_url_filename_fallback"
    assert parsed["citation"] == parsed["form_id"]
    assert parsed["text"]
