from __future__ import annotations

import json

from corpus_builder_support import build_fixture_case


def test_pdf_page_count_and_ocr_status_are_recorded(tmp_path) -> None:
    built = build_fixture_case(tmp_path)
    manifest = json.loads((built["case_root"] / "08_SOURCE_MANIFESTS_HASHES" / "source_manifest.json").read_text(encoding="utf-8"))
    pdf_row = next(row for row in manifest if row["source_type"] == "pdf")
    assert pdf_row["page_count"] == 1
    image_or_pdf_rows = [row for row in manifest if row["source_type"] in {"pdf", "image"}]
    assert all("ocr_status" in row for row in image_or_pdf_rows)
