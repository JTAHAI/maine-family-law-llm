from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from maine_family_law_llm.focaf_library import (
    audit_packaged_printables,
    get_printable,
    printable_pdf_path,
)
from maine_family_law_llm.local_corpus_index import local_ocr_choice
from maine_family_law_llm.version import PACKAGE_VERSION, VERSION


FAILING_PRINTABLE_ID = (
    "focaf-restoring-parent-child-relationships-after-disparagement-contact-refusal"
)


def test_version_is_store_compatible_v312() -> None:
    assert VERSION == "5.0.0"
    assert PACKAGE_VERSION == "5.0.0.0"


def test_all_bundled_printables_resolve_and_hash_match() -> None:
    audit = audit_packaged_printables(verify_hashes=True)
    assert audit["status"] == "pass", audit
    assert audit["expected"] == audit["resolved"]
    assert not audit["missing"]
    assert not audit["hash_mismatches"]


def test_exact_previously_broken_printable_opens() -> None:
    row = get_printable(FAILING_PRINTABLE_ID)
    assert row is not None
    path = printable_pdf_path(FAILING_PRINTABLE_ID, verify_hash=True)
    assert path is not None and path.is_file()
    assert path.read_bytes().startswith(b"%PDF")
    assert hashlib.sha256(path.read_bytes()).hexdigest().lower() == str(row["source_hash"]).lower()


def test_ocr_requires_explicit_choice(tmp_path: Path) -> None:
    index_root = tmp_path / "04_INDEXES"
    index_root.mkdir(parents=True)
    rows = [
        {
            "evidence_id": "scan-1",
            "source_locator": "scan.pdf",
            "source_hash": "abc",
            "page_count": 3,
            "ocr_status": "ocr_not_run",
        }
    ]
    (index_root / "private_search_index.json").write_text(
        json.dumps(rows), encoding="utf-8"
    )

    declined = local_ocr_choice(tmp_path, approved=False)
    assert declined["status"] == "declined"
    assert declined["candidate_pages"] == 3
    unchanged = json.loads(
        (index_root / "private_search_index.json").read_text(encoding="utf-8")
    )
    assert unchanged[0]["ocr_status"] == "ocr_not_run"


def test_ocr_ui_is_visible_and_explicit() -> None:
    ui_root = Path(__file__).resolve().parents[1] / "src" / "maine_family_law_llm" / "ui"
    html = (ui_root / "workbench.html").read_text(encoding="utf-8")
    js = (ui_root / "workbench.js").read_text(encoding="utf-8")

    assert 'id="ocr-action-button"' in html
    assert 'id="ocr-overlay"' in html
    assert "Some pages need local OCR" in html
    assert "Nothing is uploaded or transmitted" in html
    assert 'id="start-ocr-button"' in html
    assert 'id="decline-ocr-button"' in html
    assert "/api/corpus-ocr/start" in js
    assert "approved: true" in js
    assert "Cancel local OCR" in js


def test_source_card_followup_does_not_run_new_search() -> None:
    js_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "maine_family_law_llm"
        / "ui"
        / "workbench.js"
    )
    js = js_path.read_text(encoding="utf-8")
    assert "isSourceCardFollowUp" in js
    assert "No new corpus search was run" in js
    assert "I do not have a recent search result to open" in js
