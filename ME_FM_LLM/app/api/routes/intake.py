from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter

from app.api.security import review_response
from legal.evidence.matter_work_product import MatterWorkProductBuilder
from legal.matter.document_ingestor import MatterDocumentIngestor
from legal.matter.models import Matter

router = APIRouter(tags=["intake"])


@router.post("/intake/matter", summary="Register a confidential legal matter")
def intake_matter(payload: dict):
    matter = Matter(
        matter_id=payload.get("matter_id", "matter_unassigned"),
        title=payload.get("title", "Untitled matter"),
        jurisdiction=payload.get("jurisdiction", "maine"),
        tenant_id=payload.get("tenant_id", "tenant_unassigned"),
        owner_user_id=payload.get("owner_user_id"),
    )
    return review_response(
        "POST /api/intake/matter",
        "matter_intake",
        {
            "matter": asdict(matter),
            "training_allowed": False,
            "private_data_allowed_for_training": False,
            "storage_requirement": "external_encrypted_matter_store_only",
        },
    )


@router.post("/intake/document", summary="Ingest a matter document")
def intake_document(payload: dict):
    ingestor = MatterDocumentIngestor()
    document = ingestor.ingest_document(
        matter_id=payload.get("matter_id", "matter_unassigned"),
        tenant_id=payload.get("tenant_id", "tenant_unassigned"),
        filename=payload.get("filename", "uploaded.txt"),
        text=payload.get("text", ""),
    )
    return review_response(
        "POST /api/intake/document",
        "matter_document_intake",
        {
            "document_id": document.document_id,
            "matter_id": document.matter_id,
            "tenant_id": document.tenant_id,
            "classification": asdict(document.classification),
            "source_class": document.source_class,
            "data_class": document.data_class,
            "retention_policy_id": document.retention_policy_id,
            "pii_findings": document.pii_findings,
            "private_data_allowed_for_training": document.private_data_allowed_for_training,
            "audit_history": document.audit_history,
        },
    )


@router.post("/intake/report", summary="Build intake work-product report")
def intake_report(payload: dict):
    ingestor = MatterDocumentIngestor()
    matter = Matter(
        matter_id=payload.get("matter_id", "matter_unassigned"),
        title=payload.get("title", "Untitled matter"),
        jurisdiction=payload.get("jurisdiction", "maine"),
        tenant_id=payload.get("tenant_id", "tenant_unassigned"),
        owner_user_id=payload.get("owner_user_id"),
    )
    documents = [
        ingestor.ingest_document(
            matter_id=matter.matter_id,
            tenant_id=matter.tenant_id,
            filename=row.get("filename", f"document_{index}.txt"),
            text=row.get("text", ""),
        )
        for index, row in enumerate(payload.get("documents", []), start=1)
    ]
    report = ingestor.build_intake_report(matter, documents)
    work_product = MatterWorkProductBuilder().build(report, authorities=payload.get("authorities", []))
    return review_response(
        "POST /api/intake/report",
        "intake_report",
        {
            "intake_report": ingestor.report_as_dict(report),
            "work_product": work_product.to_dict(),
        },
    )
