from __future__ import annotations

import json

import pytest

from legal.evidence.matter_work_product import MatterWorkProductBuilder
from legal.matter.document_ingestor import MatterDocumentIngestor
from legal.matter.matter_store import MatterStore, MatterStoreError
from legal.matter.models import Matter
from legal.security.authz import UserContext
from legal.security.tenant_isolation import MatterAccessPolicy, MatterReference


def test_pass35_secure_document_ingestion_adds_classification_retention_audit_and_training_block():
    document = MatterDocumentIngestor().ingest_document(
        matter_id="matter-secure-1",
        tenant_id="tenant-a",
        filename="affidavit.txt",
        text=(
            "Privileged affidavit about the minor child. DOB: 1/2/2015. "
            "On 01/03/2026 the child moved schools and child support is disputed."
        ),
    )

    assert document.tenant_id == "tenant-a"
    assert document.data_class == "user_provided_confidential_matter_data"
    assert document.private_data_allowed_for_training is False
    assert document.retention_policy_id == "matter_policy_defined"
    assert "date_of_birth" in document.pii_findings
    assert "juvenile_or_sensitive_family_marker" in document.pii_findings
    assert document.redaction_count >= 1
    assert document.audit_history
    assert {event["event_type"] for event in document.audit_history} >= {
        "document_received",
        "private_data_scanned",
        "training_policy_applied",
    }


def test_pass35_matter_store_encrypts_documents_and_keeps_plaintext_outside_repo(tmp_path):
    project_root = tmp_path / "repo"
    project_root.mkdir()
    external_root = tmp_path / "external" / "matter_store"
    store = MatterStore(
        external_root,
        project_root=project_root,
        encryption_key="unit-test-encryption-key",
    )
    matter = Matter(matter_id="matter-secure-2", tenant_id="tenant-a")
    store.create_matter(matter)
    document = MatterDocumentIngestor().ingest_document(
        matter_id=matter.matter_id,
        tenant_id=matter.tenant_id,
        filename="messages.txt",
        text="On 01/03/2026 Parent A sent a message about contact with the child.",
    )

    encrypted_path = store.store_document(document)
    assert encrypted_path.suffix == ".enc"
    encrypted_text = encrypted_path.read_text(encoding="utf-8")
    assert "Parent A sent" not in encrypted_text
    assert "contact with the child" not in encrypted_text
    envelope = json.loads(encrypted_text)
    assert envelope["algorithm"].startswith("local-pbkdf2")
    loaded = store.load_document(encrypted_path)
    assert loaded["document_id"] == document.document_id
    assert loaded["storage_encryption_status"] == "encrypted_local_envelope"
    manifest = encrypted_path.parent / "documents_manifest.jsonl"
    assert manifest.exists()
    assert "private_data_allowed_for_training" in manifest.read_text(encoding="utf-8")


def test_pass35_matter_store_refuses_any_repo_local_external_store(tmp_path):
    project_root = tmp_path / "repo"
    project_root.mkdir()
    with pytest.raises(MatterStoreError):
        MatterStore(project_root / "runtime" / "matter_store", project_root=project_root)


def test_pass35_tenant_matter_isolation_blocks_cross_tenant_access():
    policy = MatterAccessPolicy()
    matter = MatterReference(matter_id="matter-1", tenant_id="tenant-a")
    allowed = UserContext(
        user_id="u1",
        tenant_id="tenant-a",
        roles=["attorney"],
        matter_ids=["matter-1"],
    )
    cross_tenant = UserContext(
        user_id="u2",
        tenant_id="tenant-b",
        roles=["attorney"],
        matter_ids=["matter-1"],
    )
    assert policy.can_access(allowed, matter, "matter:read") is True
    assert policy.can_access(cross_tenant, matter, "matter:read") is False


def test_pass36_work_product_has_issue_tree_timeline_spans_evidence_map_missing_records_and_authority_matrix():
    ingestor = MatterDocumentIngestor()
    matter = Matter(matter_id="matter-evidence-1", tenant_id="tenant-a", title="Modification")
    motion = ingestor.ingest_document(
        matter_id=matter.matter_id,
        tenant_id=matter.tenant_id,
        filename="motion_to_modify.txt",
        text=(
            "Motion to modify parental rights and responsibilities. "
            "On 01/03/2026 the child moved to a new school. "
            "Child support should be reviewed."
        ),
    )
    report = ingestor.build_intake_report(matter, [motion])
    work_product = MatterWorkProductBuilder().build(
        report,
        authorities=[
            {
                "source_id": "statute-19a-1653",
                "citation": "19-A M.R.S. § 1653",
                "title": "Parental rights and responsibilities",
                "source_class": "statute_section_reference",
                "jurisdiction": "maine",
                "authority_status": "verified_official_maine",
                "freshness_status": "fresh",
                "issue_labels": ["parental_rights_responsibilities", "child_support"],
            }
        ],
    ).to_dict()

    assert "child_support" in work_product["issue_tree"]["labels"]
    assert work_product["procedural_posture_summary"]["procedural_posture"] == "motion_to_modify"
    assert work_product["timeline"][0]["source_document_id"] == motion.document_id
    assert work_product["timeline"][0]["span_start"] is not None
    first_mapping = work_product["evidence_map"][0]
    assert first_mapping["support_status"] == "supported"
    assert first_mapping["supporting_evidence"][0]["source_document_id"] == motion.document_id
    assert first_mapping["supporting_evidence"][0]["span_start"] is not None
    assert work_product["exhibit_index"][0]["document_id"] == motion.document_id
    assert work_product["authority_matrix"][0]["citation"] == "19-A M.R.S. § 1653"
    assert "financial_disclosure_or_child_support_worksheet_missing" in work_product["missing_record_checklist"]
    assert "underlying_order_missing" in work_product["missing_record_checklist"]
    assert work_product["export_status"] == "review_required"
