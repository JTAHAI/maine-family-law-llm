from __future__ import annotations

import json
from pathlib import Path

import pytest

from legal.knowledge_bundle import (
    KnowledgeBundleError,
    KnowledgeConcept,
    build_bundle,
    parse_concept_id,
    read_concept,
    validate_bundle,
)


def test_knowledge_bundle_round_trip_and_hash_validation(tmp_path: Path) -> None:
    concept = KnowledgeConcept(
        concept_id="statutes/title19a-1653",
        type="Maine Statute",
        title="Best interest of child",
        description="Source card metadata for a Maine statute section.",
        resource="https://legislature.maine.gov/statutes/19-a/title19-Asec1653.html",
        tags=("best-interest", "parental-rights"),
        citations=("19-A M.R.S. § 1653",),
        body="# Review status\n\nOfficial-source verification required.",
        metadata={"jurisdiction": "maine", "review_required": True},
    )
    report = build_bundle(tmp_path, [concept])
    assert report.status == "pass"
    loaded = read_concept(tmp_path, tmp_path / "statutes" / "title19a-1653.md")
    assert loaded.title == concept.title
    assert loaded.metadata["jurisdiction"] == "maine"

    path = tmp_path / "statutes" / "title19a-1653.md"
    path.write_text(path.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    assert validate_bundle(tmp_path).status == "fail"


def test_knowledge_bundle_rejects_path_traversal() -> None:
    with pytest.raises(KnowledgeBundleError):
        parse_concept_id("../secrets")


def test_frontmatter_does_not_accept_object_deserialization(tmp_path: Path) -> None:
    root = tmp_path
    path = root / "bad.md"
    path.write_text(
        "---\ntype: \"Test\"\ntitle: \"Bad\"\npayload: {\"unsafe\": true}\n---\nbody\n",
        encoding="utf-8",
    )
    report = validate_bundle(root)
    assert report.status == "fail"
    assert any("unsupported frontmatter" in error for error in report.errors)


def test_dotted_concept_ids_round_trip_without_collision(tmp_path: Path) -> None:
    concept = KnowledgeConcept(
        concept_id="cases/2026.me.10",
        type="Maine Case",
        title="Example",
        body="Review required.",
    )
    assert build_bundle(tmp_path, [concept]).status == "pass"
    path = tmp_path / "cases" / "2026.me.10.md"
    assert path.is_file()
    assert read_concept(tmp_path, path).concept_id == "cases/2026.me.10"


def test_untracked_concept_files_fail_validation(tmp_path: Path) -> None:
    concept = KnowledgeConcept(
        concept_id="rules/rule52",
        type="Rule",
        title="Rule 52",
        body="Review required.",
    )
    assert build_bundle(tmp_path, [concept]).status == "pass"
    (tmp_path / "extra.md").write_text(
        '---\ntype: "Other"\ntitle: "Untracked"\n---\nbody\n', encoding="utf-8"
    )
    report = validate_bundle(tmp_path)
    assert report.status == "fail"
    assert any("missing from manifest" in error for error in report.errors)


def test_symlink_concepts_are_rejected(tmp_path: Path) -> None:
    target = tmp_path / "outside.md"
    target.write_text('---\ntype: "Other"\ntitle: "Outside"\n---\nbody\n', encoding="utf-8")
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    try:
        (bundle / "linked.md").symlink_to(target)
    except OSError:
        pytest.skip("symlinks are unavailable")
    (bundle / "manifest.json").write_text(
        json.dumps({"schema": "mfl_knowledge_bundle_v1", "concepts": []}), encoding="utf-8"
    )
    report = validate_bundle(bundle)
    assert report.status == "fail"
    assert any("symlink" in error for error in report.errors)
