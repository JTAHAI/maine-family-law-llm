from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from maine_family_law_llm.local_corpus_index import (
    public_record_view,
    rebuild_local_content_index,
    search_local_content_index,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_manifest(case_root: Path, source_paths: list[Path]) -> None:
    rows = [
        {
            "evidence_id": f"EV-TEST-{index:03d}",
            "source_path": str(path),
            "source_hash": _sha256(path),
            "source_type": "email" if path.suffix == ".eml" else "archive",
            "issue_lanes": ["record_review"],
            "privacy_status": "private",
            "text_excerpt": "",
        }
        for index, path in enumerate(source_paths, start=1)
    ]
    manifest = case_root / "08_SOURCE_MANIFESTS_HASHES" / "source_manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(rows), encoding="utf-8")


def test_private_index_recursively_extracts_email_attachments_and_zip_members(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    source_root.mkdir()
    email_path = source_root / "school_update.eml"
    email_path.write_bytes(
        b"From: school@example.test\nTo: parent@example.test\nSubject: Attendance update\nMIME-Version: 1.0\nContent-Type: multipart/mixed; boundary=part\n\n--part\nContent-Type: text/plain\n\nThe attendance meeting is Friday.\n--part\nContent-Type: text/plain; name=attachment.txt\nContent-Disposition: attachment; filename=attachment.txt\nContent-Transfer-Encoding: base64\n\nQ2hpbGQgc3VwcG9ydCBkb2N1bWVudCBmb3IgcmV2aWV3Lg==\n--part--\n"
    )
    archive_path = source_root / "records.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("court/notice.txt", "The scheduling conference was continued.")

    case_root = tmp_path / "case"
    _write_manifest(case_root, [email_path, archive_path])
    before = {_path: _sha256(_path) for _path in (email_path, archive_path)}

    proof = rebuild_local_content_index(case_root)
    matches = search_local_content_index(case_root, "scheduling conference")

    assert proof["result"] == "PASS"
    assert proof["source_evidence_modified"] is False
    assert proof["attachment_or_archive_children"] >= 2
    assert any("notice.txt" in row["source_locator"] for row in matches)
    assert before == {_path: _sha256(_path) for _path in (email_path, archive_path)}


def test_private_index_produces_inventory_and_redacted_source_cards(tmp_path: Path) -> None:
    source = tmp_path / "private_note.txt"
    source.write_text("Parenting plan exchange and school attendance records.", encoding="utf-8")
    case_root = tmp_path / "case"
    _write_manifest(case_root, [source])

    proof = rebuild_local_content_index(case_root)
    records = json.loads((case_root / "04_INDEXES" / "private_search_index.json").read_text(encoding="utf-8"))
    view = public_record_view(records[0])

    assert proof["records_indexed"] == 1
    assert (case_root / "04_INDEXES" / "FULL_LOCAL_INVENTORY.jsonl").exists()
    assert (case_root / "04_INDEXES" / "FULL_LOCAL_INVENTORY.csv").exists()
    assert (case_root / "04_INDEXES" / "private_content_index.sqlite").exists()
    assert view["source_locator"] == "private_note.txt"
    assert "source_path" not in view
    assert str(tmp_path) not in json.dumps(view)
