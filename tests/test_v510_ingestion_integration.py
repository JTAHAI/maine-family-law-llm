from __future__ import annotations

from legal.matter.document_ingestor import MatterDocumentIngestor
from legal.matter.models import Matter


def test_ingestion_surfaces_multi_labels_and_cross_document_conflicts() -> None:
    ingestor = MatterDocumentIngestor()
    first = ingestor.ingest_document(
        matter_id="matter-1",
        filename="school-hearing-email.txt",
        text="Email from the teacher. The hearing is scheduled for August 12, 2026.",
    )
    second = ingestor.ingest_document(
        matter_id="matter-1",
        filename="court-notice.txt",
        text="The hearing will occur on August 14, 2026. This is a court order notice.",
    )
    assert "school" in first.classification.labels
    assert "communication" in first.classification.labels
    report = ingestor.build_intake_report(Matter(matter_id="matter-1"), [first, second])
    assert report.document_labels[first.document_id]
    assert report.cross_document_conflicts[0]["context_key"] == "hearing_date"
    assert report.cross_document_conflicts[0]["review_required"] is True
