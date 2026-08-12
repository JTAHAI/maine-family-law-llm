from __future__ import annotations

import hashlib
import json
from pathlib import Path

from maine_family_law_llm import api
from maine_family_law_llm.intake_understanding import parse_intake
from maine_family_law_llm.local_corpus_index import (
    rebuild_local_content_index,
    search_local_content_index,
    summarize_local_search,
)
from maine_family_law_llm.search_normalization import (
    build_search_alias_text,
    normalize_search_query,
)


def _write_manifest(case_root: Path, paths: list[Path]) -> None:
    root = case_root / "08_SOURCE_MANIFESTS_HASHES"
    root.mkdir(parents=True)
    rows = []
    for index, path in enumerate(paths, start=1):
        data = path.read_bytes()
        rows.append(
            {
                "evidence_id": f"REC-{index}",
                "source_path": str(path),
                "source_hash": hashlib.sha256(data).hexdigest(),
                "source_type": path.suffix.lstrip("."),
            }
        )
    (root / "source_manifest.json").write_text(json.dumps(rows), encoding="utf-8")


def test_list_everything_contempt_related_routes_to_record_search() -> None:
    summary = parse_intake("show me a list of everything contempt-related")
    assert summary.task == "record_search"
    assert summary.search_target == "contempt"
    assert "post_judgment" in summary.issues


def test_hyphen_variants_share_canonical_terms() -> None:
    variants = (
        "post-judgment",
        "post judgment",
        "post\u2013judgment",
        "post\u2014judgment",
        "post\u2011judgment",
    )
    canonical = {normalize_search_query(value).canonical for value in variants}
    assert canonical == {"post judgment"}
    assert "interference" in build_search_alias_text("parental inter-\nference")
    assert "parent child" in build_search_alias_text("parent-child")


def test_search_finds_unicode_dash_and_ocr_line_break_hyphen(tmp_path: Path) -> None:
    first = tmp_path / "first.txt"
    first.write_text(
        "This is a post\u2013judgment filing concerning parent-child contact.",
        encoding="utf-8",
    )
    second = tmp_path / "second.txt"
    second.write_text(
        "The record describes parental inter-\nference with contact.",
        encoding="utf-8",
    )
    case_root = tmp_path / "case"
    _write_manifest(case_root, [first, second])
    assert rebuild_local_content_index(case_root)["result"] == "PASS"

    post_rows = search_local_content_index(case_root, "list all post-judgment records", limit=20)
    assert len(post_rows) == 1
    assert post_rows[0]["match_type"] == "exact_phrase"

    interference_rows = search_local_content_index(case_root, "show me interference records", limit=20)
    assert len(interference_rows) == 1
    assert interference_rows[0]["match_normalization"] == "hyphen_or_ocr_alias"
    assert "inter- ference" not in interference_rows[0]["snippet"].casefold()


def test_identical_record_copies_collapse_without_losing_copy_count(tmp_path: Path) -> None:
    content = "Motion to amend a motion for contempt."
    first = tmp_path / "motionToAmend2.txt"
    second = tmp_path / "motionToAmend2__04cb35ec.txt"
    first.write_text(content, encoding="utf-8")
    second.write_text(content, encoding="utf-8")
    case_root = tmp_path / "case"
    _write_manifest(case_root, [first, second])
    rebuild_local_content_index(case_root)

    rows = search_local_content_index(
        case_root,
        "show me a list of everything contempt-related",
        limit=40,
    )
    assert len(rows) == 1
    assert rows[0]["duplicate_copy_count"] == 2
    assert len(rows[0]["duplicate_source_ids"]) == 2
    summary = summarize_local_search("show me contempt records", rows)
    assert summary["document_count"] == 1
    assert summary["duplicate_copy_count_collapsed"] == 1


def test_record_card_grouping_uses_canonical_document_key(tmp_path: Path) -> None:
    citations = [
        {
            "source_id": "REC-1",
            "snippet": "contempt appears here",
            "metadata": {
                "source_locator": "motion.pdf",
                "source_type": "pdf",
                "canonical_document_key": "sha256:abc",
                "source_hash": "abc",
                "duplicate_copy_count": 2,
                "duplicate_basenames": ["motion.pdf", "motion-copy.pdf"],
            },
        },
        {
            "source_id": "REC-2",
            "snippet": "contempt appears here",
            "metadata": {
                "source_locator": "motion-copy.pdf",
                "source_type": "pdf",
                "canonical_document_key": "sha256:abc",
                "source_hash": "abc",
                "duplicate_copy_count": 2,
                "duplicate_basenames": ["motion.pdf", "motion-copy.pdf"],
            },
        },
    ]
    groups = api._group_record_cards(tmp_path, citations)
    assert len(groups) == 1
    assert groups[0]["duplicate_copy_count"] == 2


def test_in_chat_evidence_flyouts_remain_primary_and_show_grouping_badges() -> None:
    root = Path(__file__).resolve().parents[1]
    js = (root / "src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    for marker in (
        "data-inline-inspect-record",
        "data-inline-preview-source",
        "showSourcePreview(item, card, {pin: true})",
        "openRecordInspector(recordOpenBindingForPayload(item, payload)",
        "identical copies grouped",
        "hyphen/OCR match",
        "duplicate_copy_count_collapsed",
    ):
        assert marker in js
    assert "file://" not in js.casefold()
