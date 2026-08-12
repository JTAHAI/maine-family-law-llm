from __future__ import annotations

from pathlib import Path


from legal.matter.document_inventory import scan_matter_folder
from legal.matter.multi_label_classifier import MultiLabelMatterClassifier


def test_inventory_is_read_only_hashes_and_blocks_symlinks(tmp_path: Path) -> None:
    matter = tmp_path / "matter"
    matter.mkdir()
    order = matter / "Temporary Order.txt"
    order.write_text("The court ordered a contact schedule.", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("private", encoding="utf-8")
    link = matter / "outside-link.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        link = None

    before = order.read_bytes()
    report = scan_matter_folder(matter, hash_files=True)
    assert order.read_bytes() == before
    assert len(report.files) == 1
    assert report.files[0].sha256 is not None
    if link is not None:
        assert any(item.reason == "symlink_not_followed" for item in report.blocked)


def test_many_to_many_classification() -> None:
    classifier = MultiLabelMatterClassifier()
    result = classifier.classify(
        relative_path="Exhibit - School Email and Contact Schedule.pdf",
        text_excerpt=(
            "Email from the teacher regarding school attendance and the parental rights "
            "contact schedule. Attached as an exhibit."
        ),
    )
    labels = {item.label for item in result.labels}
    assert {"school", "communication", "parental_rights", "evidence"} <= labels
    assert result.status in {"classified", "review_required"}


def test_unreadable_unknown_document_is_review_required() -> None:
    result = MultiLabelMatterClassifier().classify(
        relative_path="scan0001.pdf", text_excerpt="", readable=False
    )
    assert result.status == "unclassified"
    assert "content_unreadable_or_not_extracted" in result.review_reasons
