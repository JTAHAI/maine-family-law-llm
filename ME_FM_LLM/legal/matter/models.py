from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from legal.data_boundaries.retention import retention_policy_for


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _matter_retention_id() -> str:
    return retention_policy_for("user_provided_confidential_matter_data").retain


@dataclass(frozen=True)
class DocumentClassification:
    document_type: str
    confidence: float
    privilege_flags: list[str] = field(default_factory=list)
    confidentiality_flags: list[str] = field(default_factory=list)
    sealed_record_warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Matter:
    matter_id: str
    jurisdiction: str = "maine"
    title: str = "Untitled matter"
    tenant_id: str = "tenant_unassigned"
    owner_user_id: str | None = None
    created_at: str = field(default_factory=_now)
    data_class: str = "user_provided_confidential_matter_data"
    retention_policy_id: str = field(default_factory=_matter_retention_id)
    training_allowed: bool = False
    private_data_allowed_for_training: bool = False
    review_required: bool = True
    audit_history: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class MatterDocument:
    document_id: str
    matter_id: str
    filename: str
    sha256: str
    text: str
    redacted_text: str
    classification: DocumentClassification
    tenant_id: str = "tenant_unassigned"
    source_class: str = "user_provided_confidential_matter_data"
    jurisdiction: str = "maine"
    parser_status: str = "parsed_text"
    freshness_status: str = "user_provided_not_authority"
    data_class: str = "user_provided_confidential_matter_data"
    retention_policy_id: str = field(default_factory=_matter_retention_id)
    retention_action: str = "delete_source_file_derived_text_embeddings_and_private_work_product"
    pii_findings: list[str] = field(default_factory=list)
    redaction_count: int = 0
    extracted_text_status: str = "provided_text"
    storage_encryption_status: str = "not_persisted"
    use_restrictions: list[str] = field(default_factory=lambda: [
        "matter_only",
        "not_for_shared_training",
        "not_official_authority",
    ])
    private_data_allowed_for_training: bool = False
    audit_history: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=_now)


@dataclass(frozen=True)
class ExtractedFact:
    fact_id: str
    document_id: str
    text: str
    confidence: float
    date: str | None = None
    issue_labels: list[str] = field(default_factory=list)
    evidence_span: tuple[int, int] | None = None


@dataclass(frozen=True)
class MatterEvent:
    event_id: str
    matter_id: str
    date: str
    description: str
    source_document_id: str | None = None
    confidence: float = 0.5


@dataclass(frozen=True)
class IntakeReport:
    matter: Matter
    documents: list[MatterDocument]
    issue_labels: list[str]
    procedural_posture: str
    red_flags: list[str]
    timeline: list[dict[str, Any]]
    evidence_map: list[dict[str, Any]]
    missing_record_checklist: list[str]
    warnings: list[str]
    review_required: bool = True
    legal_readiness: str = "matter_ingestion_foundation_only_not_enterprise_ready"
