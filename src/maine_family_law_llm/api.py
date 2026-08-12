"""Local-only FastAPI backend for the Maine Family Law LLM workbench."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import mimetypes
import os
import re
import secrets
import threading
import time
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath
from difflib import SequenceMatcher
from email import policy
from email.parser import BytesParser
from typing import Any, Iterable

from legal.product.family_justice_workbench_v205 import build_workbench_packet
from legal.drafting.findings_engine import Rule52BestInterestFindingsEngine
from app.services import AuthorityLibraryService, AuthorityProductService
from legal.security.prompt_injection import PromptInjectionScanner
from legal.security.local_request_firewall import DEFAULT_MAX_BODY_BYTES, evaluate_local_request
from legal.agent_runtime import (
    LocalAgentRunRequest,
    LocalAgentRuntime,
    LocalModelError,
    ToolInvocation,
    build_local_client,
)
from legal.local_workbench import LocalWorkbenchError, LocalWorkbenchService
from legal.document_intelligence import (
    DocumentIntelligenceError,
    analyze_document,
    create_ocr_preservation_copy,
    create_redacted_copy,
    document_intelligence_status,
)
from legal.evidence import (
    EvidenceReviewStore,
    EvidenceWorkProductError,
    EvidenceWorkProductStore,
    MatterCommandCenterError,
    MatterCommandCenterStore,
)
from legal.matter.intake_workbench import IntakeWorkbenchError, MatterIntakeStore
from legal.matter.order_intelligence import OrderIntelligenceStore
from legal.matter.calendar_review import CalendarReviewStore
from legal.matter.docket_reconciliation import DocketReconciliationStore
from legal.matter.discovery_workbench import DiscoveryWorkbenchStore
from legal.matter.exhibit_workbench import ExhibitWorkbenchStore
from legal.matter.witness_statements import WitnessStatementStore
from legal.matter.hearing_preparation import HearingPreparationStore
from legal.matter.appellate_review import AppellateReviewStore
from legal.matter.uccjea_review import UccjeaReviewStore
from legal.matter.icwa_review import IcwaReviewStore
from legal.matter.care_pathways import CarePathwayStore
from legal.matter.safety_review import SafetyReviewStore
from legal.matter.parenting_schedule import ParentingScheduleStore
from legal.matter.negotiation_matrix import NegotiationMatrixStore
from legal.matter.property_valuation import PropertyValuationStore
from legal.matter.modification_review import ModificationReviewStore
from legal.matter.foaa_requests import FoaaRequestStore
from legal.matter.filing_readiness import FilingReadinessStore
from legal.matter.image_evidence_review import ImageEvidenceStore
from legal.matter.email_integrity import EmailIntegrityStore
from legal.matter.reviewer_handoff import ReviewerHandoffStore
from legal.matter.language_access import LanguageAccessStore
from legal.matter.resource_navigator import ResourceNavigatorStore
from legal.matter.golden_path import MatterJourneyStore
from legal.forms import MaineFindingsFormsError, MaineFindingsFormsStore
from legal.retrieval.workbench import RetrievalWorkbenchError, RetrievalWorkbenchService
from legal.ops.release_pilot_hardening import (
    AttorneySandboxStore,
    MatterBackupRestoreDrill,
    PrivacySafeObservabilityStore,
    ReleaseEvidenceAuditor,
    ReleasePilotHardeningError,
    ReleasePilotHardeningService,
    find_source_root,
)
from legal.pilot.sandbox_operations import (
    AttorneySandboxOperationsError,
    AttorneySandboxOperationsStore,
)
from legal.pilot.real_matter_operations import (
    LimitedRealMatterPilotError,
    LimitedRealMatterPilotOperationsStore,
)
from legal.release.release_candidate_operations import (
    GAReleaseCandidateError,
    GAReleaseCandidateOperationsStore,
)
from legal.release.shipment_readiness_operations import (
    GAShipmentReadinessError,
    GAShipmentReadinessStore,
)
from legal.documents.docx_engine import (
    create_docx_from_text,
    engine_status as docx_engine_status,
    list_docx_paragraphs,
    tracked_edit_copy,
)
from legal.review import (
    AuthorityChangeImpactStore,
    AuthorityImpactError,
    ReviewLedgerError,
    ReviewedFilingPacketError,
    ReviewedFilingPacketStore,
    build_incremental_review_diff,
    build_reviewer_queue,
    commit_review_decision,
    list_review_history,
    prepare_review_request,
    verify_review_ledger,
)
from legal.documents.workspace import (
    DocumentWorkspaceError,
    commit_revision as commit_workspace_revision,
    commit_soft_delete,
    create_document as create_workspace_document,
    export_text_artifact,
    find_preserved_source,
    get_document as get_workspace_document,
    list_documents as list_workspace_documents,
    propose_revision as propose_workspace_revision,
    record_artifact_event,
    reject_revision as reject_workspace_revision,
    request_soft_delete,
    restore_document as restore_workspace_document,
    save_imported_source,
    verify_audit_chain,
    workspace_paths,
    workspace_status,
)

from . import __version__
from .answer import compose_answer
from .case_corpus_builder import answer_case_question, load_case_search_records
from .case_library import (
    active_case_root,
    describe_case_root,
    list_registered_case_roots,
    set_active_case_root,
)
from .chat_library import (
    expand_query_for_library,
    public_library,
    public_missing_information_prompts,
    public_prompt_packs,
    public_topics,
)
from .draft import ALLOWED_DRAFT_MODES, draft_from_sources
from .family_answer_contract import build_family_answer_contract, render_legacy_answer
from .grounding_integrity import annotate_grounding_metadata, assess_grounding_integrity
from .answer_support_integrity import assess_answer_support_integrity
from .handoff_integrity import build_handoff_safe_source_cards
from .input_integrity import harden_text_input, normalize_search_id, normalize_session_id
from .focaf_library import (
    PrintableAssetError,
    audit_packaged_printables,
    get_printable,
    printable_pdf_path,
    public_printable_view,
    search_printables,
    suggest_printables,
)
from .local_corpus_index import (
    INDEX_NAME,
    INVENTORY_CSV,
    INVENTORY_JSONL,
    is_direct_content_search,
    local_ocr_choice,
    local_ocr_engine_status,
    local_inventory_metrics,
    _candidate_bytes,
    parse_bytes,
    public_record_view,
    rebuild_local_content_index,
    run_local_ocr,
)
from .intake_understanding import (
    MAX_INTAKE_CHARS,
    IntakeSummary,
    concise_intake_label,
    parse_intake,
)
from .local_workbench_ui import render_local_workbench_html, ui_asset_root
from .ocr_prerequisites import install_local_ocr_prerequisites, ocr_prerequisite_status
from .safety import classify_prompt
from .sources import get_source, load_seed_manifest
from .retrieve import RetrievalResponse, SearchResult
from .workbench import retrieve_fixture_sources
from .version import UI_VERSION
from .runtime_resilience import runtime_health_snapshot
from .runtime_kernel import ACTIVE_STATUSES, get_runtime_kernel
from .local_agent_bridge import (
    build_host_context_and_receipt,
    context_sources_from_cards,
    source_cards_from_payload,
)

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from starlette.requests import ClientDisconnect
    from pydantic import BaseModel, Field, StrictBool
except Exception:  # pragma: no cover - lets CLI import without API extras
    FastAPI = None  # type: ignore[assignment]
    HTTPException = Exception  # type: ignore[assignment]
    HTMLResponse = None  # type: ignore[assignment]
    JSONResponse = None  # type: ignore[assignment]
    FileResponse = None  # type: ignore[assignment]
    StaticFiles = None  # type: ignore[assignment]
    Request = object  # type: ignore[assignment]

    class ClientDisconnect(Exception):
        pass

    class BaseModel:  # type: ignore[no-redef]
        pass

    StrictBool = bool  # type: ignore[assignment,misc]

    def Field(default: Any = None, *, default_factory: Any = None, **_: Any) -> Any:  # type: ignore[no-redef]
        return default_factory() if default_factory is not None else default


class QueryRequest(BaseModel):
    query: str
    limit: int = 5


class AskRequest(BaseModel):
    question: str
    answer_style: str = "plain_language"
    matter_context: str = ""
    search_mode: str = "maine_law"
    child_impact_lens: StrictBool = False
    session_id: str = ""
    last_search_id: str = ""
    input_integrity: dict[str, Any] | None = None


class DraftRequest(BaseModel):
    request: str
    mode: str = "checklist"


class AuthorityVerifyAnswerRequest(BaseModel):
    text: str
    source_ids: list[str] = Field(default_factory=list)
    quotes: list[dict[str, Any]] = Field(default_factory=list)
    claims: list[dict[str, Any] | str] = Field(default_factory=list)
    expected_jurisdiction: str = "maine"
    auto_extract_claims: StrictBool = True


class FamilyJusticeWorkbenchRequest(BaseModel):
    question: str
    audience: str = "parent"
    posture: str = "unknown"
    facts_context: str = ""
    requested_output_style: str = "plain_language"


class ActivateCorpusRequest(BaseModel):
    case_id: str = ""
    case_root: str = ""  # Compatibility only; the UI uses opaque IDs.


class LocalOcrRequest(BaseModel):
    approved: StrictBool = False
    language: str = "eng"


class InstallOcrPrerequisitesRequest(BaseModel):
    approved: StrictBool = False


class DocumentIntelligenceAnalyzeRequest(BaseModel):
    source_token: str
    approved: StrictBool = False
    run_docling: StrictBool = True
    run_presidio: StrictBool = True


class DocumentIntelligenceOcrRequest(BaseModel):
    source_token: str
    approved: StrictBool = False
    language: str = "eng"


class DocumentIntelligencePrivacyScanRequest(BaseModel):
    source_token: str
    approved: StrictBool = False
    run_presidio: StrictBool = True


class DocumentIntelligenceRedactionRequest(BaseModel):
    source_token: str
    approved: StrictBool = False
    reviewer: str = "local_operator"
    run_presidio: StrictBool = True


class RecordCompareRequest(BaseModel):
    left_record_id: str
    right_record_id: str


class EvidenceWorkProductBuildRequest(BaseModel):
    selected_evidence_ids: list[str] = Field(default_factory=list)
    focus_terms: list[str] = Field(default_factory=list)
    include_all_records: StrictBool = True
    approved: StrictBool = False


class MatterCommandCenterSnapshotRequest(BaseModel):
    selected_record_ids: list[str] = Field(default_factory=list)
    variant: str = "metadata_only"
    approved: StrictBool = False
    note: str = ""


class MatterCommandCenterPacketRequest(BaseModel):
    selected_record_ids: list[str] = Field(default_factory=list)
    snapshot_id: str = ""
    variant: str = "metadata_only"
    approved: StrictBool = False
    note: str = ""


class MatterCommandCenterPacketReviewRequest(BaseModel):
    reviewer_name: str
    reviewer_role: str = "other_reviewer"
    review_status: str = "request_changes"
    note: str = ""
    approved: StrictBool = False


class MatterCommandCenterPacketCompareRequest(BaseModel):
    left_packet_id: str = ""
    right_packet_id: str = ""


class EvidenceTimelineBuildRequest(BaseModel):
    selected_record_ids: list[str] = Field(default_factory=list)
    issue_tags: list[str] = Field(default_factory=list)
    source_types: list[str] = Field(default_factory=list)
    allegation_observation_finding: list[str] = Field(default_factory=list)
    date_start: str = ""
    date_end: str = ""
    cancel_requested: StrictBool = False


class EvidenceTimelineEventCreateRequest(BaseModel):
    event_label: str
    classification: str = "observed"
    date_value: str = "unknown"
    date_range: dict[str, Any] = Field(default_factory=dict)
    date_precision: str = "unknown"
    date_type: str = "unknown/other"
    source_record_id: str = ""
    source_block: dict[str, Any] = Field(default_factory=dict)
    source_hash: str = ""
    actor_refs: list[str] = Field(default_factory=list)
    participant_refs: list[str] = Field(default_factory=list)
    issue_tags: list[str] = Field(default_factory=list)
    confidence_basis: str = "manual"
    extraction_method: str = "manual"
    reviewer_status: str = "review_required"
    conflicts: list[str] = Field(default_factory=list)
    duplicate_group: str = ""
    notes: str = ""
    child_impact_tags: list[str] = Field(default_factory=list)


class EvidenceTimelineEventPatchRequest(BaseModel):
    event_label: str | None = None
    classification: str | None = None
    date_value: str | None = None
    date_range: dict[str, Any] | None = None
    date_precision: str | None = None
    date_type: str | None = None
    notes: str | None = None
    issue_tags: list[str] | None = None
    actor_refs: list[str] | None = None
    participant_refs: list[str] | None = None
    child_impact_tags: list[str] | None = None
    reviewer_status: str | None = None
    reviewer_name: str | None = None
    reason: str | None = None


class EvidenceClaimCreateRequest(BaseModel):
    statement: str
    claim_type: str = "factual_claim"
    scope: str = "selected_records"
    source_of_claim: str = "user"
    selected_record_ids: list[str] = Field(default_factory=list)
    selected_sentence: str = ""
    promoted_from_record_id: str = ""
    date_range: dict[str, Any] = Field(default_factory=dict)
    issue_tags: list[str] = Field(default_factory=list)
    child_impact_tags: list[str] = Field(default_factory=list)


class EvidenceClaimReviewRequest(BaseModel):
    reviewer_status: str = "reviewed"
    reviewer_notes: str = ""


class EvidenceMissingRecordsRequest(BaseModel):
    template_id: str = ""
    selected_record_ids: list[str] = Field(default_factory=list)
    relevant_date_range: dict[str, Any] = Field(default_factory=dict)
    items: list[dict[str, Any]] = Field(default_factory=list)


class EvidenceLedgerEventCreateRequest(BaseModel):
    event_date: str = "unknown"
    operative_order_record: str = ""
    exact_order_term: str = ""
    required_conduct: str = ""
    alleged_or_observed_conduct: str = ""
    supporting_spans: list[dict[str, Any]] = Field(default_factory=list)
    contradicting_spans: list[dict[str, Any]] = Field(default_factory=list)
    notice_service_status: str = "unknown"
    ability_to_comply_information: str = "unknown"
    requested_relief: str = ""
    missing_evidence: list[str] = Field(default_factory=list)
    unresolved_facts: list[str] = Field(default_factory=list)
    reviewer_status: str = "review_required"
    stale_order_warning: StrictBool = False


class EvidenceLedgerEventPatchRequest(BaseModel):
    event_date: str | None = None
    operative_order_record: str | None = None
    exact_order_term: str | None = None
    required_conduct: str | None = None
    alleged_or_observed_conduct: str | None = None
    supporting_spans: list[dict[str, Any]] | None = None
    contradicting_spans: list[dict[str, Any]] | None = None
    notice_service_status: str | None = None
    ability_to_comply_information: str | None = None
    requested_relief: str | None = None
    missing_evidence: list[str] | None = None
    unresolved_facts: list[str] | None = None
    reviewer_status: str | None = None
    stale_order_warning: StrictBool | None = None


class EvidenceExportRequest(BaseModel):
    export_kind: str
    format: str = "md"
    selected_record_ids: list[str] = Field(default_factory=list)


class RetrievalWorkbenchSearchRequest(BaseModel):
    query: str
    include_private_records: StrictBool = True
    include_authority: StrictBool = True
    top_k: int = 10


class RetrievalWorkbenchEvalRequest(BaseModel):
    min_attorney_rows: int = 1
    top_k: int = 20


class FindingsFormsReviewRequest(BaseModel):
    selected_form_ids: list[str] = Field(default_factory=list)
    posture: str = "final_order"
    approved: StrictBool = False


class FindingsFormsCompleteRequest(BaseModel):
    build_id: str
    form_values: dict[str, dict[str, str]] = Field(default_factory=dict)
    confirmed: StrictBool = False


class FindingsMatrixBuildRequest(BaseModel):
    document_id: str
    selected_form_ids: list[str] = Field(default_factory=list)
    posture: str = "final_order"
    approved: StrictBool = False


class FindingsMatrixPatchRequest(BaseModel):
    build_id: str
    reviewer_status: str = "needs_review"
    reviewer_notes: str = ""
    proposed_finding: str = ""
    supporting_record_ids: list[str] = Field(default_factory=list)
    contrary_record_ids: list[str] = Field(default_factory=list)
    approved: StrictBool = False


class FindingsRestrictionReviewRequest(BaseModel):
    proposed_restriction_language: str
    document_id: str = ""
    selected_record_ids: list[str] = Field(default_factory=list)
    posture: str = "final_order"
    approved: StrictBool = False


class FormsSessionCreateRequest(BaseModel):
    document_id: str
    proceeding_type: str = "family_matter"
    selected_form_ids: list[str] = Field(default_factory=list)
    posture: str = "final_order"
    approved: StrictBool = False


class FormsSessionPatchRequest(BaseModel):
    form_values: dict[str, dict[str, str]] = Field(default_factory=dict)
    reviewer_notes: str = ""
    selected_form_ids: list[str] = Field(default_factory=list)
    approved: StrictBool = False


class FormsSessionActionRequest(BaseModel):
    form_values: dict[str, dict[str, str]] = Field(default_factory=dict)
    confirmed: StrictBool = False


class ReleaseHardeningEvidenceAuditRequest(BaseModel):
    approved: StrictBool = False


class ReleaseHardeningObservabilityRequest(BaseModel):
    approved: StrictBool = False


class ReleaseHardeningBackupDrillRequest(BaseModel):
    approved: StrictBool = False


class AttorneySandboxParticipantRequest(BaseModel):
    participant_id: str
    role: str = "attorney_reviewer"
    bar_status_verified: StrictBool = False
    verification_reference_sha256: str = ""
    terms_accepted: StrictBool = False
    training_modules: list[str] = Field(default_factory=list)


class AttorneySandboxSessionRequest(BaseModel):
    participant_id: str
    data_classification: str = "synthetic"
    approved: StrictBool = False


class AttorneySandboxFeedbackRequest(BaseModel):
    participant_id: str
    session_id: str
    category: str = "workflow"
    severity: str = "medium"
    description: str


class AttorneySandboxProgramRequest(BaseModel):
    program_id: str
    max_questions: int = 48
    approved: StrictBool = False


class AttorneySandboxCohortRequest(BaseModel):
    program_id: str
    cohort_id: str
    participant_ids: list[str] = Field(default_factory=list)
    approved: StrictBool = False


class AttorneySandboxAssignmentRequest(BaseModel):
    program_id: str
    cohort_id: str
    participant_id: str
    question_ids: list[str] = Field(default_factory=list)
    data_classification: str = "synthetic"
    approved: StrictBool = False


class AttorneySandboxStructuredReviewRequest(BaseModel):
    participant_id: str
    session_id: str
    question_id: str
    disposition: str = "needs_fix"
    source_grounding_rating: int = 1
    legal_accuracy_rating: int = 1
    usefulness_rating: int = 1
    boundary_safety_rating: int = 1
    citation_quality_rating: int = 1
    finding_codes: list[str] = Field(default_factory=list)
    response_artifact_sha256: str
    verifier_report_sha256: str
    comment: str = ""
    approved: StrictBool = False


class AttorneySandboxSessionCompleteRequest(BaseModel):
    participant_id: str
    session_id: str
    approved: StrictBool = False


class AttorneySandboxFeedbackTriageRequest(BaseModel):
    feedback_id: str
    status: str
    disposition_note: str = ""
    remediation_evidence_sha256: str = ""
    approved: StrictBool = False


class AttorneySandboxAttestationRequest(BaseModel):
    attestation_type: str
    evidence_sha256: str
    approved: StrictBool = False


class AttorneySandboxEvalExportRequest(BaseModel):
    eval_root: str
    approved: StrictBool = False


class AttorneySandboxEvidenceBuildRequest(BaseModel):
    approved: StrictBool = False


class RealMatterPilotProgramRequest(BaseModel):
    program_id: str
    allowed_tenant_ids: list[str] = Field(default_factory=list)
    pass48_evidence_sha256: str
    approved: StrictBool = False


class RealMatterPilotEnrollmentRequest(BaseModel):
    matter_id: str
    tenant_id: str
    participant_id: str
    consent_version: str
    client_consent_evidence_sha256: str
    privacy_notice_sha256: str
    matter_store_sha256: str
    tenant_isolation_evidence_sha256: str
    encryption_evidence_sha256: str
    retention_policy_version: str
    explicit_real_matter_consent: StrictBool = False
    training_use_allowed: StrictBool = False
    export_restriction_acknowledged: StrictBool = False
    human_review_required: StrictBool = True
    approved: StrictBool = False


class RealMatterPilotWorkProductRequest(BaseModel):
    matter_id: str
    artifact_hashes: dict[str, str] = Field(default_factory=dict)
    approved: StrictBool = False


class RealMatterPilotDailyReviewRequest(BaseModel):
    matter_id: str
    participant_id: str
    review_date: str
    usefulness: str = "not_yet_determined"
    human_review_completed: StrictBool = False
    source_verification_completed: StrictBool = False
    export_gate_checked: StrictBool = False
    blocker_codes: list[str] = Field(default_factory=list)
    review_evidence_sha256: str
    approved: StrictBool = False


class RealMatterPilotExportRequest(BaseModel):
    matter_id: str
    export_type: str = "draft_review_copy"
    gate_status: str = "blocked"
    filing_ready_claimed: StrictBool = False
    export_artifact_sha256: str
    authorization_evidence_sha256: str = ""
    approved: StrictBool = False


class RealMatterPilotIncidentRequest(BaseModel):
    matter_id: str
    category: str
    severity: str
    summary_code: str
    incident_evidence_sha256: str
    approved: StrictBool = False


class RealMatterPilotIncidentUpdateRequest(BaseModel):
    incident_id: str
    status: str
    remediation_evidence_sha256: str
    retest_evidence_sha256: str = ""
    approved: StrictBool = False


class RealMatterPilotSignoffRequest(BaseModel):
    matter_id: str
    participant_id: str
    usefulness: str
    attorney_signoff_complete: StrictBool = False
    blocker_codes: list[str] = Field(default_factory=list)
    signoff_evidence_sha256: str
    approved: StrictBool = False


class RealMatterPilotEvidenceBuildRequest(BaseModel):
    approved: StrictBool = False


class GAReleaseCandidateCreateRequest(BaseModel):
    candidate_id: str
    version: str
    source_repo_zip_sha256: str
    source_repo_zip_name: str
    approved: StrictBool = False


class GAReleaseCandidateArtifactRequest(BaseModel):
    candidate_id: str
    artifact_type: str
    artifact_version: str
    reference: str
    sha256: str
    present: StrictBool = True
    external: StrictBool = True
    immutable: StrictBool = True
    approved: StrictBool = False


class GAReleaseCandidateSignoffRequest(BaseModel):
    candidate_id: str
    role: str
    signer_label: str
    status: str = "pending"
    signed_at: str
    evidence_sha256: str
    approved: StrictBool = False


class GAReleaseCandidateBlockerRequest(BaseModel):
    candidate_id: str
    blocker_id: str
    severity: str
    status: str
    description_code: str
    evidence_sha256: str
    approved: StrictBool = False


class GAReleaseCandidateFreezeRequest(BaseModel):
    candidate_id: str
    audit_enterprise_readiness_status: str = "blocked"
    approved: StrictBool = False


class GAReleaseCandidateEvidenceBuildRequest(BaseModel):
    approved: StrictBool = False


class GAShipmentCreateRequest(BaseModel):
    shipment_id: str
    version: str
    source_repo_zip_name: str
    source_repo_zip_sha256: str
    release_candidate_id: str
    release_candidate_report_sha256: str
    release_candidate_inventory_hash: str
    release_channel: str = "source_release"
    approved: StrictBool = False


class GAShipmentArtifactRequest(BaseModel):
    shipment_id: str
    artifact_type: str
    artifact_version: str
    reference: str
    sha256: str
    present: StrictBool = True
    external: StrictBool = True
    immutable: StrictBool = True
    approved: StrictBool = False


class GAShipmentControlRequest(BaseModel):
    shipment_id: str
    control: str
    satisfied: StrictBool = False
    evidence_sha256: str
    approved: StrictBool = False


class GAShipmentChannelRequest(BaseModel):
    shipment_id: str
    channel: str
    status: str = "planned"
    package_sha256: str
    qualification_evidence_sha256: str
    rollback_evidence_sha256: str
    distribution_reference: str
    receipt_sha256: str
    approved: StrictBool = False


class GAShipmentBlockerRequest(BaseModel):
    shipment_id: str
    blocker_id: str
    severity: str
    status: str
    description_code: str
    evidence_sha256: str
    approved: StrictBool = False


class GAShipmentEvaluateRequest(BaseModel):
    shipment_id: str
    release_candidate_status: str = "blocked"
    release_candidate_frozen: StrictBool = False
    release_candidate_inventory_hash: str
    approved: StrictBool = False


class GAShipmentEvidenceBuildRequest(BaseModel):
    approved: StrictBool = False


class ClearSessionRequest(BaseModel):
    session_id: str = ""


class WorkspaceDocumentCreateRequest(BaseModel):
    title: str
    content: str = ""
    document_type: str = "draft"
    note: str = ""
    tags: list[str] = Field(default_factory=list)
    source_refs: list[dict[str, Any]] = Field(default_factory=list)


class WorkspaceRevisionProposalRequest(BaseModel):
    content: str
    base_revision_id: str
    note: str = ""


class WorkspaceRevisionCommitRequest(BaseModel):
    revision_id: str
    confirmation_token: str
    confirmed: StrictBool = False


class WorkspaceRevisionRejectRequest(BaseModel):
    revision_id: str


class WorkspaceDeleteCommitRequest(BaseModel):
    confirmation_token: str
    confirmed: StrictBool = False


class WorkspaceImportRecordRequest(BaseModel):
    source_token: str
    page: int = 0
    title: str = ""
    document_type: str = "draft"


class WorkspaceDocxEditRequest(BaseModel):
    operations: list[dict[str, Any]] = Field(default_factory=list)
    author: str = "Maine Family Law LLM User"
    confirmed: StrictBool = False


class WorkspaceReviewPrepareRequest(BaseModel):
    facts: list[str] = Field(default_factory=list)
    quotes: list[dict[str, Any]] = Field(default_factory=list)
    claims: list[dict[str, Any] | str] = Field(default_factory=list)
    auto_extract_claims: StrictBool = True


class WorkspaceReviewCommitRequest(BaseModel):
    request_id: str
    confirmation_token: str
    confirmed: StrictBool = False
    decision: str = "approve_review"
    reviewer_name: str
    reviewer_role: str = "other_reviewer"
    attested: StrictBool = False
    notes: str = ""
    claim_annotations: list[dict[str, Any]] = Field(default_factory=list)


class FilingPacketDiffRequest(BaseModel):
    base_revision_id: str = ""
    target_revision_id: str = ""


class FilingPacketAssignmentRequest(BaseModel):
    reviewer_label: str
    role: str = "other_reviewer"
    capabilities: list[str] = Field(default_factory=lambda: ["review"])
    expected_revision_id: str
    exclusive: StrictBool = True
    note: str = ""


class FilingPacketBuildRequest(BaseModel):
    approved: StrictBool = False


class AuthorityImpactAnalyzeRequest(BaseModel):
    document_id: str
    base_build_id: str
    target_build_id: str


class AuthorityImpactBuildRequest(AuthorityImpactAnalyzeRequest):
    approved: StrictBool = False


class LocalAgentPreviewRequest(BaseModel):
    question: str
    source_cards: list[dict[str, Any]] = Field(default_factory=list)
    provider: str = "ollama"
    endpoint: str = "http://127.0.0.1:11434"
    model: str = "qwen2.5:7b"
    run_id: str = ""


class LocalAgentExecuteRequest(LocalAgentPreviewRequest):
    approved_manifest_sha256: str
    matter_id: str = ""
    tool_invocations: list[dict[str, Any]] = Field(default_factory=list)
    permitted_tools: list[str] = Field(default_factory=list)
    retrieval_diagnostics: dict[str, Any] = Field(default_factory=dict)


class LocalWorkbenchModelRequest(BaseModel):
    model_id: str
    display_name: str = ""
    role: str = "general_assistant"
    version: str = "unknown"
    quantization: str = ""
    artifact_sha256: str = ""
    artifact_size_bytes: int = 0
    min_ram_bytes: int = 0
    min_vram_bytes: int = 0
    context_limit_tokens: int = 0


class LocalWorkbenchRouteRequest(BaseModel):
    task: str
    preferred_model_id: str = ""


class LocalWorkbenchArtifactAdmissionRequest(BaseModel):
    model_id: str
    filename: str
    expected_sha256: str


class LocalWorkbenchPerformancePolicyRequest(BaseModel):
    mode: str = "balanced"
    max_concurrent_jobs: int = 1
    max_context_tokens: int = 4096
    memory_budget_ratio: float = 0.5
    pause_background_when_low_memory: StrictBool = True


class LocalWorkbenchJobPreflightRequest(BaseModel):
    task: str
    context_tokens: int = 0
    estimated_memory_bytes: int = 0


class LocalWorkbenchPlanRequest(BaseModel):
    plan_id: str = ""
    title: str
    objective: str = ""
    actions: list[dict[str, Any]] = Field(default_factory=list)


class LocalWorkbenchPreferencesRequest(BaseModel):
    preferences: dict[str, Any] = Field(default_factory=dict)


class LocalWorkbenchPrivacyRequest(BaseModel):
    privacy: dict[str, Any] = Field(default_factory=dict)


class LocalWorkbenchAutomationRequest(BaseModel):
    automation_id: str
    title: str = ""
    steps: list[dict[str, Any]] = Field(default_factory=list)


class LocalWorkbenchExtensionRequest(BaseModel):
    extension_id: str
    name: str = ""
    version: str = "0.0.0"
    permissions: list[str] = Field(default_factory=list)
    manifest_sha256: str = ""


class LocalWorkbenchEvaluationRequest(BaseModel):
    evaluation_id: str
    subject_id: str
    kind: str = "workflow"
    metrics: dict[str, float] = Field(default_factory=dict)
    sample_count: int = 0


if FastAPI is None:  # pragma: no cover
    app = None
else:
    from app.api.routes.children import router as children_router
    from app.api.routes.communications import router as communications_router
    from app.api.routes.multimedia import router as multimedia_router
    from app.api.routes.release_control import router as release_control_router
    from app.api.routes.governance import router as governance_router
    from app.api.routes.security_privacy import router as security_privacy_router

    app = FastAPI(
        title="Maine Family Law LLM Local Workbench",
        version=__version__,
        description="Local legal-information workbench. No legal advice, no cloud deploy, source receipts required.",
    )
    app.include_router(release_control_router, prefix="/api")
    app.include_router(governance_router, prefix="/api")
    app.include_router(security_privacy_router, prefix="/api")
    app.include_router(children_router, prefix="/api")
    app.include_router(communications_router, prefix="/api")
    app.include_router(multimedia_router, prefix="/api")


if FastAPI is not None:
    _ocr_jobs: dict[str, dict[str, Any]] = {}
    _ocr_job_lock = threading.Lock()
    _ocr_prerequisite_job: dict[str, Any] = {"status": "idle", "running": False}
    _ocr_prerequisite_lock = threading.Lock()
    # Session-scoped, in-memory source state. It is deliberately bounded,
    # short-lived, never written to disk, and disabled when the client does not
    # provide a session ID. This prevents one local browser session from
    # reopening another session's private record snippets.
    _recent_record_searches: dict[str, dict[str, Any]] = {}
    _recent_search_lock = threading.Lock()
    _RECENT_SOURCE_TTL_SECONDS = 30 * 60
    _RECENT_SOURCE_MAX_SESSIONS = 64
    _RECENT_SOURCE_MAX_CARDS = 24
    _OCR_STALLED_AFTER_SECONDS = 60
    _prompt_injection_scanner = PromptInjectionScanner()
    # Tokens are server-side capabilities, scoped to the currently active case.
    # They deliberately contain neither a filesystem location nor a corpus label.
    _record_open_tokens: dict[str, dict[str, Any]] = {}
    _record_open_lock = threading.RLock()
    _RECORD_OPEN_TTL_SECONDS = 60 * 60
    _RECORD_OPEN_MAX_TOKENS = 4096
    _RECORD_PREVIEW_TEXT_LIMIT = 120_000
    _RECORD_PREVIEW_MEMBER_LIMIT = 250
    _OPEN_CACHE_TTL_SECONDS = 24 * 60 * 60
    _OPEN_CACHE_MAX_FILES = 512
    _OPEN_CACHE_MAX_BYTES = 512 * 1024 * 1024
    _document_intelligence_artifacts: dict[str, dict[str, Any]] = {}
    _document_intelligence_artifact_lock = threading.RLock()
    _DOCUMENT_INTELLIGENCE_ARTIFACT_TTL_SECONDS = 60 * 60
    _DOCUMENT_INTELLIGENCE_ARTIFACT_MAX_TOKENS = 1024
    _evidence_work_product_artifacts: dict[str, dict[str, Any]] = {}
    _evidence_work_product_artifact_lock = threading.RLock()
    _EVIDENCE_WORK_PRODUCT_ARTIFACT_TTL_SECONDS = 60 * 60
    _EVIDENCE_WORK_PRODUCT_ARTIFACT_MAX_TOKENS = 1024
    _findings_forms_artifacts: dict[str, dict[str, Any]] = {}
    _findings_forms_artifact_lock = threading.RLock()
    _FINDINGS_FORMS_ARTIFACT_TTL_SECONDS = 60 * 60
    _FINDINGS_FORMS_ARTIFACT_MAX_TOKENS = 1024
    _filing_packet_artifacts: dict[str, dict[str, Any]] = {}
    _filing_packet_artifact_lock = threading.RLock()
    _FILING_PACKET_ARTIFACT_TTL_SECONDS = 60 * 60
    _FILING_PACKET_ARTIFACT_MAX_TOKENS = 1024
    _authority_impact_artifacts: dict[str, dict[str, Any]] = {}
    _authority_impact_artifact_lock = threading.RLock()
    _AUTHORITY_IMPACT_ARTIFACT_TTL_SECONDS = 60 * 60
    _AUTHORITY_IMPACT_ARTIFACT_MAX_TOKENS = 1024
    _sandbox_operations_artifacts: dict[str, dict[str, Any]] = {}
    _sandbox_operations_artifact_lock = threading.RLock()
    _SANDBOX_OPERATIONS_ARTIFACT_TTL_SECONDS = 60 * 60
    _SANDBOX_OPERATIONS_ARTIFACT_MAX_TOKENS = 1024
    _real_matter_pilot_artifacts: dict[str, dict[str, Any]] = {}
    _real_matter_pilot_artifact_lock = threading.RLock()
    _REAL_MATTER_PILOT_ARTIFACT_TTL_SECONDS = 60 * 60
    _REAL_MATTER_PILOT_ARTIFACT_MAX_TOKENS = 1024
    _ga_release_candidate_artifacts: dict[str, dict[str, Any]] = {}
    _ga_release_candidate_artifact_lock = threading.RLock()
    _GA_RELEASE_CANDIDATE_ARTIFACT_TTL_SECONDS = 60 * 60
    _GA_RELEASE_CANDIDATE_ARTIFACT_MAX_TOKENS = 1024
    _ga_shipment_artifacts: dict[str, dict[str, Any]] = {}
    _ga_shipment_artifact_lock = threading.RLock()
    _GA_SHIPMENT_ARTIFACT_TTL_SECONDS = 60 * 60
    _GA_SHIPMENT_ARTIFACT_MAX_TOKENS = 1024

    def _public_ocr_prerequisite_job() -> dict[str, Any]:
        with _ocr_prerequisite_lock:
            state = dict(_ocr_prerequisite_job)
        state.pop("thread", None)
        state["prerequisites"] = ocr_prerequisite_status()
        return state

    def _public_ocr_progress(state: dict[str, Any]) -> dict[str, Any]:
        """Return progress without exposing a matter path or document contents."""

        public = {
            key: value
            for key, value in state.items()
            if key not in {"cancel_event", "source_locator"}
        }
        source_locator = str(state.get("source_locator") or "")
        current_file = (
            PureWindowsPath(source_locator).name
            if "\\" in source_locator
            else Path(source_locator).name
        )
        if current_file:
            public["current_file"] = current_file[:160]
        now = time.time()
        last_progress_at = float(public.get("last_progress_at") or public.get("started_at") or now)
        public["last_progress_at"] = last_progress_at
        public["elapsed_seconds"] = max(0, int(now - float(public.get("started_at") or now)))
        public["seconds_since_update"] = max(0, int(now - last_progress_at))
        if public.get("status") in {"queued", "running", "cancelling"}:
            public["stalled"] = now - last_progress_at >= _OCR_STALLED_AFTER_SECONDS
            if public["stalled"]:
                public["display_status"] = "stalled"
            else:
                public["display_status"] = str(public.get("status") or "queued")
        else:
            public["stalled"] = False
            public["display_status"] = str(public.get("status") or "idle")
        public["local_only"] = True
        public["network_used"] = False
        return public

    def _run_ocr_prerequisite_install() -> None:
        with _ocr_prerequisite_lock:
            _ocr_prerequisite_job.update(
                {
                    "status": "running",
                    "running": True,
                    "message": "Installing Tesseract through Windows Package Manager…",
                }
            )
        result = install_local_ocr_prerequisites(approved=True)
        with _ocr_prerequisite_lock:
            _ocr_prerequisite_job.clear()
            _ocr_prerequisite_job.update(
                {
                    **result,
                    "running": False,
                    "completed_at": time.time(),
                }
            )

    def _session_key(payload: AskRequest) -> str:
        raw, _report = normalize_session_id(payload.session_id)
        if not raw:
            return ""
        # Keep the accepted identifier opaque. No user text or private matter
        # content becomes an in-memory dictionary key.
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _prune_recent_sources(now: float | None = None) -> None:
        current = float(now if now is not None else time.time())
        stale_before = current - _RECENT_SOURCE_TTL_SECONDS
        stale_keys = [
            key
            for key, entry in _recent_record_searches.items()
            if float(entry.get("created_at") or 0) < stale_before
        ]
        for key in stale_keys:
            _recent_record_searches.pop(key, None)
        if len(_recent_record_searches) > _RECENT_SOURCE_MAX_SESSIONS:
            overflow = len(_recent_record_searches) - _RECENT_SOURCE_MAX_SESSIONS
            oldest = sorted(
                _recent_record_searches.items(),
                key=lambda item: float(item[1].get("created_at") or 0),
            )[:overflow]
            for key, _ in oldest:
                _recent_record_searches.pop(key, None)

    def _bounded_citations(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
        bounded: list[dict[str, Any]] = []
        for item in values[:_RECENT_SOURCE_MAX_CARDS]:
            row = dict(item)
            row["snippet"] = str(row.get("snippet") or "")[:1600]
            metadata = dict(row.get("metadata") or {})
            for key in ("text", "text_content", "raw_text", "full_text"):
                metadata.pop(key, None)
            if "text_excerpt" in metadata:
                metadata["text_excerpt"] = str(metadata.get("text_excerpt") or "")[:1600]
            row["metadata"] = metadata
            bounded.append(row)
        return bounded

    def _public_source_locator(value: object) -> str:
        """Keep locator usefulness while removing every directory component."""
        locator = str(value or "")
        base, marker, page = locator.partition("#page=")
        members = [Path(part.replace("\\", "/")).name for part in base.split("!") if part]
        safe = "!".join(members)
        if marker and page.isdigit():
            safe += f"#page={int(page)}"
        return safe

    def _redact_citation_paths(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
        redacted: list[dict[str, Any]] = []
        for item in values:
            row = dict(item)
            metadata = dict(row.get("metadata") or {})
            if "source_locator" in metadata:
                metadata["source_locator"] = _public_source_locator(metadata["source_locator"])
            for key in ("source_path", "path", "private_copy_relpath", "external_copy_relpath"):
                metadata.pop(key, None)
            row["metadata"] = metadata
            redacted.append(row)
        return redacted

    def _prune_record_open_tokens(now: float | None = None) -> None:
        with _record_open_lock:
            current = float(now if now is not None else time.time())
            stale_before = current - _RECORD_OPEN_TTL_SECONDS
            stale = [
                token
                for token, binding in _record_open_tokens.items()
                if float(binding.get("created_at") or 0) < stale_before
            ]
            for token in stale:
                _record_open_tokens.pop(token, None)
            if len(_record_open_tokens) > _RECORD_OPEN_MAX_TOKENS:
                overflow = len(_record_open_tokens) - _RECORD_OPEN_MAX_TOKENS
                oldest = sorted(
                    _record_open_tokens.items(),
                    key=lambda item: float(item[1].get("created_at") or 0),
                )[:overflow]
                for token, _binding in oldest:
                    _record_open_tokens.pop(token, None)

    def _record_open_token(case_root: Path, evidence_id: str, source_locator: str = "") -> str:
        """Mint a short-lived opaque capability for one active-corpus record."""
        with _record_open_lock:
            _prune_record_open_tokens()
            token = secrets.token_hex(32)
            _record_open_tokens[token] = {
                "case_id": _case_id(case_root),
                "evidence_id": str(evidence_id or ""),
                "source_locator": str(source_locator or ""),
                "created_at": time.time(),
            }
            return token

    def _record_identity(citation: dict[str, Any]) -> tuple[str, str]:
        """Return the parent record and optional ZIP/email member identity."""
        meta = dict(citation.get("metadata") or {})
        parent = str(meta.get("parent_evidence_id") or citation.get("source_id") or "")
        locator = str(meta.get("source_locator") or "")
        member = locator.split("!", 1)[1] if "!" in locator else ""
        return parent, member

    def _safe_record_basename(citation: dict[str, Any]) -> str:
        meta = dict(citation.get("metadata") or {})
        locator = str(meta.get("source_locator") or "")
        # A member is the document the user searched, rather than the archive.
        visible = locator.rsplit("!", 1)[-1] if "!" in locator else locator
        visible = visible.split("#page=", 1)[0].replace("\\", "/")
        return Path(visible or str(citation.get("title") or "Record")).name[:240]

    def _attach_record_open_capabilities(
        case_root: Path | None, citations: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Attach opaque open/inspect capabilities only to indexed private records."""
        if case_root is None:
            return citations
        try:
            indexed_ids = {
                str(row.get("evidence_id") or "") for row in load_case_search_records(case_root)
            }
        except Exception:
            return citations
        output: list[dict[str, Any]] = []
        for citation in citations:
            row = dict(citation)
            metadata = dict(row.get("metadata") or {})
            parent, _member = _record_identity(row)
            if parent and parent in indexed_ids:
                locator = str(metadata.get("source_locator") or "")
                metadata["record_open_token"] = _record_open_token(case_root, parent, locator)
                metadata["record_open_page"] = int(metadata.get("page_number") or 0)
                metadata["record_open_basename"] = _safe_record_basename(row)
                metadata["record_inspection_available"] = True
            row["metadata"] = metadata
            output.append(row)
        return output

    def _group_record_cards(
        case_root: Path, citations: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        seen: set[tuple[str, int, str]] = set()
        for citation in citations:
            meta = dict(citation.get("metadata") or {})
            parent, member = _record_identity(citation)
            if not parent:
                continue
            page = int(meta.get("page_number") or 0)
            snippet = " ".join(str(citation.get("snippet") or "").split())[:500]
            canonical_key = str(
                meta.get("canonical_document_key")
                or (f"sha256:{meta.get('source_hash')}" if meta.get("source_hash") else "")
                or f"{parent}\0{member}"
            )
            key = (canonical_key, page, snippet.casefold())
            if key in seen:
                continue
            seen.add(key)
            card = grouped.setdefault(
                canonical_key,
                {
                    "source_id": parent,
                    "source_token": _record_open_token(
                        case_root, parent, str(meta.get("source_locator") or "")
                    ),
                    "basename": _safe_record_basename(citation),
                    "document_type": str(meta.get("source_type") or "record"),
                    "viewer_kind": _record_viewer_kind(
                        Path(_safe_record_basename(citation)).suffix.lower(),
                        mimetypes.guess_type(_safe_record_basename(citation))[0]
                        or "application/octet-stream",
                    ),
                    "match_count": 0,
                    "pages": [],
                    "snippets": [],
                    "duplicate_copy_count": max(1, int(meta.get("duplicate_copy_count") or 1)),
                    "duplicate_basenames": list(meta.get("duplicate_basenames") or []),
                    "canonical_document_key": canonical_key,
                },
            )
            card["duplicate_copy_count"] = max(
                int(card.get("duplicate_copy_count") or 1),
                int(meta.get("duplicate_copy_count") or 1),
            )
            for basename in list(meta.get("duplicate_basenames") or []):
                if basename and basename not in card["duplicate_basenames"]:
                    card["duplicate_basenames"].append(basename)
            card["match_count"] += 1
            if page and page not in card["pages"]:
                card["pages"].append(page)
            if snippet and snippet not in card["snippets"]:
                card["snippets"].append(snippet)
        return sorted(
            grouped.values(),
            key=lambda row: (-int(row["match_count"]), str(row["basename"]).casefold()),
        )

    def _safe_intake_anchor(value: dict[str, Any] | IntakeSummary | None) -> dict[str, Any]:
        """Keep only routing labels needed for safe short-turn continuity.

        Raw user text, dates, court names, docket numbers, search targets, and
        safety flags are intentionally excluded from the in-memory session
        anchor. Safety is always re-evaluated from the current turn.
        """

        if isinstance(value, IntakeSummary):
            summary = value
        elif isinstance(value, dict) and value:
            summary = IntakeSummary.from_dict(value)
        else:
            return {}
        return {
            "normalized_text": "",
            "task": summary.task,
            "issues": list(summary.issues[:6]),
            "procedural_posture": summary.procedural_posture,
            "requested_actions": list(summary.requested_actions[:4]),
            "child_relevant": bool(summary.child_relevant),
            "attention_level": "routine",
            "confidence": float(summary.confidence or 0.0),
        }

    def _prior_intake_anchor(payload: AskRequest) -> dict[str, Any]:
        key = _session_key(payload)
        if not key:
            return {}
        with _recent_search_lock:
            _prune_recent_sources()
            entry = dict(_recent_record_searches.get(key) or {})
        return dict(entry.get("intake_anchor") or {})

    def _parse_payload_intake(payload: AskRequest) -> IntakeSummary:
        return parse_intake(
            payload.question,
            payload.matter_context,
            prior_intake=_prior_intake_anchor(payload),
        )

    def _remember_record_search(payload: AskRequest, result: dict[str, Any]) -> dict[str, Any]:
        # Kept under the historical function name for compatibility. It now
        # remembers source cards from Maine-law, record, and combined answers.
        if str(result.get("response_kind") or "") == "source_card_followup":
            return result
        key = _session_key(payload)
        if not key:
            return result
        citations = _bounded_citations(list(result.get("citations") or []))
        search_id = str(result.get("search_id") or uuid.uuid4().hex)
        result["search_id"] = search_id
        structured = dict(result.get("structured_answer") or {})
        metadata = dict(result.get("metadata") or {})
        intake_value = result.get("intake") or structured.get("intake") or metadata.get("intake")
        entry = {
            "search_id": search_id,
            "search_summary": dict(result.get("search_summary") or {}),
            "citations": citations,
            "active_case_label": str(result.get("active_case_label") or ""),
            "search_mode": str(result.get("search_mode") or payload.search_mode),
            "response_kind": str(result.get("response_kind") or "family_answer"),
            "direct_record_search": bool(result.get("direct_record_search")),
            "intake_anchor": _safe_intake_anchor(intake_value),
            "created_at": time.time(),
            "local_only": True,
        }
        with _recent_search_lock:
            _prune_recent_sources(entry["created_at"])
            _recent_record_searches[key] = entry
            _prune_recent_sources(entry["created_at"])
        return result

    def _source_card_followup(payload: AskRequest) -> dict[str, Any] | None:
        intake = parse_intake(payload.question, payload.matter_context)
        if intake.task != "source_card_followup":
            return None
        key = _session_key(payload)
        if not key:
            return {
                "question": payload.question,
                "answer_style": payload.answer_style,
                "search_mode": _normalize_search_mode(payload.search_mode),
                "response_kind": "source_card_followup",
                "answer": "I cannot reopen prior source cards without a session ID. Ask the question again or use the Evidence drawer for the current answer.",
                "grounded": False,
                "failure_class": "conversation_session_required",
                "recovery_hint": "Use the desktop chat session or send a stable session_id with the request.",
                "citations": [],
                "source_card_count": 0,
                "review_required": True,
                "not_legal_advice": True,
                "direct_record_search": False,
                "metadata": {"intake": intake.to_dict()},
            }
        with _recent_search_lock:
            _prune_recent_sources()
            entry = dict(_recent_record_searches.get(key) or {})
        if not entry:
            return {
                "question": payload.question,
                "answer_style": payload.answer_style,
                "search_mode": _normalize_search_mode(payload.search_mode),
                "response_kind": "source_card_followup",
                "answer": "I do not have a recent answer in this session to reopen. Ask the question again, or use the Evidence drawer for the current answer.",
                "grounded": False,
                "failure_class": "no_recent_search_result",
                "recovery_hint": "Ask a source-backed question in this session first.",
                "citations": [],
                "source_card_count": 0,
                "review_required": True,
                "not_legal_advice": True,
                "direct_record_search": False,
                "metadata": {"intake": intake.to_dict()},
            }
        requested_search_id = str(payload.last_search_id or "").strip()
        if requested_search_id and requested_search_id != str(entry.get("search_id") or ""):
            return {
                "question": payload.question,
                "answer_style": payload.answer_style,
                "search_mode": _normalize_search_mode(payload.search_mode),
                "response_kind": "source_card_followup",
                "answer": "The requested source-card reference no longer matches the most recent answer in this session. Ask the underlying question again so the source set is explicit.",
                "grounded": False,
                "failure_class": "stale_source_card_reference",
                "recovery_hint": "Ask the underlying question again before reopening source cards.",
                "citations": [],
                "source_card_count": 0,
                "review_required": True,
                "not_legal_advice": True,
                "direct_record_search": False,
                "metadata": {"intake": intake.to_dict()},
            }
        citations = list(entry.get("citations") or [])
        requested_lane = str(intake.source_card_lane or "all")
        if requested_lane in {"legal_authority", "private_record"}:
            citations = [
                item
                for item in citations
                if str((item.get("metadata") or {}).get("source_lane") or "legal_authority")
                == requested_lane
            ]
        available_count = len(citations)
        selection = int(intake.source_card_selection or 0)
        if requested_lane != "all" and not citations:
            lane_label = "Maine-law" if requested_lane == "legal_authority" else "private-record"
            return {
                "question": payload.question,
                "answer_style": payload.answer_style,
                "search_mode": _normalize_search_mode(
                    str(entry.get("search_mode") or payload.search_mode)
                ),
                "response_kind": "source_card_followup",
                "answer": f"The most recent answer has no {lane_label} source cards. No new search was run.",
                "grounded": False,
                "failure_class": "source_card_lane_empty",
                "recovery_hint": "Reopen all prior source cards or ask the underlying question again in the intended source lane.",
                "citations": [],
                "source_card_count": 0,
                "review_required": True,
                "not_legal_advice": True,
                "direct_record_search": False,
                "search_id": entry.get("search_id", ""),
                "metadata": {
                    "intake": intake.to_dict(),
                    "reused_prior_search": True,
                    "requested_source_lane": requested_lane,
                },
            }
        resolved_selection = available_count if selection == -1 else selection
        if resolved_selection and resolved_selection > available_count:
            return {
                "question": payload.question,
                "answer_style": payload.answer_style,
                "search_mode": _normalize_search_mode(
                    str(entry.get("search_mode") or payload.search_mode)
                ),
                "response_kind": "source_card_followup",
                "answer": f"The prior answer has {available_count} source card"
                + ("s" if available_count != 1 else "")
                + f" in the requested lane, so source card {resolved_selection} is not available. No new search was run.",
                "grounded": False,
                "failure_class": "source_card_selection_out_of_range",
                "recovery_hint": "Open all prior source cards or select an available card number.",
                "citations": [],
                "source_card_count": 0,
                "review_required": True,
                "not_legal_advice": True,
                "direct_record_search": False,
                "search_id": entry.get("search_id", ""),
                "metadata": {
                    "intake": intake.to_dict(),
                    "reused_prior_search": True,
                    "available_source_cards": available_count,
                    "selected_source_card": resolved_selection,
                    "requested_source_lane": requested_lane,
                },
            }
        if resolved_selection:
            citations = citations[resolved_selection - 1 : resolved_selection]
        original_mode = _normalize_search_mode(str(entry.get("search_mode") or payload.search_mode))
        direct_record_search = bool(entry.get("direct_record_search"))
        selected_note = (
            f" Source card {resolved_selection} was selected." if resolved_selection else ""
        )
        lane_note = {
            "legal_authority": " Maine-law source filtering was applied.",
            "private_record": " Private-record source filtering was applied.",
        }.get(requested_lane, "")
        return {
            "question": payload.question,
            "answer_style": payload.answer_style,
            "search_mode": original_mode,
            "response_kind": "source_card_followup",
            "answer": f"{len(citations)} source card"
            + ("s" if len(citations) != 1 else "")
            + (" is" if len(citations) == 1 else " are")
            + " ready in the Evidence drawer from the most recent answer. No new search was run."
            + lane_note
            + selected_note,
            "grounded": bool(citations),
            "failure_class": "none" if citations else "no_recent_search_sources",
            "recovery_hint": "Review the original record and surrounding context.",
            "citations": citations,
            "source_card_count": len(citations),
            "review_required": True,
            "not_legal_advice": True,
            "direct_record_search": direct_record_search,
            "search_id": entry.get("search_id", ""),
            "search_summary": dict(entry.get("search_summary") or {}),
            "active_case_label": entry.get("active_case_label", ""),
            "metadata": {
                "intake": intake.to_dict(),
                "reused_prior_search": True,
                "reused_response_kind": entry.get("response_kind", ""),
                "selected_source_card": resolved_selection,
                "requested_source_lane": requested_lane,
            },
        }

    def _repo_root() -> Path:
        return Path(__file__).resolve().parents[2]

    def _brand_assets_dir() -> Path:
        return _repo_root() / "assets" / "brand" / "focaf_family_law_llm_brand_kit"

    def _ui_assets_dir() -> Path:
        return Path(str(ui_asset_root()))

    if StaticFiles is not None and _brand_assets_dir().is_dir():
        app.mount(
            "/brand-assets", StaticFiles(directory=str(_brand_assets_dir())), name="brand-assets"
        )

    if StaticFiles is not None and _ui_assets_dir().is_dir():
        app.mount("/ui-assets", StaticFiles(directory=str(_ui_assets_dir())), name="ui-assets")

    async def _read_limited_request_body(request: Request, *, max_bytes: int) -> bytes | None:
        """Consume a request body incrementally and stop at the configured cap."""

        chunks: list[bytes] = []
        total = 0
        async for chunk in request.stream():
            total += len(chunk)
            if total > max_bytes:
                return None
            if chunk:
                chunks.append(bytes(chunk))
        return b"".join(chunks)

    @app.middleware("http")
    async def local_security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = uuid.uuid4().hex
        request.state.request_id = request_id
        decision = evaluate_local_request(
            method=request.method,
            path=request.url.path,
            client_host=getattr(request.client, "host", None),
            host_header=request.headers.get("host", ""),
            origin_header=request.headers.get("origin", ""),
            sec_fetch_site=request.headers.get("sec-fetch-site", ""),
            content_length=request.headers.get("content-length", ""),
            max_body_bytes=DEFAULT_MAX_BODY_BYTES,
        )
        if not decision.allowed:
            return JSONResponse(
                status_code=decision.status_code,
                content={
                    "detail": decision.code,
                    "message": decision.detail,
                    "request_id": request_id,
                },
                headers={"X-Request-ID": request_id, "Cache-Control": "no-store"},
            )
        if request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
            try:
                body = await _read_limited_request_body(request, max_bytes=DEFAULT_MAX_BODY_BYTES)
            except ClientDisconnect:
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": "request_body_incomplete",
                        "message": "The request body was not received completely.",
                        "request_id": request_id,
                    },
                    headers={"X-Request-ID": request_id, "Cache-Control": "no-store"},
                )
            if body is None:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": "request_too_large",
                        "message": "Request body exceeds the local limit.",
                        "request_id": request_id,
                    },
                    headers={"X-Request-ID": request_id, "Cache-Control": "no-store"},
                )
            request._body = body  # type: ignore[attr-defined]
            delivered = False

            async def _receive():  # type: ignore[no-untyped-def]
                nonlocal delivered
                if delivered:
                    return {"type": "http.request", "body": b"", "more_body": False}
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}

            request._receive = _receive  # type: ignore[attr-defined]
        response = await call_next(request)
        record_preview = request.url.path.startswith("/api/records/open/")
        if not response.headers.get("Content-Security-Policy"):
            frame_ancestors = "'self'" if record_preview else "'none'"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "connect-src 'self'; "
                "img-src 'self' data:; "
                "style-src 'self' 'unsafe-inline'; "
                "script-src 'self' 'unsafe-inline'; "
                "font-src 'self'; "
                "object-src 'none'; "
                "frame-src 'self'; "
                f"frame-ancestors {frame_ancestors}; "
                "base-uri 'none'; "
                "form-action 'self'"
            )
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN" if record_preview else "DENY"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["X-DNS-Prefetch-Control"] = "off"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        if request.url.path in {"/health", "/api/health"}:
            service_instance = (
                str(os.environ.get("MFL_LOCAL_API_INSTANCE_ID") or "").strip().casefold()
            )
            if re.fullmatch(r"[0-9a-f]{64}", service_instance):
                response.headers["X-MFL-Service-Instance"] = service_instance
                response.headers["X-MFL-Service-Pid"] = str(os.getpid())
        response.headers["X-Request-ID"] = request_id
        return response

    def _health_payload() -> dict[str, Any]:
        return runtime_health_snapshot()

    def _runtime_diagnostics_payload() -> dict[str, Any]:
        active_case = active_case_root()
        case_summary = describe_case_root(active_case) if active_case else None
        return {
            "status": "ok",
            "version": __version__,
            "ui_version": UI_VERSION,
            "mode": "local-workbench",
            "enter_to_submit": True,
            "enter_submit_clears_input": True,
            "branding": "Constitutional public-service chat shell with local brand assets served from /brand-assets",
            "brand_assets_mounted": _brand_assets_dir().is_dir(),
            "appeals_routing_fix": True,
            "chat_library_routing_v187": True,
            "constitutional_chat_shell_v208": True,
            "constitutional_chat_shell_v3": True,
            "chat_panel_primary_layout": True,
            "split_ui_assets": True,
            "evidence_drawer_default_closed": False,
            "command_palette_shortcut": "Ctrl+K",
            "justice_easter_egg_shortcut": "Ctrl+J",
            "constitutional_bar_pass02": True,
            "privacy_overlay": True,
            "keyboard_shortcuts_overlay": True,
            "command_palette_grouped": True,
            "record_drilldown_chat_cards_v450": True,
            "hyphen_aware_record_search_v530": True,
            "duplicate_evidence_collapse_v530": True,
            "brand_kit": "assets/brand/focaf_family_law_llm_brand_kit",
            "appeals_test_question": "What court handles appeals?",
            "workbench_url": "/",
            "review_required": True,
            "not_legal_advice": True,
            "active_case_label": case_summary["label"] if case_summary else "",
            "registered_case_count": len(list_registered_case_roots()),
        }

    def _case_id(case_root: Path) -> str:
        return hashlib.sha256(str(case_root.resolve()).encode("utf-8")).hexdigest()[:16]

    def _public_case_summary(summary: dict[str, Any]) -> dict[str, Any]:
        return {
            "case_id": _case_id(Path(str(summary["case_root"]))),
            "label": summary["label"],
            "indexed_records": summary["indexed_records"],
            "pdf_pages": summary["pdf_pages"],
            "active": bool(summary.get("active")),
            "registered_at": summary.get("registered_at", ""),
            "last_selected_at": summary.get("last_selected_at", ""),
        }

    def _resolve_case_id(case_id: str) -> Path | None:
        for summary in list_registered_case_roots():
            root = Path(str(summary["case_root"]))
            if _case_id(root) == case_id:
                return root
        return None

    def _active_case_chat_payload(
        payload: AskRequest, *, finalize: bool = True
    ) -> dict[str, Any] | None:
        case_root = active_case_root()
        if case_root is None:
            return None
        records = load_case_search_records(case_root)
        if not records:
            return None
        case_summary = describe_case_root(case_root)
        answer_payload = answer_case_question(case_root, payload.question, role="court")
        grounded = answer_payload["direct_answer"] != "not found in the indexed corpus."
        answer_text = answer_payload["direct_answer"]
        direct_search = is_direct_content_search(payload.question)
        if direct_search:
            citations = list(answer_payload.get("citations", []))
            summary = dict(answer_payload.get("search_summary") or {})
            target = str(summary.get("search_target") or payload.question).strip()
            match_count = int(summary.get("result_count") or len(citations))
            exact_phrase = int(summary.get("exact_phrase") or 0)
            exact_token = int(summary.get("exact_token") or 0)
            related = int(summary.get("related") or 0)
            ocr_count = int(summary.get("ocr_derived") or 0)
            document_count = int(summary.get("document_count") or 0)
            page_count = int(summary.get("page_count") or 0)
            lines = ["Search result:"]
            if exact_phrase:
                lines.append(
                    f'- Exact phrase "{target}": {exact_phrase} match'
                    + ("es." if exact_phrase != 1 else ".")
                )
            elif exact_token:
                lines.append(
                    f'- Exact word/term match for "{target}": {exact_token} record'
                    + ("s." if exact_token != 1 else ".")
                )
            elif related:
                lines.append(
                    f'- No exact phrase or word match for "{target}"; {related} FTS-related result'
                    + ("s were returned." if related != 1 else " was returned.")
                )
            else:
                lines.append(
                    f'- No searchable content match for "{target}" in the selected matter.'
                )
            if match_count:
                detail = f"- {match_count} result" + ("s" if match_count != 1 else "")
                if document_count:
                    detail += f" across {document_count} document" + (
                        "s" if document_count != 1 else ""
                    )
                if page_count:
                    detail += f" and {page_count} page" + ("s" if page_count != 1 else "")
                lines.append(detail + ".")
                lines.append(
                    "- Open the source cards to review the locator, page, match type, and surrounding snippet."
                )
            if ocr_count:
                lines.append(
                    f"- {ocr_count} result"
                    + ("s were" if ocr_count != 1 else " was")
                    + " derived from local OCR and should be checked against the page image."
                )
            answer_text = "\n".join(lines)
        result = {
            "question": payload.question,
            "answer_style": payload.answer_style,
            "matter_context_used": bool((payload.matter_context or "").strip()),
            "safety": {
                "category": "private_case_corpus",
                "requires_citations": True,
                "requires_disclaimer": True,
                "requires_emergency_language": False,
            },
            "answer": answer_text,
            "response_kind": "local_search_results" if direct_search else "private_record_answer",
            "search_summary": answer_payload.get("search_summary", {}),
            "direct_record_search": direct_search,
            "grounded": grounded,
            "failure_class": "none" if grounded else "not_found_in_indexed_case_corpus",
            "recovery_hint": "Switch the active corpus, broaden the question, or inspect the case search portal if the answer stayed empty.",
            "citations": answer_payload.get("citations", []),
            "source_card_count": len(answer_payload.get("citations", [])),
            "review_required": True,
            "not_legal_advice": True,
            "corpus_mode": "active_case_corpus",
            "active_case_label": case_summary["label"],
            "metadata": {
                "active_case_label": case_summary["label"],
                "indexed_records": case_summary["indexed_records"],
                "pdf_pages": case_summary["pdf_pages"],
                "missing_information": []
                if grounded
                else ["Confirm the right client/family corpus is active for this install."],
                "follow_up_questions": []
                if grounded
                else ["Do you need to switch to another family or client corpus first?"],
                "intake": _parse_payload_intake(payload).to_dict(),
            },
        }
        # Always group record cards for private-corpus responses so the UI can render
        # clickable drill-down cards instead of repeating raw snippet text.
        result["record_groups"] = _group_record_cards(case_root, list(result["citations"]))
        result["search_summary"] = dict(result["search_summary"]) | {
            "unique_document_count": len(result["record_groups"])
        }
        if direct_search:
            result["source_card_count"] = len(result["record_groups"])
        result["family_printables"] = (
            suggest_printables(payload.question) if not direct_search else []
        )
        return _finalize_family_response(result, payload) if finalize else result

    SEARCH_MODES = {"maine_law", "my_records", "both"}

    ANSWER_STYLES = {
        "plain_language",
        "checklist",
        "source_first",
        "research_brief",
        "intake",
        "professional_boundary",
        "source_card_table",
        "questions_to_ask",
        "missing_information",
    }

    def _normalize_answer_style(value: str) -> str:
        style = str(value or "plain_language").strip().lower()[:80]
        return style if style in ANSWER_STYLES else "plain_language"

    _RETRIEVAL_GENERIC_TOKENS = {
        "all",
        "and",
        "answer",
        "do",
        "give",
        "it",
        "legal",
        "me",
        "now",
        "outcome",
        "please",
        "tell",
        "that",
        "the",
        "this",
        "what",
    }

    def _retrieval_query_has_substance(value: str) -> bool:
        tokens = {
            token.casefold()
            for token in re.findall(r"[A-Za-z0-9'-]+", str(value or ""))
            if len(token) > 1
        }
        return bool(tokens - _RETRIEVAL_GENERIC_TOKENS)

    def _normalize_search_mode(value: str) -> str:
        mode = str(value or "maine_law").strip().lower()
        return mode if mode in SEARCH_MODES else "maine_law"

    def _authority_result_snippet(
        text: str,
        *,
        source_span: dict[str, Any],
        matched_terms: Iterable[str],
    ) -> str:
        text = str(text or "")
        start = source_span.get("start_offset")
        end = source_span.get("end_offset")
        if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(text):
            return " ".join(text[start:end].split())[:1200]
        folded = text.casefold()
        positions = [
            folded.find(str(term).casefold())
            for term in sorted(matched_terms, key=lambda value: len(str(value)), reverse=True)
            if len(str(term).strip()) > 2
        ]
        position = next((value for value in positions if value >= 0), 0)
        start = max(0, position - 180)
        end = min(len(text), position + 820)
        return " ".join(text[start:end].split())[:1200]

    def _retrieve_official_authority(query: str, *, limit: int = 5) -> RetrievalResponse:
        """Adapt the admitted external authority product to the public answer contract."""

        def development_fixture_fallback() -> RetrievalResponse | None:
            if str(os.environ.get("MFL_RUNTIME_MODE") or "source").strip().lower() == "store":
                return None
            response = retrieve_fixture_sources(expand_query_for_library(query), limit=limit)
            return RetrievalResponse(
                query=response.query,
                results=response.results,
                failure_class=response.failure_class,
                recovery_hint=response.recovery_hint,
                confidence=response.confidence,
                diagnostics={
                    **dict(response.diagnostics or {}),
                    "authority_product_active": False,
                    "fixture_fallback_used": True,
                    "development_only": True,
                    "human_review_required": True,
                },
            )

        runtime_mode = str(os.environ.get("MFL_RUNTIME_MODE") or "source").strip().lower()
        if runtime_mode != "store" and os.environ.get("MFL_USE_ACTIVE_AUTHORITY_IN_SOURCE") != "1":
            development_response = development_fixture_fallback()
            if development_response is not None:
                return development_response

        try:
            authority_service = AuthorityProductService()
            payload = authority_service.search(query, limit=limit)
        except Exception:
            development_response = development_fixture_fallback()
            if development_response is not None:
                return development_response
            return RetrievalResponse(
                query=query,
                results=(),
                failure_class="official_authority_product_unavailable",
                recovery_hint=(
                    "The verified local Maine authority product is unavailable. "
                    "Open Authority status, restore or update the approved external authority data, and retry."
                ),
                confidence="none",
                diagnostics={
                    "authority_product_active": False,
                    "fixture_fallback_used": False,
                    "human_review_required": True,
                },
            )
        if payload.get("status") != "pass":
            development_response = development_fixture_fallback()
            if development_response is not None:
                return development_response
            return RetrievalResponse(
                query=query,
                results=(),
                failure_class="official_authority_product_unavailable",
                recovery_hint=(
                    "The verified local Maine authority product is not active. "
                    "Open Authority status, repair the approved source product, and retry."
                ),
                confidence="none",
                diagnostics={
                    "authority_product_active": False,
                    "fixture_fallback_used": False,
                    "blockers": list(payload.get("blockers") or []),
                    "human_review_required": True,
                },
            )

        resolution_by_source: dict[str, dict[str, Any]] = {}
        citation_context = list(payload.get("citation_resolution_context") or [])
        for resolution in citation_context:
            if resolution.get("status") == "found" and resolution.get("source_id"):
                resolution_by_source[str(resolution["source_id"])] = resolution

        results: list[SearchResult] = []
        for row in list(payload.get("retrieved_sources") or [])[: max(1, min(limit, 20))]:
            document = dict(row.get("document") or {})
            card = dict(row.get("source_card") or {})
            source_id = str(row.get("source_id") or document.get("source_id") or "")
            resolution = resolution_by_source.get(source_id, {})
            resolution_metadata = dict(resolution.get("metadata") or {})
            document_metadata = dict(document.get("metadata") or {})
            span = dict(
                resolution_metadata.get("source_span")
                or card.get("source_span")
                or document_metadata.get("source_span")
                or {}
            )
            citation_data = dict(resolution.get("citation") or {})
            citation = str(
                citation_data.get("normalized")
                or document.get("citation")
                or card.get("citation")
                or "Official Maine authority"
            )
            raw_title = str(document.get("title") or card.get("title") or citation)
            title = raw_title if len(raw_title) <= 240 else citation
            matched_terms = tuple(str(value) for value in row.get("matched_terms") or [])
            metadata = {
                **document_metadata,
                "source_lane": "legal_authority",
                "official": True,
                "jurisdiction": str(document.get("jurisdiction") or "Maine"),
                "source_type": str(document.get("source_class") or "official_authority"),
                "source_class": str(document.get("source_class") or "official_authority"),
                "authority_status": str(
                    resolution.get("authority_status")
                    or document.get("authority_status")
                    or "verified_official_maine"
                ),
                "freshness_status": str(
                    resolution_metadata.get("freshness_status")
                    or document.get("freshness_status")
                    or "unknown"
                ),
                "official_url": document.get("url_or_path") or card.get("url_or_path"),
                "source_hash": resolution_metadata.get("source_hash")
                or document_metadata.get("hash")
                or card.get("hash_value"),
                "hash": resolution_metadata.get("source_hash")
                or document_metadata.get("hash")
                or card.get("hash_value"),
                "source_span": span,
                "start_offset": span.get("start_offset"),
                "end_offset": span.get("end_offset"),
                "build_id": payload.get("build_id"),
                "exact_source_span": bool(span),
                "fixture_fallback_used": False,
                "review_required": True,
                "proposition": "Supports a review-required statement from admitted official Maine authority.",
            }
            exact_preview = ""
            if resolution and isinstance(span.get("start_offset"), int) and isinstance(span.get("end_offset"), int):
                try:
                    span_payload = authority_service.get_source_span(
                        source_id,
                        start_offset=int(span["start_offset"]),
                        end_offset=int(span["end_offset"]),
                    )
                    if span_payload.get("status") == "pass":
                        exact_preview = str(span_payload.get("source_span_preview") or "")
                except Exception:
                    exact_preview = ""
            results.append(
                SearchResult(
                    chunk_id=str(document.get("chunk_id") or f"{source_id}:authority"),
                    source_id=source_id,
                    score=float(row.get("score") or 0.0),
                    title=title,
                    citation=citation,
                    snippet=(
                        " ".join(exact_preview.split())[:1200]
                        if exact_preview
                        else _authority_result_snippet(
                            str(document.get("text") or ""),
                            source_span=span,
                            matched_terms=matched_terms,
                        )
                    ),
                    metadata=metadata,
                    matched_terms=matched_terms,
                    lexical_coverage=0.0,
                    exact_reference_match=str(row.get("method") or "") == "admitted_exact_citation",
                    source_class=str(document.get("source_class") or "official_authority"),
                )
            )

        exact_not_found = bool(citation_context) and not any(
            item.get("status") == "found" for item in citation_context
        )
        if exact_not_found:
            results = []
        failure_class = (
            "exact_reference_not_found"
            if exact_not_found
            else ("no_sources_found" if not results else "none")
        )
        return RetrievalResponse(
            query=query,
            results=tuple(results),
            failure_class=failure_class,
            recovery_hint=(
                "Verify the citation against an official Maine source and refresh the authority product."
                if exact_not_found
                else ("Use a more specific Maine legal issue, citation, rule, case, or form ID." if not results else "")
            ),
            confidence="high" if results and not exact_not_found else "none",
            diagnostics={
                "authority_product_active": True,
                "authority_build_id": payload.get("build_id"),
                "fixture_fallback_used": False,
                "citation_resolution_context": citation_context,
                "result_count": len(results),
                "human_review_required": True,
            },
        )

    def _general_law_payload(
        payload: AskRequest,
        *,
        finalize: bool = True,
    ) -> dict[str, Any]:
        question = (payload.question or "").strip()
        prompt_findings = _prompt_injection_scanner.scan_user_prompt(question)
        retrieval_question = (
            _prompt_injection_scanner.sanitize_user_prompt_for_retrieval(question)
            if prompt_findings
            else question
        )
        query_text = retrieval_question

        if payload.matter_context.strip():
            query_text = f"{retrieval_question}\n\nContext: {payload.matter_context.strip()}"

        safety_text = question
        if payload.matter_context.strip():
            safety_text += f"\n\nContext: {payload.matter_context.strip()}"
        safety = classify_prompt(safety_text)
        intake = _parse_payload_intake(payload)

        if prompt_findings and not _retrieval_query_has_substance(retrieval_question):
            result = {
                "question": question,
                "answer_style": payload.answer_style,
                "search_mode": "maine_law",
                "response_kind": "family_answer",
                "intake": intake.to_dict(),
                "intake_label": concise_intake_label(intake),
                "matter_context_used": bool(payload.matter_context.strip()),
                "safety": safety.to_dict(),
                "answer": (
                    "The instruction-override language was ignored, and no specific Maine family-law question remained for source retrieval. "
                    "State the legal issue, court paper, order paragraph, or process question you want reviewed."
                ),
                "grounded": False,
                "failure_class": "substantive_question_required_after_prompt_sanitization",
                "recovery_hint": "Ask a concrete Maine family-law question without instructions to bypass sources, safety, or review.",
                "citations": [],
                "review_required": True,
                "metadata": {
                    "record_lane": False,
                    "legal_authority_lane": True,
                    "intake": intake.to_dict(),
                    "retrieval_query_sanitized": True,
                    "retrieval_query_retained": False,
                },
            }
            return _finalize_family_response(result, payload) if finalize else result

        retrieval = _retrieve_official_authority(query_text)

        exact_results = [
            item
            for item in retrieval.results
            if item.exact_reference_match
            and retrieval.diagnostics.get("authority_product_active") is True
            and retrieval.diagnostics.get("fixture_fallback_used") is not True
        ]
        retrieval_blocked = retrieval.failure_class in {
            "exact_reference_not_found",
            "official_authority_product_unavailable",
        } or (retrieval.failure_class != "none" and safety.requires_citations)
        if retrieval_blocked:
            answer_payload = {
                "answer": (
                    "I cannot answer this legal-source question substantively because the requested "
                    "authority was not resolved in the verified active Maine authority product. "
                    "No bundled fixture or model memory was substituted."
                ),
                "grounded": False,
                "failure_class": retrieval.failure_class,
                "recovery_hint": retrieval.recovery_hint,
                "review_required": True,
                "source_card_count": 0,
                "citations": [],
                "metadata": {
                    "answer_strategy": "fail_closed_authority_retrieval",
                    "fixture_fallback_used": False,
                },
            }
        elif exact_results:
            primary = exact_results[0]
            freshness = str(primary.metadata.get("freshness_status") or "unknown").replace("_", " ")
            answer_payload: dict[str, Any] = {
                "answer": (
                    f"The active official Maine authority product resolves {primary.citation}. "
                    "The exact retrieved source span reads:\n\n"
                    f"“{primary.snippet}”\n\n"
                    f"Freshness status: {freshness}. Review the exact source card and official page "
                    "before relying on this passage. This is legal information, not legal advice."
                ),
                "grounded": True,
                "failure_class": "none",
                "recovery_hint": "",
                "review_required": True,
                "source_card_count": len(retrieval.results),
                "citations": [item.to_dict() for item in retrieval.results],
                "metadata": {
                    "answer_strategy": "exact_admitted_authority_span",
                    "authority_build_id": primary.metadata.get("build_id"),
                    "exact_source_span": True,
                },
            }
        else:
            answer = compose_answer(
                retrieval_question or question,
                retrieval.results,
                safety,
                answer_style=payload.answer_style,
                matter_context=payload.matter_context,
            )
            answer_payload = answer.to_dict()

        result = {
            "question": question,
            "answer_style": payload.answer_style,
            "search_mode": "maine_law",
            "response_kind": "family_answer",
            "intake": intake.to_dict(),
            "intake_label": concise_intake_label(intake),
            "matter_context_used": bool(payload.matter_context.strip()),
            "safety": safety.to_dict(),
            **answer_payload,
        }

        if retrieval.failure_class != "none" and not result.get("grounded"):
            result["failure_class"] = retrieval.failure_class
            result["recovery_hint"] = retrieval.recovery_hint

        result["source_card_count"] = len(result.get("citations", []))
        result["corpus_mode"] = "general_maine_law"

        metadata = dict(result.get("metadata") or {})
        metadata.update(
            {
                "record_lane": False,
                "legal_authority_lane": True,
                "intake": intake.to_dict(),
                "retrieval_query_sanitized": bool(prompt_findings),
                "retrieval_query_retained": bool(retrieval_question),
                "retrieval_confidence": retrieval.confidence,
                "retrieval_diagnostics": dict(retrieval.diagnostics or {}),
                "retrieval_failure_class": retrieval.failure_class,
            }
        )
        result["retrieval_diagnostics"] = dict(retrieval.diagnostics or {})
        result["retrieval_confidence"] = retrieval.confidence
        result["metadata"] = metadata
        result["family_printables"] = suggest_printables(retrieval_question or question)

        return _finalize_family_response(result, payload) if finalize else result

    def _annotate_source_lanes(citations: list[dict[str, Any]], lane: str) -> list[dict[str, Any]]:
        """Make source provenance machine-readable in every response surface."""

        annotated: list[dict[str, Any]] = []
        for item in citations:
            copy = dict(item)
            metadata = dict(copy.get("metadata") or {})
            actual_lane = str(metadata.get("source_lane") or lane)
            metadata["source_lane"] = actual_lane
            if actual_lane == "legal_authority":
                metadata.setdefault("official", True)
                metadata.setdefault("jurisdiction", "Maine")
                metadata.setdefault(
                    "proposition", "Supports a statement of Maine law or court process."
                )
            else:
                metadata["official"] = False
                metadata.setdefault(
                    "proposition",
                    "Shows text from the active private matter only; it is not legal authority and does not prove a disputed fact.",
                )
            copy["metadata"] = metadata
            annotated.append(copy)
        return annotated

    def _annotate_instruction_boundaries(
        citations: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Mark instruction-like retrieved text as untrusted document content.

        Source text is never allowed to alter routing, safety rules, or source
        precedence. The original snippet remains visible for evidentiary review;
        the metadata adds a machine-readable warning instead of silently editing
        a user's record.
        """

        annotated: list[dict[str, Any]] = []
        warnings: list[str] = []
        for item in citations:
            copy = dict(item)
            metadata = dict(copy.get("metadata") or {})
            lane = str(metadata.get("source_lane") or "legal_authority")
            metadata["trust_boundary"] = (
                "private_record_text_is_untrusted_data_not_instructions"
                if lane == "private_record"
                else "retrieved_legal_text_is_source_data_not_instructions"
            )
            snippet = str(copy.get("snippet") or metadata.get("text_excerpt") or "")
            findings = _prompt_injection_scanner.scan_document_text(snippet)
            if findings:
                metadata["instruction_like_text_detected"] = True
                metadata["instruction_like_findings"] = [finding.kind for finding in findings]
                warnings.append(
                    "One or more source cards contain instruction-like text. Treat that text only as record or source content; it cannot change app rules."
                )
            else:
                metadata["instruction_like_text_detected"] = False
            copy["metadata"] = metadata
            annotated.append(copy)
        return annotated, list(dict.fromkeys(warnings))

    def _dedupe_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keep one useful card per legal source and per private-record locator.

        Legal retrieval often returns multiple chunks from the same statute or
        guide.  Repeating the same source card makes an answer look better
        grounded than it is.  Private records remain page/member-specific so a
        user can still inspect each distinct local match.
        """

        deduped: list[dict[str, Any]] = []
        seen: set[tuple[object, ...]] = set()
        for item in citations:
            metadata = dict(item.get("metadata") or {})
            lane = str(metadata.get("source_lane") or "legal_authority")
            source_id = str(item.get("source_id") or metadata.get("id") or "")
            if lane == "private_record":
                key: tuple[object, ...] = (
                    lane,
                    source_id,
                    str(metadata.get("source_locator") or ""),
                    int(metadata.get("page_number") or 0),
                )
            else:
                key = (
                    lane,
                    source_id
                    or str(item.get("citation") or metadata.get("citation_hint") or "")
                    or str(item.get("title") or metadata.get("title") or ""),
                )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _first_answer_paragraph(value: str, limit: int = 900) -> str:
        text = str(value or "").strip()
        text = text.split("Citation appendix:", 1)[0].strip()
        paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
        if not paragraphs:
            return "No substantive answer was established."
        return paragraphs[0][:limit]

    def _attach_local_agent_disclosure(
        result: dict[str, Any],
        payload: AskRequest,
        citations: list[dict[str, Any]],
        metadata: dict[str, Any],
    ) -> None:
        """Attach an exact local-context manifest and hash-bound host receipt.

        Nothing is transmitted by this step.  The manifest is the visible packet
        a user may later approve for a loopback-only local model run.
        """

        run_id = str(result.get("search_id") or result.get("request_id") or uuid.uuid4().hex)
        manifest, receipt = build_host_context_and_receipt(
            question=str(result.get("question") or payload.question),
            answer=str(result.get("answer") or ""),
            cards=citations,
            run_id=run_id,
            retrieval_diagnostics=dict(
                result.get("retrieval_diagnostics") or metadata.get("retrieval_diagnostics") or {}
            ),
        )
        result["context_manifest"] = manifest
        result["provenance_receipt"] = receipt
        result["local_agent_available"] = bool(manifest.get("entry_count"))
        result["local_agent_policy"] = {
            "enabled_by_default": False,
            "loopback_only": True,
            "remote_providers_enabled": False,
            "exact_manifest_approval_required": True,
            "source_text_is_untrusted_data": True,
            "review_required": True,
        }
        metadata["context_manifest"] = manifest
        metadata["provenance_receipt"] = receipt

    def _finalize_family_response(result: dict[str, Any], payload: AskRequest) -> dict[str, Any]:
        """Attach the canonical v3 answer contract and derive the legacy text from it."""

        mode = _normalize_search_mode(str(result.get("search_mode") or payload.search_mode))
        raw_citations = _attach_record_open_capabilities(
            active_case_root(), list(result.get("citations") or [])
        )
        citations = _redact_citation_paths(raw_citations)
        default_lane = "private_record" if mode == "my_records" else "legal_authority"
        citations = _dedupe_citations(_annotate_source_lanes(citations, default_lane))
        citations = annotate_grounding_metadata(citations)
        citations, document_security_warnings = _annotate_instruction_boundaries(citations)
        grounding_integrity = assess_grounding_integrity(citations, search_mode=mode)
        metadata = dict(result.get("metadata") or {})
        existing_intake = (
            result.get("intake")
            or metadata.get("intake")
            or (result.get("structured_answer") or {}).get("intake")
        )
        intake = (
            IntakeSummary.from_dict(existing_intake)
            if isinstance(existing_intake, dict) and existing_intake
            else _parse_payload_intake(payload)
        )
        metadata.setdefault("intake", intake.to_dict())
        prompt_findings = _prompt_injection_scanner.scan_user_prompt(payload.question)
        security_warnings = list(document_security_warnings)
        if prompt_findings:
            security_warnings.append(
                "Instruction-override language in the current prompt was ignored; it cannot change source, privacy, safety, or review requirements."
            )
        metadata["security_warnings"] = list(dict.fromkeys(security_warnings))
        metadata["prompt_injection_findings"] = [finding.kind for finding in prompt_findings]
        metadata["instruction_like_source_card_count"] = sum(
            1
            for item in citations
            if bool((item.get("metadata") or {}).get("instruction_like_text_detected"))
        )
        metadata["grounding_integrity"] = grounding_integrity
        input_integrity = dict(payload.input_integrity or {})
        metadata["input_integrity"] = input_integrity
        integrity_flags = set(input_integrity.get("security_flags") or [])
        if integrity_flags:
            metadata["security_warnings"] = list(
                dict.fromkeys(
                    [
                        *metadata["security_warnings"],
                        "Invisible controls, invalid identifiers, or oversized input were neutralized at the local request boundary. Review the normalized question before relying on the answer.",
                    ]
                )
            )
        answer_support_integrity = assess_answer_support_integrity(
            str(result.get("answer") or ""),
            citations,
            grounding_integrity=grounding_integrity,
        )
        metadata["answer_support_integrity"] = answer_support_integrity
        handoff_safe_source_cards = build_handoff_safe_source_cards(citations)
        metadata["handoff_integrity"] = {
            "schema_version": "handoff_integrity_v1",
            "default_export_is_redacted": True,
            "source_card_count": len(handoff_safe_source_cards),
            "private_record_content_omitted_count": sum(
                1
                for item in handoff_safe_source_cards
                if bool((item.get("metadata") or {}).get("private_content_omitted_by_default"))
            ),
        }
        lane_grounding = {
            "legal_authority": bool(citations) if mode == "maine_law" else False,
            "private_record": bool(citations) if mode == "my_records" else False,
        }
        if mode == "both":
            legal_count = int(metadata.get("legal_source_count") or 0)
            record_count = int(metadata.get("record_source_count") or 0)
            lane_grounding = {
                "legal_authority": legal_count > 0,
                "private_record": record_count > 0,
            }
        contract = build_family_answer_contract(
            question=str(result.get("question") or payload.question),
            legacy_answer=str(result.get("answer") or ""),
            citations=citations,
            search_mode=mode,
            safety=dict(result.get("safety") or {}),
            missing_information=metadata.get("missing_information") or [],
            follow_up_questions=metadata.get("follow_up_questions") or [],
            recommended_next_steps=metadata.get("recommended_next_steps") or [],
            child_impact_enabled=bool(payload.child_impact_lens),
            lane_grounding=lane_grounding,
            intake=intake,
            response_kind=str(
                result.get("response_kind")
                or (
                    "local_search_results"
                    if result.get("direct_record_search")
                    else "family_answer"
                )
            ),
            answer_style=payload.answer_style,
            grounding_integrity=grounding_integrity,
            answer_support_integrity=answer_support_integrity,
        )
        result["citations"] = citations
        result["handoff_safe_source_cards"] = handoff_safe_source_cards
        result["answer_support_integrity"] = answer_support_integrity
        result["request_integrity"] = input_integrity
        result["source_card_count"] = len(citations)
        result["security_warnings"] = metadata["security_warnings"]
        result["grounding_integrity"] = grounding_integrity
        result["current_law_verified"] = bool(grounding_integrity.get("current_law_verified"))
        if (
            result.get("direct_record_search")
            or str(result.get("response_kind") or "") == "corpus_inventory"
        ):
            result["structured_answer"] = contract
            result["intake"] = intake.to_dict()
            result["intake_label"] = concise_intake_label(intake)
            result["source_lanes"] = lane_grounding
            result["metadata"] = metadata
            _attach_local_agent_disclosure(result, payload, citations, metadata)
            return _remember_record_search(payload, result)
        result["structured_answer"] = contract
        result["answer"] = render_legacy_answer(contract)
        result["source_lanes"] = contract["lane_grounding"]
        result["metadata"] = metadata
        _attach_local_agent_disclosure(result, payload, citations, metadata)
        return _remember_record_search(payload, result)

    @app.exception_handler(Exception)
    async def json_exception_handler(request: Request, exc: Exception) -> JSONResponse:  # type: ignore[type-arg]
        request_id = str(getattr(request.state, "request_id", "") or uuid.uuid4().hex)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "internal_server_error",
                "message": "The local workbench could not complete this request.",
                "request_id": request_id,
                "recovery_hint": "Restart START_LOCAL_CHAT.ps1, refresh the browser, and retry. If this persists, include the request ID in the issue report.",
            },
        )

    @app.get("/", response_class=HTMLResponse)
    def local_chat_workbench() -> str:
        return render_local_workbench_html()

    @app.get("/workbench", response_class=HTMLResponse)
    def workbench() -> str:
        return render_local_workbench_html()

    @app.post("/api/chat")
    def api_chat(payload: AskRequest) -> dict[str, Any]:
        return ask(payload)

    @app.post("/api/ask")
    def api_ask(payload: AskRequest) -> dict[str, Any]:
        return ask(payload)

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return _health_payload()

    @app.get("/api/health")
    def api_health() -> dict[str, Any]:
        return _health_payload()

    @app.get("/api/local-agent/status")
    def local_agent_status() -> dict[str, Any]:
        return {
            "schema_version": "local_agent_status_v1",
            "enabled_by_default": False,
            "loopback_only": True,
            "literal_loopback_ip_required": True,
            "remote_providers_enabled": False,
            "supported_providers": [
                {
                    "provider_id": "ollama",
                    "default_endpoint": "http://127.0.0.1:11434",
                    "default_model": "qwen2.5:7b",
                },
                {
                    "provider_id": "openai_compatible_local",
                    "default_endpoint": "http://127.0.0.1:1234",
                    "default_model": "local-model",
                },
            ],
            "exact_manifest_approval_required": True,
            "review_required": True,
        }

    def _local_agent_runtime_from_request(payload: LocalAgentPreviewRequest) -> LocalAgentRuntime:
        try:
            client = build_local_client(
                provider=payload.provider,
                endpoint=payload.endpoint,
                model_name=payload.model,
                timeout_seconds=120,
            )
        except (ValueError, LocalModelError) as exc:
            detail = getattr(exc, "code", None) or str(exc)
            raise HTTPException(
                status_code=400, detail={"error": detail, "loopback_only": True}
            ) from exc
        return LocalAgentRuntime(client)

    @app.post("/api/local-agent/preview")
    def local_agent_preview(payload: LocalAgentPreviewRequest) -> dict[str, Any]:
        sources = context_sources_from_cards(source_cards_from_payload(payload.source_cards))
        if not sources:
            raise HTTPException(
                status_code=400, detail={"error": "local_agent_context_sources_required"}
            )
        runtime = _local_agent_runtime_from_request(payload)
        try:
            manifest, _, injection_report = runtime.preview(
                question=payload.question,
                sources=sources,
                run_id=payload.run_id or uuid.uuid4().hex,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc
        return {
            "schema_version": "local_agent_preview_response_v1",
            "status": "approval_required",
            "context_manifest": manifest.to_dict(),
            "injection_report": injection_report,
            "model": {
                "provider_id": runtime.client.provider_id,
                "model_id": runtime.client.model_name,
                "endpoint_class": runtime.client.endpoint.endpoint_class,
                "endpoint_host": runtime.client.endpoint.host,
                "endpoint_port": runtime.client.endpoint.port,
                "loopback_only": True,
            },
            "source_cards": source_cards_from_payload(payload.source_cards),
            "review_required": True,
        }

    @app.post("/api/local-agent/run")
    def local_agent_run(payload: LocalAgentExecuteRequest) -> dict[str, Any]:
        if payload.tool_invocations:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "local_agent_ui_tool_execution_not_enabled",
                    "message": "The browser flow uses approved source context only. Host tools require a separately registered handler.",
                },
            )
        sources = context_sources_from_cards(source_cards_from_payload(payload.source_cards))
        if not sources:
            raise HTTPException(
                status_code=400, detail={"error": "local_agent_context_sources_required"}
            )
        runtime = _local_agent_runtime_from_request(payload)
        request = LocalAgentRunRequest(
            question=payload.question,
            sources=sources,
            approved_manifest_sha256=payload.approved_manifest_sha256,
            matter_id=payload.matter_id or None,
            tool_invocations=tuple(
                ToolInvocation(str(item.get("name") or ""), dict(item.get("args") or {}))
                for item in payload.tool_invocations
                if isinstance(item, dict)
            ),
            permitted_tools=frozenset(payload.permitted_tools),
            retrieval_diagnostics=dict(payload.retrieval_diagnostics or {}),
            run_id=payload.run_id or uuid.uuid4().hex,
        )
        result = runtime.run(request)
        if result.status == "blocked":
            raise HTTPException(status_code=409, detail=result.to_dict())
        return {
            **result.to_dict(),
            "citations": source_cards_from_payload(payload.source_cards),
            "local_agent_result": True,
            "grounded": bool(result.context_manifest.entries),
            "source_card_count": len(result.context_manifest.entries),
        }

    @app.post("/api/session/clear")
    def clear_chat_session(payload: ClearSessionRequest) -> dict[str, Any]:
        key = _session_key(
            AskRequest(question="session-clear", session_id=str(payload.session_id or ""))
        )
        cleared = False
        if key:
            with _recent_search_lock:
                _prune_recent_sources()
                cleared = _recent_record_searches.pop(key, None) is not None
        return {
            "status": "cleared",
            "session_state_removed": cleared,
            "local_only": True,
            "persisted_to_disk": False,
        }

    @app.get("/api/version")
    def api_version() -> dict[str, str]:
        return {"version": __version__, "api_mode": "local-workbench", "workbench_url": "/"}

    @app.get("/api/authority/status")
    def local_authority_status() -> dict[str, Any]:
        return AuthorityLibraryService().status()

    @app.get("/api/authority/builds")
    def local_authority_builds(limit: int = 20) -> dict[str, Any]:
        return AuthorityLibraryService().list_builds(limit=limit)

    @app.get("/api/authority/sources")
    def local_authority_sources(
        query: str = "",
        source_class: str = "",
        freshness: str = "",
        issue_tag: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        return AuthorityLibraryService().list_sources(
            query=query,
            source_class=source_class,
            freshness=freshness,
            issue_tag=issue_tag,
            limit=limit,
            offset=offset,
        )

    @app.get("/api/authority/sources/{source_id}")
    def local_authority_source(source_id: str) -> dict[str, Any]:
        return AuthorityLibraryService().get_source(source_id)

    @app.get("/api/authority/sources/{source_id}/span")
    def local_authority_source_span(
        source_id: str,
        start_offset: int | None = None,
        end_offset: int | None = None,
    ) -> dict[str, Any]:
        return AuthorityLibraryService().get_source_span(
            source_id, start_offset=start_offset, end_offset=end_offset
        )

    @app.get("/api/authority/update-report/{build_id}")
    def local_authority_update_report(build_id: str) -> dict[str, Any]:
        return AuthorityLibraryService().get_update_report(build_id)

    class AuthorityUpdateRequest(BaseModel):
        dry_run: StrictBool = False
        fixture_mode: StrictBool = False
        allow_live: StrictBool = False
        force_refresh: StrictBool = False
        source_classes: list[str] = Field(default_factory=list)
        max_targets: int | None = None

    @app.post("/api/authority/update")
    def local_authority_update(payload: AuthorityUpdateRequest) -> dict[str, Any]:
        return AuthorityLibraryService().update(
            dry_run=bool(payload.dry_run),
            source_classes=payload.source_classes,
            fixture_mode=bool(payload.fixture_mode),
            force_refresh=bool(payload.force_refresh),
            allow_live=bool(payload.allow_live),
            max_targets=payload.max_targets,
        )

    @app.post("/api/authority/update/cancel")
    def local_authority_update_cancel(payload: dict | None = None) -> dict[str, Any]:
        job_id = str((payload or {}).get("job_id") or "").strip() or None
        return AuthorityLibraryService().cancel_update(job_id)

    @app.post("/api/authority/verify-answer")
    def verify_answer_against_active_authority(
        payload: AuthorityVerifyAnswerRequest,
    ) -> dict[str, Any]:
        text_result = harden_text_input(payload.text, max_length=200_000, preserve_newlines=True)
        try:
            result = AuthorityProductService().verify_output(
                text=text_result.value,
                source_ids=payload.source_ids,
                quotes=payload.quotes,
                claims=payload.claims,
                expected_jurisdiction=str(payload.expected_jurisdiction or "maine")[:64],
                auto_extract_claims=bool(payload.auto_extract_claims),
            )
        except (FileNotFoundError, ValueError, OSError):
            result = {
                "status": "blocked",
                "blockers": ["active_authority_product_unavailable_or_unverified"],
                "review_required": True,
            }
        result["request_integrity"] = text_result.report()
        return result

    @app.get("/api/runtime-diagnostics")
    def runtime_diagnostics() -> dict[str, Any]:
        return _runtime_diagnostics_payload()

    def _local_workbench_service() -> LocalWorkbenchService:
        """Resolve a local-only control-plane store without disclosing its path."""

        case_root = active_case_root()
        if case_root is not None:
            return LocalWorkbenchService(case_root)
        local_base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local")
        return LocalWorkbenchService(local_base / "MaineFamilyLawLLM" / "Workbench")

    def _local_workbench_call(operation):  # type: ignore[no-untyped-def]
        try:
            return operation()
        except LocalWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc

    @app.get("/api/local-workbench/status")
    def local_workbench_status() -> dict[str, Any]:
        return _local_workbench_call(lambda: _local_workbench_service().status())

    @app.get("/api/local-workbench/readiness")
    def local_workbench_readiness() -> dict[str, Any]:
        return _local_workbench_call(lambda: _local_workbench_service().readiness())

    @app.post("/api/local-workbench/models")
    def local_workbench_register_model(payload: LocalWorkbenchModelRequest) -> dict[str, Any]:
        return _local_workbench_call(
            lambda: _local_workbench_service().register_model(payload.model_dump())
        )

    @app.post("/api/local-workbench/models/admit-artifact")
    def local_workbench_admit_artifact(
        payload: LocalWorkbenchArtifactAdmissionRequest,
    ) -> dict[str, Any]:
        return _local_workbench_call(
            lambda: _local_workbench_service().admit_local_artifact(payload.model_dump())
        )

    @app.post("/api/local-workbench/models/route")
    def local_workbench_route_model(payload: LocalWorkbenchRouteRequest) -> dict[str, Any]:
        return _local_workbench_call(
            lambda: _local_workbench_service().route_model(payload.model_dump())
        )

    @app.put("/api/local-workbench/performance-policy")
    def local_workbench_configure_performance(
        payload: LocalWorkbenchPerformancePolicyRequest,
    ) -> dict[str, Any]:
        return _local_workbench_call(
            lambda: _local_workbench_service().configure_performance_policy(payload.model_dump())
        )

    @app.post("/api/local-workbench/jobs/preflight")
    def local_workbench_preflight_job(payload: LocalWorkbenchJobPreflightRequest) -> dict[str, Any]:
        return _local_workbench_call(
            lambda: _local_workbench_service().preflight_local_job(payload.model_dump())
        )

    @app.post("/api/local-workbench/plans")
    def local_workbench_propose_plan(payload: LocalWorkbenchPlanRequest) -> dict[str, Any]:
        return _local_workbench_call(
            lambda: _local_workbench_service().propose_plan(payload.model_dump())
        )

    @app.post("/api/local-workbench/plans/{plan_id}/approve")
    def local_workbench_approve_plan(plan_id: str) -> dict[str, Any]:
        return _local_workbench_call(lambda: _local_workbench_service().approve_plan(plan_id))

    @app.put("/api/local-workbench/preferences")
    def local_workbench_preferences(payload: LocalWorkbenchPreferencesRequest) -> dict[str, Any]:
        return _local_workbench_call(
            lambda: _local_workbench_service().set_preferences(payload.preferences)
        )

    @app.put("/api/local-workbench/privacy")
    def local_workbench_privacy(payload: LocalWorkbenchPrivacyRequest) -> dict[str, Any]:
        return _local_workbench_call(
            lambda: _local_workbench_service().set_privacy(payload.privacy)
        )

    @app.post("/api/local-workbench/automations")
    def local_workbench_create_automation(
        payload: LocalWorkbenchAutomationRequest,
    ) -> dict[str, Any]:
        return _local_workbench_call(
            lambda: _local_workbench_service().create_automation(payload.model_dump())
        )

    @app.post("/api/local-workbench/automations/{automation_id}/propose-run")
    def local_workbench_propose_automation_run(automation_id: str) -> dict[str, Any]:
        return _local_workbench_call(
            lambda: _local_workbench_service().propose_automation_run(automation_id)
        )

    @app.post("/api/local-workbench/extensions")
    def local_workbench_register_extension(
        payload: LocalWorkbenchExtensionRequest,
    ) -> dict[str, Any]:
        return _local_workbench_call(
            lambda: _local_workbench_service().register_extension(payload.model_dump())
        )

    @app.post("/api/local-workbench/work-items")
    def local_workbench_create_work_item(payload: dict[str, Any]) -> dict[str, Any]:
        return _local_workbench_call(lambda: _local_workbench_service().create_work_item(payload))

    @app.post("/api/local-workbench/source-snapshots")
    def local_workbench_snapshot_source(payload: dict[str, Any]) -> dict[str, Any]:
        return _local_workbench_call(lambda: _local_workbench_service().snapshot_source(payload))

    @app.post("/api/local-workbench/source-changes/route")
    def local_workbench_route_source_changes(payload: dict[str, Any]) -> dict[str, Any]:
        return _local_workbench_call(
            lambda: _local_workbench_service().route_source_change(payload)
        )

    @app.post("/api/local-workbench/connectors")
    def local_workbench_register_connector(payload: dict[str, Any]) -> dict[str, Any]:
        return _local_workbench_call(lambda: _local_workbench_service().register_connector(payload))

    @app.post("/api/local-workbench/templates")
    def local_workbench_register_template(payload: dict[str, Any]) -> dict[str, Any]:
        return _local_workbench_call(lambda: _local_workbench_service().register_template(payload))

    @app.post("/api/local-workbench/handoffs")
    def local_workbench_prepare_handoff(payload: dict[str, Any]) -> dict[str, Any]:
        return _local_workbench_call(lambda: _local_workbench_service().prepare_handoff(payload))

    @app.get("/api/local-workbench/portable-manifest")
    def local_workbench_portable_manifest() -> dict[str, Any]:
        return _local_workbench_call(lambda: _local_workbench_service().portable_manifest())

    @app.get("/api/local-workbench/backup-restore/status")
    def local_workbench_backup_restore_status() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        return MatterBackupRestoreDrill(
            case_root, repo_root=_release_hardening_repo_root()
        ).status()

    @app.post("/api/local-workbench/backup-restore/drill")
    def local_workbench_backup_restore_drill(
        payload: ReleaseHardeningBackupDrillRequest,
    ) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return MatterBackupRestoreDrill(
                case_root, repo_root=_release_hardening_repo_root()
            ).run(approved=payload.approved)
        except ReleasePilotHardeningError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc

    @app.post("/api/local-workbench/release-evidence")
    def local_workbench_record_release_evidence(payload: dict[str, Any]) -> dict[str, Any]:
        return _local_workbench_call(
            lambda: _local_workbench_service().record_release_evidence(payload)
        )

    @app.get("/api/local-workbench/release-readiness")
    def local_workbench_release_readiness() -> dict[str, Any]:
        return _local_workbench_call(lambda: _local_workbench_service().release_readiness())

    @app.post("/api/local-workbench/evaluations")
    def local_workbench_record_evaluation(
        payload: LocalWorkbenchEvaluationRequest,
    ) -> dict[str, Any]:
        return _local_workbench_call(
            lambda: _local_workbench_service().record_evaluation(payload.model_dump())
        )

    def _case_inventory_chat_payload(payload: AskRequest) -> dict[str, Any] | None:
        case_root = active_case_root()
        if case_root is None:
            return None
        records = load_case_search_records(case_root)
        if not records:
            return None
        metrics = local_inventory_metrics(records)
        parser_statuses: dict[str, int] = {}
        source_types: dict[str, int] = {}
        document_kinds: dict[str, int] = {}
        top_level: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in records:
            parser = str(row.get("parser_status") or "unknown")
            source_type = str(row.get("source_type") or "unknown")
            kind = str(
                dict(row.get("parser_metadata") or {}).get("document_kind")
                or source_type
                or "unknown"
            )
            parser_statuses[parser] = parser_statuses.get(parser, 0) + 1
            source_types[source_type] = source_types.get(source_type, 0) + 1
            document_kinds[kind] = document_kinds.get(kind, 0) + 1
            if source_type in {"pdf_page", "image_page"}:
                continue
            evidence_id = str(row.get("evidence_id") or "")
            if not evidence_id or evidence_id in seen:
                continue
            seen.add(evidence_id)
            top_level.append(row)
        top_level.sort(
            key=lambda row: (
                str(row.get("source_type") or ""),
                str(row.get("source_locator") or row.get("title") or "").casefold(),
            )
        )
        citations: list[dict[str, Any]] = []
        for row in top_level[:24]:
            view = public_record_view(row)
            citations.append(
                {
                    "source_id": view.get("evidence_id") or "",
                    "title": view.get("title") or "Indexed record",
                    "snippet": "",
                    "metadata": {
                        **view,
                        "source_lane": "private_record",
                        "official": False,
                        "authority_status": "private_record_not_legal_authority",
                        "proposition": "Inventory entry only; open the original record before relying on its contents.",
                    },
                }
            )
        warnings = sum(
            parser_statuses.get(key, 0) for key in ("unreadable", "unsupported", "metadata_only")
        )
        names = [
            str((item.get("metadata") or {}).get("source_locator") or item.get("title") or "")
            for item in citations
        ]
        lines = [
            "Indexed corpus inventory:",
            f"- Matter: {describe_case_root(case_root)['label']}",
            f"- {len(top_level)} top-level record(s); {len(records)} total index row(s), including page and attachment rows.",
            f"- {metrics['searchable_records']} searchable record(s); {metrics['searchable_pages']} searchable page(s).",
            f"- {metrics['ocr_candidate_documents']} document(s) contain {metrics['ocr_candidate_pages']} scanned or image-only page(s) awaiting local OCR.",
            f"- {warnings} record(s) need parser or readability review.",
        ]
        if names:
            lines.append(
                "- First indexed records: "
                + "; ".join(names[:12])
                + ("; …" if len(top_level) > 12 else ".")
            )
        lines.append(
            "- Open the record source cards for the first 24 entries, or search for a word or phrase to narrow the corpus."
        )
        return {
            "question": payload.question,
            "answer_style": payload.answer_style,
            "search_mode": "my_records",
            "requested_search_mode": _normalize_search_mode(payload.search_mode),
            "response_kind": "corpus_inventory",
            "direct_record_search": False,
            "answer": "\n".join(lines),
            "grounded": True,
            "failure_class": "none",
            "recovery_hint": "Search the selected records for a specific term, or open the corpus manager to change matters.",
            "citations": citations,
            "source_card_count": len(citations),
            "review_required": True,
            "not_legal_advice": True,
            "corpus_mode": "active_case_corpus",
            "active_case_label": describe_case_root(case_root)["label"],
            "inventory_summary": {
                "records": len(records),
                "top_level_records": len(top_level),
                "source_types": dict(sorted(source_types.items())),
                "document_kinds": dict(sorted(document_kinds.items())),
                "parser_statuses": dict(sorted(parser_statuses.items())),
                **metrics,
            },
            "metadata": {
                "intake": _parse_payload_intake(payload).to_dict(),
                "record_source_count": len(citations),
                "legal_source_count": 0,
                "missing_information": [],
            },
        }

    @app.get("/sources")
    def sources() -> list[dict[str, Any]]:
        library = AuthorityLibraryService()
        if library.data_root is not None:
            sources_payload = library.list_sources(limit=200)
            if sources_payload.get("sources"):
                return list(sources_payload.get("sources") or [])
        case_root = active_case_root()
        if case_root is not None:
            records = load_case_search_records(case_root)
            if records:
                return [public_record_view(row) for row in records[:200]]
        return [entry.to_dict() for entry in load_seed_manifest()]

    @app.get("/api/corpus-library")
    def api_corpus_library() -> dict[str, Any]:
        active_case = active_case_root()
        case_summary = describe_case_root(active_case) if active_case else None
        return {
            "active_case_id": _case_id(active_case) if active_case else "",
            "active_case_label": case_summary["label"] if case_summary else "",
            "cases": [_public_case_summary(summary) for summary in list_registered_case_roots()],
        }

    @app.post("/api/activate-corpus")
    def api_activate_corpus(payload: ActivateCorpusRequest) -> dict[str, Any]:
        case_root = _resolve_case_id(payload.case_id)
        if case_root is None and payload.case_root:
            candidate = Path(payload.case_root).expanduser()
            if candidate.exists():
                case_root = candidate
        if case_root is None or not case_root.exists():
            raise HTTPException(status_code=404, detail="case_corpus_not_found")
        set_active_case_root(case_root)
        summary = describe_case_root(case_root)
        return {
            "status": "ok",
            "active_case_id": _case_id(case_root),
            "active_case_label": summary["label"],
        }

    @app.get("/api/corpus-inventory")
    def corpus_inventory() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            return {"status": "no_active_matter", "records": 0}
        records = load_case_search_records(case_root)
        parser_statuses: dict[str, int] = {}
        source_types: dict[str, int] = {}
        for row in records:
            parser_statuses[str(row.get("parser_status") or "unknown")] = (
                parser_statuses.get(str(row.get("parser_status") or "unknown"), 0) + 1
            )
            source_types[str(row.get("source_type") or "unknown")] = (
                source_types.get(str(row.get("source_type") or "unknown"), 0) + 1
            )
        inventory_metrics = local_inventory_metrics(records)
        ocr_candidates = inventory_metrics["ocr_candidate_documents"]
        ocr_candidate_pages = inventory_metrics["ocr_candidate_pages"]
        searchable_records = inventory_metrics["searchable_records"]
        searchable_pages = inventory_metrics["searchable_pages"]
        image_only_pages = ocr_candidate_pages
        document_kinds: dict[str, int] = {}
        for row in records:
            kind = str(dict(row.get("parser_metadata") or {}).get("document_kind") or "unknown")
            document_kinds[kind] = document_kinds.get(kind, 0) + 1
        warnings = sum(
            count
            for status, count in parser_statuses.items()
            if status in {"unreadable", "unsupported", "metadata_only"}
        )
        return {
            "status": "ok",
            "case_label": describe_case_root(case_root)["label"],
            "records": len(records),
            "parser_statuses": parser_statuses,
            "source_types": source_types,
            "ocr_candidates": ocr_candidates,
            "ocr_candidate_records": ocr_candidates,
            "ocr_candidate_pages": ocr_candidate_pages,
            "searchable_records": searchable_records,
            "searchable_pages": searchable_pages,
            "image_only_pages": image_only_pages,
            "document_kinds": dict(sorted(document_kinds.items())),
            "intake_parser": "deterministic_local_v2",
            "inventory_state": "ocr_choice_required"
            if ocr_candidate_pages
            else ("ready_with_warnings" if warnings else "ready"),
            "ocr_engine": local_ocr_engine_status(),
            "index": "local SQLite FTS5 when available",
            "source_evidence_modified": False,
            "local_only": True,
            "network_used": False,
        }

    def _intake_store() -> MatterIntakeStore:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return MatterIntakeStore(case_root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    def _intake_records() -> list[dict[str, Any]]:
        case_root = active_case_root()
        return list(load_case_search_records(case_root)) if case_root is not None else []

    def _intake_call(operation):  # type: ignore[no-untyped-def]
        try:
            return operation()
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.post("/api/intake/matters")
    def intake_create_matter(payload: dict[str, Any]) -> dict[str, Any]:
        """Create an encrypted, review-required intake in the selected local matter."""
        return _intake_call(lambda: _intake_store().create(payload))

    @app.get("/api/intake/matters/{matter_id}")
    def intake_get_matter(matter_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _intake_store().get(matter_id))

    @app.patch("/api/intake/matters/{matter_id}")
    def intake_update_matter(matter_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _intake_store().update(matter_id, payload))

    @app.post("/api/intake/matters/{matter_id}/classify")
    def intake_classify(matter_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _intake_store().classify(matter_id, payload))

    @app.post("/api/intake/matters/{matter_id}/posture")
    def intake_posture(matter_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _intake_store().posture(matter_id, payload))

    @app.post("/api/intake/matters/{matter_id}/issue-tree")
    def intake_issue_tree(matter_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _intake_store().issue_tree(matter_id, payload))

    @app.get("/api/intake/matters/{matter_id}/coverage")
    def intake_coverage(matter_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _intake_store().coverage(matter_id, _intake_records()))

    @app.post("/api/intake/matters/{matter_id}/complete")
    def intake_complete(matter_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _intake_store().complete(matter_id, _intake_records()))

    @app.get("/api/intake/matters/{matter_id}/receipt")
    def intake_receipt(matter_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _intake_store().receipt(matter_id))

    def _journey_store() -> MatterJourneyStore:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        return MatterJourneyStore(case_root)

    @app.get("/api/matter-journey/{matter_id}")
    def matter_journey_status(matter_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        return _intake_call(
            lambda: _journey_store().status(
                matter_id,
                corpus_metrics=local_inventory_metrics(case_root),
            )
        )

    @app.post("/api/matter-journey/{matter_id}/checkpoints")
    def matter_journey_checkpoint(matter_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _journey_store().record_checkpoint(matter_id, payload))

    def _order_store() -> OrderIntelligenceStore:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return OrderIntelligenceStore(case_root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/orders/inventory")
    def order_inventory() -> dict[str, Any]:
        return _intake_call(lambda: _order_store().inventory())

    @app.post("/api/orders")
    def order_add(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _order_store().add_orders(payload))

    @app.get("/api/orders/terms")
    def order_terms(order_id: str = "") -> dict[str, Any]:
        return _intake_call(lambda: _order_store().terms(order_id or None))

    @app.get("/api/orders/receipt")
    def order_receipt() -> dict[str, Any]:
        return _intake_call(lambda: _order_store().receipt())

    @app.get("/api/orders/{order_id}")
    def order_detail(order_id: str) -> dict[str, Any]:
        return _intake_call(
            lambda: {
                "status": "review_required",
                "review_required": True,
                "orders": _order_store().terms(order_id),
            }
        )

    @app.post("/api/orders/graph")
    def order_graph(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _order_store().graph(payload))

    @app.post("/api/orders/compare")
    def order_compare(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(
            lambda: _order_store().compare(
                str(payload.get("left_term_id") or ""), str(payload.get("right_term_id") or "")
            )
        )

    @app.post("/api/orders/operative-candidate-review")
    def order_operate_review(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _order_store().review_candidate(payload))

    @app.post("/api/orders/obligation-ledger")
    def order_ledger(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _order_store().ledger(payload))

    def _calendar_store() -> CalendarReviewStore:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return CalendarReviewStore(case_root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/calendar/events")
    def calendar_events() -> dict[str, Any]:
        return _intake_call(lambda: _calendar_store().inventory())

    @app.post("/api/calendar/events")
    def calendar_add_events(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _calendar_store().add_events(payload))

    @app.post("/api/calendar/rules")
    def calendar_add_rules(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _calendar_store().add_rules(payload))

    @app.post("/api/calendar/deadline-candidates")
    def calendar_deadline_candidate(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _calendar_store().calculate(payload))

    @app.get("/api/calendar/receipt")
    def calendar_receipt() -> dict[str, Any]:
        return _intake_call(lambda: _calendar_store().receipt())

    def _docket_store() -> DocketReconciliationStore:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return DocketReconciliationStore(case_root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/docket/inventory")
    def docket_inventory() -> dict[str, Any]:
        return _intake_call(lambda: _docket_store().inventory())

    @app.post("/api/docket/import")
    def docket_import(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _docket_store().import_entries(payload))

    @app.post("/api/docket/local-records")
    def docket_local_records(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _docket_store().add_local_records(payload))

    @app.get("/api/docket/reconcile")
    def docket_reconcile() -> dict[str, Any]:
        return _intake_call(lambda: _docket_store().reconcile())

    @app.get("/api/docket/receipt")
    def docket_receipt() -> dict[str, Any]:
        return _intake_call(lambda: _docket_store().receipt())

    def _discovery_store() -> DiscoveryWorkbenchStore:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return DiscoveryWorkbenchStore(case_root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/discovery/inventory")
    def discovery_inventory() -> dict[str, Any]:
        return _intake_call(lambda: _discovery_store().inventory())

    @app.post("/api/discovery/items")
    def discovery_items(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _discovery_store().add_items(payload))

    @app.post("/api/discovery/productions")
    def discovery_productions(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _discovery_store().add_productions(payload))

    @app.get("/api/discovery/gaps")
    def discovery_gaps() -> dict[str, Any]:
        return _intake_call(lambda: _discovery_store().gaps())

    @app.get("/api/discovery/receipt")
    def discovery_receipt() -> dict[str, Any]:
        return _intake_call(lambda: _discovery_store().receipt())

    def _exhibit_store() -> ExhibitWorkbenchStore:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return ExhibitWorkbenchStore(case_root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/exhibits/inventory")
    def exhibit_inventory() -> dict[str, Any]:
        return _intake_call(lambda: _exhibit_store().inventory())

    @app.post("/api/exhibits/candidates")
    def exhibit_candidates(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _exhibit_store().add_candidates(payload))

    @app.post("/api/exhibits/labels/review")
    def exhibit_label_review(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _exhibit_store().review_label(payload))

    @app.post("/api/exhibits/numbering")
    def exhibit_numbering(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _exhibit_store().create_numbering(payload))

    @app.post("/api/exhibits/binders")
    def exhibit_binder(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _exhibit_store().create_binder(payload))

    @app.get("/api/exhibits/binders/{binder_id}/manifest")
    def exhibit_manifest(binder_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _exhibit_store().manifest(binder_id))

    @app.get("/api/exhibits/receipt")
    def exhibit_receipt() -> dict[str, Any]:
        return _intake_call(lambda: _exhibit_store().receipt())

    def _statement_store() -> WitnessStatementStore:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return WitnessStatementStore(case_root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/statements/inventory")
    def statement_inventory() -> dict[str, Any]:
        return _intake_call(lambda: _statement_store().inventory())

    @app.post("/api/statements/people")
    def statement_people(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _statement_store().add_people(payload))

    @app.post("/api/statements")
    def statement_add(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _statement_store().add_statements(payload))

    @app.post("/api/statements/compare")
    def statement_compare(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(
            lambda: _statement_store().compare(
                str(payload.get("left_statement_id") or ""),
                str(payload.get("right_statement_id") or ""),
            )
        )

    @app.post("/api/statements/outline")
    def statement_outline(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _statement_store().outline(payload))

    @app.get("/api/statements/receipt")
    def statement_receipt() -> dict[str, Any]:
        return _intake_call(lambda: _statement_store().receipt())

    def _hearing_store() -> HearingPreparationStore:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return HearingPreparationStore(case_root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/hearings/inventory")
    def hearing_inventory() -> dict[str, Any]:
        return _intake_call(lambda: _hearing_store().inventory())

    @app.post("/api/hearings")
    def hearing_add(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _hearing_store().add_hearings(payload))

    @app.get("/api/hearings/receipt")
    def hearing_receipt() -> dict[str, Any]:
        return _intake_call(lambda: _hearing_store().receipt())

    def _appellate_store() -> AppellateReviewStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return AppellateReviewStore(root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/appellate/inventory")
    def appellate_inventory() -> dict[str, Any]:
        return _intake_call(lambda: _appellate_store().inventory())

    @app.post("/api/appellate")
    def appellate_add(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _appellate_store().add(payload))

    @app.get("/api/appellate/receipt")
    def appellate_receipt() -> dict[str, Any]:
        return _intake_call(lambda: _appellate_store().receipt())

    @app.get("/api/appellate/{appeal_id}/verify")
    def appellate_verify(appeal_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _appellate_store().verify(appeal_id))

    @app.get("/api/appellate/{appeal_id}/packet")
    def appellate_packet(appeal_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _appellate_store().packet(appeal_id))

    def _uccjea_store() -> UccjeaReviewStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return UccjeaReviewStore(root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/uccjea/inventory")
    def uccjea_inventory() -> dict[str, Any]:
        return _intake_call(lambda: _uccjea_store().inventory())

    @app.post("/api/uccjea/connections")
    def uccjea_connections(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _uccjea_store().connections(payload))

    @app.post("/api/uccjea/proceedings")
    def uccjea_proceedings(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _uccjea_store().proceedings(payload))

    @app.get("/api/uccjea/factors")
    def uccjea_factors() -> dict[str, Any]:
        return _intake_call(lambda: _uccjea_store().factors())

    @app.get("/api/uccjea/receipt")
    def uccjea_receipt() -> dict[str, Any]:
        return _intake_call(lambda: _uccjea_store().receipt())

    def _icwa_store() -> IcwaReviewStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return IcwaReviewStore(root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/icwa/inventory")
    def icwa_inventory() -> dict[str, Any]:
        return _intake_call(lambda: _icwa_store().inventory())

    @app.post("/api/icwa/inquiries")
    def icwa_inquiries(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _icwa_store().inquiry(payload))

    @app.post("/api/icwa/notices")
    def icwa_notices(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _icwa_store().notices(payload))

    @app.get("/api/icwa/completeness")
    def icwa_completeness() -> dict[str, Any]:
        return _intake_call(lambda: _icwa_store().completeness())

    @app.get("/api/icwa/receipt")
    def icwa_receipt() -> dict[str, Any]:
        return _intake_call(lambda: _icwa_store().receipt())

    def _care_store() -> CarePathwayStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return CarePathwayStore(root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/care-pathways/inventory")
    def care_inventory() -> dict[str, Any]:
        return _intake_call(lambda: _care_store().inventory())

    @app.post("/api/care-pathways")
    def care_add(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _care_store().add(payload))

    @app.get("/api/care-pathways/gaps")
    def care_gaps() -> dict[str, Any]:
        return _intake_call(lambda: _care_store().gaps())

    @app.get("/api/care-pathways/receipt")
    def care_receipt() -> dict[str, Any]:
        return _intake_call(lambda: _care_store().receipt())

    def _safety_store() -> SafetyReviewStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return SafetyReviewStore(root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/safety/inventory")
    def safety_inventory() -> dict[str, Any]:
        return _intake_call(lambda: _safety_store().inventory())

    @app.post("/api/safety/records")
    def safety_records(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _safety_store().add(payload))

    @app.get("/api/safety/receipt")
    def safety_receipt() -> dict[str, Any]:
        return _intake_call(lambda: _safety_store().receipt())

    def _schedule_store() -> ParentingScheduleStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return ParentingScheduleStore(root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/parenting-schedule/inventory")
    def schedule_inventory() -> dict[str, Any]:
        return _intake_call(lambda: _schedule_store().inventory())

    @app.post("/api/parenting-schedule/terms")
    def schedule_terms(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _schedule_store().add_terms(payload))

    @app.post("/api/parenting-schedule/scenarios")
    def schedule_scenario(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _schedule_store().scenario(payload))

    @app.get("/api/parenting-schedule/receipt")
    def schedule_receipt() -> dict[str, Any]:
        return _intake_call(lambda: _schedule_store().receipt())

    def _negotiation_store() -> NegotiationMatrixStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return NegotiationMatrixStore(root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/negotiation/inventory")
    def negotiation_inventory() -> dict[str, Any]:
        return _intake_call(lambda: _negotiation_store().inventory())

    @app.post("/api/negotiation/proposals")
    def negotiation_add(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _negotiation_store().add(payload))

    @app.post("/api/negotiation/compare")
    def negotiation_compare(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(
            lambda: _negotiation_store().compare(
                str(payload.get("left_id") or ""), str(payload.get("right_id") or "")
            )
        )

    @app.get("/api/negotiation/receipt")
    def negotiation_receipt() -> dict[str, Any]:
        return _intake_call(lambda: _negotiation_store().receipt())

    def _property_store() -> PropertyValuationStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return PropertyValuationStore(root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/property/inventory")
    def property_inventory() -> dict[str, Any]:
        return _intake_call(lambda: _property_store().inventory())

    @app.post("/api/property/items")
    def property_items(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _property_store().add(payload))

    @app.get("/api/property/receipt")
    def property_receipt() -> dict[str, Any]:
        return _intake_call(lambda: _property_store().receipt())

    def _modification_store() -> ModificationReviewStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return ModificationReviewStore(root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/modification/inventory")
    def modification_inventory() -> dict[str, Any]:
        return _intake_call(lambda: _modification_store().inventory())

    @app.post("/api/modification/changes")
    def modification_changes(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _modification_store().add(payload))

    @app.get("/api/modification/receipt")
    def modification_receipt() -> dict[str, Any]:
        return _intake_call(lambda: _modification_store().receipt())

    def _foaa_store() -> FoaaRequestStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return FoaaRequestStore(root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/foaa/inventory")
    def foaa_inventory() -> dict[str, Any]:
        return _intake_call(lambda: _foaa_store().inventory())

    @app.post("/api/foaa/requests")
    def foaa_requests(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _foaa_store().add(payload))

    @app.get("/api/foaa/receipt")
    def foaa_receipt() -> dict[str, Any]:
        return _intake_call(lambda: _foaa_store().receipt())

    def _filing_store() -> FilingReadinessStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return FilingReadinessStore(root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/filing-readiness/inventory")
    def filing_inventory() -> dict[str, Any]:
        return _intake_call(lambda: _filing_store().inventory())

    @app.post("/api/filing-readiness/packages")
    def filing_packages(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _filing_store().add(payload))

    @app.get("/api/filing-readiness/receipt")
    def filing_receipt() -> dict[str, Any]:
        return _intake_call(lambda: _filing_store().receipt())

    def _image_store() -> ImageEvidenceStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return ImageEvidenceStore(root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/image-evidence/inventory")
    def image_inventory() -> dict[str, Any]:
        return _intake_call(lambda: _image_store().inventory())

    @app.post("/api/image-evidence/items")
    def image_items(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _image_store().add(payload))

    @app.get("/api/image-evidence/receipt")
    def image_receipt() -> dict[str, Any]:
        return _intake_call(lambda: _image_store().receipt())

    def _email_store() -> EmailIntegrityStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return EmailIntegrityStore(root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/email-integrity/inventory")
    def email_inventory() -> dict[str, Any]:
        return _intake_call(lambda: _email_store().inventory())

    @app.post("/api/email-integrity/exports")
    def email_exports(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _email_store().add(payload))

    @app.get("/api/email-integrity/receipt")
    def email_receipt() -> dict[str, Any]:
        return _intake_call(lambda: _email_store().receipt())

    def _handoff_store() -> ReviewerHandoffStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return ReviewerHandoffStore(root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/reviewer-handoff/inventory")
    def handoff_inventory() -> dict[str, Any]:
        return _intake_call(lambda: _handoff_store().inventory())

    @app.post("/api/reviewer-handoff")
    def handoff_add(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _handoff_store().add(payload))

    @app.get("/api/reviewer-handoff/receipt")
    def handoff_receipt() -> dict[str, Any]:
        return _intake_call(lambda: _handoff_store().receipt())

    def _language_store() -> LanguageAccessStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return LanguageAccessStore(root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/language-access/inventory")
    def language_inventory() -> dict[str, Any]:
        return _intake_call(lambda: _language_store().inventory())

    @app.post("/api/language-access/copies")
    def language_copies(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _language_store().add(payload))

    @app.get("/api/language-access/receipt")
    def language_receipt() -> dict[str, Any]:
        return _intake_call(lambda: _language_store().receipt())

    def _resource_store() -> ResourceNavigatorStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return ResourceNavigatorStore(root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/resources/inventory")
    def resource_inventory() -> dict[str, Any]:
        return _intake_call(lambda: _resource_store().inventory())

    @app.post("/api/resources")
    def resource_add(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _resource_store().add(payload))

    @app.get("/api/resources/receipt")
    def resource_receipt() -> dict[str, Any]:
        return _intake_call(lambda: _resource_store().receipt())

    @app.get("/api/filing-readiness/{package_id}/validate")
    def filing_validate(package_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _filing_store().validate(package_id))

    @app.get("/api/hearings/{hearing_id}/blockers")
    def hearing_blockers(hearing_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _hearing_store().blockers(hearing_id))

    @app.get("/api/hearings/{hearing_id}/pack")
    def hearing_pack(hearing_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _hearing_store().pack(hearing_id))

    @app.post("/api/hearings/notes")
    def hearing_note(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _hearing_store().add_note(payload))

    @app.get("/api/corpus-ocr/prerequisites")
    def corpus_ocr_prerequisites() -> dict[str, Any]:
        return _public_ocr_prerequisite_job()

    @app.get("/api/corpus-ocr/prerequisites/status")
    def corpus_ocr_prerequisites_status() -> dict[str, Any]:
        return _public_ocr_prerequisite_job()

    @app.post("/api/corpus-ocr/prerequisites/install")
    def corpus_ocr_prerequisites_install(payload: InstallOcrPrerequisitesRequest) -> dict[str, Any]:
        if not payload.approved:
            raise HTTPException(status_code=400, detail="ocr_prerequisite_install_consent_required")
        status = ocr_prerequisite_status()
        if not status.get("one_click_available"):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "one_click_install_unavailable",
                    "message": "One-click installation is unavailable. Open the manual Tesseract install page, then recheck.",
                    "manual_install_url": status.get("manual_install_url"),
                    "windows_installer_url": status.get("windows_installer_url"),
                },
            )
        with _ocr_prerequisite_lock:
            already_running = bool(_ocr_prerequisite_job.get("running"))
            if not already_running:
                _ocr_prerequisite_job.clear()
                _ocr_prerequisite_job.update(
                    {
                        "status": "queued",
                        "running": True,
                        "message": "OCR prerequisite installation queued.",
                        "started_at": time.time(),
                    }
                )
        if already_running:
            return _public_ocr_prerequisite_job()
        thread = threading.Thread(
            target=_run_ocr_prerequisite_install, name="mfl-ocr-prerequisite-install", daemon=True
        )
        thread.start()
        return _public_ocr_prerequisite_job()

    @app.get("/api/corpus-ocr/candidates")
    def corpus_ocr_candidates() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        preview = local_ocr_choice(case_root, approved=False)
        if preview.get("status") == "declined":
            preview = dict(preview)
            preview["status"] = "choice_required"
        return preview

    @app.post("/api/corpus-ocr/choice")
    def corpus_ocr_choice(payload: LocalOcrRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        return local_ocr_choice(case_root, approved=bool(payload.approved))

    @app.post("/api/corpus-ocr/start")
    def corpus_ocr_start(payload: LocalOcrRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        if not payload.approved:
            raise HTTPException(status_code=400, detail="ocr_explicit_consent_required")
        readiness = local_ocr_choice(case_root, approved=True)
        if readiness.get("status") != "ready":
            raise HTTPException(status_code=409, detail=readiness)
        case_key = _case_id(case_root)
        kernel = get_runtime_kernel()
        with _ocr_job_lock:
            existing = _ocr_jobs.get(case_key)
            if existing and existing.get("status") in {"queued", "running"}:
                return {key: value for key, value in existing.items() if key != "cancel_event"}
            cancel_event = threading.Event()
            durable_job = next(
                (
                    job
                    for job in kernel.list_jobs(matter_id=case_key, limit=20)
                    if job.get("job_type") == "local_ocr" and job.get("status") in ACTIVE_STATUSES
                ),
                None,
            )
            if durable_job is None:
                durable_job = kernel.create_job(
                    "local_ocr",
                    {
                        "language": (payload.language or "eng").strip() or "eng",
                        "candidates": int(readiness.get("candidates") or 0),
                        "candidate_pages": int(readiness.get("candidate_pages") or 0),
                    },
                    matter_id=case_key,
                )
            job_id = str(durable_job["job_id"])
            worker_id = f"ocr-{uuid.uuid4().hex}"
            state: dict[str, Any] = {
                "job_id": job_id,
                "runtime_job_id": job_id,
                "status": "queued",
                "current": 0,
                "total": int(readiness.get("candidates") or 0),
                "candidate_pages": int(readiness.get("candidate_pages") or 0),
                "processed_documents": 0,
                "processed_pages": 0,
                "started_at": time.time(),
                "last_progress_at": time.time(),
                "local_only": True,
                "network_used": False,
                "cancel_event": cancel_event,
            }
            _ocr_jobs[case_key] = state

        def update_progress(update: dict[str, Any]) -> None:
            safe_update = {key: value for key, value in update.items() if key != "proof_path"}
            with _ocr_job_lock:
                current_state = _ocr_jobs.get(case_key)
                if current_state is not None:
                    current_state.update(safe_update)
                    current_state["updated_at"] = time.time()
                    current_state["last_progress_at"] = current_state["updated_at"]
                    current_state["processed_documents"] = int(
                        safe_update.get("current")
                        or safe_update.get("completed")
                        or current_state.get("processed_documents")
                        or 0
                    )
                    current_state["processed_pages"] = int(
                        safe_update.get("processed_pages")
                        or current_state.get("processed_pages")
                        or 0
                    )
                    current = int(
                        current_state.get("current")
                        or current_state.get("processed_documents")
                        or 0
                    )
                    total = max(1, int(current_state.get("total") or 1))
                    try:
                        kernel.heartbeat(job_id, worker_id, current / total)
                    except (KeyError, RuntimeError):
                        pass

        def cancellation_requested() -> bool:
            durable = kernel.get_job(job_id)
            return cancel_event.is_set() or bool(
                durable and durable.get("status") in {"cancel_requested", "cancelled"}
            )

        def worker() -> None:
            try:
                kernel.claim_job(job_id, worker_id, lease_seconds=300)
            except RuntimeError:
                durable = kernel.get_job(job_id)
                if not durable or durable.get("status") != "running":
                    update_progress({"status": str((durable or {}).get("status") or "failed")})
                    return
            update_progress({"status": "running"})
            try:
                result = run_local_ocr(
                    case_root,
                    language=(payload.language or "eng").strip() or "eng",
                    progress=update_progress,
                    should_cancel=cancellation_requested,
                )
                update_progress(result)
                kernel.finish_job(
                    job_id,
                    worker_id,
                    result={
                        key: value
                        for key, value in result.items()
                        if key not in {"proof_path", "source_locator"}
                    },
                )
            except Exception:
                error = {
                    "code": "local_ocr_failed",
                    "message": (
                        "Local OCR could not complete. Review the engine status and "
                        "source-page readability, then retry."
                    ),
                }
                update_progress({"status": "failed", "error": error["message"]})
                try:
                    kernel.finish_job(job_id, worker_id, error=error)
                except (KeyError, RuntimeError):
                    pass

        threading.Thread(target=worker, name=f"mfl-local-ocr-{job_id[:8]}", daemon=True).start()
        return _public_ocr_progress(state)

    @app.get("/api/corpus-ocr/status")
    def corpus_ocr_status() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        case_key = _case_id(case_root)
        with _ocr_job_lock:
            state = dict(_ocr_jobs.get(case_key) or {})
        if state:
            return _public_ocr_progress(state)
        durable = next(
            (
                job
                for job in get_runtime_kernel().list_jobs(matter_id=case_key, limit=20)
                if job.get("job_type") == "local_ocr"
            ),
            None,
        )
        if durable is not None:
            payload = dict(durable.get("payload") or {})
            return {
                "job_id": durable["job_id"],
                "runtime_job_id": durable["job_id"],
                "status": durable["status"],
                "display_status": durable["status"],
                "current": int(
                    float(durable.get("progress") or 0) * int(payload.get("candidates") or 0)
                ),
                "total": int(payload.get("candidates") or 0),
                "candidate_pages": int(payload.get("candidate_pages") or 0),
                "resumable": durable["status"] == "queued",
                "persistent": True,
                "local_only": True,
                "network_used": False,
            }
        preview = local_ocr_choice(case_root, approved=False)
        return {
            "status": "idle",
            "candidates": int(preview.get("candidates") or 0),
            "candidate_pages": int(preview.get("candidate_pages") or 0),
            "engine": preview.get("engine") or local_ocr_engine_status(),
            "local_only": True,
            "network_used": False,
        }

    @app.post("/api/corpus-ocr/cancel")
    def corpus_ocr_cancel() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        case_key = _case_id(case_root)
        with _ocr_job_lock:
            state = _ocr_jobs.get(case_key)
            if not state or state.get("status") not in {"queued", "running"}:
                return {"status": "idle", "cancel_requested": False}
            cancel_event = state.get("cancel_event")
            if isinstance(cancel_event, threading.Event):
                cancel_event.set()
            state["cancel_requested"] = True
            runtime_job_id = str(state.get("runtime_job_id") or state.get("job_id") or "")
            if runtime_job_id:
                try:
                    get_runtime_kernel().request_cancel(runtime_job_id)
                except KeyError:
                    pass
        return {"status": "cancelling", "cancel_requested": True}

    @app.post("/api/corpus-rebuild-index")
    def corpus_rebuild_index() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        return rebuild_local_content_index(case_root)

    @app.post("/api/corpus-delete-index")
    def corpus_delete_index() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        index_root = case_root / "04_INDEXES"
        removed: list[str] = []
        for name in (INDEX_NAME, INVENTORY_JSONL, INVENTORY_CSV, "private_search_index.json"):
            path = index_root / name
            if path.exists():
                path.unlink()
                removed.append(name)
        return {"status": "ok", "removed": removed, "source_documents_deleted": False}

    def _resolve_record_capability(token: str, page: int = 0) -> dict[str, Any]:
        """Resolve an opaque token to a verified active-corpus file or member."""

        token = str(token or "").strip().lower()
        if not re.fullmatch(r"[a-f0-9]{64}", token):
            raise HTTPException(status_code=404, detail="record_open_not_available")
        if page < 0 or page > 100_000:
            raise HTTPException(status_code=422, detail="record_open_invalid_page")
        _prune_record_open_tokens()
        case_root = active_case_root()
        with _record_open_lock:
            stored_binding = _record_open_tokens.get(token)
            binding = dict(stored_binding) if stored_binding else None
        if case_root is None or not binding:
            raise HTTPException(status_code=404, detail="record_open_not_available")
        if str(binding.get("case_id") or "") != _case_id(case_root):
            raise HTTPException(status_code=404, detail="record_open_not_available")

        evidence_id = str(binding.get("evidence_id") or "")
        source_locator = str(binding.get("source_locator") or "")
        rows = load_case_search_records(case_root)
        by_id = {str(item.get("evidence_id") or ""): item for item in rows}
        row = by_id.get(evidence_id)
        if row is None:
            raise HTTPException(status_code=404, detail="record_open_not_indexed")

        root = row
        visited: set[str] = set()
        while str(root.get("parent_evidence_id") or ""):
            parent_id = str(root.get("parent_evidence_id") or "")
            if parent_id in visited or parent_id not in by_id:
                raise HTTPException(status_code=404, detail="record_open_not_indexed")
            visited.add(parent_id)
            root = by_id[parent_id]

        staged_rel = str(root.get("private_copy_relpath") or "")
        rel_path = Path(staged_rel)
        if not staged_rel or rel_path.is_absolute() or ".." in rel_path.parts:
            raise HTTPException(status_code=404, detail="record_open_not_available")
        path = (case_root / rel_path).resolve()
        try:
            path.relative_to(case_root.resolve())
        except ValueError:
            raise HTTPException(status_code=404, detail="record_open_not_available") from None
        if not path.is_file():
            raise HTTPException(status_code=404, detail="record_open_source_missing")

        expected = str(root.get("source_hash") or "").lower()
        actual = hashlib.sha256(path.read_bytes()).hexdigest().lower()
        if expected and actual != expected:
            raise HTTPException(status_code=409, detail="record_open_source_hash_mismatch")

        locator_page = 0
        locator_without_page, marker, locator_page_text = source_locator.partition("#page=")
        if marker and locator_page_text.isdigit():
            locator_page = int(locator_page_text)
        resolved_page = int(page or locator_page or 0)
        candidate = dict(root)
        candidate["source_path"] = str(path)
        candidate["source_locator"] = locator_without_page or str(
            root.get("source_locator") or path.name
        )
        try:
            data, suffix = _candidate_bytes(candidate)
        except (FileNotFoundError, ValueError, KeyError, zipfile.BadZipFile):
            raise HTTPException(status_code=404, detail="record_open_source_missing") from None

        matching_row = row
        target_locator = str(candidate["source_locator"])
        for candidate_row in rows:
            candidate_meta_locator = str(candidate_row.get("source_locator") or "")
            candidate_base = candidate_meta_locator.split("#page=", 1)[0]
            candidate_page = int(candidate_row.get("page_number") or 0)
            if candidate_base == target_locator and (
                not resolved_page or candidate_page in {0, resolved_page}
            ):
                matching_row = candidate_row
                if candidate_page == resolved_page:
                    break

        filename = _safe_record_basename({"metadata": {"source_locator": target_locator}})
        mime_type = mimetypes.guess_type(f"record{suffix}")[0] or "application/octet-stream"
        return {
            "case_root": case_root,
            "token": token,
            "binding": binding,
            "rows": rows,
            "root": root,
            "row": matching_row,
            "path": path,
            "data": data,
            "suffix": suffix.lower(),
            "mime_type": mime_type,
            "filename": filename,
            "source_locator": target_locator,
            "page": resolved_page,
            "source_hash": actual,
        }

    def _record_viewer_kind(suffix: str, mime_type: str) -> str:
        suffix = str(suffix or "").lower()
        if suffix == ".pdf":
            return "pdf"
        if suffix in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".heic"}:
            return "image"
        if suffix in {".eml", ".mbox", ".mbx"}:
            return "email"
        if suffix in {".csv", ".tsv"}:
            return "table"
        if suffix in {".txt", ".md", ".log", ".json", ".xml", ".html", ".htm", ".rtf", ".ics"}:
            return "text"
        if suffix in {".docx", ".xlsx", ".pptx"}:
            return "office_text"
        if suffix == ".zip":
            return "archive"
        if suffix in {".mp3", ".m4a", ".wav", ".ogg", ".flac"} or mime_type.startswith("audio/"):
            return "audio"
        if suffix in {".mp4", ".mov", ".avi", ".webm", ".mkv"} or mime_type.startswith("video/"):
            return "video"
        return "binary"

    def _bounded_preview_text(value: str) -> tuple[str, bool]:
        text = str(value or "")
        return text[:_RECORD_PREVIEW_TEXT_LIMIT], len(text) > _RECORD_PREVIEW_TEXT_LIMIT

    def _safe_email_preview(resolved: dict[str, Any]) -> dict[str, Any]:
        data = bytes(resolved["data"])
        try:
            message = BytesParser(policy=policy.default).parsebytes(data)
        except Exception:
            return {
                "headers": {},
                "body": "The email could not be parsed safely.",
                "attachments": [],
                "parse_status": "unreadable",
            }
        headers = {
            key: str(message.get(key, ""))[:4000]
            for key in ("From", "To", "Cc", "Subject", "Date", "Message-ID", "In-Reply-To")
            if message.get(key)
        }
        body_parts: list[str] = []
        attachments: list[dict[str, Any]] = []
        base_locator = str(resolved["source_locator"])
        case_root = Path(resolved["case_root"])
        evidence_id = str(resolved["binding"].get("evidence_id") or "")
        for part in message.walk():
            if part.is_multipart():
                continue
            filename = str(part.get_filename() or "")
            content_type = str(part.get_content_type() or "application/octet-stream")
            if filename:
                safe_name = Path(filename.replace("\\", "/")).name[:240] or "attachment"
                payload = part.get_payload(decode=True) or b""
                member_locator = f"{base_locator}!{filename}"
                member_token = _record_open_token(case_root, evidence_id, member_locator)
                attachments.append(
                    {
                        "filename": safe_name,
                        "content_type": content_type,
                        "size_bytes": len(payload),
                        "source_token": member_token,
                        "viewer_kind": _record_viewer_kind(
                            Path(filename).suffix.lower(), content_type
                        ),
                    }
                )
                continue
            if content_type not in {"text/plain", "text/html"}:
                continue
            try:
                content = part.get_content()
            except Exception:
                raw = part.get_payload(decode=True) or b""
                content = raw.decode(part.get_content_charset() or "utf-8", errors="replace")
            if isinstance(content, bytes):
                content = content.decode(part.get_content_charset() or "utf-8", errors="replace")
            if content_type == "text/html":
                content = parse_bytes(
                    str(content).encode("utf-8"), suffix=".html", locator="message.html"
                ).text
            if str(content).strip():
                body_parts.append(str(content).strip())
        body, truncated = _bounded_preview_text("\n\n".join(body_parts))
        return {
            "headers": headers,
            "body": body,
            "body_truncated": truncated,
            "attachments": attachments[:_RECORD_PREVIEW_MEMBER_LIMIT],
            "attachment_count": len(attachments),
            "parse_status": "parsed",
        }

    def _safe_archive_preview(resolved: dict[str, Any]) -> dict[str, Any]:
        members: list[dict[str, Any]] = []
        data = bytes(resolved["data"])
        base_locator = str(resolved["source_locator"])
        case_root = Path(resolved["case_root"])
        evidence_id = str(resolved["binding"].get("evidence_id") or "")
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                declared = len(archive.infolist())
                for info in archive.infolist():
                    member = Path(info.filename)
                    if info.is_dir() or member.is_absolute() or ".." in member.parts:
                        continue
                    safe_name = Path(info.filename.replace("\\", "/")).name[:240] or "member"
                    member_locator = f"{base_locator}!{info.filename}"
                    member_token = _record_open_token(case_root, evidence_id, member_locator)
                    content_type = mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
                    members.append(
                        {
                            "filename": safe_name,
                            "member_locator": "!".join(
                                Path(part.replace("\\", "/")).name
                                for part in member_locator.split("!")
                            ),
                            "size_bytes": int(info.file_size or 0),
                            "compressed_size_bytes": int(info.compress_size or 0),
                            "source_token": member_token,
                            "viewer_kind": _record_viewer_kind(member.suffix.lower(), content_type),
                        }
                    )
                    if len(members) >= _RECORD_PREVIEW_MEMBER_LIMIT:
                        break
        except zipfile.BadZipFile:
            return {"members": [], "member_count": 0, "parse_status": "unreadable"}
        return {
            "members": members,
            "member_count": declared,
            "members_truncated": declared > len(members),
            "parse_status": "parsed",
        }

    def _safe_table_preview(data: bytes, suffix: str) -> dict[str, Any]:
        decoded = data.decode("utf-8-sig", errors="replace")
        delimiter = "\t" if suffix == ".tsv" else ","
        rows: list[list[str]] = []
        reader = csv.reader(io.StringIO(decoded), delimiter=delimiter)
        for row in reader:
            rows.append([str(cell)[:1000] for cell in row[:40]])
            if len(rows) >= 120:
                break
        return {
            "rows": rows,
            "rows_truncated": len(decoded.splitlines()) > len(rows),
            "column_limit": 40,
        }

    def _record_inspection_payload(resolved: dict[str, Any]) -> dict[str, Any]:
        suffix = str(resolved["suffix"])
        mime_type = str(resolved["mime_type"])
        viewer_kind = _record_viewer_kind(suffix, mime_type)
        data = bytes(resolved["data"])
        row = dict(resolved.get("row") or {})
        root = dict(resolved.get("root") or {})
        page = int(resolved.get("page") or row.get("page_number") or 0)
        parser_metadata = dict(row.get("parser_metadata") or root.get("parser_metadata") or {})
        page_count = int(
            row.get("page_count")
            or root.get("page_count")
            or parser_metadata.get("page_count")
            or 0
        )
        preview: dict[str, Any] = {}

        if viewer_kind == "email":
            preview = _safe_email_preview(resolved)
        elif viewer_kind == "archive":
            preview = _safe_archive_preview(resolved)
        elif viewer_kind == "table":
            preview = _safe_table_preview(data, suffix)
        elif viewer_kind in {"text", "office_text"}:
            parsed = parse_bytes(data, suffix=suffix, locator=str(resolved["filename"]))
            text, truncated = _bounded_preview_text(parsed.text)
            preview = {
                "text": text,
                "text_truncated": truncated,
                "parser_status": parsed.parser_status,
                "text_status": parsed.text_status,
            }
        elif viewer_kind == "pdf":
            if not page_count:
                parsed = parse_bytes(data, suffix=suffix, locator=str(resolved["filename"]))
                page_count = parsed.page_count
            text = str(row.get("text_content") or row.get("text_excerpt") or "")
            text, truncated = _bounded_preview_text(text)
            preview = {"page_text": text, "page_text_truncated": truncated}
        elif viewer_kind == "image":
            preview = {
                "ocr_text": str(row.get("text_content") or row.get("text_excerpt") or "")[
                    :_RECORD_PREVIEW_TEXT_LIMIT
                ],
                "ocr_status": str(row.get("ocr_status") or root.get("ocr_status") or "unknown"),
            }
        else:
            preview = {
                "message": "A safe in-app rendering is not available for this file type. You can open or download the verified original."
            }

        query = f"?page={page}" if page else "?page=0"
        return {
            "status": "ok",
            "local_only": True,
            "review_required": True,
            "token": str(resolved["token"]),
            "filename": str(resolved["filename"]),
            "extension": suffix,
            "mime_type": mime_type,
            "viewer_kind": viewer_kind,
            "size_bytes": len(data),
            "page": page,
            "page_count": page_count,
            "source_hash_verified": True,
            "evidence_id": str(row.get("evidence_id") or root.get("evidence_id") or "")[:256],
            "safe_locator": _public_source_locator(str(resolved["source_locator"])),
            "source_type": str(
                row.get("source_type") or root.get("source_type") or suffix.lstrip(".") or "record"
            ),
            "parser_status": str(
                row.get("parser_status") or root.get("parser_status") or "unknown"
            ),
            "text_status": str(row.get("text_status") or root.get("text_status") or "unknown"),
            "ocr_status": str(row.get("ocr_status") or root.get("ocr_status") or "unknown"),
            "open_url": f"/api/records/open/{resolved['token']}{query}",
            "download_url": f"/api/records/open/{resolved['token']}{query}&download=true",
            "preview": preview,
        }

    def _prune_open_cache(cache: Path, now: float | None = None) -> None:
        current = float(now if now is not None else time.time())
        entries: list[tuple[Path, os.stat_result]] = []
        try:
            candidates = list(cache.iterdir())
        except OSError:
            return
        for candidate in candidates:
            try:
                if candidate.is_symlink() or not candidate.is_file():
                    continue
                stat_result = candidate.stat()
            except OSError:
                continue
            if current - stat_result.st_mtime > _OPEN_CACHE_TTL_SECONDS:
                try:
                    candidate.unlink()
                except OSError:
                    pass
                continue
            entries.append((candidate, stat_result))
        total_bytes = sum(item.st_size for _path, item in entries)
        if len(entries) <= _OPEN_CACHE_MAX_FILES and total_bytes <= _OPEN_CACHE_MAX_BYTES:
            return
        for candidate, stat_result in sorted(entries, key=lambda item: item[1].st_mtime):
            if len(entries) <= _OPEN_CACHE_MAX_FILES and total_bytes <= _OPEN_CACHE_MAX_BYTES:
                break
            try:
                candidate.unlink()
            except OSError:
                continue
            total_bytes -= stat_result.st_size
            entries = [item for item in entries if item[0] != candidate]

    def _materialize_open_cache(case_root: Path, data: bytes, suffix: str) -> Path:
        resolved_case = case_root.expanduser().resolve(strict=True)
        cache = resolved_case / "04_INDEXES" / "open_cache"
        if cache.exists() and cache.is_symlink():
            raise HTTPException(status_code=409, detail="record_open_cache_unsafe")
        cache.mkdir(parents=True, exist_ok=True)
        resolved_cache = cache.resolve(strict=True)
        if resolved_case not in resolved_cache.parents:
            raise HTTPException(status_code=409, detail="record_open_cache_unsafe")
        try:
            os.chmod(resolved_cache, 0o700)
        except OSError:
            pass
        _prune_open_cache(resolved_cache)
        safe_suffix = suffix if re.fullmatch(r"\.[a-z0-9]{1,12}", suffix) else ""
        target = resolved_cache / f"{hashlib.sha256(data).hexdigest()}{safe_suffix}"
        if target.exists():
            if target.is_symlink() or target.resolve(strict=True).parent != resolved_cache:
                raise HTTPException(status_code=409, detail="record_open_cache_unsafe")
            return target
        temporary = resolved_cache / f".{target.name}.{secrets.token_hex(8)}.tmp"
        try:
            with temporary.open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.chmod(temporary, 0o600)
            except OSError:
                pass
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                try:
                    temporary.unlink()
                except OSError:
                    pass
        return target

    def _prune_document_intelligence_artifacts(now: float | None = None) -> None:
        current = float(now if now is not None else time.time())
        with _document_intelligence_artifact_lock:
            stale_before = current - _DOCUMENT_INTELLIGENCE_ARTIFACT_TTL_SECONDS
            stale = [
                token
                for token, binding in _document_intelligence_artifacts.items()
                if float(binding.get("created_at") or 0) < stale_before
            ]
            for token in stale:
                _document_intelligence_artifacts.pop(token, None)
            if len(_document_intelligence_artifacts) > _DOCUMENT_INTELLIGENCE_ARTIFACT_MAX_TOKENS:
                overflow = (
                    len(_document_intelligence_artifacts)
                    - _DOCUMENT_INTELLIGENCE_ARTIFACT_MAX_TOKENS
                )
                oldest = sorted(
                    _document_intelligence_artifacts.items(),
                    key=lambda item: float(item[1].get("created_at") or 0),
                )[:overflow]
                for token, _binding in oldest:
                    _document_intelligence_artifacts.pop(token, None)

    def _document_intelligence_artifact_token(
        case_root: Path, relative_path: str, sha256: str
    ) -> str:
        relative = Path(str(relative_path or ""))
        if relative.is_absolute() or ".." in relative.parts:
            raise HTTPException(status_code=409, detail="document_intelligence_artifact_unsafe")
        path = (case_root / relative).resolve()
        try:
            path.relative_to(case_root.resolve())
        except ValueError:
            raise HTTPException(
                status_code=409, detail="document_intelligence_artifact_unsafe"
            ) from None
        if path.is_symlink() or not path.is_file():
            raise HTTPException(status_code=404, detail="document_intelligence_artifact_missing")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if sha256 and actual != str(sha256).lower():
            raise HTTPException(
                status_code=409, detail="document_intelligence_artifact_hash_mismatch"
            )
        _prune_document_intelligence_artifacts()
        token = secrets.token_hex(32)
        with _document_intelligence_artifact_lock:
            _document_intelligence_artifacts[token] = {
                "case_id": _case_id(case_root),
                "relative_path": relative.as_posix(),
                "sha256": actual,
                "created_at": time.time(),
            }
        return token

    def _attach_document_intelligence_artifact(
        case_root: Path, artifact: dict[str, Any] | None, *, record_id: str | None = None
    ) -> dict[str, Any] | None:
        if not isinstance(artifact, dict) or not artifact.get("relative_path"):
            return artifact
        row = dict(artifact)
        token = _document_intelligence_artifact_token(
            case_root,
            str(row.get("relative_path") or ""),
            str(row.get("sha256") or ""),
        )
        receipt_relative_path = str(
            row.get("receipt_relative_path") or row.get("relative_path") or ""
        )
        receipt_sha256 = str(row.get("receipt_sha256") or row.get("sha256") or "")
        with _document_intelligence_artifact_lock:
            _document_intelligence_artifacts[token] = {
                "case_id": _case_id(case_root),
                "record_id": str(record_id or ""),
                "relative_path": str(artifact.get("relative_path") or ""),
                "sha256": str(artifact.get("sha256") or ""),
                "receipt_relative_path": receipt_relative_path,
                "receipt_sha256": receipt_sha256,
                "artifact_type": str(row.get("artifact_type") or "document_intelligence_artifact"),
                "created_at": time.time(),
            }
        row.pop("relative_path", None)
        row["artifact_id"] = token
        row["download_token"] = token
        row["download_url"] = f"/api/document-intelligence/artifacts/{token}"
        row["receipt_url"] = f"/api/artifacts/{token}/receipt"
        return row

    def _document_intelligence_input(source_token: str) -> dict[str, Any]:
        resolved = _resolve_record_capability(source_token, 0)
        case_root = Path(resolved["case_root"])
        data = bytes(resolved["data"])
        suffix = str(resolved["suffix"])
        path = Path(resolved["path"])
        if "!" in str(resolved["source_locator"]):
            path = _materialize_open_cache(case_root, data, suffix)
        return {
            "case_root": case_root,
            "path": path,
            "source_hash": hashlib.sha256(data).hexdigest(),
            "filename": str(resolved["filename"]),
            "suffix": suffix,
        }

    def _resolve_record_rows(record_id: str) -> tuple[Path, list[dict[str, Any]], dict[str, Any]]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        rows = load_case_search_records(case_root)
        for row in rows:
            if str(row.get("evidence_id") or "") == str(record_id or ""):
                return Path(case_root), rows, dict(row)
        raise HTTPException(status_code=404, detail="record_not_found")

    def _record_capability_for_row(case_root: Path, row: dict[str, Any]) -> dict[str, Any]:
        evidence_id = str(row.get("evidence_id") or "")
        locator = str(row.get("source_locator") or row.get("title") or "")
        return _resolve_record_capability(
            _record_open_token(case_root, evidence_id, locator), int(row.get("page_number") or 0)
        )

    def _record_text_for_row(case_root: Path, row: dict[str, Any]) -> str:
        resolved = _record_capability_for_row(case_root, row)
        preview = dict(resolved.get("preview") or {})
        if resolved.get("viewer_kind") == "pdf":
            return str(preview.get("page_text") or "")
        if resolved.get("viewer_kind") == "image":
            return str(preview.get("ocr_text") or "")
        if resolved.get("viewer_kind") in {"text", "office_text"}:
            return str(preview.get("text") or "")
        return str(preview.get("body") or preview.get("message") or "")

    def _normalize_for_compare(value: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()

    def _record_duplicate_report(rows: list[dict[str, Any]], row: dict[str, Any]) -> dict[str, Any]:
        source_hash = str(row.get("source_hash") or "")
        canonical_key = str(
            row.get("canonical_document_key")
            or row.get("parent_evidence_id")
            or row.get("evidence_id")
            or source_hash
        )
        exact = [dict(item) for item in rows if str(item.get("source_hash") or "") == source_hash]
        base_text = _normalize_for_compare(
            str(row.get("text_excerpt") or row.get("text_content") or "")
        )
        near_candidates: list[dict[str, Any]] = []
        changed_copies: list[dict[str, Any]] = []
        for item in rows:
            if item is row:
                continue
            other_hash = str(item.get("source_hash") or "")
            other_key = str(
                item.get("canonical_document_key")
                or item.get("parent_evidence_id")
                or item.get("evidence_id")
                or other_hash
            )
            other_text = _normalize_for_compare(
                str(item.get("text_excerpt") or item.get("text_content") or "")
            )
            similarity = (
                SequenceMatcher(None, base_text, other_text).ratio()
                if base_text or other_text
                else 0.0
            )
            if other_hash == source_hash:
                continue
            if similarity >= 0.78:
                near_candidates.append(
                    {
                        "record_id": str(item.get("evidence_id") or ""),
                        "similarity": round(similarity, 6),
                        "page_count": int(item.get("page_count") or 0),
                        "source_hash": other_hash,
                        "same_canonical_group": other_key == canonical_key,
                        "parser_status": str(item.get("parser_status") or ""),
                        "ocr_status": str(item.get("ocr_status") or ""),
                    }
                )
            if other_key == canonical_key and other_hash and other_hash != source_hash:
                changed_copies.append(
                    {
                        "record_id": str(item.get("evidence_id") or ""),
                        "source_hash": other_hash,
                        "page_count": int(item.get("page_count") or 0),
                        "parser_status": str(item.get("parser_status") or ""),
                        "ocr_status": str(item.get("ocr_status") or ""),
                    }
                )
        exact_duplicate = len(exact) > 1
        return {
            "schema_version": "record_duplicate_report_v1",
            "record_id": str(row.get("evidence_id") or ""),
            "duplicate_group_id": canonical_key,
            "exact_duplicate": exact_duplicate,
            "exact_duplicates": [
                {
                    "record_id": str(item.get("evidence_id") or ""),
                    "page_count": int(item.get("page_count") or 0),
                    "source_hash": str(item.get("source_hash") or ""),
                    "parser_status": str(item.get("parser_status") or ""),
                    "ocr_status": str(item.get("ocr_status") or ""),
                }
                for item in exact
            ],
            "near_duplicate_candidates": near_candidates[:100],
            "changed_copy_candidates": changed_copies[:100],
            "retention_status": str(row.get("retention_status") or "preserve_original"),
            "review_required": True,
        }

    def _document_intelligence_receipt(token: str) -> dict[str, Any]:
        token = str(token or "").strip().lower()
        if not re.fullmatch(r"[a-f0-9]{64}", token):
            raise HTTPException(
                status_code=404, detail="document_intelligence_receipt_not_available"
            )
        _prune_document_intelligence_artifacts()
        case_root = active_case_root()
        with _document_intelligence_artifact_lock:
            binding = dict(_document_intelligence_artifacts.get(token) or {})
        if case_root is None or not binding or binding.get("case_id") != _case_id(case_root):
            raise HTTPException(
                status_code=404, detail="document_intelligence_receipt_not_available"
            )
        relative = Path(
            str(binding.get("receipt_relative_path") or binding.get("relative_path") or "")
        )
        if relative.is_absolute() or ".." in relative.parts:
            raise HTTPException(
                status_code=404, detail="document_intelligence_receipt_not_available"
            )
        path = (case_root / relative).resolve()
        try:
            path.relative_to(case_root.resolve())
        except ValueError:
            raise HTTPException(
                status_code=404, detail="document_intelligence_receipt_not_available"
            ) from None
        if path.is_symlink() or not path.is_file():
            raise HTTPException(
                status_code=404, detail="document_intelligence_receipt_not_available"
            )
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        expected = str(binding.get("receipt_sha256") or binding.get("sha256") or "")
        if expected and actual != expected:
            raise HTTPException(
                status_code=409, detail="document_intelligence_receipt_hash_mismatch"
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise HTTPException(
                status_code=409,
                detail=f"document_intelligence_receipt_invalid:{exc.__class__.__name__}",
            ) from None
        if not isinstance(payload, dict):
            raise HTTPException(status_code=409, detail="document_intelligence_receipt_invalid")
        return payload

    def _find_record_artifact_binding(
        case_root: Path, record_id: str, *, artifact_type_prefix: str | None = None
    ) -> tuple[str, dict[str, Any]]:
        with _document_intelligence_artifact_lock:
            items = list(_document_intelligence_artifacts.items())
        case_key = _case_id(case_root)
        for token, binding in sorted(
            items, key=lambda item: float(item[1].get("created_at") or 0), reverse=True
        ):
            if str(binding.get("case_id") or "") != case_key:
                continue
            if str(binding.get("record_id") or "") != str(record_id or ""):
                continue
            artifact_type = str(binding.get("artifact_type") or "")
            if artifact_type_prefix and not artifact_type.startswith(artifact_type_prefix):
                continue
            return token, dict(binding)
        raise HTTPException(status_code=404, detail="document_intelligence_artifact_not_available")

    @app.get("/api/document-intelligence/status")
    def document_intelligence_runtime_status() -> dict[str, Any]:
        return document_intelligence_status()

    @app.post("/api/document-intelligence/analyze")
    def document_intelligence_analyze(
        payload: DocumentIntelligenceAnalyzeRequest,
    ) -> dict[str, Any]:
        if payload.approved is not True:
            raise HTTPException(status_code=409, detail="document_intelligence_consent_required")
        source = _document_intelligence_input(payload.source_token)
        try:
            result = analyze_document(
                case_root=source["case_root"],
                source_path=source["path"],
                source_hash=source["source_hash"],
                run_docling=bool(payload.run_docling),
                run_presidio=bool(payload.run_presidio),
            )
        except DocumentIntelligenceError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None
        output = dict(result)
        output["artifact"] = _attach_document_intelligence_artifact(
            source["case_root"], result.get("artifact")
        )
        output["source"]["filename"] = source["filename"]
        return output

    @app.post("/api/document-intelligence/ocr-preservation")
    def document_intelligence_ocr_preservation(
        payload: DocumentIntelligenceOcrRequest,
    ) -> dict[str, Any]:
        source = _document_intelligence_input(payload.source_token)
        try:
            result = create_ocr_preservation_copy(
                case_root=source["case_root"],
                source_path=source["path"],
                source_hash=source["source_hash"],
                approved=bool(payload.approved),
                language=str(payload.language or "eng")[:32],
            )
        except DocumentIntelligenceError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None
        output = dict(result)
        artifacts = dict(result.get("artifacts") or {})
        output["artifacts"] = {
            key: _attach_document_intelligence_artifact(source["case_root"], value)
            for key, value in artifacts.items()
        }
        return output

    @app.get("/api/document-intelligence/artifacts/{token}")
    def document_intelligence_artifact_download(token: str):  # type: ignore[no-untyped-def]
        token = str(token or "").strip().lower()
        if not re.fullmatch(r"[a-f0-9]{64}", token):
            raise HTTPException(
                status_code=404, detail="document_intelligence_artifact_not_available"
            )
        _prune_document_intelligence_artifacts()
        case_root = active_case_root()
        with _document_intelligence_artifact_lock:
            binding = dict(_document_intelligence_artifacts.get(token) or {})
        if case_root is None or not binding or binding.get("case_id") != _case_id(case_root):
            raise HTTPException(
                status_code=404, detail="document_intelligence_artifact_not_available"
            )
        relative = Path(str(binding.get("relative_path") or ""))
        if relative.is_absolute() or ".." in relative.parts:
            raise HTTPException(
                status_code=404, detail="document_intelligence_artifact_not_available"
            )
        path = (case_root / relative).resolve()
        try:
            path.relative_to(case_root.resolve())
        except ValueError:
            raise HTTPException(
                status_code=404, detail="document_intelligence_artifact_not_available"
            ) from None
        if path.is_symlink() or not path.is_file():
            raise HTTPException(
                status_code=404, detail="document_intelligence_artifact_not_available"
            )
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != str(binding.get("sha256") or ""):
            raise HTTPException(
                status_code=409, detail="document_intelligence_artifact_hash_mismatch"
            )
        return FileResponse(
            path,
            filename=path.name,
            media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "X-MFL-Hash-Verified": "true",
            },
            content_disposition_type="attachment",
        )

    @app.get("/api/artifacts/{artifact_id}/receipt")
    def document_intelligence_artifact_receipt(artifact_id: str) -> dict[str, Any]:
        payload = _document_intelligence_receipt(artifact_id)
        with _document_intelligence_artifact_lock:
            binding = dict(
                _document_intelligence_artifacts.get(str(artifact_id or "").strip().lower()) or {}
            )
        if binding.get("artifact_type"):
            payload["artifact_type"] = str(
                binding.get("artifact_type") or payload.get("artifact_type") or ""
            )
        payload["artifact_id"] = str(artifact_id or "").strip().lower()
        return payload

    @app.get("/api/records/{record_id}/integrity")
    def record_document_integrity(record_id: str) -> dict[str, Any]:
        case_root, rows, row = _resolve_record_rows(record_id)
        resolved = _record_capability_for_row(case_root, row)
        source = _record_inspection_payload(resolved)
        duplicate_report = _record_duplicate_report(rows, row)
        try:
            analysis = analyze_document(
                case_root=case_root,
                source_path=Path(resolved["path"]),
                source_hash=str(resolved["source_hash"]),
                run_docling=False,
                run_presidio=False,
            )
        except DocumentIntelligenceError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None
        return {
            "schema_version": "record_integrity_response_v1",
            "record_id": str(row.get("evidence_id") or ""),
            "local_only": True,
            "review_required": True,
            "integrity": analysis.get("integrity", {}),
            "preview": source,
            "duplicate_report": duplicate_report,
            "privacy_review": analysis.get("privacy_review", {}),
            "provenance": analysis.get("provenance", {}),
        }

    @app.get("/api/records/{record_id}/blocks")
    def record_document_blocks(record_id: str, limit: int = 200, offset: int = 0) -> dict[str, Any]:
        case_root, _rows, row = _resolve_record_rows(record_id)
        resolved = _record_capability_for_row(case_root, row)
        try:
            analysis = analyze_document(
                case_root=case_root,
                source_path=Path(resolved["path"]),
                source_hash=str(resolved["source_hash"]),
                run_docling=False,
                run_presidio=False,
            )
        except DocumentIntelligenceError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None
        blocks = list((analysis.get("structured_document") or {}).get("blocks") or [])
        start = max(0, int(offset or 0))
        end = start + max(0, int(limit or 0))
        return {
            "schema_version": "record_blocks_response_v1",
            "record_id": str(row.get("evidence_id") or ""),
            "total": len(blocks),
            "offset": start,
            "limit": max(0, int(limit or 0)),
            "blocks": blocks[start:end],
            "comparison": (analysis.get("structured_document") or {}).get("comparison", {}),
            "selection_reason": analysis.get("selection_reason"),
            "provenance": analysis.get("provenance", {}),
            "review_required": True,
        }

    @app.post("/api/records/{record_id}/parse")
    def record_document_parse(
        record_id: str, payload: DocumentIntelligenceAnalyzeRequest
    ) -> dict[str, Any]:
        if payload.approved is not True:
            raise HTTPException(status_code=409, detail="document_intelligence_consent_required")
        case_root, _rows, row = _resolve_record_rows(record_id)
        resolved = _record_capability_for_row(case_root, row)
        try:
            analysis = analyze_document(
                case_root=case_root,
                source_path=Path(resolved["path"]),
                source_hash=str(resolved["source_hash"]),
                run_docling=bool(payload.run_docling),
                run_presidio=bool(payload.run_presidio),
            )
        except DocumentIntelligenceError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None
        artifact = _attach_document_intelligence_artifact(
            case_root, analysis.get("artifact"), record_id=str(row.get("evidence_id") or "")
        )
        return {
            **analysis,
            "artifact": artifact,
            "record_id": str(row.get("evidence_id") or ""),
        }

    @app.post("/api/records/{record_id}/ocr")
    def record_document_ocr(
        record_id: str, payload: DocumentIntelligenceOcrRequest
    ) -> dict[str, Any]:
        case_root, _rows, row = _resolve_record_rows(record_id)
        resolved = _record_capability_for_row(case_root, row)
        try:
            result = create_ocr_preservation_copy(
                case_root=case_root,
                source_path=Path(resolved["path"]),
                source_hash=str(resolved["source_hash"]),
                approved=bool(payload.approved),
                language=str(payload.language or "eng")[:32],
            )
        except DocumentIntelligenceError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None
        output = dict(result)
        output["artifacts"] = {
            key: _attach_document_intelligence_artifact(
                case_root, value, record_id=str(row.get("evidence_id") or "")
            )
            for key, value in dict(result.get("artifacts") or {}).items()
        }
        output["record_id"] = str(row.get("evidence_id") or "")
        return output

    @app.get("/api/records/{record_id}/ocr-comparison")
    def record_document_ocr_comparison(record_id: str) -> dict[str, Any]:
        case_root, _rows, row = _resolve_record_rows(record_id)
        resolved = _record_capability_for_row(case_root, row)
        try:
            token, _binding = _find_record_artifact_binding(
                case_root,
                str(row.get("evidence_id") or ""),
                artifact_type_prefix="ocr_preservation",
            )
        except HTTPException:
            return {
                "schema_version": "ocr_comparison_response_v1",
                "record_id": str(row.get("evidence_id") or ""),
                "status": "blocked",
                "blockers": ["ocr_preservation_copy_not_found"],
                "review_required": True,
                "local_only": True,
            }
        receipt = _document_intelligence_receipt(token)
        comparison = dict(receipt.get("comparison") or {})
        comparison["source_sha256"] = str(resolved["source_hash"])
        return {
            "schema_version": "ocr_comparison_response_v1",
            "record_id": str(row.get("evidence_id") or ""),
            "status": "pass",
            "local_only": True,
            "review_required": True,
            "comparison": comparison,
            "receipt": receipt,
        }

    @app.post("/api/records/{record_id}/privacy-scan")
    def record_document_privacy_scan(
        record_id: str, payload: DocumentIntelligencePrivacyScanRequest
    ) -> dict[str, Any]:
        if payload.approved is not True:
            raise HTTPException(status_code=409, detail="document_intelligence_consent_required")
        case_root, _rows, row = _resolve_record_rows(record_id)
        resolved = _record_capability_for_row(case_root, row)
        try:
            analysis = analyze_document(
                case_root=case_root,
                source_path=Path(resolved["path"]),
                source_hash=str(resolved["source_hash"]),
                run_docling=False,
                run_presidio=bool(payload.run_presidio),
            )
        except DocumentIntelligenceError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None
        return {
            "schema_version": "record_privacy_scan_response_v1",
            "record_id": str(row.get("evidence_id") or ""),
            "local_only": True,
            "review_required": True,
            "privacy_review": analysis.get("privacy_review", {}),
            "integrity": analysis.get("integrity", {}),
            "provenance": analysis.get("provenance", {}),
        }

    @app.post("/api/records/{record_id}/redaction-proposal")
    def record_document_redaction_proposal(
        record_id: str, payload: DocumentIntelligenceRedactionRequest
    ) -> dict[str, Any]:
        case_root, _rows, row = _resolve_record_rows(record_id)
        resolved = _record_capability_for_row(case_root, row)
        try:
            analysis = analyze_document(
                case_root=case_root,
                source_path=Path(resolved["path"]),
                source_hash=str(resolved["source_hash"]),
                run_docling=False,
                run_presidio=bool(payload.run_presidio),
            )
        except DocumentIntelligenceError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None
        privacy = dict(analysis.get("privacy_review") or {})
        return {
            "schema_version": "record_redaction_proposal_v1",
            "record_id": str(row.get("evidence_id") or ""),
            "local_only": True,
            "review_required": True,
            "privacy_review": privacy,
            "redaction_candidates": [
                {
                    "span_start": int(item.get("start") or 0),
                    "span_end": int(item.get("end") or 0),
                    "rule": str(item.get("entity_type") or ""),
                    "replacement": str(item.get("replacement") or ""),
                    "recognizer": str(item.get("recognizer") or ""),
                }
                for item in privacy.get("findings") or []
                if isinstance(item, dict)
            ],
            "integrity": analysis.get("integrity", {}),
            "provenance": analysis.get("provenance", {}),
        }

    @app.post("/api/records/{record_id}/redacted-copy")
    def record_document_redacted_copy(
        record_id: str, payload: DocumentIntelligenceRedactionRequest
    ) -> dict[str, Any]:
        if payload.approved is not True:
            raise HTTPException(status_code=409, detail="document_intelligence_consent_required")
        case_root, _rows, row = _resolve_record_rows(record_id)
        resolved = _record_capability_for_row(case_root, row)
        try:
            result = create_redacted_copy(
                case_root=case_root,
                source_path=Path(resolved["path"]),
                source_hash=str(resolved["source_hash"]),
                approved=True,
                reviewer=str(payload.reviewer or "local_operator"),
                run_presidio=bool(payload.run_presidio),
            )
        except DocumentIntelligenceError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None
        output = dict(result)
        output["artifacts"] = {
            key: _attach_document_intelligence_artifact(
                case_root, value, record_id=str(row.get("evidence_id") or "")
            )
            for key, value in dict(result.get("artifacts") or {}).items()
        }
        output["record_id"] = str(row.get("evidence_id") or "")
        return output

    @app.get("/api/records/{record_id}/duplicates")
    def record_document_duplicates(record_id: str) -> dict[str, Any]:
        case_root, rows, row = _resolve_record_rows(record_id)
        report = _record_duplicate_report(rows, row)
        report["local_only"] = True
        return report

    @app.post("/api/records/compare")
    def compare_records(payload: RecordCompareRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        rows = load_case_search_records(case_root)
        by_id = {str(item.get("evidence_id") or ""): dict(item) for item in rows}
        left = by_id.get(str(payload.left_record_id or ""))
        right = by_id.get(str(payload.right_record_id or ""))
        if left is None or right is None:
            raise HTTPException(status_code=404, detail="record_not_found")
        left_text = _normalize_for_compare(
            str(left.get("text_excerpt") or left.get("text_content") or "")
        )
        right_text = _normalize_for_compare(
            str(right.get("text_excerpt") or right.get("text_content") or "")
        )
        similarity = (
            SequenceMatcher(None, left_text, right_text).ratio() if left_text or right_text else 0.0
        )
        field_differences = {}
        for field_name in (
            "source_hash",
            "page_count",
            "parser_status",
            "ocr_status",
            "text_status",
            "source_type",
            "canonical_document_key",
        ):
            if str(left.get(field_name) or "") != str(right.get(field_name) or ""):
                field_differences[field_name] = {
                    "left": left.get(field_name),
                    "right": right.get(field_name),
                }
        page_delta = int(right.get("page_count") or 0) - int(left.get("page_count") or 0)
        return {
            "schema_version": "record_compare_response_v1",
            "left_record_id": str(payload.left_record_id or ""),
            "right_record_id": str(payload.right_record_id or ""),
            "same": str(left.get("source_hash") or "") == str(right.get("source_hash") or ""),
            "exact_duplicate": str(left.get("source_hash") or "")
            == str(right.get("source_hash") or ""),
            "similarity": round(similarity, 6),
            "page_count_delta": page_delta,
            "text_additions": sorted(set(right_text.split()) - set(left_text.split()))[:100],
            "text_removals": sorted(set(left_text.split()) - set(right_text.split()))[:100],
            "field_differences": field_differences,
            "left": {
                "record_id": str(left.get("evidence_id") or ""),
                "source_hash": left.get("source_hash"),
                "page_count": left.get("page_count"),
                "parser_status": left.get("parser_status"),
                "ocr_status": left.get("ocr_status"),
            },
            "right": {
                "record_id": str(right.get("evidence_id") or ""),
                "source_hash": right.get("source_hash"),
                "page_count": right.get("page_count"),
                "parser_status": right.get("parser_status"),
                "ocr_status": right.get("ocr_status"),
            },
            "review_required": True,
            "local_only": True,
        }

    @app.get("/api/records/inspect/{token}")
    def inspect_record(token: str, page: int = 0) -> dict[str, Any]:
        """Return a bounded, safe local preview for any indexed record type."""
        return _record_inspection_payload(_resolve_record_capability(token, page))

    @app.get("/api/records/open/{token}")
    def open_record(token: str, page: int = 0, download: bool = False):  # type: ignore[no-untyped-def]
        """Open or download a hash-verified active-corpus source without exposing paths."""
        resolved = _resolve_record_capability(token, page)
        path = Path(resolved["path"])
        data = bytes(resolved["data"])
        suffix = str(resolved["suffix"])
        if "!" in str(resolved["source_locator"]):
            path = _materialize_open_cache(Path(resolved["case_root"]), data, suffix)

        # Never execute active HTML/SVG/script content in the local app origin.
        active_content = suffix in {".html", ".htm", ".svg", ".xml", ".js", ".mjs"}
        media_type = "text/plain; charset=utf-8" if active_content else str(resolved["mime_type"])
        force_attachment = bool(
            download
            or active_content
            or suffix in {".eml", ".mbox", ".mbx", ".docx", ".xlsx", ".pptx", ".zip"}
        )
        headers = {
            "X-MFL-Page": str(int(resolved["page"] or 0)),
            "X-MFL-Hash-Verified": "true",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        }
        return FileResponse(
            path,
            media_type=media_type,
            filename=str(resolved["filename"]),
            headers=headers,
            content_disposition_type="attachment" if force_attachment else "inline",
        )

    def _workspace_case_root() -> Path:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        return Path(case_root)

    def _raise_workspace_error(exc: DocumentWorkspaceError) -> None:
        raise HTTPException(
            status_code=int(exc.status_code),
            detail={"code": exc.code, "message": exc.message},
        ) from None

    def _document_workspace_filing_gate_headers(
        case_root: Path, document_id: str
    ) -> dict[str, str]:
        try:
            packet = ReviewedFilingPacketStore(case_root).active(document_id=document_id)
        except (DocumentWorkspaceError, ReviewedFilingPacketError):
            return {
                "X-MFLL-Filing-Gate-Status": "review_required",
                "X-MFLL-Filing-Gate-Blockers": "review_packet_missing",
            }
        filing_gate = (packet.get("packet") or {}).get("filing_gate") or {}
        blockers = [str(item) for item in (filing_gate.get("blockers") or []) if str(item)]
        gate_report = (
            filing_gate.get("gate_report") or filing_gate.get("immutable_gate_report") or {}
        )
        headers = {
            "X-MFLL-Filing-Gate-Status": str(
                filing_gate.get("export_status") or filing_gate.get("status") or "review_required"
            ),
            "X-MFLL-Filing-Gate-Blockers": ",".join(blockers) if blockers else "none",
        }
        report_hash = str(
            gate_report.get("immutable_report_hash")
            or filing_gate.get("immutable_report_hash")
            or ""
        )
        if report_hash:
            headers["X-MFLL-Filing-Gate-Hash"] = report_hash
        return headers

    def _raise_review_error(exc: ReviewLedgerError) -> None:
        raise HTTPException(
            status_code=int(exc.status_code),
            detail={"code": exc.code, "message": exc.message},
        ) from None

    @app.get("/api/document-workspace/status")
    def document_workspace_status() -> dict[str, Any]:
        try:
            status = workspace_status(_workspace_case_root())
            return status | {
                "docx": docx_engine_status(),
                "originals_immutable": bool(status.get("originals_preserved")),
                "explicit_confirmation_required": bool(
                    status.get("destructive_actions_approval_gated")
                ),
                "audit_chain": status.get("audit", {}),
            }
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)

    @app.get("/api/document-workspace/documents")
    def document_workspace_list(include_deleted: bool = False, limit: int = 200) -> dict[str, Any]:
        try:
            rows = list_workspace_documents(
                _workspace_case_root(),
                include_deleted=bool(include_deleted),
                limit=limit,
            )
            return {
                "schema_version": "document_workspace_list_v1",
                "documents": rows,
                "count": len(rows),
                "local_only": True,
                "review_required_default": True,
            }
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)

    @app.post("/api/document-workspace/documents")
    def document_workspace_create(payload: WorkspaceDocumentCreateRequest) -> dict[str, Any]:
        try:
            document = create_workspace_document(
                _workspace_case_root(),
                title=payload.title,
                content=payload.content,
                document_type=payload.document_type,
                note=payload.note,
                tags=payload.tags,
                source_refs=payload.source_refs,
            )
            return {
                "status": "created",
                "document": document,
                "actions": [
                    {"type": "open_document_workspace", "document_id": document["document_id"]},
                    {
                        "type": "export_document",
                        "format": "docx",
                        "document_id": document["document_id"],
                    },
                ],
                "review_required": True,
                "filing_ready": False,
            }
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)

    @app.get("/api/document-workspace/documents/{document_id}")
    def document_workspace_get(document_id: str) -> dict[str, Any]:
        try:
            return {
                "document": get_workspace_document(_workspace_case_root(), document_id),
                "local_only": True,
            }
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)

    @app.post("/api/document-workspace/documents/{document_id}/proposals")
    def document_workspace_propose(
        document_id: str,
        payload: WorkspaceRevisionProposalRequest,
    ) -> dict[str, Any]:
        try:
            proposal = propose_workspace_revision(
                _workspace_case_root(),
                document_id,
                content=payload.content,
                base_revision_id=payload.base_revision_id,
                note=payload.note,
            )
            return {
                "status": "proposal_ready",
                "proposal": proposal,
                "requires_explicit_confirmation": True,
                "original_preserved": True,
            }
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)

    @app.post("/api/document-workspace/documents/{document_id}/commit")
    def document_workspace_commit(
        document_id: str,
        payload: WorkspaceRevisionCommitRequest,
    ) -> dict[str, Any]:
        try:
            document = commit_workspace_revision(
                _workspace_case_root(),
                document_id,
                revision_id=payload.revision_id,
                confirmation_token=payload.confirmation_token,
                confirmed=payload.confirmed,
            )
            return {
                "status": "committed",
                "document": document,
                "original_preserved": True,
                "review_required": True,
                "filing_ready": False,
            }
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)

    @app.post("/api/document-workspace/documents/{document_id}/reject")
    def document_workspace_reject(
        document_id: str,
        payload: WorkspaceRevisionRejectRequest,
    ) -> dict[str, Any]:
        try:
            return {
                "status": "rejected",
                "document": reject_workspace_revision(
                    _workspace_case_root(),
                    document_id,
                    revision_id=payload.revision_id,
                ),
            }
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)

    @app.post("/api/document-workspace/documents/{document_id}/delete-request")
    def document_workspace_delete_request(document_id: str) -> dict[str, Any]:
        try:
            return request_soft_delete(_workspace_case_root(), document_id)
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)

    @app.post("/api/document-workspace/documents/{document_id}/delete")
    def document_workspace_delete(
        document_id: str,
        payload: WorkspaceDeleteCommitRequest,
    ) -> dict[str, Any]:
        try:
            return commit_soft_delete(
                _workspace_case_root(),
                document_id,
                confirmation_token=payload.confirmation_token,
                confirmed=payload.confirmed,
            )
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)

    @app.post("/api/document-workspace/documents/{document_id}/restore")
    def document_workspace_restore(document_id: str) -> dict[str, Any]:
        try:
            return {
                "status": "restored",
                "document": restore_workspace_document(_workspace_case_root(), document_id),
            }
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)

    @app.post("/api/document-workspace/import-record")
    def document_workspace_import_record(payload: WorkspaceImportRecordRequest) -> dict[str, Any]:
        try:
            resolved = _resolve_record_capability(payload.source_token, payload.page)
            parsed = parse_bytes(
                bytes(resolved["data"]),
                suffix=str(resolved["suffix"]),
                locator=str(resolved["filename"]),
            )
            row = dict(resolved.get("row") or {})
            content = str(parsed.text or row.get("text_content") or row.get("text_excerpt") or "")
            if not content.strip():
                content = (
                    "[No editable text was extracted from this preserved source. "
                    "Use the document inspector to review the original and OCR it if needed.]"
                )
            title = payload.title.strip() or str(resolved["filename"])
            source_ref = {
                "source_id": str(resolved["binding"].get("evidence_id") or ""),
                "title": str(resolved["filename"]),
                "source_class": str(row.get("source_type") or str(resolved["suffix"]).lstrip(".")),
                "hash": str(resolved["source_hash"]),
                "page": int(resolved.get("page") or 0),
                "safe_locator": _public_source_locator(str(resolved["source_locator"])),
            }
            document = create_workspace_document(
                _workspace_case_root(),
                title=title,
                content=content,
                document_type=payload.document_type,
                note="Imported from a hash-verified private record. Original preserved separately.",
                source_refs=[source_ref],
            )
            preserved = save_imported_source(
                _workspace_case_root(),
                document_id=str(document["document_id"]),
                data=bytes(resolved["data"]),
                suffix=str(resolved["suffix"]),
                source_hash=str(resolved["source_hash"]),
            )
            return {
                "status": "imported",
                "document": document,
                "preserved_source": preserved,
                "actions": [
                    {"type": "open_document_workspace", "document_id": document["document_id"]},
                    {"type": "inspect_source", "source_token": payload.source_token},
                ],
                "original_preserved": True,
                "review_required": True,
            }
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)

    @app.get("/api/document-workspace/documents/{document_id}/export")
    def document_workspace_export(document_id: str, format: str = "txt"):  # type: ignore[no-untyped-def,redefined-builtin]
        try:
            case_root = _workspace_case_root()
            requested = str(format or "txt").lower()
            document = get_workspace_document(case_root, document_id)
            gate_headers = _document_workspace_filing_gate_headers(case_root, document_id)
            if requested in {"txt", "md"}:
                path = export_text_artifact(case_root, document_id, format_name=requested)
            elif requested == "docx":
                paths = workspace_paths(case_root)
                slug = (
                    re.sub(r"[^A-Za-z0-9._-]+", "-", str(document["title"])).strip("-.")[:80]
                    or "document"
                )
                path = paths.exports / f"{slug}-{str(document['current_revision_id'])[:8]}.docx"
                result = create_docx_from_text(
                    title=str(document["title"]),
                    content=str(document.get("content") or ""),
                    output_path=path,
                    allowed_output_root=paths.exports,
                )
                record_artifact_event(
                    case_root,
                    document_id=document_id,
                    revision_id=str(document["current_revision_id"]),
                    format_name="docx",
                    artifact_sha256=str(result["sha256"]),
                    size_bytes=int(result["size_bytes"]),
                )
            else:
                raise DocumentWorkspaceError(
                    "unsupported_export_format",
                    "Supported export formats are txt, md, and docx.",
                )
            media_type = {
                ".txt": "text/plain; charset=utf-8",
                ".md": "text/markdown; charset=utf-8",
                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            }.get(path.suffix.lower(), "application/octet-stream")
            return FileResponse(
                path,
                media_type=media_type,
                filename=path.name,
                content_disposition_type="attachment",
                headers={
                    "Cache-Control": "no-store",
                    "X-Content-Type-Options": "nosniff",
                    **gate_headers,
                },
            )
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)

    def _raise_evidence_work_product_error(exc: EvidenceWorkProductError) -> None:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    def _raise_matter_command_center_error(exc: MatterCommandCenterError) -> None:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    def _matter_command_center_store() -> MatterCommandCenterStore:
        case_root = active_case_root()
        if case_root is None:
            raise MatterCommandCenterError(
                "active_matter_unavailable", "The active matter is unavailable.", status_code=409
            )
        return MatterCommandCenterStore(case_root)

    def _matter_command_center_records() -> list[dict[str, Any]]:
        case_root = active_case_root()
        if case_root is None:
            return []
        return load_case_search_records(case_root)

    def _prune_evidence_work_product_artifacts(now: float | None = None) -> None:
        current = float(now if now is not None else time.time())
        stale_before = current - _EVIDENCE_WORK_PRODUCT_ARTIFACT_TTL_SECONDS
        with _evidence_work_product_artifact_lock:
            stale = [
                token
                for token, binding in _evidence_work_product_artifacts.items()
                if float(binding.get("created_at") or 0) < stale_before
            ]
            for token in stale:
                _evidence_work_product_artifacts.pop(token, None)
            if len(_evidence_work_product_artifacts) > _EVIDENCE_WORK_PRODUCT_ARTIFACT_MAX_TOKENS:
                overflow = (
                    len(_evidence_work_product_artifacts)
                    - _EVIDENCE_WORK_PRODUCT_ARTIFACT_MAX_TOKENS
                )
                oldest = sorted(
                    _evidence_work_product_artifacts.items(),
                    key=lambda item: float(item[1].get("created_at") or 0),
                )[:overflow]
                for token, _binding in oldest:
                    _evidence_work_product_artifacts.pop(token, None)

    def _evidence_work_product_artifact_token(
        case_root: Path,
        *,
        build_id: str,
        filename: str,
        sha256: str,
    ) -> str:
        store = EvidenceWorkProductStore(case_root)
        path, _media_type = store.resolve_artifact(build_id, filename)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if sha256 and actual != str(sha256).lower():
            raise HTTPException(
                status_code=409, detail="evidence_work_product_artifact_hash_mismatch"
            )
        _prune_evidence_work_product_artifacts()
        token = secrets.token_hex(32)
        with _evidence_work_product_artifact_lock:
            _evidence_work_product_artifacts[token] = {
                "case_id": _case_id(case_root),
                "build_id": build_id,
                "filename": Path(filename).name,
                "sha256": actual,
                "created_at": time.time(),
            }
        return token

    def _public_evidence_work_product_result(
        case_root: Path, result: dict[str, Any]
    ) -> dict[str, Any]:
        output = dict(result)
        build_id = str(output.get("build_id") or "")
        public_artifacts = []
        for raw in output.get("artifacts") or []:
            if not isinstance(raw, dict):
                continue
            row = dict(raw)
            filename = Path(str(row.pop("relative_path", "") or row.get("name") or "")).name
            if not filename:
                continue
            token = _evidence_work_product_artifact_token(
                case_root,
                build_id=build_id,
                filename=filename,
                sha256=str(row.get("sha256") or ""),
            )
            row["filename"] = filename
            row["download_token"] = token
            row["download_url"] = f"/api/evidence-work-product/artifacts/{token}"
            public_artifacts.append(row)
        output["artifacts"] = public_artifacts
        return output

    @app.get("/api/evidence-work-product/status")
    def evidence_work_product_status() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            return {
                "status": "unavailable",
                "active_matter": False,
                "indexed_record_count": 0,
                "active_build": None,
                "local_only": True,
                "review_required": True,
            }
        records = load_case_search_records(case_root)
        active_build: dict[str, Any] | None = None
        try:
            active = EvidenceWorkProductStore(case_root).active()
            if active.get("status") == "pass":
                packet = active.get("packet") or {}
                active_build = {
                    "build_id": active.get("build_id"),
                    "summary": packet.get("summary") or {},
                    "generated_at": packet.get("generated_at"),
                    "verification": active.get("verification") or {},
                }
        except EvidenceWorkProductError:
            active_build = None
        return {
            "status": "ready",
            "active_matter": True,
            "indexed_record_count": len(records),
            "active_build": active_build,
            "local_only": True,
            "review_required": True,
        }

    @app.post("/api/evidence-work-product/build")
    def evidence_work_product_build(payload: EvidenceWorkProductBuildRequest) -> dict[str, Any]:
        if payload.approved is not True:
            raise HTTPException(status_code=409, detail="evidence_work_product_consent_required")
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        selected = [] if payload.include_all_records else list(payload.selected_evidence_ids or [])
        if not payload.include_all_records and not selected:
            raise HTTPException(status_code=400, detail="selected_evidence_id_required")
        try:
            result = EvidenceWorkProductStore(case_root).build(
                load_case_search_records(case_root),
                selected_evidence_ids=selected,
                focus_terms=payload.focus_terms,
                activate=True,
            )
            return _public_evidence_work_product_result(case_root, result.as_dict())
        except EvidenceWorkProductError as exc:
            _raise_evidence_work_product_error(exc)

    @app.get("/api/evidence-work-product/active")
    def evidence_work_product_active() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _public_evidence_work_product_result(
                case_root, EvidenceWorkProductStore(case_root).active()
            )
        except EvidenceWorkProductError as exc:
            _raise_evidence_work_product_error(exc)

    @app.get("/api/evidence-work-product/verify")
    def evidence_work_product_verify(build_id: str = "") -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return EvidenceWorkProductStore(case_root).verify(build_id or None)
        except EvidenceWorkProductError as exc:
            _raise_evidence_work_product_error(exc)

    @app.get("/api/evidence-work-product/artifacts/{token}")
    def evidence_work_product_artifact_download(token: str):  # type: ignore[no-untyped-def]
        token = str(token or "").strip().lower()
        if not re.fullmatch(r"[a-f0-9]{64}", token):
            raise HTTPException(
                status_code=404, detail="evidence_work_product_artifact_not_available"
            )
        _prune_evidence_work_product_artifacts()
        case_root = active_case_root()
        with _evidence_work_product_artifact_lock:
            binding = dict(_evidence_work_product_artifacts.get(token) or {})
        if case_root is None or not binding or binding.get("case_id") != _case_id(case_root):
            raise HTTPException(
                status_code=404, detail="evidence_work_product_artifact_not_available"
            )
        try:
            path, media_type = EvidenceWorkProductStore(case_root).resolve_artifact(
                str(binding.get("build_id") or ""),
                str(binding.get("filename") or ""),
            )
        except EvidenceWorkProductError as exc:
            _raise_evidence_work_product_error(exc)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != str(binding.get("sha256") or ""):
            raise HTTPException(
                status_code=409, detail="evidence_work_product_artifact_hash_mismatch"
            )
        return FileResponse(
            path,
            filename=path.name,
            media_type=media_type,
            content_disposition_type="attachment",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    @app.get("/api/matters/{matter_id}/command-center")
    def matter_command_center(matter_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            return {
                "status": "blocked",
                "blockers": ["active_matter_unavailable"],
                "review_required": True,
            }
        try:
            return _matter_command_center_store().command_center(
                matter_id, _matter_command_center_records()
            )
        except MatterCommandCenterError as exc:
            _raise_matter_command_center_error(exc)

    @app.post("/api/matters/{matter_id}/review-snapshot")
    def matter_review_snapshot(
        matter_id: str, payload: MatterCommandCenterSnapshotRequest
    ) -> dict[str, Any]:
        try:
            result = _matter_command_center_store().freeze_snapshot(
                matter_id,
                _matter_command_center_records(),
                selected_record_ids=payload.selected_record_ids,
                variant=payload.variant,
                approved=payload.approved,
                note=payload.note,
            )
            return result
        except MatterCommandCenterError as exc:
            _raise_matter_command_center_error(exc)

    @app.post("/api/matters/{matter_id}/evidence-packet")
    def matter_evidence_packet(
        matter_id: str, payload: MatterCommandCenterPacketRequest
    ) -> dict[str, Any]:
        try:
            result = _matter_command_center_store().build_evidence_packet(
                matter_id,
                _matter_command_center_records(),
                selected_record_ids=payload.selected_record_ids,
                snapshot_id=payload.snapshot_id,
                variant=payload.variant,
                approved=payload.approved,
                note=payload.note,
            )
            return result
        except MatterCommandCenterError as exc:
            _raise_matter_command_center_error(exc)

    @app.get("/api/matters/{matter_id}/evidence-packet")
    def matter_evidence_packet_get(matter_id: str) -> dict[str, Any]:
        try:
            store = _matter_command_center_store()
            command_center = store.command_center(matter_id, _matter_command_center_records())
            packet_id = str(command_center.get("latest_packet_id") or "")
            if not packet_id:
                return {
                    "status": "blocked",
                    "blockers": ["matter_evidence_packet_unavailable"],
                    "review_required": True,
                }
            return store.packet(packet_id)
        except MatterCommandCenterError as exc:
            _raise_matter_command_center_error(exc)

    @app.get("/api/matters/{matter_id}/evidence-packets")
    def matter_evidence_packets(matter_id: str) -> dict[str, Any]:
        try:
            return _matter_command_center_store().list_packets(matter_id)
        except MatterCommandCenterError as exc:
            _raise_matter_command_center_error(exc)

    @app.get("/api/evidence-packets/{packet_id}")
    def matter_evidence_packet_get_by_id(packet_id: str) -> dict[str, Any]:
        try:
            return _matter_command_center_store().packet(packet_id)
        except MatterCommandCenterError as exc:
            _raise_matter_command_center_error(exc)

    @app.get("/api/evidence-packets/{packet_id}/receipt")
    def matter_evidence_packet_receipt(packet_id: str) -> dict[str, Any]:
        try:
            return _matter_command_center_store().receipt(packet_id)
        except MatterCommandCenterError as exc:
            _raise_matter_command_center_error(exc)

    @app.post("/api/evidence-packets/{packet_id}/review")
    def matter_evidence_packet_review(
        packet_id: str, payload: MatterCommandCenterPacketReviewRequest
    ) -> dict[str, Any]:
        try:
            return _matter_command_center_store().review_packet(
                packet_id,
                reviewer_name=payload.reviewer_name,
                reviewer_role=payload.reviewer_role,
                review_status=payload.review_status,
                note=payload.note,
                approved=payload.approved,
            )
        except MatterCommandCenterError as exc:
            _raise_matter_command_center_error(exc)

    @app.post("/api/evidence-packets/{packet_id}/compare")
    def matter_evidence_packet_compare(
        packet_id: str, payload: MatterCommandCenterPacketCompareRequest
    ) -> dict[str, Any]:
        try:
            left_packet_id = payload.left_packet_id or packet_id
            right_packet_id = payload.right_packet_id
            return _matter_command_center_store().compare_packets(left_packet_id, right_packet_id)
        except MatterCommandCenterError as exc:
            _raise_matter_command_center_error(exc)

    def _raise_evidence_review_error(exc: Exception) -> None:
        detail = str(exc) or exc.__class__.__name__
        if detail == "case_root_unavailable":
            raise HTTPException(status_code=404, detail="active_matter_unavailable") from None
        if detail in {"event_not_found", "claim_not_found", "ledger_event_not_found"}:
            raise HTTPException(status_code=404, detail=detail) from None
        if detail == "operative_order_language_required":
            raise HTTPException(status_code=409, detail=detail) from None
        if detail.startswith("unsupported_export"):
            raise HTTPException(status_code=400, detail=detail) from None
        raise HTTPException(status_code=400, detail=detail) from None

    def _review_store(case_root: Path) -> EvidenceReviewStore:
        return EvidenceReviewStore(case_root)

    def _review_records(
        case_root: Path, selected_record_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        rows = load_case_search_records(case_root)
        selected = {str(item).strip() for item in (selected_record_ids or []) if str(item).strip()}
        if not selected:
            return rows
        return [
            row
            for row in rows
            if str(row.get("evidence_id") or "") in selected
            or str(row.get("parent_evidence_id") or "") in selected
        ]

    @app.post("/api/timeline/build")
    def timeline_build(payload: EvidenceTimelineBuildRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).build_timeline(
                _review_records(case_root, payload.selected_record_ids),
                selected_record_ids=payload.selected_record_ids,
                issue_tags=payload.issue_tags,
                source_types=payload.source_types,
                allegation_observation_finding=payload.allegation_observation_finding,
                date_start=payload.date_start or None,
                date_end=payload.date_end or None,
                cancel_requested=bool(payload.cancel_requested),
            )
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.get("/api/timeline")
    def timeline_get(limit: int = 200, offset: int = 0) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        return _review_store(case_root).get_timeline(limit=limit, offset=offset)

    @app.post("/api/timeline/events")
    def timeline_event_create(payload: EvidenceTimelineEventCreateRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).create_event(payload.model_dump())
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.patch("/api/timeline/events/{event_id}")
    def timeline_event_patch(
        event_id: str, payload: EvidenceTimelineEventPatchRequest
    ) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            data = {key: value for key, value in payload.model_dump().items() if value is not None}
            return _review_store(case_root).patch_event(event_id, data)
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.get("/api/timeline/events/{event_id}/history")
    def timeline_event_history(event_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).get_event_history(event_id)
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.post("/api/evidence/claims")
    def evidence_claim_create(payload: EvidenceClaimCreateRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).create_claim(
                payload.model_dump(),
                records=_review_records(case_root, payload.selected_record_ids),
            )
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.post("/api/evidence/claims/{claim_id}/review")
    def evidence_claim_review(claim_id: str, payload: EvidenceClaimReviewRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).review_claim(claim_id, payload.model_dump())
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.get("/api/evidence/claims/{claim_id}")
    def evidence_claim_get(claim_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).get_claim(claim_id)
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.get("/api/evidence/coverage")
    def evidence_coverage(selected_record_ids: str = "") -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        selected = [item.strip() for item in selected_record_ids.split(",") if item.strip()]
        return _review_store(case_root).coverage(
            records=_review_records(case_root, selected), selected_record_ids=selected
        )

    @app.post("/api/evidence/missing-records")
    def evidence_missing_records(payload: EvidenceMissingRecordsRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).create_missing_records(
                payload.model_dump(),
                records=_review_records(case_root, payload.selected_record_ids),
            )
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.get("/api/enforcement/ledger")
    def enforcement_ledger() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        return _review_store(case_root).get_ledger()

    @app.post("/api/enforcement/ledger/events")
    def enforcement_ledger_event_create(
        payload: EvidenceLedgerEventCreateRequest,
    ) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).create_ledger_event(payload.model_dump())
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.patch("/api/enforcement/ledger/events/{event_id}")
    def enforcement_ledger_event_patch(
        event_id: str, payload: EvidenceLedgerEventPatchRequest
    ) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            data = {key: value for key, value in payload.model_dump().items() if value is not None}
            return _review_store(case_root).patch_ledger_event(event_id, data)
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.get("/api/evidence/review-history")
    def evidence_review_history(limit: int = 200, offset: int = 0) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        return _review_store(case_root).get_review_history(limit=limit, offset=offset)

    @app.post("/api/evidence/export")
    def evidence_export(payload: EvidenceExportRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).export_work_product(
                export_kind=payload.export_kind,
                format_name=payload.format,
                selected_record_ids=payload.selected_record_ids,
            )
        except Exception as exc:
            _raise_evidence_review_error(exc)

    def _raise_retrieval_workbench_error(exc: RetrievalWorkbenchError) -> None:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/retrieval-workbench/status")
    def retrieval_workbench_status() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            return {
                "status": "blocked",
                "blockers": ["active_matter_unavailable"],
                "review_required": True,
            }
        records = load_case_search_records(case_root)
        return RetrievalWorkbenchService(case_root).status(private_record_count=len(records))

    @app.post("/api/retrieval-workbench/search")
    def retrieval_workbench_search(payload: RetrievalWorkbenchSearchRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return RetrievalWorkbenchService(case_root).search(
                payload.query,
                private_records=load_case_search_records(case_root),
                include_private_records=payload.include_private_records,
                include_authority=payload.include_authority,
                top_k=payload.top_k,
            )
        except RetrievalWorkbenchError as exc:
            _raise_retrieval_workbench_error(exc)

    @app.post("/api/retrieval-workbench/evaluate")
    def retrieval_workbench_evaluate(payload: RetrievalWorkbenchEvalRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return RetrievalWorkbenchService(case_root).evaluate_attorney_gold(
                min_rows=max(1, min(int(payload.min_attorney_rows or 1), 5_000)),
                top_k=max(1, min(int(payload.top_k or 20), 100)),
            )
        except RetrievalWorkbenchError as exc:
            _raise_retrieval_workbench_error(exc)

    def _raise_release_pilot_hardening_error(exc: ReleasePilotHardeningError) -> None:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    def _release_hardening_repo_root() -> Path:
        return find_source_root(Path(__file__).resolve())

    @app.get("/api/release-pilot-hardening/status")
    def release_pilot_hardening_status() -> dict[str, Any]:
        return ReleasePilotHardeningService(
            _release_hardening_repo_root(),
            active_case_root(),
        ).status()

    @app.post("/api/release-pilot-hardening/evidence/audit")
    def release_pilot_hardening_evidence_audit(
        payload: ReleaseHardeningEvidenceAuditRequest,
    ) -> dict[str, Any]:
        if payload.approved is not True:
            raise HTTPException(status_code=409, detail="release_evidence_audit_approval_required")
        try:
            result = ReleaseEvidenceAuditor(_release_hardening_repo_root()).audit()
            case_root = active_case_root()
            if case_root is not None:
                PrivacySafeObservabilityStore(case_root).record(
                    "api_request",
                    metrics={"count": 1},
                    labels={
                        "component": "release_hardening",
                        "operation": "evidence_audit",
                        "status": result.get("status") or "blocked",
                    },
                )
            return result
        except ReleasePilotHardeningError as exc:
            _raise_release_pilot_hardening_error(exc)

    @app.post("/api/release-pilot-hardening/observability/self-test")
    def release_pilot_hardening_observability_self_test(
        payload: ReleaseHardeningObservabilityRequest,
    ) -> dict[str, Any]:
        if payload.approved is not True:
            raise HTTPException(status_code=409, detail="observability_self_test_approval_required")
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            store = PrivacySafeObservabilityStore(case_root)
            record = store.record(
                "self_test",
                metrics={"count": 1, "duration_ms": 0},
                labels={
                    "component": "local_observability",
                    "operation": "self_test",
                    "status": "pass",
                },
            )
            return {
                "status": "pass",
                "record": record,
                "verification": store.verify(),
                "review_required": True,
            }
        except ReleasePilotHardeningError as exc:
            _raise_release_pilot_hardening_error(exc)

    @app.post("/api/release-pilot-hardening/backup-restore/drill")
    def release_pilot_hardening_backup_restore_drill(
        payload: ReleaseHardeningBackupDrillRequest,
    ) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            started = time.perf_counter()
            result = MatterBackupRestoreDrill(
                case_root,
                repo_root=_release_hardening_repo_root(),
            ).run(approved=payload.approved)
            PrivacySafeObservabilityStore(case_root).record(
                "backup_restore",
                metrics={
                    "count": 1,
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                    "bytes": int(result.get("total_bytes") or 0),
                },
                labels={
                    "component": "matter_backup",
                    "operation": "restore_rehearsal",
                    "status": result.get("status") or "blocked",
                },
            )
            return result
        except ReleasePilotHardeningError as exc:
            _raise_release_pilot_hardening_error(exc)

    @app.post("/api/release-pilot-hardening/pilot/participants")
    def release_pilot_hardening_pilot_participant(
        payload: AttorneySandboxParticipantRequest,
    ) -> dict[str, Any]:
        try:
            return AttorneySandboxStore(_release_hardening_repo_root()).register_participant(
                participant_id=payload.participant_id,
                role=payload.role,
                bar_status_verified=payload.bar_status_verified,
                verification_reference_sha256=payload.verification_reference_sha256,
                terms_accepted=payload.terms_accepted,
                training_modules=payload.training_modules,
            )
        except ReleasePilotHardeningError as exc:
            _raise_release_pilot_hardening_error(exc)

    @app.post("/api/release-pilot-hardening/pilot/sessions")
    def release_pilot_hardening_pilot_session(
        payload: AttorneySandboxSessionRequest,
    ) -> dict[str, Any]:
        try:
            return AttorneySandboxStore(_release_hardening_repo_root()).start_session(
                participant_id=payload.participant_id,
                data_classification=payload.data_classification,
                approved=payload.approved,
            )
        except ReleasePilotHardeningError as exc:
            _raise_release_pilot_hardening_error(exc)

    @app.post("/api/release-pilot-hardening/pilot/feedback")
    def release_pilot_hardening_pilot_feedback(
        payload: AttorneySandboxFeedbackRequest,
    ) -> dict[str, Any]:
        try:
            return AttorneySandboxStore(_release_hardening_repo_root()).add_feedback(
                participant_id=payload.participant_id,
                session_id=payload.session_id,
                category=payload.category,
                severity=payload.severity,
                description=payload.description,
            )
        except ReleasePilotHardeningError as exc:
            _raise_release_pilot_hardening_error(exc)

    @app.get("/api/release-pilot-hardening/pilot/dashboard")
    def release_pilot_hardening_pilot_dashboard() -> dict[str, Any]:
        try:
            return AttorneySandboxStore(_release_hardening_repo_root()).dashboard()
        except ReleasePilotHardeningError as exc:
            _raise_release_pilot_hardening_error(exc)

    def _raise_sandbox_operations_error(exc: AttorneySandboxOperationsError) -> None:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    def _sandbox_operations_store() -> AttorneySandboxOperationsStore:
        return AttorneySandboxOperationsStore(_release_hardening_repo_root())

    def _sandbox_operations_scope(store: AttorneySandboxOperationsStore) -> str:
        if store.root is None:
            return ""
        return hashlib.sha256(str(store.root.resolve()).encode("utf-8")).hexdigest()

    def _prune_sandbox_operations_artifacts(now: float | None = None) -> None:
        current = float(now if now is not None else time.time())
        stale_before = current - _SANDBOX_OPERATIONS_ARTIFACT_TTL_SECONDS
        with _sandbox_operations_artifact_lock:
            stale = [
                token
                for token, binding in _sandbox_operations_artifacts.items()
                if float(binding.get("created_at") or 0) < stale_before
            ]
            for token in stale:
                _sandbox_operations_artifacts.pop(token, None)
            if len(_sandbox_operations_artifacts) > _SANDBOX_OPERATIONS_ARTIFACT_MAX_TOKENS:
                overflow = (
                    len(_sandbox_operations_artifacts) - _SANDBOX_OPERATIONS_ARTIFACT_MAX_TOKENS
                )
                oldest = sorted(
                    _sandbox_operations_artifacts.items(),
                    key=lambda item: float(item[1].get("created_at") or 0),
                )[:overflow]
                for token, _binding in oldest:
                    _sandbox_operations_artifacts.pop(token, None)

    def _public_sandbox_operations_artifacts(
        store: AttorneySandboxOperationsStore,
        result: dict[str, Any],
    ) -> list[dict[str, Any]]:
        generation_id = str(result.get("generation_id") or "")
        public: list[dict[str, Any]] = []
        _prune_sandbox_operations_artifacts()
        for artifact in result.get("artifacts") or []:
            if not isinstance(artifact, dict):
                continue
            filename = str(artifact.get("filename") or "")
            sha256 = str(artifact.get("sha256") or "")
            if not filename or not re.fullmatch(r"[a-f0-9]{64}", sha256):
                continue
            token = secrets.token_hex(32)
            with _sandbox_operations_artifact_lock:
                _sandbox_operations_artifacts[token] = {
                    "created_at": time.time(),
                    "scope": _sandbox_operations_scope(store),
                    "generation_id": generation_id,
                    "filename": filename,
                    "sha256": sha256,
                }
            public.append(
                {
                    "filename": filename,
                    "sha256": sha256,
                    "size_bytes": int(artifact.get("size_bytes") or 0),
                    "download_url": f"/api/attorney-sandbox-operations/artifacts/{token}",
                }
            )
        return public

    @app.get("/api/attorney-sandbox-operations/status")
    def attorney_sandbox_operations_status() -> dict[str, Any]:
        try:
            return _sandbox_operations_store().status()
        except AttorneySandboxOperationsError as exc:
            return {
                "status": "blocked",
                "blockers": [exc.code],
                "real_matter_allowed": False,
                "pass48_complete": False,
                "external_launch_evidence_gate_required": True,
            }

    @app.post("/api/attorney-sandbox-operations/programs")
    def attorney_sandbox_operations_program(
        payload: AttorneySandboxProgramRequest,
    ) -> dict[str, Any]:
        try:
            return _sandbox_operations_store().create_program(
                program_id=payload.program_id,
                max_questions=max(1, min(int(payload.max_questions or 48), 250)),
                approved=payload.approved,
            )
        except AttorneySandboxOperationsError as exc:
            _raise_sandbox_operations_error(exc)

    @app.post("/api/attorney-sandbox-operations/cohorts")
    def attorney_sandbox_operations_cohort(payload: AttorneySandboxCohortRequest) -> dict[str, Any]:
        try:
            return _sandbox_operations_store().create_cohort(
                program_id=payload.program_id,
                cohort_id=payload.cohort_id,
                participant_ids=payload.participant_ids,
                approved=payload.approved,
            )
        except AttorneySandboxOperationsError as exc:
            _raise_sandbox_operations_error(exc)

    @app.post("/api/attorney-sandbox-operations/assignments")
    def attorney_sandbox_operations_assignment(
        payload: AttorneySandboxAssignmentRequest,
    ) -> dict[str, Any]:
        try:
            return _sandbox_operations_store().create_assignment(
                program_id=payload.program_id,
                cohort_id=payload.cohort_id,
                participant_id=payload.participant_id,
                question_ids=payload.question_ids,
                data_classification=payload.data_classification,
                approved=payload.approved,
            )
        except AttorneySandboxOperationsError as exc:
            _raise_sandbox_operations_error(exc)

    @app.post("/api/attorney-sandbox-operations/reviews")
    def attorney_sandbox_operations_review(
        payload: AttorneySandboxStructuredReviewRequest,
    ) -> dict[str, Any]:
        try:
            return _sandbox_operations_store().submit_review(
                participant_id=payload.participant_id,
                session_id=payload.session_id,
                question_id=payload.question_id,
                disposition=payload.disposition,
                source_grounding_rating=payload.source_grounding_rating,
                legal_accuracy_rating=payload.legal_accuracy_rating,
                usefulness_rating=payload.usefulness_rating,
                boundary_safety_rating=payload.boundary_safety_rating,
                citation_quality_rating=payload.citation_quality_rating,
                finding_codes=payload.finding_codes,
                response_artifact_sha256=payload.response_artifact_sha256,
                verifier_report_sha256=payload.verifier_report_sha256,
                comment=payload.comment,
                approved=payload.approved,
            )
        except AttorneySandboxOperationsError as exc:
            _raise_sandbox_operations_error(exc)

    @app.post("/api/attorney-sandbox-operations/sessions/complete")
    def attorney_sandbox_operations_complete(
        payload: AttorneySandboxSessionCompleteRequest,
    ) -> dict[str, Any]:
        try:
            return _sandbox_operations_store().complete_session(
                participant_id=payload.participant_id,
                session_id=payload.session_id,
                approved=payload.approved,
            )
        except AttorneySandboxOperationsError as exc:
            _raise_sandbox_operations_error(exc)

    @app.post("/api/attorney-sandbox-operations/feedback/triage")
    def attorney_sandbox_operations_triage(
        payload: AttorneySandboxFeedbackTriageRequest,
    ) -> dict[str, Any]:
        try:
            return _sandbox_operations_store().triage_feedback(
                feedback_id=payload.feedback_id,
                status=payload.status,
                disposition_note=payload.disposition_note,
                remediation_evidence_sha256=payload.remediation_evidence_sha256,
                approved=payload.approved,
            )
        except AttorneySandboxOperationsError as exc:
            _raise_sandbox_operations_error(exc)

    @app.post("/api/attorney-sandbox-operations/attestations")
    def attorney_sandbox_operations_attestation(
        payload: AttorneySandboxAttestationRequest,
    ) -> dict[str, Any]:
        try:
            return _sandbox_operations_store().record_external_attestation(
                attestation_type=payload.attestation_type,
                evidence_sha256=payload.evidence_sha256,
                approved=payload.approved,
            )
        except AttorneySandboxOperationsError as exc:
            _raise_sandbox_operations_error(exc)

    @app.post("/api/attorney-sandbox-operations/eval/export")
    def attorney_sandbox_operations_eval_export(
        payload: AttorneySandboxEvalExportRequest,
    ) -> dict[str, Any]:
        try:
            return _sandbox_operations_store().export_eval_candidates(
                payload.eval_root, approved=payload.approved
            )
        except AttorneySandboxOperationsError as exc:
            _raise_sandbox_operations_error(exc)

    @app.post("/api/attorney-sandbox-operations/evidence/build")
    def attorney_sandbox_operations_evidence_build(
        payload: AttorneySandboxEvidenceBuildRequest,
    ) -> dict[str, Any]:
        try:
            store = _sandbox_operations_store()
            result = store.build_evidence_packet(approved=payload.approved)
            return {**result, "artifacts": _public_sandbox_operations_artifacts(store, result)}
        except AttorneySandboxOperationsError as exc:
            _raise_sandbox_operations_error(exc)

    @app.get("/api/attorney-sandbox-operations/artifacts/{token}")
    def attorney_sandbox_operations_artifact(token: str):  # type: ignore[no-untyped-def]
        token = str(token or "").strip().casefold()
        if not re.fullmatch(r"[a-f0-9]{64}", token):
            raise HTTPException(status_code=404, detail="sandbox_operations_artifact_not_available")
        _prune_sandbox_operations_artifacts()
        with _sandbox_operations_artifact_lock:
            binding = dict(_sandbox_operations_artifacts.get(token) or {})
        try:
            store = _sandbox_operations_store()
        except AttorneySandboxOperationsError:
            raise HTTPException(
                status_code=404, detail="sandbox_operations_artifact_not_available"
            ) from None
        if not binding or binding.get("scope") != _sandbox_operations_scope(store):
            raise HTTPException(status_code=404, detail="sandbox_operations_artifact_not_available")
        try:
            path, media_type = store.resolve_artifact(
                str(binding.get("generation_id") or ""),
                str(binding.get("filename") or ""),
            )
        except AttorneySandboxOperationsError as exc:
            _raise_sandbox_operations_error(exc)
        if hashlib.sha256(path.read_bytes()).hexdigest() != str(binding.get("sha256") or ""):
            raise HTTPException(status_code=409, detail="sandbox_operations_artifact_hash_mismatch")
        return FileResponse(
            path,
            filename=path.name,
            media_type=media_type,
            content_disposition_type="attachment",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    def _raise_real_matter_pilot_error(exc: LimitedRealMatterPilotError) -> None:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    def _real_matter_pilot_store() -> LimitedRealMatterPilotOperationsStore:
        return LimitedRealMatterPilotOperationsStore(_release_hardening_repo_root())

    def _real_matter_pilot_scope(store: LimitedRealMatterPilotOperationsStore) -> str:
        if store.root is None:
            return ""
        return hashlib.sha256(str(store.root.resolve()).encode("utf-8")).hexdigest()

    def _prune_real_matter_pilot_artifacts(now: float | None = None) -> None:
        current = float(now if now is not None else time.time())
        stale_before = current - _REAL_MATTER_PILOT_ARTIFACT_TTL_SECONDS
        with _real_matter_pilot_artifact_lock:
            stale = [
                token
                for token, binding in _real_matter_pilot_artifacts.items()
                if float(binding.get("created_at") or 0) < stale_before
            ]
            for token in stale:
                _real_matter_pilot_artifacts.pop(token, None)
            if len(_real_matter_pilot_artifacts) > _REAL_MATTER_PILOT_ARTIFACT_MAX_TOKENS:
                overflow = (
                    len(_real_matter_pilot_artifacts) - _REAL_MATTER_PILOT_ARTIFACT_MAX_TOKENS
                )
                oldest = sorted(
                    _real_matter_pilot_artifacts.items(),
                    key=lambda item: float(item[1].get("created_at") or 0),
                )[:overflow]
                for token, _binding in oldest:
                    _real_matter_pilot_artifacts.pop(token, None)

    def _public_real_matter_pilot_artifacts(
        store: LimitedRealMatterPilotOperationsStore,
        result: dict[str, Any],
    ) -> list[dict[str, Any]]:
        generation_id = str(result.get("generation_id") or "")
        public: list[dict[str, Any]] = []
        _prune_real_matter_pilot_artifacts()
        for artifact in result.get("artifacts") or []:
            if not isinstance(artifact, dict):
                continue
            filename = str(artifact.get("filename") or "")
            sha256 = str(artifact.get("sha256") or "")
            if not filename or not re.fullmatch(r"[a-f0-9]{64}", sha256):
                continue
            token = secrets.token_hex(32)
            with _real_matter_pilot_artifact_lock:
                _real_matter_pilot_artifacts[token] = {
                    "created_at": time.time(),
                    "scope": _real_matter_pilot_scope(store),
                    "generation_id": generation_id,
                    "filename": filename,
                    "sha256": sha256,
                }
            public.append(
                {
                    "filename": filename,
                    "sha256": sha256,
                    "size_bytes": int(artifact.get("size_bytes") or 0),
                    "download_url": f"/api/limited-real-matter-pilot/artifacts/{token}",
                }
            )
        return public

    @app.get("/api/limited-real-matter-pilot/status")
    def limited_real_matter_pilot_status() -> dict[str, Any]:
        try:
            return _real_matter_pilot_store().status()
        except LimitedRealMatterPilotError as exc:
            return {
                "status": "blocked",
                "blockers": [exc.code],
                "training_use_allowed": False,
                "human_review_required": True,
                "pass49_complete": False,
                "external_launch_evidence_gate_required": True,
            }

    @app.post("/api/limited-real-matter-pilot/programs")
    def limited_real_matter_pilot_program(payload: RealMatterPilotProgramRequest) -> dict[str, Any]:
        try:
            return _real_matter_pilot_store().create_program(
                program_id=payload.program_id,
                allowed_tenant_ids=payload.allowed_tenant_ids,
                pass48_evidence_sha256=payload.pass48_evidence_sha256,
                approved=payload.approved,
            )
        except LimitedRealMatterPilotError as exc:
            _raise_real_matter_pilot_error(exc)

    @app.post("/api/limited-real-matter-pilot/matters")
    def limited_real_matter_pilot_matter(
        payload: RealMatterPilotEnrollmentRequest,
    ) -> dict[str, Any]:
        try:
            return _real_matter_pilot_store().enroll_matter(
                matter_id=payload.matter_id,
                tenant_id=payload.tenant_id,
                participant_id=payload.participant_id,
                consent_version=payload.consent_version,
                client_consent_evidence_sha256=payload.client_consent_evidence_sha256,
                privacy_notice_sha256=payload.privacy_notice_sha256,
                matter_store_sha256=payload.matter_store_sha256,
                tenant_isolation_evidence_sha256=payload.tenant_isolation_evidence_sha256,
                encryption_evidence_sha256=payload.encryption_evidence_sha256,
                retention_policy_version=payload.retention_policy_version,
                explicit_real_matter_consent=payload.explicit_real_matter_consent,
                training_use_allowed=payload.training_use_allowed,
                export_restriction_acknowledged=payload.export_restriction_acknowledged,
                human_review_required=payload.human_review_required,
                approved=payload.approved,
            )
        except LimitedRealMatterPilotError as exc:
            _raise_real_matter_pilot_error(exc)

    @app.post("/api/limited-real-matter-pilot/work-products")
    def limited_real_matter_pilot_work_product(
        payload: RealMatterPilotWorkProductRequest,
    ) -> dict[str, Any]:
        try:
            return _real_matter_pilot_store().record_work_product(
                matter_id=payload.matter_id,
                artifact_hashes=payload.artifact_hashes,
                approved=payload.approved,
            )
        except LimitedRealMatterPilotError as exc:
            _raise_real_matter_pilot_error(exc)

    @app.post("/api/limited-real-matter-pilot/daily-reviews")
    def limited_real_matter_pilot_daily_review(
        payload: RealMatterPilotDailyReviewRequest,
    ) -> dict[str, Any]:
        try:
            return _real_matter_pilot_store().record_daily_review(
                matter_id=payload.matter_id,
                participant_id=payload.participant_id,
                review_date=payload.review_date,
                usefulness=payload.usefulness,
                human_review_completed=payload.human_review_completed,
                source_verification_completed=payload.source_verification_completed,
                export_gate_checked=payload.export_gate_checked,
                blocker_codes=payload.blocker_codes,
                review_evidence_sha256=payload.review_evidence_sha256,
                approved=payload.approved,
            )
        except LimitedRealMatterPilotError as exc:
            _raise_real_matter_pilot_error(exc)

    @app.post("/api/limited-real-matter-pilot/exports")
    def limited_real_matter_pilot_export(payload: RealMatterPilotExportRequest) -> dict[str, Any]:
        try:
            return _real_matter_pilot_store().record_export_attempt(
                matter_id=payload.matter_id,
                export_type=payload.export_type,
                gate_status=payload.gate_status,
                filing_ready_claimed=payload.filing_ready_claimed,
                export_artifact_sha256=payload.export_artifact_sha256,
                authorization_evidence_sha256=payload.authorization_evidence_sha256,
                approved=payload.approved,
            )
        except LimitedRealMatterPilotError as exc:
            _raise_real_matter_pilot_error(exc)

    @app.post("/api/limited-real-matter-pilot/incidents")
    def limited_real_matter_pilot_incident(
        payload: RealMatterPilotIncidentRequest,
    ) -> dict[str, Any]:
        try:
            return _real_matter_pilot_store().open_incident(
                matter_id=payload.matter_id,
                category=payload.category,
                severity=payload.severity,
                summary_code=payload.summary_code,
                incident_evidence_sha256=payload.incident_evidence_sha256,
                approved=payload.approved,
            )
        except LimitedRealMatterPilotError as exc:
            _raise_real_matter_pilot_error(exc)

    @app.post("/api/limited-real-matter-pilot/incidents/update")
    def limited_real_matter_pilot_incident_update(
        payload: RealMatterPilotIncidentUpdateRequest,
    ) -> dict[str, Any]:
        try:
            return _real_matter_pilot_store().update_incident(
                incident_id=payload.incident_id,
                status=payload.status,
                remediation_evidence_sha256=payload.remediation_evidence_sha256,
                retest_evidence_sha256=payload.retest_evidence_sha256,
                approved=payload.approved,
            )
        except LimitedRealMatterPilotError as exc:
            _raise_real_matter_pilot_error(exc)

    @app.post("/api/limited-real-matter-pilot/signoffs")
    def limited_real_matter_pilot_signoff(payload: RealMatterPilotSignoffRequest) -> dict[str, Any]:
        try:
            return _real_matter_pilot_store().record_signoff(
                matter_id=payload.matter_id,
                participant_id=payload.participant_id,
                usefulness=payload.usefulness,
                attorney_signoff_complete=payload.attorney_signoff_complete,
                blocker_codes=payload.blocker_codes,
                signoff_evidence_sha256=payload.signoff_evidence_sha256,
                approved=payload.approved,
            )
        except LimitedRealMatterPilotError as exc:
            _raise_real_matter_pilot_error(exc)

    @app.post("/api/limited-real-matter-pilot/evidence/build")
    def limited_real_matter_pilot_evidence_build(
        payload: RealMatterPilotEvidenceBuildRequest,
    ) -> dict[str, Any]:
        try:
            store = _real_matter_pilot_store()
            result = store.build_evidence_packet(approved=payload.approved)
            return {**result, "artifacts": _public_real_matter_pilot_artifacts(store, result)}
        except LimitedRealMatterPilotError as exc:
            _raise_real_matter_pilot_error(exc)

    @app.get("/api/limited-real-matter-pilot/artifacts/{token}")
    def limited_real_matter_pilot_artifact(token: str):  # type: ignore[no-untyped-def]
        token = str(token or "").strip().casefold()
        if not re.fullmatch(r"[a-f0-9]{64}", token):
            raise HTTPException(status_code=404, detail="real_matter_pilot_artifact_not_available")
        _prune_real_matter_pilot_artifacts()
        with _real_matter_pilot_artifact_lock:
            binding = dict(_real_matter_pilot_artifacts.get(token) or {})
        try:
            store = _real_matter_pilot_store()
        except LimitedRealMatterPilotError:
            raise HTTPException(
                status_code=404, detail="real_matter_pilot_artifact_not_available"
            ) from None
        if not binding or binding.get("scope") != _real_matter_pilot_scope(store):
            raise HTTPException(status_code=404, detail="real_matter_pilot_artifact_not_available")
        try:
            path, media_type = store.resolve_artifact(
                str(binding.get("generation_id") or ""),
                str(binding.get("filename") or ""),
            )
        except LimitedRealMatterPilotError as exc:
            _raise_real_matter_pilot_error(exc)
        if hashlib.sha256(path.read_bytes()).hexdigest() != str(binding.get("sha256") or ""):
            raise HTTPException(status_code=409, detail="real_matter_pilot_artifact_hash_mismatch")
        return FileResponse(
            path,
            filename=path.name,
            media_type=media_type,
            content_disposition_type="attachment",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    def _raise_ga_release_candidate_error(exc: GAReleaseCandidateError) -> None:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    def _ga_release_candidate_store() -> GAReleaseCandidateOperationsStore:
        return GAReleaseCandidateOperationsStore(_release_hardening_repo_root())

    def _ga_release_candidate_scope(store: GAReleaseCandidateOperationsStore) -> str:
        if store.root is None:
            return ""
        return hashlib.sha256(str(store.root.resolve()).encode("utf-8")).hexdigest()

    def _prune_ga_release_candidate_artifacts(now: float | None = None) -> None:
        current = float(now if now is not None else time.time())
        stale_before = current - _GA_RELEASE_CANDIDATE_ARTIFACT_TTL_SECONDS
        with _ga_release_candidate_artifact_lock:
            stale = [
                token
                for token, binding in _ga_release_candidate_artifacts.items()
                if float(binding.get("created_at") or 0) < stale_before
            ]
            for token in stale:
                _ga_release_candidate_artifacts.pop(token, None)
            if len(_ga_release_candidate_artifacts) > _GA_RELEASE_CANDIDATE_ARTIFACT_MAX_TOKENS:
                overflow = (
                    len(_ga_release_candidate_artifacts) - _GA_RELEASE_CANDIDATE_ARTIFACT_MAX_TOKENS
                )
                oldest = sorted(
                    _ga_release_candidate_artifacts.items(),
                    key=lambda item: float(item[1].get("created_at") or 0),
                )[:overflow]
                for token, _binding in oldest:
                    _ga_release_candidate_artifacts.pop(token, None)

    def _public_ga_release_candidate_artifacts(
        store: GAReleaseCandidateOperationsStore,
        result: dict[str, Any],
    ) -> list[dict[str, Any]]:
        generation_id = str(result.get("generation_id") or "")
        public: list[dict[str, Any]] = []
        _prune_ga_release_candidate_artifacts()
        for artifact in result.get("artifacts") or []:
            if not isinstance(artifact, dict):
                continue
            filename = str(artifact.get("filename") or "")
            sha256 = str(artifact.get("sha256") or "")
            if not filename or not re.fullmatch(r"[a-f0-9]{64}", sha256):
                continue
            token = secrets.token_hex(32)
            with _ga_release_candidate_artifact_lock:
                _ga_release_candidate_artifacts[token] = {
                    "created_at": time.time(),
                    "scope": _ga_release_candidate_scope(store),
                    "generation_id": generation_id,
                    "filename": filename,
                    "sha256": sha256,
                }
            public.append(
                {
                    "filename": filename,
                    "sha256": sha256,
                    "size_bytes": int(artifact.get("size_bytes") or 0),
                    "download_url": f"/api/ga-release-candidate/artifacts/{token}",
                }
            )
        return public

    @app.get("/api/ga-release-candidate/status")
    def ga_release_candidate_status() -> dict[str, Any]:
        try:
            return _ga_release_candidate_store().status()
        except GAReleaseCandidateError as exc:
            return {
                "status": "blocked",
                "blockers": [exc.code],
                "release_candidate_frozen": False,
                "pass50_complete": False,
                "external_launch_evidence_gate_required": True,
            }

    @app.post("/api/ga-release-candidate/candidates")
    def ga_release_candidate_create(payload: GAReleaseCandidateCreateRequest) -> dict[str, Any]:
        try:
            return _ga_release_candidate_store().create_candidate(
                candidate_id=payload.candidate_id,
                version=payload.version,
                source_repo_zip_sha256=payload.source_repo_zip_sha256,
                source_repo_zip_name=payload.source_repo_zip_name,
                approved=payload.approved,
            )
        except GAReleaseCandidateError as exc:
            _raise_ga_release_candidate_error(exc)

    @app.post("/api/ga-release-candidate/artifacts")
    def ga_release_candidate_artifact_record(
        payload: GAReleaseCandidateArtifactRequest,
    ) -> dict[str, Any]:
        try:
            return _ga_release_candidate_store().record_artifact(
                candidate_id=payload.candidate_id,
                artifact_type=payload.artifact_type,
                artifact_version=payload.artifact_version,
                reference=payload.reference,
                sha256=payload.sha256,
                present=payload.present,
                external=payload.external,
                immutable=payload.immutable,
                approved=payload.approved,
            )
        except GAReleaseCandidateError as exc:
            _raise_ga_release_candidate_error(exc)

    @app.post("/api/ga-release-candidate/signoffs")
    def ga_release_candidate_signoff(payload: GAReleaseCandidateSignoffRequest) -> dict[str, Any]:
        try:
            return _ga_release_candidate_store().record_signoff(
                candidate_id=payload.candidate_id,
                role=payload.role,
                signer_label=payload.signer_label,
                status=payload.status,
                signed_at=payload.signed_at,
                evidence_sha256=payload.evidence_sha256,
                approved=payload.approved,
            )
        except GAReleaseCandidateError as exc:
            _raise_ga_release_candidate_error(exc)

    @app.post("/api/ga-release-candidate/blockers")
    def ga_release_candidate_blocker(payload: GAReleaseCandidateBlockerRequest) -> dict[str, Any]:
        try:
            return _ga_release_candidate_store().record_blocker(
                candidate_id=payload.candidate_id,
                blocker_id=payload.blocker_id,
                severity=payload.severity,
                status=payload.status,
                description_code=payload.description_code,
                evidence_sha256=payload.evidence_sha256,
                approved=payload.approved,
            )
        except GAReleaseCandidateError as exc:
            _raise_ga_release_candidate_error(exc)

    @app.post("/api/ga-release-candidate/freeze")
    def ga_release_candidate_freeze(payload: GAReleaseCandidateFreezeRequest) -> dict[str, Any]:
        try:
            return _ga_release_candidate_store().freeze_candidate(
                candidate_id=payload.candidate_id,
                audit_enterprise_readiness_status=payload.audit_enterprise_readiness_status,
                approved=payload.approved,
            )
        except GAReleaseCandidateError as exc:
            _raise_ga_release_candidate_error(exc)

    @app.post("/api/ga-release-candidate/evidence/build")
    def ga_release_candidate_evidence_build(
        payload: GAReleaseCandidateEvidenceBuildRequest,
    ) -> dict[str, Any]:
        try:
            store = _ga_release_candidate_store()
            result = store.build_evidence_packet(approved=payload.approved)
            return {**result, "artifacts": _public_ga_release_candidate_artifacts(store, result)}
        except GAReleaseCandidateError as exc:
            _raise_ga_release_candidate_error(exc)

    @app.get("/api/ga-release-candidate/artifacts/{token}")
    def ga_release_candidate_artifact(token: str):  # type: ignore[no-untyped-def]
        token = str(token or "").strip().casefold()
        if not re.fullmatch(r"[a-f0-9]{64}", token):
            raise HTTPException(
                status_code=404, detail="ga_release_candidate_artifact_not_available"
            )
        _prune_ga_release_candidate_artifacts()
        with _ga_release_candidate_artifact_lock:
            binding = dict(_ga_release_candidate_artifacts.get(token) or {})
        try:
            store = _ga_release_candidate_store()
        except GAReleaseCandidateError:
            raise HTTPException(
                status_code=404, detail="ga_release_candidate_artifact_not_available"
            ) from None
        if not binding or binding.get("scope") != _ga_release_candidate_scope(store):
            raise HTTPException(
                status_code=404, detail="ga_release_candidate_artifact_not_available"
            )
        try:
            path, media_type = store.resolve_artifact(
                str(binding.get("generation_id") or ""),
                str(binding.get("filename") or ""),
            )
        except GAReleaseCandidateError as exc:
            _raise_ga_release_candidate_error(exc)
        if hashlib.sha256(path.read_bytes()).hexdigest() != str(binding.get("sha256") or ""):
            raise HTTPException(
                status_code=409, detail="ga_release_candidate_artifact_hash_mismatch"
            )
        return FileResponse(
            path,
            filename=path.name,
            media_type=media_type,
            content_disposition_type="attachment",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    def _raise_findings_forms_error(exc: MaineFindingsFormsError) -> None:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    def _prune_findings_forms_artifacts(now: float | None = None) -> None:
        current = float(now if now is not None else time.time())
        stale_before = current - _FINDINGS_FORMS_ARTIFACT_TTL_SECONDS
        with _findings_forms_artifact_lock:
            stale = [
                token
                for token, binding in _findings_forms_artifacts.items()
                if float(binding.get("created_at") or 0) < stale_before
            ]
            for token in stale:
                _findings_forms_artifacts.pop(token, None)
            if len(_findings_forms_artifacts) > _FINDINGS_FORMS_ARTIFACT_MAX_TOKENS:
                overflow = len(_findings_forms_artifacts) - _FINDINGS_FORMS_ARTIFACT_MAX_TOKENS
                oldest = sorted(
                    _findings_forms_artifacts.items(),
                    key=lambda item: float(item[1].get("created_at") or 0),
                )[:overflow]
                for token, _binding in oldest:
                    _findings_forms_artifacts.pop(token, None)

    def _public_findings_forms_artifacts(
        case_root: Path,
        *,
        build_id: str,
        artifacts: list[dict[str, Any]],
        completion_id: str = "",
    ) -> list[dict[str, Any]]:
        _prune_findings_forms_artifacts()
        public = []
        store = MaineFindingsFormsStore(case_root)
        for raw in artifacts:
            name = str(raw.get("name") or "")
            sha256 = str(raw.get("sha256") or "").lower()
            try:
                path, media_type = store.resolve_artifact(
                    build_id, name, completion_id=completion_id
                )
            except MaineFindingsFormsError:
                continue
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if sha256 and actual != sha256:
                continue
            token = secrets.token_hex(32)
            with _findings_forms_artifact_lock:
                _findings_forms_artifacts[token] = {
                    "case_id": _case_id(case_root),
                    "build_id": build_id,
                    "completion_id": completion_id,
                    "filename": name,
                    "sha256": actual,
                    "created_at": time.time(),
                }
            row = dict(raw)
            row["sha256"] = actual
            row["media_type"] = media_type
            row["download_url"] = f"/api/findings-forms/artifacts/{token}"
            row.pop("relative_path", None)
            public.append(row)
        return public

    def _findings_root(case_root: Path) -> Path:
        return MaineFindingsFormsStore(case_root).root

    def _findings_matrix_history_path(case_root: Path) -> Path:
        return _findings_root(case_root) / "findings-matrix-history.jsonl"

    def _findings_session_path(case_root: Path, session_id: str) -> Path:
        return _findings_root(case_root) / "sessions" / f"{session_id}.json"

    def _utc_now() -> str:
        return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def _json_sha(payload: dict[str, Any] | list[Any]) -> str:
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
                "utf-8"
            )
        ).hexdigest()

    def _safe_snippet(value: Any, *, limit: int = 240) -> str:
        return " ".join(str(value or "").replace("\x00", "").split())[:limit]

    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8"
        )

    def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, ensure_ascii=False))
            handle.write("\n")

    def _load_json(path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise FileNotFoundError(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("json_object_required")
        return payload

    def _normalized_ids(values: Iterable[str] | None) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for raw in values or []:
            value = str(raw or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            output.append(value)
        return output

    def _findings_active_packet(case_root: Path, document_id: str = "") -> dict[str, Any]:
        store = MaineFindingsFormsStore(case_root)
        if document_id:
            active = store.active(document_id=document_id)
        else:
            active = store.active()
        return active["packet"]

    def _findings_matrix_rows(case_root: Path, document_id: str = "") -> list[dict[str, Any]]:
        packet = _findings_active_packet(case_root, document_id=document_id)
        findings = packet.get("findings_review") or {}
        return list(findings.get("factor_matrix") or [])

    def _matrix_history_entries(
        case_root: Path, build_id: str, element_id: str
    ) -> list[dict[str, Any]]:
        path = _findings_matrix_history_path(case_root)
        entries: list[dict[str, Any]] = []
        if not path.is_file():
            return entries
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip():
                continue
            try:
                row = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            if (
                str(row.get("build_id") or "") == build_id
                and str(row.get("element_id") or "") == element_id
            ):
                entries.append(row)
        return entries

    def _selected_records(
        rows: list[dict[str, Any]], selected_ids: Iterable[str] | None
    ) -> list[dict[str, Any]]:
        ids = {
            str(value or "").strip() for value in (selected_ids or []) if str(value or "").strip()
        }
        if not ids:
            return list(rows)
        output = []
        for row in rows:
            record_id = str(
                row.get("evidence_id") or row.get("source_id") or row.get("record_id") or ""
            ).strip()
            if record_id in ids:
                output.append(row)
        return output

    def _session_payload(case_root: Path, session_id: str) -> dict[str, Any]:
        try:
            session = _load_json(_findings_session_path(case_root, session_id))
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="forms_session_not_found") from None
        except ValueError:
            raise HTTPException(status_code=409, detail="forms_session_invalid") from None
        if str(session.get("session_id") or "") != session_id:
            raise HTTPException(status_code=409, detail="forms_session_invalid") from None
        return session

    def _active_authority_forms() -> tuple[list[dict[str, Any]], dict[str, Any]]:
        try:
            result = AuthorityProductService().list_forms(limit=500)
            return list(result.get("forms") or []), result
        except (FileNotFoundError, ValueError, OSError):
            return [], {
                "status": "blocked",
                "blockers": ["active_authority_form_catalog_unavailable_or_unverified"],
                "review_required": True,
            }

    @app.get("/api/findings-forms/status")
    def findings_forms_status(document_id: str = "") -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            return {
                "status": "blocked",
                "blockers": ["active_matter_unavailable"],
                "review_required": True,
            }
        forms, authority = _active_authority_forms()
        payload: dict[str, Any] = {
            "status": "pass" if forms else "review_required",
            "authority": {
                "status": authority.get("status"),
                "build_id": authority.get("build_id"),
                "form_count": len(forms),
            },
            "catalog": MaineFindingsFormsStore(case_root).catalog(forms),
            "review_required": True,
        }
        if document_id:
            try:
                payload["active"] = MaineFindingsFormsStore(case_root).active(
                    document_id=document_id
                )
            except MaineFindingsFormsError:
                payload["active"] = None
        return payload

    @app.post("/api/findings-forms/documents/{document_id}/review")
    def findings_forms_review(
        document_id: str, payload: FindingsFormsReviewRequest
    ) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        forms, authority = _active_authority_forms()
        try:
            result = (
                MaineFindingsFormsStore(case_root)
                .build_review(
                    document_id,
                    authority_forms=forms,
                    selected_form_ids=payload.selected_form_ids,
                    posture=payload.posture,
                    evidence_records=load_case_search_records(case_root),
                    approved=payload.approved,
                )
                .as_dict()
            )
            result["authority"] = {
                "status": authority.get("status"),
                "build_id": authority.get("build_id"),
                "form_count": len(forms),
            }
            result["artifacts"] = _public_findings_forms_artifacts(
                case_root, build_id=result["build_id"], artifacts=result.get("artifacts") or []
            )
            return result
        except (MaineFindingsFormsError, DocumentWorkspaceError) as exc:
            if isinstance(exc, MaineFindingsFormsError):
                _raise_findings_forms_error(exc)
            _raise_workspace_error(exc)

    @app.get("/api/findings-forms/documents/{document_id}/active")
    def findings_forms_active(document_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            result = MaineFindingsFormsStore(case_root).active(document_id=document_id)
            result["artifacts"] = _public_findings_forms_artifacts(
                case_root, build_id=result["build_id"], artifacts=result.get("artifacts") or []
            )
            return result
        except MaineFindingsFormsError as exc:
            _raise_findings_forms_error(exc)

    @app.get("/api/findings-forms/verify")
    def findings_forms_verify(build_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return MaineFindingsFormsStore(case_root).verify(build_id)
        except MaineFindingsFormsError as exc:
            _raise_findings_forms_error(exc)

    @app.post("/api/findings-forms/complete")
    def findings_forms_complete(payload: FindingsFormsCompleteRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            result = MaineFindingsFormsStore(case_root).complete_forms(
                payload.build_id,
                form_values=payload.form_values,
                confirmed=payload.confirmed,
            )
            result["artifacts"] = _public_findings_forms_artifacts(
                case_root,
                build_id=result["build_id"],
                completion_id=result["completion_id"],
                artifacts=result.get("artifacts") or [],
            )
            return result
        except (MaineFindingsFormsError, DocumentWorkspaceError) as exc:
            if isinstance(exc, MaineFindingsFormsError):
                _raise_findings_forms_error(exc)
            _raise_workspace_error(exc)

    @app.get("/api/findings-forms/artifacts/{token}")
    def findings_forms_artifact_download(token: str):  # type: ignore[no-untyped-def]
        token = str(token or "").strip().lower()
        if not re.fullmatch(r"[a-f0-9]{64}", token):
            raise HTTPException(status_code=404, detail="findings_forms_artifact_not_available")
        _prune_findings_forms_artifacts()
        case_root = active_case_root()
        with _findings_forms_artifact_lock:
            binding = dict(_findings_forms_artifacts.get(token) or {})
        if case_root is None or not binding or binding.get("case_id") != _case_id(case_root):
            raise HTTPException(status_code=404, detail="findings_forms_artifact_not_available")
        try:
            path, media_type = MaineFindingsFormsStore(case_root).resolve_artifact(
                str(binding.get("build_id") or ""),
                str(binding.get("filename") or ""),
                completion_id=str(binding.get("completion_id") or ""),
            )
        except MaineFindingsFormsError as exc:
            _raise_findings_forms_error(exc)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != str(binding.get("sha256") or ""):
            raise HTTPException(status_code=409, detail="findings_forms_artifact_hash_mismatch")
        return FileResponse(
            path,
            filename=path.name,
            media_type=media_type,
            content_disposition_type="attachment",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    @app.get("/api/findings/matrix")
    def findings_matrix(document_id: str = "") -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            return {
                "status": "blocked",
                "blockers": ["active_matter_unavailable"],
                "review_required": True,
            }
        try:
            store = MaineFindingsFormsStore(case_root)
            active = store.active(document_id=document_id) if document_id else store.active()
            matrix = list(
                (active.get("packet") or {}).get("findings_review", {}).get("factor_matrix") or []
            )
            return {
                "status": "pass",
                "build_id": active.get("build_id"),
                "document_id": (active.get("packet") or {}).get("document_id"),
                "matrix": matrix,
                "blockers": list((active.get("packet") or {}).get("blockers") or []),
                "review_required": True,
            }
        except MaineFindingsFormsError as exc:
            _raise_findings_forms_error(exc)

    @app.post("/api/findings/matrix/build")
    def findings_matrix_build(payload: FindingsMatrixBuildRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        forms, authority = _active_authority_forms()
        try:
            result = (
                MaineFindingsFormsStore(case_root)
                .build_review(
                    payload.document_id,
                    authority_forms=forms,
                    selected_form_ids=payload.selected_form_ids,
                    posture=payload.posture,
                    evidence_records=load_case_search_records(case_root),
                    approved=payload.approved,
                )
                .as_dict()
            )
            packet = result.get("packet") or {}
            result["authority"] = {
                "status": authority.get("status"),
                "build_id": authority.get("build_id"),
                "form_count": len(forms),
            }
            result["matrix"] = list(
                (packet.get("findings_review") or {}).get("factor_matrix") or []
            )
            result["forms"] = packet.get("form_catalog")
            return result
        except (MaineFindingsFormsError, DocumentWorkspaceError) as exc:
            if isinstance(exc, MaineFindingsFormsError):
                _raise_findings_forms_error(exc)
            _raise_workspace_error(exc)

    @app.patch("/api/findings/matrix/{element_id}")
    def findings_matrix_patch(
        element_id: str, payload: FindingsMatrixPatchRequest
    ) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            store = MaineFindingsFormsStore(case_root)
            active = store.load(payload.build_id)
            matrix = list(
                (active.get("packet") or {}).get("findings_review", {}).get("factor_matrix") or []
            )
            row = next(
                (item for item in matrix if str(item.get("factor_id") or "") == element_id), None
            )
            if row is None:
                raise MaineFindingsFormsError(
                    "matrix_element_not_found",
                    "The findings matrix element was not found.",
                    status_code=404,
                )
            history_entry = {
                "schema_version": "maine_findings_matrix_history_v1",
                "history_id": uuid.uuid4().hex,
                "build_id": payload.build_id,
                "element_id": element_id,
                "reviewer_status": _safe_snippet(payload.reviewer_status, limit=80),
                "reviewer_notes": _safe_snippet(payload.reviewer_notes, limit=1000),
                "proposed_finding": _safe_snippet(payload.proposed_finding, limit=2000),
                "supporting_record_ids": _normalized_ids(payload.supporting_record_ids),
                "contrary_record_ids": _normalized_ids(payload.contrary_record_ids),
                "factor_label": row.get("label"),
                "factor_status": row.get("status"),
                "matrix_row_sha256": _json_sha(row),
                "generated_at": _utc_now(),
                "review_required": True,
                "approved": bool(payload.approved),
            }
            _append_jsonl(_findings_matrix_history_path(case_root), history_entry)
            return {
                "status": "review_required",
                "build_id": payload.build_id,
                "element_id": element_id,
                "matrix_element": row,
                "history": _matrix_history_entries(case_root, payload.build_id, element_id),
                "review_required": True,
            }
        except MaineFindingsFormsError as exc:
            _raise_findings_forms_error(exc)

    @app.get("/api/findings/matrix/{element_id}/history")
    def findings_matrix_history(element_id: str, build_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            return {
                "status": "blocked",
                "blockers": ["active_matter_unavailable"],
                "review_required": True,
            }
        try:
            return {
                "status": "pass",
                "build_id": build_id,
                "element_id": element_id,
                "history": _matrix_history_entries(case_root, build_id, element_id),
                "review_required": True,
            }
        except MaineFindingsFormsError as exc:
            _raise_findings_forms_error(exc)

    @app.post("/api/findings/restrictions/review")
    def findings_restrictions_review(payload: FindingsRestrictionReviewRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            return {
                "status": "blocked",
                "blockers": ["active_matter_unavailable"],
                "review_required": True,
            }
        records = load_case_search_records(case_root)
        selected_records = _selected_records(records, payload.selected_record_ids)
        engine = Rule52BestInterestFindingsEngine()
        restriction_report = engine.contact_restriction_support(
            payload.proposed_restriction_language, evidence_records=selected_records
        )
        delegation_report = engine.third_party_delegation_review(
            payload.proposed_restriction_language
        )
        pfa_warning = engine.pfa_independent_analysis_warning(payload.proposed_restriction_language)
        return {
            "status": "review_required"
            if restriction_report.get("restriction_detected")
            or delegation_report.get("delegation_detected")
            else "checked",
            "restriction_language": payload.proposed_restriction_language,
            "document_id": payload.document_id,
            "selected_record_ids": _normalized_ids(payload.selected_record_ids),
            "restriction_report": restriction_report,
            "delegation_report": delegation_report,
            "pfa_family_overlap_warning": pfa_warning,
            "authority_citation": "Maine Rule 52 / best-interest review only",
            "approved": bool(payload.approved),
            "review_required": True,
        }

    @app.get("/api/forms")
    def forms_catalog(
        proceeding_type: str = "",
        form_id: str = "",
        title: str = "",
        issue: str = "",
        posture: str = "",
        freshness: str = "",
        limit: int = 100,
    ) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            return {
                "status": "blocked",
                "blockers": ["active_matter_unavailable"],
                "review_required": True,
            }
        forms, authority = _active_authority_forms()
        store = MaineFindingsFormsStore(case_root)
        catalog = store.catalog(forms)
        entries = list(catalog.get("entries") or [])
        if proceeding_type:
            entries = [
                row for row in entries if str(row.get("filing_context") or "") == proceeding_type
            ]
        if form_id:
            entries = [row for row in entries if str(row.get("form_id") or "") == form_id]
        if title:
            needle = title.casefold()
            entries = [row for row in entries if needle in str(row.get("title") or "").casefold()]
        if issue:
            entries = [row for row in entries if issue in (row.get("issue_labels") or [])]
        if posture:
            entries = [
                row
                for row in entries
                if posture in str(row.get("filing_context") or "")
                or posture in str(row.get("title") or "").casefold()
            ]
        if freshness:
            entries = [
                row
                for row in entries
                if str(row.get("freshness_status") or "").casefold() == freshness.casefold()
            ]
        entries = entries[: max(1, min(int(limit or 100), 200))]
        return {
            "status": "pass" if entries else "review_required",
            "authority": {
                "status": authority.get("status"),
                "build_id": authority.get("build_id"),
                "form_count": len(forms),
            },
            "catalog": catalog,
            "forms": entries,
            "count": len(entries),
            "filters": {
                "proceeding_type": proceeding_type,
                "form_id": form_id,
                "title": title,
                "issue": issue,
                "posture": posture,
                "freshness": freshness,
            },
            "review_required": True,
        }

    @app.post("/api/forms/session")
    def forms_session_create(payload: FormsSessionCreateRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        forms, authority = _active_authority_forms()
        store = MaineFindingsFormsStore(case_root)
        build = store.build_review(
            payload.document_id,
            authority_forms=forms,
            selected_form_ids=payload.selected_form_ids,
            posture=payload.proceeding_type or payload.posture,
            evidence_records=load_case_search_records(case_root),
            approved=payload.approved,
        )
        session_id = uuid.uuid4().hex[:24]
        session = {
            "schema_version": "maine_forms_session_v1",
            "session_id": session_id,
            "build_id": build.build_id,
            "document_id": payload.document_id,
            "proceeding_type": payload.proceeding_type,
            "selected_form_ids": _normalized_ids(payload.selected_form_ids),
            "form_values": {},
            "reviewer_notes": "",
            "generated_at": _utc_now(),
            "updated_at": _utc_now(),
            "completion_id": "",
            "review_required": True,
        }
        _write_json(_findings_session_path(case_root, session_id), session)
        return {
            "status": build.status,
            "session_id": session_id,
            "build_id": build.build_id,
            "document_id": payload.document_id,
            "proceeding_type": payload.proceeding_type,
            "selected_form_ids": _normalized_ids(payload.selected_form_ids),
            "catalog": build.packet.get("form_catalog"),
            "matrix": list((build.packet.get("findings_review") or {}).get("factor_matrix") or []),
            "blockers": list(build.blockers),
            "review_required": True,
        }

    @app.patch("/api/forms/session/{session_id}")
    def forms_session_patch(session_id: str, payload: FormsSessionPatchRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        session = _session_payload(case_root, session_id)
        session["selected_form_ids"] = _normalized_ids(payload.selected_form_ids) or list(
            session.get("selected_form_ids") or []
        )
        session["form_values"] = dict(payload.form_values or {})
        session["reviewer_notes"] = _safe_snippet(payload.reviewer_notes, limit=2000)
        session["updated_at"] = _utc_now()
        session["review_required"] = True
        _write_json(_findings_session_path(case_root, session_id), session)
        return {"status": "pass", "session": session, "review_required": True}

    @app.post("/api/forms/session/{session_id}/validate")
    def forms_session_validate(
        session_id: str, payload: FormsSessionActionRequest
    ) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        session = _session_payload(case_root, session_id)
        if payload.confirmed is not True:
            raise HTTPException(status_code=409, detail="explicit_confirmation_required")
        merged_values = dict(session.get("form_values") or {})
        for form_id, fields in (payload.form_values or {}).items():
            merged_values[form_id] = dict(fields or {})
        result = MaineFindingsFormsStore(case_root).complete_forms(
            session["build_id"], form_values=merged_values, confirmed=True
        )
        session["form_values"] = merged_values
        session["completion_id"] = result.get("completion_id") or ""
        session["updated_at"] = _utc_now()
        _write_json(_findings_session_path(case_root, session_id), session)
        return {
            "status": result["status"],
            "validation": result["completion"],
            "artifacts": result["artifacts"],
            "review_required": True,
            "filing_ready": False,
        }

    @app.post("/api/forms/session/{session_id}/generate")
    def forms_session_generate(
        session_id: str, payload: FormsSessionActionRequest
    ) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        session = _session_payload(case_root, session_id)
        if payload.confirmed is not True:
            raise HTTPException(status_code=409, detail="explicit_confirmation_required")
        merged_values = dict(session.get("form_values") or {})
        for form_id, fields in (payload.form_values or {}).items():
            merged_values[form_id] = dict(fields or {})
        result = MaineFindingsFormsStore(case_root).complete_forms(
            session["build_id"], form_values=merged_values, confirmed=True
        )
        session["form_values"] = merged_values
        session["completion_id"] = result.get("completion_id") or ""
        session["updated_at"] = _utc_now()
        _write_json(_findings_session_path(case_root, session_id), session)
        return {
            "status": result["status"],
            **result,
            "session_id": session_id,
            "review_required": True,
        }

    @app.get("/api/forms/session/{session_id}/receipt")
    def forms_session_receipt(session_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        session = _session_payload(case_root, session_id)
        completion_id = str(session.get("completion_id") or "")
        if not completion_id:
            return {
                "status": "blocked",
                "blockers": ["session_completion_missing"],
                "session_id": session_id,
                "review_required": True,
            }
        receipt_path, _media_type = MaineFindingsFormsStore(case_root).resolve_artifact(
            str(session.get("build_id") or ""),
            "form-completion-receipt.json",
            completion_id=completion_id,
        )
        receipt = _load_json(receipt_path)
        return {
            "status": "pass",
            "session_id": session_id,
            "receipt": receipt,
            "review_required": True,
        }

    @app.get("/api/forms/{form_id}")
    def form_catalog_entry(form_id: str) -> dict[str, Any]:
        response = forms_catalog(form_id=form_id)
        entries = list(response.get("forms") or [])
        if not entries:
            raise HTTPException(status_code=404, detail="form_not_found")
        return {
            "status": "pass",
            "form": entries[0],
            "authority": response.get("authority"),
            "review_required": True,
        }

    @app.post("/api/document-workspace/documents/{document_id}/review/prepare")
    def document_workspace_review_prepare(
        document_id: str,
        payload: WorkspaceReviewPrepareRequest,
    ) -> dict[str, Any]:
        try:
            case_root = _workspace_case_root()
            document = get_workspace_document(case_root, document_id)
            source_ids = []
            for row in document.get("source_refs") or []:
                if not isinstance(row, dict):
                    continue
                source_id = str(row.get("source_id") or "").strip()
                source_class = str(row.get("source_class") or "").lower()
                if source_id and source_class not in {"private_record", "record", "matter_record"}:
                    source_ids.append(source_id)
            try:
                authority_result = AuthorityProductService().verify_output(
                    text=str(document.get("content") or ""),
                    source_ids=source_ids,
                    quotes=payload.quotes,
                    claims=payload.claims,
                    expected_jurisdiction="maine",
                    auto_extract_claims=bool(payload.auto_extract_claims),
                )
            except (FileNotFoundError, ValueError, OSError):
                authority_result = {
                    "status": "blocked",
                    "blockers": ["active_authority_product_unavailable_or_unverified"],
                    "review_required": True,
                }
            return prepare_review_request(
                case_root,
                document_id,
                authority_result=authority_result,
                facts=payload.facts,
                records=load_case_search_records(case_root),
            )
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)
        except ReviewLedgerError as exc:
            _raise_review_error(exc)

    @app.post("/api/document-workspace/documents/{document_id}/review/commit")
    def document_workspace_review_commit(
        document_id: str,
        payload: WorkspaceReviewCommitRequest,
    ) -> dict[str, Any]:
        try:
            return commit_review_decision(
                _workspace_case_root(),
                document_id,
                request_id=payload.request_id,
                confirmation_token=payload.confirmation_token,
                confirmed=payload.confirmed,
                decision=payload.decision,
                reviewer_name=payload.reviewer_name,
                reviewer_role=payload.reviewer_role,
                attested=payload.attested,
                notes=payload.notes,
                claim_annotations=payload.claim_annotations,
            )
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)
        except ReviewLedgerError as exc:
            _raise_review_error(exc)

    @app.get("/api/document-workspace/review-queue")
    def document_workspace_review_queue(
        include_completed: bool = False, limit: int = 200
    ) -> dict[str, Any]:
        try:
            return build_reviewer_queue(
                _workspace_case_root(),
                include_completed=bool(include_completed),
                limit=limit,
            )
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)
        except ReviewLedgerError as exc:
            _raise_review_error(exc)

    @app.get("/api/document-workspace/documents/{document_id}/reviews")
    def document_workspace_review_history(document_id: str) -> dict[str, Any]:
        try:
            return list_review_history(_workspace_case_root(), document_id)
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)
        except ReviewLedgerError as exc:
            _raise_review_error(exc)

    @app.get("/api/document-workspace/documents/{document_id}/reviews/verify")
    def document_workspace_review_verify(document_id: str) -> dict[str, Any]:
        try:
            return verify_review_ledger(_workspace_case_root(), document_id)
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)
        except ReviewLedgerError as exc:
            _raise_review_error(exc)

    def _raise_filing_packet_error(exc: ReviewedFilingPacketError) -> None:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    def _prune_filing_packet_artifacts(now: float | None = None) -> None:
        current = float(now if now is not None else time.time())
        stale_before = current - _FILING_PACKET_ARTIFACT_TTL_SECONDS
        with _filing_packet_artifact_lock:
            stale = [
                token
                for token, binding in _filing_packet_artifacts.items()
                if float(binding.get("created_at") or 0) < stale_before
            ]
            for token in stale:
                _filing_packet_artifacts.pop(token, None)
            if len(_filing_packet_artifacts) > _FILING_PACKET_ARTIFACT_MAX_TOKENS:
                overflow = len(_filing_packet_artifacts) - _FILING_PACKET_ARTIFACT_MAX_TOKENS
                oldest = sorted(
                    _filing_packet_artifacts.items(),
                    key=lambda item: float(item[1].get("created_at") or 0),
                )[:overflow]
                for token, _binding in oldest:
                    _filing_packet_artifacts.pop(token, None)

    def _public_filing_packet_artifacts(
        case_root: Path, result: dict[str, Any]
    ) -> list[dict[str, Any]]:
        _prune_filing_packet_artifacts()
        store = ReviewedFilingPacketStore(case_root)
        public: list[dict[str, Any]] = []
        build_id = str(result.get("build_id") or "")
        for raw in result.get("artifacts") or []:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name") or "")
            try:
                path, media_type = store.resolve_artifact(build_id, name)
            except ReviewedFilingPacketError:
                continue
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if str(raw.get("sha256") or "") and actual != str(raw.get("sha256") or ""):
                continue
            token = secrets.token_hex(32)
            with _filing_packet_artifact_lock:
                _filing_packet_artifacts[token] = {
                    "case_id": _case_id(case_root),
                    "build_id": build_id,
                    "filename": name,
                    "sha256": actual,
                    "created_at": time.time(),
                }
            row = dict(raw)
            row["sha256"] = actual
            row["media_type"] = media_type
            row["download_url"] = f"/api/reviewed-filing-packet/artifacts/{token}"
            public.append(row)
        return public

    @app.get("/api/reviewed-filing-packet/status")
    def reviewed_filing_packet_status(document_id: str = "") -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            return {
                "status": "blocked",
                "blockers": ["active_matter_unavailable"],
                "review_required": True,
            }
        store = ReviewedFilingPacketStore(case_root)
        result: dict[str, Any] = {"status": "available", "review_required": True}
        if document_id:
            try:
                result["assignments"] = store.assignments_for(document_id)
                result["incremental_review"] = build_incremental_review_diff(case_root, document_id)
                try:
                    active = store.active(document_id=document_id)
                    if active.get("status") == "pass":
                        active["artifacts"] = _public_filing_packet_artifacts(case_root, active)
                    result["active"] = active
                except ReviewedFilingPacketError:
                    result["active"] = None
            except DocumentWorkspaceError as exc:
                _raise_workspace_error(exc)
            except ReviewLedgerError as exc:
                _raise_review_error(exc)
            except ReviewedFilingPacketError as exc:
                _raise_filing_packet_error(exc)
        return result

    @app.post("/api/reviewed-filing-packet/documents/{document_id}/diff")
    def reviewed_filing_packet_diff(
        document_id: str, payload: FilingPacketDiffRequest
    ) -> dict[str, Any]:
        try:
            return build_incremental_review_diff(
                _workspace_case_root(),
                document_id,
                base_revision_id=payload.base_revision_id,
                target_revision_id=payload.target_revision_id,
            )
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)
        except ReviewLedgerError as exc:
            _raise_review_error(exc)
        except ReviewedFilingPacketError as exc:
            _raise_filing_packet_error(exc)

    @app.get("/api/reviewed-filing-packet/documents/{document_id}/assignments")
    def reviewed_filing_packet_assignments(document_id: str) -> dict[str, Any]:
        try:
            return ReviewedFilingPacketStore(_workspace_case_root()).assignments_for(document_id)
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)
        except ReviewedFilingPacketError as exc:
            _raise_filing_packet_error(exc)

    @app.post("/api/reviewed-filing-packet/documents/{document_id}/assignments")
    def reviewed_filing_packet_assign(
        document_id: str, payload: FilingPacketAssignmentRequest
    ) -> dict[str, Any]:
        try:
            return ReviewedFilingPacketStore(_workspace_case_root()).assign(
                document_id,
                reviewer_label=payload.reviewer_label,
                role=payload.role,
                capabilities=payload.capabilities,
                expected_revision_id=payload.expected_revision_id,
                exclusive=payload.exclusive,
                note=payload.note,
            )
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)
        except ReviewedFilingPacketError as exc:
            _raise_filing_packet_error(exc)

    @app.post("/api/reviewed-filing-packet/documents/{document_id}/build")
    def reviewed_filing_packet_build(
        document_id: str, payload: FilingPacketBuildRequest
    ) -> dict[str, Any]:
        try:
            case_root = _workspace_case_root()
            authority_status = AuthorityProductService().status()
            current_authority_build_id = (
                str(authority_status.get("build_id") or "")
                if authority_status.get("status") == "pass"
                else ""
            )
            try:
                current_forms = list(
                    AuthorityProductService().list_forms(limit=500).get("forms") or []
                )
            except (FileNotFoundError, ValueError, OSError):
                current_forms = []
            result = ReviewedFilingPacketStore(case_root).build(
                document_id,
                approved=payload.approved,
                current_authority_build_id=current_authority_build_id,
                current_forms=current_forms,
                current_records=load_case_search_records(case_root),
            )
            result["artifacts"] = _public_filing_packet_artifacts(case_root, result)
            return result
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)
        except ReviewLedgerError as exc:
            _raise_review_error(exc)
        except ReviewedFilingPacketError as exc:
            _raise_filing_packet_error(exc)

    @app.get("/api/reviewed-filing-packet/verify")
    def reviewed_filing_packet_verify(build_id: str) -> dict[str, Any]:
        try:
            return ReviewedFilingPacketStore(_workspace_case_root()).verify(build_id)
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)
        except ReviewedFilingPacketError as exc:
            _raise_filing_packet_error(exc)

    @app.get("/api/reviewed-filing-packet/artifacts/{token}")
    def reviewed_filing_packet_artifact(token: str):
        _prune_filing_packet_artifacts()
        with _filing_packet_artifact_lock:
            binding = dict(_filing_packet_artifacts.get(str(token or "")) or {})
        case_root = active_case_root()
        if case_root is None or not binding or binding.get("case_id") != _case_id(case_root):
            raise HTTPException(status_code=404, detail="filing_packet_artifact_not_available")
        try:
            path, media_type = ReviewedFilingPacketStore(case_root).resolve_artifact(
                str(binding.get("build_id") or ""), str(binding.get("filename") or "")
            )
        except ReviewedFilingPacketError as exc:
            _raise_filing_packet_error(exc)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != str(binding.get("sha256") or ""):
            raise HTTPException(status_code=409, detail="filing_packet_artifact_hash_mismatch")
        return FileResponse(
            path,
            filename=path.name,
            media_type=media_type,
            content_disposition_type="attachment",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    def _raise_authority_impact_error(exc: AuthorityImpactError) -> None:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    def _authority_impact_store(case_root: Path) -> AuthorityChangeImpactStore:
        service = AuthorityProductService()
        if service.data_root is None:
            raise AuthorityImpactError(
                "authority_data_root_not_configured",
                "MAINE_FAMILY_LAW_DATA_ROOT is not configured.",
                status_code=409,
            )
        return AuthorityChangeImpactStore(
            case_root,
            data_root=service.data_root,
            repo_root=find_source_root(Path(__file__)),
        )

    def _prune_authority_impact_artifacts(now: float | None = None) -> None:
        current = float(now if now is not None else time.time())
        stale_before = current - _AUTHORITY_IMPACT_ARTIFACT_TTL_SECONDS
        with _authority_impact_artifact_lock:
            stale = [
                token
                for token, binding in _authority_impact_artifacts.items()
                if float(binding.get("created_at") or 0) < stale_before
            ]
            for token in stale:
                _authority_impact_artifacts.pop(token, None)
            if len(_authority_impact_artifacts) > _AUTHORITY_IMPACT_ARTIFACT_MAX_TOKENS:
                overflow = len(_authority_impact_artifacts) - _AUTHORITY_IMPACT_ARTIFACT_MAX_TOKENS
                oldest = sorted(
                    _authority_impact_artifacts.items(),
                    key=lambda item: float(item[1].get("created_at") or 0),
                )[:overflow]
                for token, _binding in oldest:
                    _authority_impact_artifacts.pop(token, None)

    def _public_authority_impact_artifacts(
        case_root: Path, result: dict[str, Any]
    ) -> list[dict[str, Any]]:
        _prune_authority_impact_artifacts()
        store = _authority_impact_store(case_root)
        public: list[dict[str, Any]] = []
        build_id = str(result.get("build_id") or "")
        for raw in result.get("artifacts") or []:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name") or "")
            try:
                path, media_type = store.resolve_artifact(build_id, name)
            except AuthorityImpactError:
                continue
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if str(raw.get("sha256") or "") and actual != str(raw.get("sha256") or ""):
                continue
            token = secrets.token_hex(32)
            with _authority_impact_artifact_lock:
                _authority_impact_artifacts[token] = {
                    "case_id": _case_id(case_root),
                    "build_id": build_id,
                    "filename": name,
                    "sha256": actual,
                    "created_at": time.time(),
                }
            row = dict(raw)
            row["sha256"] = actual
            row["media_type"] = media_type
            row["download_url"] = f"/api/authority-change-impact/artifacts/{token}"
            public.append(row)
        return public

    @app.get("/api/authority-change-impact/status")
    def authority_change_impact_status(document_id: str = "") -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            return {
                "status": "blocked",
                "blockers": ["active_matter_unavailable"],
                "review_required": True,
            }
        try:
            store = _authority_impact_store(case_root)
            result = store.list_generations()
            if document_id:
                try:
                    active = store.active(document_id=document_id)
                    active["artifacts"] = _public_authority_impact_artifacts(case_root, active)
                    result["active"] = active
                except AuthorityImpactError:
                    result["active"] = None
            return result
        except AuthorityImpactError as exc:
            _raise_authority_impact_error(exc)

    @app.post("/api/authority-change-impact/analyze")
    def authority_change_impact_analyze(payload: AuthorityImpactAnalyzeRequest) -> dict[str, Any]:
        try:
            return _authority_impact_store(_workspace_case_root()).analyze_document(
                payload.document_id,
                payload.base_build_id,
                payload.target_build_id,
            )
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)
        except ReviewLedgerError as exc:
            _raise_review_error(exc)
        except AuthorityImpactError as exc:
            _raise_authority_impact_error(exc)

    @app.post("/api/authority-change-impact/build")
    def authority_change_impact_build(payload: AuthorityImpactBuildRequest) -> dict[str, Any]:
        try:
            case_root = _workspace_case_root()
            result = _authority_impact_store(case_root).build(
                payload.document_id,
                payload.base_build_id,
                payload.target_build_id,
                approved=payload.approved,
            )
            result["artifacts"] = _public_authority_impact_artifacts(case_root, result)
            return result
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)
        except ReviewLedgerError as exc:
            _raise_review_error(exc)
        except AuthorityImpactError as exc:
            _raise_authority_impact_error(exc)

    @app.get("/api/authority-change-impact/verify")
    def authority_change_impact_verify(build_id: str) -> dict[str, Any]:
        try:
            return _authority_impact_store(_workspace_case_root()).verify(build_id)
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)
        except AuthorityImpactError as exc:
            _raise_authority_impact_error(exc)

    @app.get("/api/authority-change-impact/artifacts/{token}")
    def authority_change_impact_artifact(token: str):
        _prune_authority_impact_artifacts()
        with _authority_impact_artifact_lock:
            binding = dict(_authority_impact_artifacts.get(str(token or "")) or {})
        case_root = active_case_root()
        if case_root is None or not binding or binding.get("case_id") != _case_id(case_root):
            raise HTTPException(status_code=404, detail="authority_impact_artifact_not_available")
        try:
            path, media_type = _authority_impact_store(case_root).resolve_artifact(
                str(binding.get("build_id") or ""),
                str(binding.get("filename") or ""),
            )
        except AuthorityImpactError as exc:
            _raise_authority_impact_error(exc)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != str(binding.get("sha256") or ""):
            raise HTTPException(status_code=409, detail="authority_impact_artifact_hash_mismatch")
        return FileResponse(
            path,
            filename=path.name,
            media_type=media_type,
            content_disposition_type="attachment",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    @app.get("/api/document-workspace/docx/status")
    def document_workspace_docx_status() -> dict[str, Any]:
        return docx_engine_status()

    @app.get("/api/document-workspace/documents/{document_id}/docx/paragraphs")
    def document_workspace_docx_paragraphs(
        document_id: str,
        start: int = 1,
        limit: int = 200,
    ) -> dict[str, Any]:
        try:
            case_root = _workspace_case_root()
            paths = workspace_paths(case_root)
            source = find_preserved_source(case_root, document_id, extension=".docx")
            return list_docx_paragraphs(
                source_path=source,
                allowed_source_root=paths.sources,
                start=start,
                limit=limit,
            )
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)

    @app.post("/api/document-workspace/documents/{document_id}/docx/tracked-edit")
    def document_workspace_docx_tracked_edit(
        document_id: str,
        payload: WorkspaceDocxEditRequest,
    ) -> dict[str, Any]:
        try:
            if payload.confirmed is not True:
                raise DocumentWorkspaceError(
                    "explicit_confirmation_required",
                    "Confirm the tracked Word edits before creating a revised copy.",
                    status_code=409,
                )
            case_root = _workspace_case_root()
            paths = workspace_paths(case_root)
            document = get_workspace_document(case_root, document_id)
            source = find_preserved_source(case_root, document_id, extension=".docx")
            artifact_id = uuid.uuid4().hex
            output = paths.exports / (
                f"{document_id}-{str(document['current_revision_id'])}-{artifact_id}.docx"
            )
            result = tracked_edit_copy(
                source_path=source,
                allowed_source_root=paths.sources,
                output_path=output,
                allowed_output_root=paths.exports,
                operations=payload.operations,
                author=payload.author,
            )
            gate_headers = _document_workspace_filing_gate_headers(case_root, document_id)
            record_artifact_event(
                case_root,
                document_id=document_id,
                revision_id=str(document["current_revision_id"]),
                format_name="docx",
                artifact_sha256=str(result["sha256"]),
                size_bytes=int(result["size_bytes"]),
                tracked_changes=True,
            )
            return {
                "status": "tracked_copy_created",
                "artifact_id": artifact_id,
                "download_url": f"/api/document-workspace/artifacts/{artifact_id}",
                "sha256": result["sha256"],
                "source_sha256": result["source_sha256"],
                "edit_count": result["edit_count"],
                "edits": result["edits"],
                "tracked_changes": True,
                "original_preserved": True,
                "review_required": True,
                "filing_ready": False,
                "filing_gate_headers": gate_headers,
            }
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)

    @app.get("/api/document-workspace/artifacts/{artifact_id}")
    def document_workspace_artifact(artifact_id: str):  # type: ignore[no-untyped-def]
        try:
            artifact_id = str(artifact_id or "").strip().lower()
            if not re.fullmatch(r"[a-f0-9]{32}", artifact_id):
                raise DocumentWorkspaceError(
                    "artifact_not_found", "The artifact was not found.", status_code=404
                )
            paths = workspace_paths(_workspace_case_root())
            candidates = [
                path
                for path in paths.exports.glob(f"*-{artifact_id}.docx")
                if path.is_file() and not path.is_symlink()
            ]
            if len(candidates) != 1:
                raise DocumentWorkspaceError(
                    "artifact_not_found", "The artifact was not found.", status_code=404
                )
            artifact = candidates[0]
            if artifact.resolve(strict=True).parent != paths.exports.resolve(strict=True):
                raise DocumentWorkspaceError(
                    "artifact_not_found", "The artifact was not found.", status_code=404
                )
            return FileResponse(
                artifact,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                filename="review-required-tracked-draft.docx",
                content_disposition_type="attachment",
                headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
            )
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)

    @app.get("/api/document-workspace/audit/verify")
    def document_workspace_audit_verify() -> dict[str, Any]:
        try:
            return verify_audit_chain(_workspace_case_root())
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)

    @app.get("/api/import-guidance")
    def import_guidance() -> dict[str, Any]:
        return {
            "local_only": True,
            "sources": ["files", "folders", "ZIP archives", "email exports", "phone exports"],
            "formats": [
                "PDF",
                "DOCX",
                "TXT",
                "MD",
                "HTML",
                "RTF",
                "EML",
                "CSV",
                "XLSX",
                "PPTX",
                "ZIP",
                "images",
                "audio/video metadata",
            ],
            "how_to_start": "Open the desktop launcher and choose Create New Case Corpus or Reopen Intake / Add More Evidence.",
            "focaf_links": [
                "https://focaf.jtforme.com/",
                "https://focaf.jtforme.com/download-library/",
            ],
            "notice": "FOCAF links open separately in your browser, are optional, and are not legal authority. The workbench sends no matter details or search terms to them.",
        }

    @app.get("/api/printables")
    def printables() -> dict[str, Any]:
        return {
            "authority_status": "not_legal_authority",
            "resource_lane": "family_printable_secondary_resource",
            "results": search_printables("family", limit=6)["results"],
        }

    @app.get("/api/printables/search")
    def printable_search(q: str = "", limit: int = 4) -> dict[str, Any]:
        safe_query = " ".join(str(q or "").split())[:500]
        safe_limit = min(20, max(1, int(limit or 4)))
        return search_printables(safe_query, limit=safe_limit)

    @app.get("/api/printables/{document_id}")
    def printable_preview(document_id: str) -> dict[str, Any]:
        document = get_printable(document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="printable_not_found")
        return public_printable_view(document) | {
            "headings": document.get("headings", []),
            "warnings": document.get("warnings", []),
        }

    @app.get("/api/printables-asset-audit")
    def printable_asset_audit() -> dict[str, Any]:
        audit = audit_packaged_printables(verify_hashes=True)
        if audit.get("status") != "pass":
            raise HTTPException(status_code=500, detail=audit)
        return audit

    @app.get("/api/printables/{document_id}/open")
    def printable_open(document_id: str):  # type: ignore[no-untyped-def]
        if FileResponse is None:
            raise HTTPException(status_code=500, detail="printable_file_response_unavailable")
        try:
            path = printable_pdf_path(document_id, verify_hash=True)
        except PrintableAssetError as exc:
            status_code = 409 if exc.code == "printable_hash_mismatch" else 500
            raise HTTPException(
                status_code=status_code,
                detail={
                    "code": exc.code,
                    "document_id": exc.document_id,
                    "expected_asset": exc.expected_path,
                },
            ) from exc
        if path is None:
            raise HTTPException(status_code=404, detail="printable_unknown")
        return FileResponse(path, media_type="application/pdf", filename=path.name)

    @app.get("/api/question-library")
    def question_library() -> list[dict[str, Any]]:
        return public_library()

    @app.get("/api/question-topics")
    def question_topics() -> list[dict[str, Any]]:
        return public_topics()

    @app.get("/api/starter-prompt-packs")
    def starter_prompt_packs() -> list[dict[str, Any]]:
        return public_prompt_packs()

    @app.get("/api/missing-information-prompts")
    def missing_information_prompts() -> list[dict[str, Any]]:
        return public_missing_information_prompts()

    @app.post("/api/intake/understand")
    def understand_intake(payload: AskRequest) -> dict[str, Any]:
        summary = _parse_payload_intake(payload)
        return {
            "status": "ok",
            "intake": summary.to_dict(),
            "intake_label": concise_intake_label(summary),
            "local_only": True,
            "network_used": False,
            "legal_or_factual_finding": False,
        }

    @app.post("/api/family-justice-workbench")
    def family_justice_workbench(payload: FamilyJusticeWorkbenchRequest) -> dict[str, Any]:
        question_integrity = harden_text_input(payload.question, max_length=MAX_INTAKE_CHARS)
        facts_integrity = harden_text_input(
            payload.facts_context, max_length=8000, preserve_newlines=True
        )
        packet = build_workbench_packet(
            question_integrity.value,
            audience=str(payload.audience or "parent")[:80],
            posture=str(payload.posture or "unknown")[:80],
            facts_context=facts_integrity.value,
            requested_output_style=str(payload.requested_output_style or "plain_language")[:80],
        )
        packet["request_integrity"] = {
            "question": question_integrity.report(),
            "facts_context": facts_integrity.report(),
        }
        return packet

    @app.post("/retrieve")
    def retrieve(payload: QueryRequest) -> dict[str, Any]:
        query_integrity = harden_text_input(payload.query, max_length=MAX_INTAKE_CHARS)
        query = query_integrity.value
        safe_limit = min(20, max(1, int(payload.limit or 5)))
        expanded_query = expand_query_for_library(query)
        response = _retrieve_official_authority(expanded_query, limit=safe_limit)
        return {
            "query": response.query,
            "failure_class": response.failure_class,
            "recovery_hint": response.recovery_hint,
            "confidence": response.confidence,
            "diagnostics": dict(response.diagnostics or {}),
            "results": [result.to_dict() for result in response.results],
            "request_integrity": query_integrity.report(),
        }

    @app.post("/ask")
    def ask(payload: AskRequest) -> dict[str, Any]:
        question_result = harden_text_input(payload.question, max_length=MAX_INTAKE_CHARS)
        context_result = harden_text_input(
            payload.matter_context, max_length=4000, preserve_newlines=True
        )
        session_id, session_report = normalize_session_id(payload.session_id)
        last_search_id, search_id_report = normalize_search_id(payload.last_search_id)
        payload.question = question_result.value
        payload.matter_context = context_result.value
        payload.session_id = session_id
        payload.last_search_id = (
            last_search_id
            if search_id_report["accepted"]
            else ("__invalid__" if search_id_report["provided"] else "")
        )
        payload.answer_style = _normalize_answer_style(payload.answer_style)
        question = payload.question
        security_flags = [
            flag
            for report in (question_result.report(), context_result.report())
            for flag in report.get("flags", [])
            if flag
            in {
                "unicode_direction_controls_removed",
                "nonprinting_controls_removed",
                "null_bytes_removed",
                "input_truncated_to_local_limit",
            }
        ]
        if session_report["provided"] and not session_report["accepted"]:
            security_flags.append("invalid_session_identifier_rejected")
        if search_id_report["provided"] and not search_id_report["accepted"]:
            security_flags.append("invalid_search_identifier_rejected")
        payload.input_integrity = {
            "schema_version": "request_integrity_v1",
            "question": question_result.report(),
            "matter_context": context_result.report(),
            "session_id": session_report,
            "last_search_id": search_id_report,
            "security_flags": list(dict.fromkeys(security_flags)),
            "raw_input_stored": False,
        }
        mode = _normalize_search_mode(payload.search_mode)
        intake = _parse_payload_intake(payload)

        if not question:
            return {
                "question": payload.question,
                "answer_style": payload.answer_style,
                "search_mode": mode,
                "matter_context_used": bool((payload.matter_context or "").strip()),
                "safety": {
                    "category": "general",
                    "requires_citations": False,
                    "requires_disclaimer": True,
                    "requires_emergency_language": False,
                },
                "answer": ("Type a Maine family-law question, then press Enter or click Ask."),
                "grounded": False,
                "failure_class": "empty_question",
                "recovery_hint": (
                    "Enter a question such as: What are Maine's best-interest factors?"
                ),
                "citations": [],
                "source_card_count": 0,
                "request_integrity": dict(payload.input_integrity or {}),
            }

        try:
            followup = _source_card_followup(payload)
            if followup is not None:
                return _finalize_family_response(followup, payload)

            if intake.task == "corpus_inventory":
                inventory = _case_inventory_chat_payload(payload)
                if inventory is not None:
                    inventory["mode_routing_note"] = (
                        "Corpus inventory command routed to My records; no Maine-law search was run."
                    )
                    return _finalize_family_response(inventory, payload)
                unavailable_inventory = {
                    "question": question,
                    "answer_style": payload.answer_style,
                    "search_mode": "my_records",
                    "requested_search_mode": mode,
                    "response_kind": "corpus_inventory",
                    "answer": "No active indexed matter is selected. Choose a matter before listing its indexed records.",
                    "grounded": False,
                    "failure_class": "no_active_matter",
                    "recovery_hint": "Choose a matter in the corpus library, then ask to list the indexed corpus again.",
                    "citations": [],
                    "source_card_count": 0,
                    "review_required": True,
                    "not_legal_advice": True,
                    "corpus_mode": "no_active_case_corpus",
                    "metadata": {
                        "intake": intake.to_dict(),
                        "missing_information": ["Select the intended local matter/corpus."],
                    },
                }
                return _finalize_family_response(unavailable_inventory, payload)

            # Direct record-search commands are data commands. They must not be
            # hijacked by the Maine-law lane merely because Both is selected.
            if intake.task == "record_search" and mode != "my_records":
                records = _active_case_chat_payload(payload, finalize=False)
                if records is not None:
                    records = dict(records)
                    records["requested_search_mode"] = mode
                    records["search_mode"] = "my_records"
                    records["mode_routing_note"] = (
                        "Direct content-search command routed to My records; no Maine-law search was run."
                    )
                    return _finalize_family_response(records, payload)
                unavailable_search = {
                    "question": question,
                    "answer_style": payload.answer_style,
                    "search_mode": "my_records",
                    "requested_search_mode": mode,
                    "response_kind": "local_search_results",
                    "direct_record_search": True,
                    "search_summary": {
                        "query": question,
                        "search_target": intake.search_target,
                        "result_count": 0,
                        "exact_phrase": 0,
                        "exact_token": 0,
                        "related": 0,
                        "response_kind": "local_search_results",
                    },
                    "answer": (
                        "Search result:\n"
                        "- No active indexed matter is selected. Choose a matter before searching private records.\n"
                        "- No Maine-law search was substituted for this records command."
                    ),
                    "grounded": False,
                    "failure_class": "no_active_matter",
                    "recovery_hint": "Choose a matter in the corpus library, then run the search again.",
                    "citations": [],
                    "source_card_count": 0,
                    "review_required": True,
                    "not_legal_advice": True,
                    "corpus_mode": "no_active_case_corpus",
                    "metadata": {
                        "intake": intake.to_dict(),
                        "missing_information": ["Select the intended local matter/corpus."],
                    },
                }
                return _finalize_family_response(unavailable_search, payload)

            if mode == "my_records":
                records = _active_case_chat_payload(payload)

                if records is None:
                    unavailable = {
                        "question": question,
                        "answer_style": payload.answer_style,
                        "search_mode": "my_records",
                        "matter_context_used": bool(payload.matter_context.strip()),
                        "safety": {
                            "category": "private_case_corpus",
                            "requires_citations": True,
                            "requires_disclaimer": True,
                            "requires_emergency_language": False,
                        },
                        "answer": (
                            "No active indexed matter is available. "
                            "Choose a matter before searching "
                            "private records."
                        ),
                        "grounded": False,
                        "failure_class": "no_active_matter",
                        "recovery_hint": ("Choose a matter in the corpus library."),
                        "citations": [],
                        "source_card_count": 0,
                        "review_required": True,
                        "not_legal_advice": True,
                        "corpus_mode": "no_active_case_corpus",
                    }
                    return _finalize_family_response(unavailable, payload)

                result = dict(records)
                result["search_mode"] = "my_records"
                return _remember_record_search(payload, result)

            legal = _general_law_payload(payload, finalize=mode != "both")

            if mode == "maine_law":
                return legal

            records = _active_case_chat_payload(payload, finalize=False)

            if records is None:
                result = dict(legal)
                result["search_mode"] = "both"
                result["failure_class"] = "no_active_matter_for_combined_search"
                result["recovery_hint"] = "Choose a matter to add private-record analysis."
                result["answer"] = (
                    "Maine-law lane: "
                    + _first_answer_paragraph(str(legal.get("answer", "")))
                    + "\n\nMatter-record lane: No active indexed matter was available, so no private facts were searched."
                )
                result["response_kind"] = "combined_lane_answer"
                result["metadata"] = {
                    **dict(result.get("metadata") or {}),
                    "legal_source_count": len(legal.get("citations") or []),
                    "record_source_count": 0,
                }
                return _finalize_family_response(result, payload)

            legal_citations = _annotate_source_lanes(
                list(legal.get("citations", [])), "legal_authority"
            )
            record_citations = _annotate_source_lanes(
                list(records.get("citations", [])), "private_record"
            )
            citations = legal_citations + record_citations

            legal_grounded = bool(legal.get("grounded"))
            records_grounded = bool(records.get("grounded"))

            combined = {
                "question": question,
                "answer_style": payload.answer_style,
                "search_mode": "both",
                "matter_context_used": bool(payload.matter_context.strip()),
                "safety": legal.get("safety", {}),
                "answer": (
                    "Maine-law lane: "
                    + _first_answer_paragraph(str(legal.get("answer", "")))
                    + "\n\nMatter-record lane: "
                    + _first_answer_paragraph(str(records.get("answer", "")))
                    + "\n\nThe law lane can support legal information. The record lane only shows what appears in the selected files."
                ),
                "response_kind": "combined_lane_answer",
                "grounded": (legal_grounded or records_grounded),
                "failure_class": (
                    "none"
                    if legal_grounded and records_grounded
                    else "combined_search_requires_review"
                ),
                "recovery_hint": (
                    "Review Maine-law source cards separately from private-record source cards."
                ),
                "citations": citations,
                "source_card_count": len(citations),
                "review_required": True,
                "not_legal_advice": True,
                "corpus_mode": "combined_law_and_records",
                "active_case_label": records.get(
                    "active_case_label",
                    "",
                ),
                "metadata": {
                    "record_lane": True,
                    "legal_authority_lane": True,
                    "legal_source_count": len(legal_citations),
                    "record_source_count": len(record_citations),
                    "intake": intake.to_dict(),
                },
                "family_printables": list(legal.get("family_printables") or [])[:3],
            }
            return _finalize_family_response(combined, payload)

        except Exception:
            return {
                "question": question,
                "answer_style": payload.answer_style,
                "search_mode": mode,
                "matter_context_used": bool((payload.matter_context or "").strip()),
                "safety": {
                    "category": "error",
                    "requires_citations": False,
                    "requires_disclaimer": True,
                    "requires_emergency_language": False,
                },
                "answer": (
                    "The local workbench could not complete this request. "
                    "No local path, record text, or raw exception detail was returned."
                ),
                "grounded": False,
                "failure_class": ("local_workbench_internal_error"),
                "recovery_hint": ("Restart the desktop app, refresh, and retry."),
                "citations": [],
                "source_card_count": 0,
                "request_integrity": dict(payload.input_integrity or {}),
            }

    @app.post("/draft")
    def draft(payload: DraftRequest) -> dict[str, Any]:
        request_integrity = harden_text_input(
            payload.request, max_length=MAX_INTAKE_CHARS, preserve_newlines=True
        )
        request_text = request_integrity.value
        mode = str(payload.mode or "checklist")[:80]
        if mode not in ALLOWED_DRAFT_MODES:
            mode = "checklist"
        prompt_findings = _prompt_injection_scanner.scan_user_prompt(request_text)
        retrieval_query = (
            _prompt_injection_scanner.sanitize_user_prompt_for_retrieval(request_text)
            if prompt_findings
            else request_text
        )
        if _retrieval_query_has_substance(retrieval_query):
            retrieval = _retrieve_official_authority(retrieval_query)
            retrieval_results = retrieval.results
            retrieval_diagnostics = {
                **dict(retrieval.diagnostics or {}),
                "confidence": retrieval.confidence,
                "failure_class": retrieval.failure_class,
                "query_sanitized": bool(prompt_findings),
            }
        else:
            retrieval_results = ()
            retrieval_diagnostics = {
                "schema_version": "retrieval_diagnostics_v2",
                "confidence": "none",
                "failure_class": "substantive_draft_request_required_after_prompt_sanitization",
                "query_sanitized": bool(prompt_findings),
                "human_review_required": True,
            }
        draft_result = draft_from_sources(
            request_text,
            retrieval_results,
            mode=mode,
            retrieval_diagnostics=retrieval_diagnostics,
        )
        return {
            "text": draft_result.text,
            "failure_class": draft_result.failure_class,
            "recovery_hint": draft_result.recovery_hint,
            "citations": [item.to_dict() for item in draft_result.citations],
            "structured_sections": list(draft_result.structured_sections),
            "draft_integrity": dict(draft_result.review_report or {}),
            "request_integrity": request_integrity.report(),
            "review_required": True,
            "filing_ready": False,
        }

    @app.get("/inspect-source/{source_id}")
    def inspect_source(
        source_id: str,
        start_offset: int | None = None,
        end_offset: int | None = None,
    ) -> dict[str, Any]:
        source_id = str(source_id or "").strip()[:240]
        if not source_id:
            raise HTTPException(status_code=400, detail="source_id_required")
        product = AuthorityProductService()
        try:
            if start_offset is not None and end_offset is not None:
                payload = product.get_source_span(
                    source_id,
                    start_offset=start_offset,
                    end_offset=end_offset,
                )
            else:
                payload = product.get_source(source_id)
            if payload.get("status") == "pass":
                return payload
        except Exception:
            pass
        library = AuthorityLibraryService()
        if library.data_root is not None:
            payload = library.get_source(source_id)
            if payload.get("status") == "pass":
                return payload
        case_root = active_case_root()
        if case_root is not None:
            for row in load_case_search_records(case_root):
                if str(row.get("evidence_id", "")) == source_id:
                    return public_record_view(row)
        entry = get_source(load_seed_manifest(), source_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="source_not_found")
        return entry.to_dict()

    def _raise_ga_shipment_error(exc: GAShipmentReadinessError) -> None:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    def _ga_shipment_store() -> GAShipmentReadinessStore:
        return GAShipmentReadinessStore(_release_hardening_repo_root())

    def _ga_shipment_scope(store: GAShipmentReadinessStore) -> str:
        if store.root is None:
            return ""
        return hashlib.sha256(str(store.root.resolve()).encode("utf-8")).hexdigest()

    def _prune_ga_shipment_artifacts(now: float | None = None) -> None:
        current = float(now if now is not None else time.time())
        stale_before = current - _GA_SHIPMENT_ARTIFACT_TTL_SECONDS
        with _ga_shipment_artifact_lock:
            stale = [
                token
                for token, binding in _ga_shipment_artifacts.items()
                if float(binding.get("created_at") or 0) < stale_before
            ]
            for token in stale:
                _ga_shipment_artifacts.pop(token, None)
            if len(_ga_shipment_artifacts) > _GA_SHIPMENT_ARTIFACT_MAX_TOKENS:
                overflow = len(_ga_shipment_artifacts) - _GA_SHIPMENT_ARTIFACT_MAX_TOKENS
                ordered = sorted(
                    _ga_shipment_artifacts.items(),
                    key=lambda item: float(item[1].get("created_at") or 0),
                )
                for token, _ in ordered[:overflow]:
                    _ga_shipment_artifacts.pop(token, None)

    def _public_ga_shipment_artifacts(
        store: GAShipmentReadinessStore, result: dict[str, Any]
    ) -> list[dict[str, Any]]:
        _prune_ga_shipment_artifacts()
        public: list[dict[str, Any]] = []
        for artifact in result.get("artifacts") or []:
            filename = str(artifact.get("filename") or "")
            digest = str(artifact.get("sha256") or "")
            token = hashlib.sha256(
                f"{result.get('generation_id')}:{filename}:{digest}:{secrets.token_hex(16)}".encode(
                    "utf-8"
                )
            ).hexdigest()
            with _ga_shipment_artifact_lock:
                _ga_shipment_artifacts[token] = {
                    "generation_id": result.get("generation_id"),
                    "filename": filename,
                    "sha256": digest,
                    "scope": _ga_shipment_scope(store),
                    "created_at": time.time(),
                }
            public.append(
                {**artifact, "download_url": f"/api/ga-shipment-readiness/artifacts/{token}"}
            )
        return public

    @app.get("/api/ga-shipment-readiness/status")
    def ga_shipment_readiness_status() -> dict[str, Any]:
        try:
            return _ga_shipment_store().status()
        except GAShipmentReadinessError as exc:
            if exc.code == "release_root_not_configured":
                return {
                    "status": "blocked",
                    "stage": "ga_shipment_readiness_operations",
                    "pass51_complete": False,
                    "external_shipment_evidence_required": True,
                    "blockers": [exc.code],
                }
            _raise_ga_shipment_error(exc)

    @app.post("/api/ga-shipment-readiness/shipments")
    def ga_shipment_create(payload: GAShipmentCreateRequest) -> dict[str, Any]:
        try:
            return _ga_shipment_store().create_shipment(**payload.model_dump())
        except GAShipmentReadinessError as exc:
            _raise_ga_shipment_error(exc)

    @app.post("/api/ga-shipment-readiness/artifacts")
    def ga_shipment_artifact_record(payload: GAShipmentArtifactRequest) -> dict[str, Any]:
        try:
            return _ga_shipment_store().record_artifact(**payload.model_dump())
        except GAShipmentReadinessError as exc:
            _raise_ga_shipment_error(exc)

    @app.post("/api/ga-shipment-readiness/controls")
    def ga_shipment_control_record(payload: GAShipmentControlRequest) -> dict[str, Any]:
        try:
            return _ga_shipment_store().record_control(**payload.model_dump())
        except GAShipmentReadinessError as exc:
            _raise_ga_shipment_error(exc)

    @app.post("/api/ga-shipment-readiness/channels")
    def ga_shipment_channel_record(payload: GAShipmentChannelRequest) -> dict[str, Any]:
        try:
            return _ga_shipment_store().record_channel(**payload.model_dump())
        except GAShipmentReadinessError as exc:
            _raise_ga_shipment_error(exc)

    @app.post("/api/ga-shipment-readiness/blockers")
    def ga_shipment_blocker_record(payload: GAShipmentBlockerRequest) -> dict[str, Any]:
        try:
            return _ga_shipment_store().record_blocker(**payload.model_dump())
        except GAShipmentReadinessError as exc:
            _raise_ga_shipment_error(exc)

    @app.post("/api/ga-shipment-readiness/evaluate")
    def ga_shipment_evaluate(payload: GAShipmentEvaluateRequest) -> dict[str, Any]:
        try:
            return _ga_shipment_store().evaluate_shipment(**payload.model_dump())
        except GAShipmentReadinessError as exc:
            _raise_ga_shipment_error(exc)

    @app.post("/api/ga-shipment-readiness/evidence/build")
    def ga_shipment_evidence_build(payload: GAShipmentEvidenceBuildRequest) -> dict[str, Any]:
        try:
            store = _ga_shipment_store()
            result = store.build_evidence_packet(approved=payload.approved)
            return {**result, "artifacts": _public_ga_shipment_artifacts(store, result)}
        except GAShipmentReadinessError as exc:
            _raise_ga_shipment_error(exc)

    @app.get("/api/ga-shipment-readiness/artifacts/{token}")
    def ga_shipment_artifact(token: str):  # type: ignore[no-untyped-def]
        token = str(token or "").strip().casefold()
        if not re.fullmatch(r"[a-f0-9]{64}", token):
            raise HTTPException(status_code=404, detail="ga_shipment_artifact_not_available")
        _prune_ga_shipment_artifacts()
        with _ga_shipment_artifact_lock:
            binding = dict(_ga_shipment_artifacts.get(token) or {})
        try:
            store = _ga_shipment_store()
        except GAShipmentReadinessError:
            raise HTTPException(
                status_code=404, detail="ga_shipment_artifact_not_available"
            ) from None
        if not binding or binding.get("scope") != _ga_shipment_scope(store):
            raise HTTPException(status_code=404, detail="ga_shipment_artifact_not_available")
        try:
            path, media_type = store.resolve_artifact(
                str(binding.get("generation_id") or ""), str(binding.get("filename") or "")
            )
        except GAShipmentReadinessError as exc:
            _raise_ga_shipment_error(exc)
        if hashlib.sha256(path.read_bytes()).hexdigest() != str(binding.get("sha256") or ""):
            raise HTTPException(status_code=409, detail="ga_shipment_artifact_hash_mismatch")
        return FileResponse(
            path,
            filename=path.name,
            media_type=media_type,
            content_disposition_type="attachment",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )
