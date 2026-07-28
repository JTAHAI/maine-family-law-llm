from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DocumentClassification:
    document_type: str
    confidence: float = 0.0
    privilege_flags: list[str] = field(default_factory=list)
    confidentiality_flags: list[str] = field(default_factory=list)
    sealed_record_warnings: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    label_confidence: dict[str, float] = field(default_factory=dict)
    classification_status: str = "unclassified"
    review_reasons: list[str] = field(default_factory=list)


@dataclass
class Matter:
    matter_id: str
    title: str = "Untitled matter"
    tenant_id: str = "tenant_unassigned"
    jurisdiction: str = "maine"
    training_allowed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
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
    data_class: str = "user_provided_confidential_matter_data"
    private_data_allowed_for_training: bool = False
    parser_status: str = "parsed_text"
    retention_policy_id: str = "matter_policy_defined"
    retention_action: str = "matter_policy_defined"
    pii_findings: list[str] = field(default_factory=list)
    redaction_count: int = 0
    extracted_text_status: str = "provided_text"
    audit_history: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedFact:
    fact_id: str
    document_id: str
    text: str
    confidence: float = 0.0
    date: str | None = None
    issue_labels: list[str] = field(default_factory=list)
    evidence_span: tuple[int, int] | None = None


@dataclass
class MatterEvent:
    event_id: str
    matter_id: str
    date: str
    description: str
    source_document_id: str | None = None
    span_start: int | None = None
    span_end: int | None = None
    confidence: float = 0.0


@dataclass
class IntakeReport:
    matter: Matter
    documents: list[MatterDocument]
    issue_labels: list[str] = field(default_factory=list)
    procedural_posture: str = "unknown"
    red_flags: list[str] = field(default_factory=list)
    timeline: list[dict[str, Any]] = field(default_factory=list)
    evidence_map: list[dict[str, Any]] = field(default_factory=list)
    missing_record_checklist: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    document_labels: dict[str, list[str]] = field(default_factory=dict)
    cross_document_conflicts: list[dict[str, Any]] = field(default_factory=list)
