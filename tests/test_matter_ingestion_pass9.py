from __future__ import annotations

import pytest

from legal.matter.document_ingestor import MatterDocumentIngestor
from legal.matter.matter_store import MatterStore, MatterStoreError
from legal.matter.models import Matter


def test_matter_document_ingestion_redacts_and_classifies_sensitive_content():
    document = MatterDocumentIngestor().ingest_document(
        matter_id="matter_001",
        filename="affidavit.txt",
        text=(
            "Affidavit of parent. On 2026-01-03 the minor child lived with Parent A. "
            "DOB: 1/2/2015. Contact me at parent@example.com. Child support is disputed."
        ),
    )

    assert document.source_class == "user_provided_confidential_matter_data"
    assert document.private_data_allowed_for_training is False
    assert document.classification.document_type == "affidavit"
    assert "sealed_or_sensitive_family_record" in document.classification.sealed_record_warnings
    assert "[REDACTED_DOB]" in document.redacted_text
    assert "[REDACTED_EMAIL]" in document.redacted_text


def test_intake_report_contains_issue_posture_timeline_evidence_and_missing_records():
    ingestor = MatterDocumentIngestor()
    matter = Matter(matter_id="matter_002", title="Custody and support")
    document = ingestor.ingest_document(
        matter_id=matter.matter_id,
        filename="motion_to_modify.txt",
        text=(
            "Motion to modify parental rights and responsibilities. "
            "On 01/03/2026 the child moved to a new school. "
            "Child support should be reviewed."
        ),
    )
    report = ingestor.build_intake_report(matter, [document])

    assert report.matter.training_allowed is False
    assert "child_support" in report.issue_labels
    assert report.procedural_posture == "motion_to_modify"
    assert report.timeline[0]["date"] == "01/03/2026"
    assert report.evidence_map
    assert any(item["support_status"] == "supported" for item in report.evidence_map)
    assert "financial_disclosure_or_child_support_worksheet_missing" in report.missing_record_checklist


def test_matter_store_refuses_repository_local_store(tmp_path):
    project_root = tmp_path / "repo"
    project_root.mkdir()
    with pytest.raises(MatterStoreError):
        MatterStore(project_root / "matter_store", project_root=project_root)


def test_matter_store_allows_external_store(tmp_path):
    project_root = tmp_path / "repo"
    external_root = tmp_path / "external" / "matter_store"
    project_root.mkdir()
    store = MatterStore(external_root, project_root=project_root)
    matter = Matter(matter_id="matter_003")
    matter_dir = store.create_matter(matter)
    assert matter_dir.exists()
    assert (matter_dir / "matter.json").exists()
