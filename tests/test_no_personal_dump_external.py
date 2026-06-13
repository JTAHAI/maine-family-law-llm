from __future__ import annotations

import json

from corpus_builder_support import build_fixture_case


def test_external_release_excludes_unrelated_personal_material(tmp_path) -> None:
    built = build_fixture_case(tmp_path)
    search_index_text = (built["case_root"] / "04_INDEXES" / "search_index.jsonl").read_text(encoding="utf-8")
    assert "unrelated birthday planning" not in search_index_text.lower()
    assert "nonlegal chapter updates" not in search_index_text.lower()
    manifest = json.loads((built["case_root"] / "08_SOURCE_MANIFESTS_HASHES" / "source_manifest.json").read_text(encoding="utf-8"))
    personal_row = next(row for row in manifest if row["source_path"].endswith("unrelated_personal_newsletter.txt"))
    assert personal_row["external_release_allowed"] is False
    assert "personal_nonlegal" in personal_row["privacy_classes"]
