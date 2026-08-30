"""Local-only FastAPI backend for the Maine Family Law LLM workbench."""

from __future__ import annotations

import csv
from contextvars import ContextVar
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
from typing import Any, Callable, Iterable

from legal.product.family_justice_workbench_v205 import build_workbench_packet
from legal.drafting.findings_engine import Rule52BestInterestFindingsEngine
from legal.drafting.outline_workbench import OutlineWorkbenchStore
from legal.drafting.sentence_support_map import SentenceSupportMapStore
from legal.drafting.citation_insertion import CitationInsertionStore
from legal.drafting.quote_safe_drafting import QuoteSafeDraftStore
from legal.drafting.requirement_profiles import DraftRequirementProfileStore
from legal.drafting.revision_rationale import RevisionRationaleStore
from legal.drafting.dual_view import DualViewStore
from legal.drafting.argument_matrix import ArgumentMatrixStore
from legal.drafting.export_provenance import ExportProvenanceStore
from legal.matter.procedure_pathway import ProcedurePathwayStore
from legal.matter.service_method_matrix import ServiceMethodMatrixStore
from legal.matter.business_day_review import BusinessDayReviewStore
from legal.matter.hearing_countdown import HearingCountdownStore
from legal.matter.filing_preflight import FilingPreflightStore
from legal.matter.fee_waiver_workspace import FeeWaiverWorkspaceStore
from legal.matter.venue_location_navigator import VenueLocationNavigatorStore
from legal.matter.post_filing_reconciliation import PostFilingReconciliationStore
from legal.matter.order_calendar_extraction import OrderCalendarExtractionStore
from legal.matter.child_support_worksheet import ChildSupportWorksheetStore
from legal.matter.financial_affidavit import FinancialAffidavitStore
from legal.matter.asset_tracing import AssetTracingStore
from legal.matter.debt_reconciliation import DebtReconciliationStore
from legal.matter.settlement_scenarios import SettlementScenarioStore
from legal.matter.implementation_feasibility import ImplementationFeasibilityStore
from legal.matter.communication_plan import CommunicationPlanStore
from legal.matter.compliance_log import ComplianceLogStore
from legal.runtime.hardware_benchmark import HardwareBenchmarkStore
from legal.runtime.model_admission_benchmark import ModelAdmissionBenchmarkStore
from legal.runtime.warm_model_pool import WarmModelPoolStore
from legal.runtime.context_cache import ContextCacheStore
from legal.runtime.speculative_retrieval import SpeculativeRetrievalStore
from legal.runtime.context_budget import ContextBudgetStore
from legal.runtime.batch_scheduler import BatchInferenceScheduler
from legal.runtime.low_memory_mode import LowMemoryModeStore
from legal.runtime.crash_recovery import RuntimeCrashRecovery
from legal.runtime.health_dashboard import (
    HealthDashboardError,
    HealthDependencyDashboardStore,
    collect_dashboard as collect_health_dependency_dashboard,
)
from legal.runtime.job_journal import (
    JobJournalError,
    JobJournalReceiptStore,
    collect_job_journal,
)
from legal.runtime.idempotency import IdempotencyMiddleware, IdempotencyRegistry
from legal.runtime.database_integrity import (
    DatabaseIntegrityError,
    DatabaseIntegrityReceiptStore,
    run_database_integrity_check,
)
from legal.runtime.power_loss_resilience import (
    PowerLossResilienceError,
    PowerLossResilienceReceiptStore,
    run_power_loss_resilience_drill,
)
from legal.runtime.storage_pressure import (
    StoragePressureError,
    StoragePressureReceiptStore,
    forecast_storage_pressure,
)
from legal.runtime.clock_skew import ClockSkewError, ClockSkewMonitor
from legal.runtime.performance_regression import (
    PerformanceGateError,
    PerformanceGateReceiptStore,
    evaluate_performance_gates,
    performance_budget_catalog,
)
from legal.runtime.failure_replay import (
    FailureReplayError,
    FailureReplayReceiptStore,
    failure_replay_catalog,
    replay_sanitized_failure,
)
from legal.runtime.cross_device_transfer import CrossDeviceTransferError, CrossDeviceTransferStore
from legal.runtime.schema_migration_lab import SchemaMigrationLab, SchemaMigrationLabError
from legal.product.command_bar import search as search_command_bar
from legal.product.unified_matter_search import search as unified_matter_search
from legal.product.smart_views import SmartViewStore
from legal.product.recent_work import RecentWorkStore
from legal.product.workspace_tabs import WorkspaceTabsStore
from legal.product.command_history import CommandHistoryStore
from legal.product.bulk_review_queue import BulkReviewQueueStore
from legal.product.favorites import FavoritesStore
from legal.product.user_labels import UserLabelsStore
from legal.product.daily_matter_brief import DailyMatterBriefStore
from app.services import AuthorityLibraryService, AuthorityProductService
from legal.security.prompt_injection import PromptInjectionScanner
from legal.security.local_request_firewall import DEFAULT_MAX_BODY_BYTES, evaluate_local_request
from legal.security.local_api_abuse_guard import LocalApiAbuseGuard
from legal.agent_runtime import (
    LocalAgentRunRequest,
    LocalAgentRuntime,
    LocalModelError,
    build_local_client,
)
from legal.local_workbench import LocalWorkbenchError, LocalWorkbenchService
from legal.document_intelligence import (
    DocumentIntelligenceError,
    analyze_document,
    create_content_disarm_copy,
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
from legal.evidence.watch_folder_queue import scan_candidates as scan_watch_folder_candidates
from legal.evidence.scanner_review import scanner_review_plan
from legal.evidence.handwriting_review import review_handwriting
from legal.evidence.document_type_review import classify_document
from legal.evidence.page_quality_review import page_quality_map
from legal.evidence.table_lineage_review import table_lineage
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
from legal.matter.fact_pins import FactPinStore
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
from legal.matter.archival_pdf_export import ArchivalPdfExportStore
from legal.matter.structured_evidence_export import StructuredEvidenceExportStore
from legal.matter.print_review import PrintReviewStore
from legal.matter.external_tool_boundary import ExternalToolBoundaryStore
from legal.matter.document_comparison import DocumentComparisonStore
from legal.matter.metadata_review import MetadataReviewStore
from legal.matter.import_policy import ImportPolicyStore
from legal.matter.reviewer_handoff import ReviewerHandoffStore
from legal.matter.structured_comment_threads import StructuredCommentThreadStore
from legal.matter.review_assignments import ReviewAssignmentStore
from legal.matter.bundle_merge import BundleMergeStore
from legal.matter.language_access import LanguageAccessStore
from legal.matter.resource_navigator import ResourceNavigatorStore
from legal.matter.golden_path import MatterJourneyStore
from legal.forms import MaineFindingsFormsError, MaineFindingsFormsStore
from legal.forms.session_store import GuidedFormSessionStore
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
from legal.governance.legal_hold import LegalHoldError, LegalHoldStore

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
from legal.answering.review_scope import AnswerAssertions, AnswerReviewScopes
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
)

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.exceptions import RequestValidationError
    from fastapi.exception_handlers import request_validation_exception_handler
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
    from fastapi.staticfiles import StaticFiles
    from starlette.requests import ClientDisconnect
    from pydantic import BaseModel, Field, StrictBool
except Exception:  # pragma: no cover - lets CLI import without API extras
    FastAPI = None  # type: ignore[assignment]
    HTTPException = Exception  # type: ignore[assignment]
    HTMLResponse = None  # type: ignore[assignment]
    JSONResponse = None  # type: ignore[assignment]
    FileResponse = None  # type: ignore[assignment]
    StreamingResponse = None  # type: ignore[assignment]
    StaticFiles = None  # type: ignore[assignment]
    Request = object  # type: ignore[assignment]

    class ClientDisconnect(Exception):
        pass

    class BaseModel:  # type: ignore[no-redef]
        pass

    StrictBool = bool  # type: ignore[assignment,misc]

    def Field(default: Any = None, *, default_factory: Any = None, **_: Any) -> Any:  # type: ignore[no-redef]
        return default_factory() if default_factory is not None else default


if FastAPI is not None:
    # These contracts require the optional API extra. Keep CLI import model/API
    # empty, but do not hide real integration errors once that extra is present.
    from app.services.local_agent_context_service import (
        LocalAgentApprovalStore, LocalAgentAuditStore, LocalAgentContextError,
        LocalAgentContextService, LocalAgentSourceReference, digest as local_agent_digest,
    )
    from app.services.local_agent_run_service import LocalAgentRunStore
    from app.api.model_packs import register_model_pack_routes


class QueryRequest(BaseModel):
    query: str
    limit: int = 5


class AskRequest(BaseModel):
    question: str
    answer_style: str = "plain_language"
    response_depth: str = "standard"
    audience: str = "self_represented"
    matter_context: str = ""
    search_mode: str = "maine_law"
    child_impact_lens: StrictBool = False
    session_id: str = ""
    last_search_id: str = ""
    input_integrity: dict[str, Any] | None = None


class ConversationContextCompactionRequest(BaseModel):
    session_id: str
    expected_search_id: str = ""


class ConversationAnswerCorrectionRequest(BaseModel):
    """One review-required, immutable correction proposal for a displayed answer."""

    session_id: str
    expected_search_id: str
    original_sentence: str
    proposed_correction: str
    reason_code: str = "other"
    reason_note: str = ""


class ConversationAnswerCorrectionRerunRequest(BaseModel):
    session_id: str
    expected_search_id: str
    original_sentence: str
    proposed_correction: str


class ConversationLatencyObservationRequest(BaseModel):
    session_id: str
    expected_search_id: str
    first_feedback_ms: int | None = None
    total_duration_ms: int
    server_duration_ms: int | None = None
    queue_delay_ms: int | None = None
    cache_state: str = "unknown"
    model_output_tokens: int = 0
    hardware_concurrency: int = 0
    device_memory_gib: float = 0.0


class ConversationAnswerComparisonRequest(BaseModel):
    session_id: str
    expected_search_id: str
    approach_a: str
    approach_b: str


class ConversationBranchRequest(BaseModel):
    session_id: str
    expected_search_id: str


class ConversationUsefulnessRequest(BaseModel):
    session_id: str
    expected_search_id: str


# This is a user-visible responsiveness contract, not an answer-quality shortcut.
# The initial event is intentionally generic because source retrieval and verifier
# results are not yet known; the canonical /ask result remains the sole answer.
STREAM_FIRST_FEEDBACK_BUDGET_MS = 150


def _stream_event(event: str, payload: dict[str, Any]) -> str:
    """Serialize one safe, structured Server-Sent Event frame."""

    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    return f"event: {event}\ndata: {body}\n\n"


def iter_stream_answer_events(
    payload: AskRequest,
    answer_runner: Callable[[AskRequest], dict[str, Any]],
) -> Iterable[str]:
    """Yield honest progress before executing the canonical answer path.

    Keeping this generator outside the route makes the first-feedback budget
    testable without claiming that first source retrieval or verification has
    completed. The answer runner is invoked only after the safe progress
    states; its output is emitted unchanged as the canonical result payload.
    """

    started_at = time.perf_counter()
    yield _stream_event(
        "accepted",
        {
            "stage": "accepted",
            "message": "Question received locally. Preparing a review-required answer.",
            "first_feedback_budget_ms": STREAM_FIRST_FEEDBACK_BUDGET_MS,
            "server_elapsed_ms": 0,
            "local_only": True,
            "review_required": True,
        },
    )
    retrieving_elapsed_ms = max(0, round((time.perf_counter() - started_at) * 1000))
    yield _stream_event(
        "retrieving",
        {
            "stage": "retrieving",
            "message": "Finding relevant Maine sources and checking the selected matter context.",
            "server_elapsed_ms": retrieving_elapsed_ms,
            "local_only": True,
            "review_required": True,
        },
    )
    result = answer_runner(payload)
    duration_ms = max(0, round((time.perf_counter() - started_at) * 1000))
    yield _stream_event(
        "result",
        {
            "stage": "complete",
            "duration_ms": duration_ms,
            "payload": result,
            "local_only": True,
            "review_required": bool(result.get("review_required", True)),
        },
    )
    yield _stream_event(
        "complete",
        {
            "stage": "complete",
            "duration_ms": duration_ms,
            "local_only": True,
            "review_required": bool(result.get("review_required", True)),
        },
    )


class DraftRequest(BaseModel):
    request: str
    mode: str = "checklist"


class DraftOutlineCreateRequest(BaseModel):
    outline_id: str
    issue_id: str
    issue_label: str
    reviewer_safe_id: str
    purpose: str = ""
    selected_evidence: list[dict[str, Any]] = Field(default_factory=list)
    selected_authority: list[dict[str, Any]] = Field(default_factory=list)
    user_confirmed: StrictBool = False


class SentenceSupportMapRequest(BaseModel):
    reviewer_safe_id: str
    selected_authority: list[dict[str, Any]] = Field(default_factory=list)
    user_confirmed: StrictBool = False


class CitationInsertionRequest(BaseModel):
    reviewer_safe_id: str
    selected_text: str
    occurrence_index: int = 0
    authority: dict[str, Any] = Field(default_factory=dict)
    user_confirmed: StrictBool = False


class QuoteSafeDraftRequest(BaseModel):
    reviewer_safe_id: str
    selected_text: str
    quote_text: str
    authority: dict[str, Any] = Field(default_factory=dict)
    normalized_quote_approved: StrictBool = False
    user_confirmed: StrictBool = False


class DraftRequirementProfileRequest(BaseModel):
    profile_id: str
    label: str
    reviewer_safe_id: str
    required_sections: list[str] = Field(default_factory=list)
    max_characters: int = 10000
    review_gates: list[str] = Field(default_factory=list)
    user_confirmed: StrictBool = False

class RevisionRationaleRequest(BaseModel):
    reviewer_safe_id: str
    change_summary: str
    reason: str
    affected_claim_ids: list[str] = Field(default_factory=list)
    verifier_impact: str = "not_run"
    user_confirmed: StrictBool = False

class DualViewRequest(BaseModel):
    view_id: str
    reviewer_safe_id: str
    plain_language_text: str
    user_confirmed: StrictBool = False


class ArgumentMatrixRequest(BaseModel):
    matrix_id: str
    issue_label: str
    reviewer_safe_id: str
    positions: list[dict[str, Any]] = Field(default_factory=list)
    user_confirmed: StrictBool = False


class ProcedurePathwayRequest(BaseModel):
    pathway_id: str
    reviewer_safe_id: str
    case_type: str = "unknown"
    posture: str = "unknown"
    venue_label: str
    existing_orders: list[dict[str, Any]] = Field(default_factory=list)
    authority_source_id: str
    user_confirmed: StrictBool = False


class ServiceMethodMatrixRequest(BaseModel):
    matrix_id: str
    reviewer_safe_id: str
    selected_method: str = "unknown"
    proof: dict[str, Any] = Field(default_factory=dict)
    authority_source_id: str
    exceptions: list[str] = Field(default_factory=list)
    unresolved_facts: list[str] = Field(default_factory=list)
    user_confirmed: StrictBool = False


class BusinessDayCalendarInputRequest(BaseModel):
    input_id: str
    calendar_key: str
    version_label: str
    jurisdiction_label: str
    reviewer_safe_id: str
    valid_from: str
    valid_through: str
    holidays: list[str] = Field(default_factory=list)
    authority_source_id: str
    user_confirmed: StrictBool = False


class BusinessDayCalculationRequest(BaseModel):
    calculation_id: str
    input_id: str
    reviewer_safe_id: str
    start_date: str
    business_days: int
    user_confirmed: StrictBool = False


class HearingCountdownRequest(BaseModel):
    countdown_id: str
    reviewer_safe_id: str
    hearing_label: str
    confirmed_date: str
    notice_source: dict[str, Any] = Field(default_factory=dict)
    milestone_offsets: list[int] = Field(default_factory=list)
    missing_proof_prompts: list[str] = Field(default_factory=list)
    user_confirmed: StrictBool = False


class FilingPreflightRequest(BaseModel):
    preflight_id: str
    reviewer_safe_id: str
    caption_label: str
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    form_source_ids: list[str] = Field(default_factory=list)
    checks: dict[str, bool] = Field(default_factory=dict)
    document_id: str = ""
    user_confirmed: StrictBool = False


class FeeWaiverWorkspaceRequest(BaseModel):
    workspace_id: str
    reviewer_safe_id: str
    purpose_label: str
    authority_source_id: str
    facts: list[dict[str, Any]] = Field(default_factory=list)
    user_confirmed: StrictBool = False


class ChildSupportWorksheetRequest(BaseModel):
    workspace_id: str
    reviewer_safe_id: str
    authority_source_id: str
    inputs: list[dict[str, Any]] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)
    user_confirmed: StrictBool = False


class FinancialAffidavitRequest(BaseModel):
    workspace_id: str
    reviewer_safe_id: str
    entries: list[dict[str, Any]] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    user_confirmed: StrictBool = False


class AssetTracingRequest(BaseModel):
    ledger_id: str
    reviewer_safe_id: str
    assets: list[dict[str, Any]] = Field(default_factory=list)
    user_confirmed: StrictBool = False


class DebtReconciliationRequest(BaseModel):
    workspace_id: str
    reviewer_safe_id: str
    statements: list[dict[str, Any]] = Field(default_factory=list)
    user_confirmed: StrictBool = False


class SettlementScenarioRequest(BaseModel):
    comparison_id: str
    reviewer_safe_id: str
    scenarios: list[dict[str, Any]] = Field(default_factory=list)
    user_confirmed: StrictBool = False


class ImplementationFeasibilityRequest(BaseModel):
    review_id: str
    reviewer_safe_id: str
    clauses: list[dict[str, Any]] = Field(default_factory=list)
    user_confirmed: StrictBool = False


class CommunicationPlanRequest(BaseModel):
    plan_id: str
    reviewer_safe_id: str
    terms: list[dict[str, Any]] = Field(default_factory=list)
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    user_confirmed: StrictBool = False


class ComplianceLogRequest(BaseModel):
    log_id: str
    reviewer_safe_id: str
    term_id: str
    event_id: str
    date_candidate: str
    text: str
    event_state: str
    event_source_ref: dict[str, Any] = Field(default_factory=dict)
    user_confirmed: StrictBool = False


class HardwareBenchmarkRequest(BaseModel):
    benchmark_id: str
    user_confirmed: StrictBool = False


class ModelAdmissionBenchmarkRequest(BaseModel):
    benchmark_id: str
    provider: str = "ollama"
    endpoint: str = "http://127.0.0.1:11434"
    model: str = "qwen2.5:7b"
    user_confirmed: StrictBool = False


class WarmModelPoolWarmRequest(BaseModel):
    task: str
    preferred_model_id: str = ""
    thermal_state: str = "unknown"
    user_confirmed: StrictBool = False


class WarmModelPoolReleaseRequest(BaseModel):
    model_id: str
    reason: str = "operator_requested"


class ContextCacheEntryRequest(BaseModel):
    cache_id: str
    kind: str
    scope: str
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    artifact: dict[str, Any] | list[Any] | str = Field(default_factory=dict)


class ContextCacheInvalidationRequest(BaseModel):
    changes: list[dict[str, Any]] = Field(default_factory=list)


class SpeculativeRetrievalRequest(BaseModel):
    preview_id: str
    typed_intent: str


class ContextBudgetRequest(BaseModel):
    budget_id: str
    task: str = "review"
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    verifier_requirements: dict[str, Any] = Field(default_factory=dict)
    requested_context_tokens: int = 0


class BatchInferenceScheduleRequest(BaseModel):
    batch_id: str
    items: list[dict[str, Any]] = Field(default_factory=list)
    user_confirmed: StrictBool = False


class LowMemoryModeRequest(BaseModel):
    active: StrictBool = True
    user_confirmed: StrictBool = False

class VenueLocationWorkspaceRequest(BaseModel):
    workspace_id: str
    reviewer_safe_id: str
    location_label: str
    contact_label: str = ""
    unresolved_facts: list[str] = Field(default_factory=list)
    authority_source_id: str
    user_confirmed: StrictBool = False
class PostFilingReconciliationRequest(BaseModel):
    reconciliation_id: str
    reviewer_safe_id: str
    receipt_source: dict[str, Any] = Field(default_factory=dict)
    submitted_items: list[dict[str, Any]] = Field(default_factory=list)
    docket_expectations: list[dict[str, Any]] = Field(default_factory=list)
    user_confirmed: StrictBool = False


class AuthorityVerifyAnswerRequest(BaseModel):
    text: str
    answer_review_scope: str = Field(default="", max_length=128)
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


class DocumentIntelligenceContentDisarmRequest(BaseModel):
    source_token: str
    approved: StrictBool = False
    reviewer: str = "local_operator"


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
    source_record_id: str | None = None
    source_hash: str | None = None
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


class AttachmentCoverageCreateRequest(BaseModel):
    attachment_id: str
    attachment_label: str
    coverage_state: str = "referenced"
    source_record_id: str
    source_hash: str = ""
    linked_record_id: str = ""


class AttachmentCoverageReviewRequest(BaseModel):
    coverage_state: str
    linked_record_id: str = ""
    reviewer_notes: str = ""


class FactGraphNodeRequest(BaseModel):
    node_id: str
    node_kind: str
    label: str
    fact_state: str = "not_yet_reviewed"
    source_record_id: str
    source_hash: str = ""


class FactGraphEdgeRequest(BaseModel):
    edge_id: str
    source_node_id: str
    target_node_id: str
    relationship: str
    fact_state: str = "not_yet_reviewed"
    source_record_id: str
    source_hash: str = ""
    relationship_basis: str = "reviewer_supplied"
    relationship_note: str = ""


class IssueProofMatrixCreateRequest(BaseModel):
    item_id: str
    issue_id: str
    issue_label: str
    proof_item_id: str
    proof_label: str
    evidence_role: str
    source_record_id: str
    source_hash: str = ""
    authority_candidate: str = ""
    review_state: str = "review_required"


class IssueProofMatrixReviewRequest(BaseModel):
    review_state: str = "review_required"
    reviewer_notes: str = ""


class MatterChangeDigestCheckpointRequest(BaseModel):
    checkpoint_id: str
    checkpoint_label: str


class RecordLineageCreateRequest(BaseModel):
    link_id: str
    relationship: str
    original_record_id: str
    original_source_hash: str = ""
    derivative_record_id: str
    derivative_source_hash: str = ""
    reviewer_notes: str = ""


class EntityResolutionCandidateRequest(BaseModel):
    candidate_id: str
    entity_label: str
    entity_type: str = "person"
    left_record_id: str
    left_source_hash: str = ""
    right_record_id: str
    right_source_hash: str = ""
    reviewer_notes: str = ""


class EntityResolutionConfirmationRequest(BaseModel):
    confirmation: str
    canonical_entity_id: str = ""
    reviewer_notes: str = ""


class EntityResolutionRevokeRequest(BaseModel):
    reviewer_notes: str = ""


class WatchFolderScanRequest(BaseModel):
    folder: str
    limit: int = 200

class ScannerReviewRequest(BaseModel):
    original_sha256: str
    page_count: int
    duplex: bool = False
    blank_pages: list[int] = Field(default_factory=list)
    rotations: dict[int, int] = Field(default_factory=dict)
class HandwritingReviewRequest(BaseModel):
    source_hash: str
    ocr_confidence: float | None = None
    handwriting_signal: bool = False
class DocumentTypeReviewRequest(BaseModel):
    source_hash: str
    text_excerpt: str = ""
class PageQualityReviewRequest(BaseModel):
    source_hash: str
    pages: list[dict[str, Any]] = Field(default_factory=list)
class TableLineageRequest(BaseModel):
    source_hash: str
    cells: list[dict[str, Any]] = Field(default_factory=list)


class DocumentComparisonCreateRequest(BaseModel):
    comparison_id: str
    left_record_id: str
    right_record_id: str


class MetadataReviewBatchRequest(BaseModel):
    batch_id: str
    record_ids: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    document_date: str = "unknown"
    custodian_safe_id: str = "unknown"
    confidentiality: str = "review_required"
    document_type: str = "unknown"
    reviewer_notes: str = ""


class ImportPolicyProfileRequest(BaseModel):
    profile_id: str
    max_file_bytes: int = 250 * 1024 * 1024
    allowed_extensions: list[str] = Field(default_factory=list)
    privacy_scan_required: StrictBool = True
    quarantine_unknown_extensions: StrictBool = True
    local_ocr_review_for_images: StrictBool = True


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


class AuthorityImpactMatterRequest(BaseModel):
    base_build_id: str
    target_build_id: str


class LocalAgentPreviewRequest(BaseModel):
    model_config = {"extra": "forbid"}
    question: str = Field(min_length=1, max_length=20_000)
    source_refs: list[LocalAgentSourceReference] = Field(default_factory=list, max_length=24)
    matter_id: str = Field(default="", max_length=64)
    task: str = Field(default="authority_review", pattern=r"^(intake_triage|evidence_review|authority_review|drafting|parenting_plan_review|financial_disclosure_review|safety_privacy_review)$")
    provider: str = "ollama"
    endpoint: str = Field(default="http://127.0.0.1:11434", max_length=256)
    model: str = Field(default="qwen2.5:7b", max_length=256)
    run_id: str = Field(default="", max_length=128)


class LocalAgentExecuteRequest(LocalAgentPreviewRequest):
    approved_manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    approval_token: str = Field(pattern=r"^[a-f0-9]{64}$")
    tool_invocations: list[dict[str, Any]] = Field(default_factory=list)
    permitted_tools: list[str] = Field(default_factory=list)
    retrieval_diagnostics: dict[str, Any] = Field(default_factory=dict)


class LocalAgentCancelRequest(BaseModel):
    model_config = {"extra": "forbid"}
    matter_id: str = Field(min_length=1, max_length=64)
    run_id: str = Field(pattern=r"^[a-f0-9]{32}$")


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
    runtime_provider: str = ""
    runtime_endpoint: str = ""
    runtime_model_name: str = ""


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
    from app.api.routes.productivity import router as productivity_router
    from app.api.routes.addons import router as addons_router
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
    app.include_router(productivity_router, prefix="/api")
    app.include_router(addons_router, prefix="/api")


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
    _local_api_abuse_guard = LocalApiAbuseGuard()
    # Tokens are server-side capabilities, scoped to the currently active case.
    # They deliberately contain neither a filesystem location nor a corpus label.
    _record_open_tokens: dict[str, dict[str, Any]] = {}
    _record_open_lock = threading.RLock()
    _local_agent_approvals = LocalAgentApprovalStore()
    _local_agent_runs = LocalAgentRunStore()
    _answer_review_scopes = AnswerReviewScopes()
    _record_capability_identity: ContextVar[dict[str, str]] = ContextVar(
        "record_capability_identity",
        default={"role": "reviewer", "tenant_id": "local-desktop", "client_session_id": "legacy-local-session"},
    )
    _RECORD_OPEN_TTL_SECONDS = 60 * 60
    _RECORD_OPEN_MAX_TOKENS = 4096
    _RECORD_CAPABILITY_ACTIONS = frozenset(
        {
            "record_inspect",
            "record_open",
            "record_document_intelligence",
            "record_workspace_import",
            "record_local_agent",
        }
    )
    # Download capabilities use the same non-secret browser-session boundary as
    # record capabilities.  Every registry keeps its capability server-side;
    # URLs contain only an opaque, short-lived token and never a matter path.
    _ARTIFACT_CAPABILITY_ACTIONS = frozenset({"artifact_download", "artifact_receipt"})
    _RECORD_PREVIEW_TEXT_LIMIT = 120_000
    _RECORD_PREVIEW_MEMBER_LIMIT = 250
    _OPEN_CACHE_TTL_SECONDS = 24 * 60 * 60
    _OPEN_CACHE_MAX_FILES = 512
    _OPEN_CACHE_MAX_BYTES = 512 * 1024 * 1024
    _document_intelligence_artifacts: dict[str, dict[str, Any]] = {}
    _document_intelligence_artifact_lock = threading.RLock()
    _DOCUMENT_INTELLIGENCE_ARTIFACT_TTL_SECONDS = 60 * 60
    _DOCUMENT_INTELLIGENCE_ARTIFACT_MAX_TOKENS = 1024
    _document_workspace_artifacts: dict[str, dict[str, Any]] = {}
    _document_workspace_artifact_lock = threading.RLock()
    _DOCUMENT_WORKSPACE_ARTIFACT_TTL_SECONDS = 60 * 60
    _DOCUMENT_WORKSPACE_ARTIFACT_MAX_TOKENS = 1024
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

    def _record_open_token(
        case_root: Path,
        evidence_id: str,
        source_locator: str = "",
        *,
        allowed_actions: Iterable[str] | None = None,
    ) -> str:
        """Mint a short-lived opaque capability for one active-corpus record.

        The value is an in-memory bearer secret, but is additionally bound to
        the active matter, the current local browser session, role/tenant labels
        and a small read-action allow-list. It deliberately contains no path,
        record text, or user-provided label.
        """

        requested_actions = {
            str(action or "").strip()
            for action in (allowed_actions if allowed_actions is not None else _RECORD_CAPABILITY_ACTIONS)
        }
        if not requested_actions or not requested_actions.issubset(_RECORD_CAPABILITY_ACTIONS):
            raise ValueError("record_capability_action_invalid")
        identity = dict(_record_capability_identity.get())
        with _record_open_lock:
            _prune_record_open_tokens()
            token = secrets.token_hex(32)
            _record_open_tokens[token] = {
                "case_id": _case_id(case_root),
                "evidence_id": str(evidence_id or ""),
                "source_locator": str(source_locator or ""),
                "resource_type": "matter_record",
                "resource_id": str(evidence_id or ""),
                "allowed_actions": sorted(requested_actions),
                "role": str(identity.get("role") or "reviewer"),
                "tenant_id": str(identity.get("tenant_id") or "local-desktop"),
                "client_session_id": str(
                    identity.get("client_session_id") or "legacy-local-session"
                ),
                "created_at": time.time(),
            }
            return token

    def _artifact_capability_binding(
        *,
        resource_type: str,
        resource_id: str,
        allowed_actions: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        """Bind one opaque artifact registry entry to this local session.

        The caller retains the matter/scope and integrity fields needed to
        locate the artifact.  This helper adds only the fail-closed access
        boundary and intentionally never serializes a filesystem location.
        """

        requested_actions = {
            str(action or "").strip()
            for action in (
                allowed_actions
                if allowed_actions is not None
                else {"artifact_download", "artifact_receipt"}
            )
        }
        if (
            not str(resource_type or "").strip()
            or not str(resource_id or "").strip()
            or not requested_actions.issubset(_ARTIFACT_CAPABILITY_ACTIONS)
        ):
            raise ValueError("artifact_capability_invalid")
        identity = dict(_record_capability_identity.get())
        return {
            "resource_type": str(resource_type),
            "resource_id": str(resource_id),
            "allowed_actions": sorted(requested_actions),
            "role": str(identity.get("role") or "reviewer"),
            "tenant_id": str(identity.get("tenant_id") or "local-desktop"),
            "client_session_id": str(
                identity.get("client_session_id") or "legacy-local-session"
            ),
        }

    def _artifact_capability_allowed(
        binding: dict[str, Any],
        *,
        resource_type: str,
        expected_action: str = "artifact_download",
    ) -> bool:
        """Return true only for the originating session and artifact class."""

        if expected_action not in _ARTIFACT_CAPABILITY_ACTIONS:
            return False
        identity = dict(_record_capability_identity.get())
        return bool(
            binding
            and str(binding.get("resource_type") or "") == resource_type
            and bool(str(binding.get("resource_id") or ""))
            and expected_action in set(binding.get("allowed_actions") or [])
            and all(
                str(binding.get(key) or "") == str(identity.get(key) or "")
                for key in ("role", "tenant_id", "client_session_id")
            )
        )

    def _prune_document_workspace_artifacts(now: float | None = None) -> None:
        current = float(now if now is not None else time.time())
        stale_before = current - _DOCUMENT_WORKSPACE_ARTIFACT_TTL_SECONDS
        with _document_workspace_artifact_lock:
            stale = [
                token
                for token, binding in _document_workspace_artifacts.items()
                if float(binding.get("created_at") or 0) < stale_before
            ]
            for token in stale:
                _document_workspace_artifacts.pop(token, None)
            overflow = len(_document_workspace_artifacts) - _DOCUMENT_WORKSPACE_ARTIFACT_MAX_TOKENS
            if overflow > 0:
                oldest = sorted(
                    _document_workspace_artifacts.items(),
                    key=lambda item: float(item[1].get("created_at") or 0),
                )[:overflow]
                for token, _binding in oldest:
                    _document_workspace_artifacts.pop(token, None)

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

    def _conversation_matter_scope() -> str:
        """Return an opaque scope marker; never persist a matter path or name."""

        root = active_case_root()
        if root is None:
            return "general_maine_law"
        return "matter:" + hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:24]

    def _context_compaction_receipt(
        *,
        session_id: str,
        entry: dict[str, Any],
        matter_scope: str,
    ) -> dict[str, Any]:
        """Build a reversible, no-prose context receipt from already-safe state.

        Conversation text is deliberately excluded. The client retains the
        visible transcript; the service retains only routing labels and hashes
        that can be inspected, discarded, and never promoted to case facts.
        """

        anchor = _safe_intake_anchor(dict(entry.get("intake_anchor") or {}))
        source_ids = [
            str(item.get("source_id") or "")
            for item in list(entry.get("citations") or [])
            if str(item.get("source_id") or "")
        ]
        source_digest = hashlib.sha256(
            json.dumps(sorted(set(source_ids)), separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        body = {
            "schema_version": "safe_conversation_context_v1",
            "session_id": session_id,
            "matter_scope": matter_scope,
            "search_id": str(entry.get("search_id") or ""),
            "response_kind": str(entry.get("response_kind") or ""),
            "safe_routing_anchor": anchor,
            "source_card_count": len(source_ids),
            "source_basis_sha256": source_digest,
            "raw_turn_text_stored": False,
            "fact_promotion": "prohibited",
            "review_required": True,
            "reversible_inspection": "The visible local transcript remains unchanged; this receipt can be inspected or discarded without changing it.",
        }
        body["context_id"] = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:32]
        return body

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
        matter_scope = _conversation_matter_scope()
        with _recent_search_lock:
            prior_entry = dict(_recent_record_searches.get(key) or {})
        prior_compaction = (
            dict(prior_entry.get("context_compaction") or {})
            if str(prior_entry.get("matter_scope") or "") == matter_scope
            else {}
        )
        entry = {
            "search_id": search_id,
            "search_summary": dict(result.get("search_summary") or {}),
            "citations": citations,
            "active_case_label": str(result.get("active_case_label") or ""),
            "search_mode": str(result.get("search_mode") or payload.search_mode),
            "response_kind": str(result.get("response_kind") or "family_answer"),
            "direct_record_search": bool(result.get("direct_record_search")),
            "intake_anchor": _safe_intake_anchor(intake_value),
            "matter_scope": matter_scope,
            "context_compaction": prior_compaction,
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

    def _record_capability_request_identity(request: Request) -> dict[str, str]:
        """Return the non-secret local session boundary for opaque record tokens.

        This is deliberately a browser-session binding, not an identity proof or
        a replacement for the canonical role boundary. It prevents a token from
        one local workbench tab/session being replayed by another session while
        keeping the legacy local-desktop default deterministic for supported
        migrations and API-only recovery paths.
        """

        role = str(request.headers.get("X-User-Role") or "reviewer").strip().lower()
        if role not in {"admin", "attorney", "paralegal", "reviewer"}:
            role = "reviewer"
        tenant_id = str(request.headers.get("X-Tenant-Id") or "local-desktop").strip()
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", tenant_id):
            tenant_id = "local-desktop"
        client_session_id = str(
            request.headers.get("X-MFLL-Client-Session") or "legacy-local-session"
        ).strip().lower()
        if not re.fullmatch(r"[a-f0-9]{32,64}|legacy-local-session", client_session_id):
            client_session_id = "legacy-local-session"
        return {"role": role, "tenant_id": tenant_id, "client_session_id": client_session_id}

    def _require_local_dashboard_identity(request: Request) -> dict[str, str]:
        """Require an explicit local role, tenant, and browser session for a receipt.

        The dashboard is read-only as to the matter's records, but its explicit
        refresh creates an encrypted audit receipt.  Do not silently fall back
        to the legacy/default header values for that state-changing action.
        """

        role = str(request.headers.get("X-User-Role") or "").strip().lower()
        tenant_id = str(request.headers.get("X-Tenant-Id") or "").strip()
        session_id = str(request.headers.get("X-MFLL-Client-Session") or "").strip().lower()
        if role not in {"admin", "attorney", "paralegal", "reviewer"}:
            raise HTTPException(status_code=403, detail="dashboard_role_required")
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", tenant_id):
            raise HTTPException(status_code=403, detail="dashboard_tenant_required")
        if not re.fullmatch(r"[a-f0-9]{32,64}", session_id):
            raise HTTPException(status_code=403, detail="dashboard_session_required")
        return {"role": role, "tenant_id": tenant_id, "client_session_id": session_id}

    # A single encrypted boundary covers every JSON mutation route.  The
    # resolver is evaluated per request (after this module has defined
    # ``_case_id``), so its only persisted contribution is a matter hash.
    app.add_middleware(
        IdempotencyMiddleware,
        matter_scope_resolver=lambda: (
            _case_id(Path(active_case_root())) if active_case_root() is not None else "no_active_matter"
        ),
    )

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
            # The streamed route keeps ASGI receive untouched so disconnects
            # remain observable. Require a browser-provided bounded length on
            # that route rather than creating a chunked-body size bypass.
            require_content_length=request.url.path == "/ask/stream",
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
        rate_decision = _local_api_abuse_guard.check(
            method=request.method,
            path=request.url.path,
            client_host=getattr(request.client, "host", None),
        )
        if not rate_decision.allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": rate_decision.code,
                    "message": "The local workbench is receiving requests too quickly. Wait briefly and try again.",
                    "request_id": request_id,
                },
                headers={
                    "X-Request-ID": request_id,
                    "Retry-After": str(rate_decision.retry_after_seconds),
                    "Cache-Control": "no-store",
                },
            )
        # Streaming answers must keep the original receive channel intact so
        # Starlette can observe a genuine client disconnect.  The stream route
        # requires the bounded Content-Length checked above and its schema is
        # still hardened by `ask`.
        streaming_answer_request = request.url.path == "/ask/stream"
        if request.method.upper() not in {"GET", "HEAD", "OPTIONS"} and not streaming_answer_request:
            original_receive = request._receive  # type: ignore[attr-defined]
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
                    # The request body was already replayed to FastAPI.  Delegate
                    # later calls to the original ASGI receive channel so a
                    # StreamingResponse can wait for a real disconnect instead
                    # of receiving an invalid second http.request message.
                    return await original_receive()
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}

            request._receive = _receive  # type: ignore[attr-defined]
        identity_context = _record_capability_identity.set(
            _record_capability_request_identity(request)
        )
        try:
            response = await call_next(request)
        finally:
            _record_capability_identity.reset(identity_context)
        record_preview = request.url.path.startswith("/api/records/open/")
        if not response.headers.get("Content-Security-Policy"):
            frame_ancestors = "'self'" if record_preview else "'none'"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "connect-src 'self'; "
                "img-src 'self' data: blob:; "
                "media-src 'self' blob:; "
                "style-src 'self' 'unsafe-inline'; "
                "script-src 'self' 'unsafe-inline'; "
                "font-src 'self'; "
                "object-src 'none'; "
                "frame-src 'self' blob:; "
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
        if request.url.path.startswith("/api/"):
            response.headers["X-MFLL-Audit-Event-Id"] = request_id
            response.headers["X-MFLL-Audit-Event-Type"] = (
                f"{request.method.upper()}:{request.url.path}"
            )
            response.headers["X-MFLL-RBAC"] = "local-desktop-reviewer"
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

    def _normalize_response_depth(value: str) -> str:
        depth = str(value or "standard").strip().lower()[:32]
        return depth if depth in {"concise", "standard", "thorough"} else "standard"

    def _normalize_audience(value: str) -> str:
        aliases = {"parent": "self_represented", "lawyer": "attorney_review", "caregiver": "self_represented", "counselor": "legal_aid_intake", "therapist": "legal_aid_intake"}
        audience = aliases.get(str(value or "").strip().lower(), str(value or "").strip().lower())
        return audience if audience in {"self_represented", "legal_aid_intake", "paralegal", "attorney_review"} else "self_represented"

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

    _FAST_LOCAL_HELP_RULES: tuple[tuple[str, tuple[str, ...], str, str, str], ...] = (
        (
            "import_records",
            (
                r"\bhow (?:do|can) i (?:import|add|upload) (?:my )?(?:records|documents|files)\b",
                r"\bwhere (?:do|can) i (?:import|add|upload) (?:my )?(?:records|documents|files)\b",
            ),
            "setup",
            "Open matter setup",
            "Open Workspace, choose Matter setup, select or create a local matter, then use the desktop intake flow to approve the records you want indexed. The workbench does not read a folder merely because it exists.",
        ),
        (
            "open_source_cards",
            (
                r"\bhow (?:do|can) i (?:open|see|inspect|view) (?:the )?(?:source cards?|sources?)\b",
                r"\bwhere (?:are|can i find) (?:the )?(?:source cards?|sources?)\b",
            ),
            "evidence",
            "Open evidence",
            "Open Workspace, then Evidence. Each result keeps Maine authority, private matter records, and model analysis in separate lanes. Open a card to inspect its exact source or record context.",
        ),
        (
            "review_required_explainer",
            (
                r"\bwhat does review required mean\b",
                r"\bwhy (?:is|are) (?:this|that|the answer|my answer) review required\b",
            ),
            "review",
            "Open review details",
            "Review required means the workbench has not treated the response as a legal conclusion, a finding of fact, or filing-ready work. Open Workspace, then Review, to inspect missing information, source boundaries, and blockers.",
        ),
        (
            "starter_questions",
            (
                r"\bhow (?:do|can) i (?:find|open|use) (?:starter )?(?:questions|prompts)\b",
                r"\bwhere (?:are|can i find) (?:starter )?(?:questions|prompts)\b",
            ),
            "starters",
            "Open starter questions",
            "Open Workspace, then Starter questions, to choose a reviewed prompt. Selecting a prompt only fills the local chat composer; you remain in control of whether to send it.",
        ),
    )

    def _fast_local_help_payload(payload: AskRequest, intake: IntakeSummary) -> dict[str, Any] | None:
        """Return a zero-retrieval route only for narrowly scoped product help.

        This is deliberately not a shortcut for Maine-law, case-status, factual,
        deadline, or drafting questions. Those requests continue through the
        full canonical retrieval and verifier path. Fast responses contain no
        matter content and point to a concrete shipped UI artifact instead of
        fabricating a source card.
        """

        normalized = " ".join(re.findall(r"[a-z0-9]+", str(payload.question or "").casefold()))
        if not normalized or len(normalized) > 180:
            return None
        for route_id, patterns, panel, action_label, answer in _FAST_LOCAL_HELP_RULES:
            if not any(re.search(pattern, normalized) for pattern in patterns):
                continue
            return {
                "question": payload.question,
                "answer_style": payload.answer_style,
                "search_mode": _normalize_search_mode(payload.search_mode),
                "response_kind": "local_help_fast_path",
                "answer": answer,
                "grounded": False,
                "failure_class": "none",
                "recovery_hint": "Use the action below, or ask a specific Maine-law or records question when you are ready.",
                "citations": [],
                "source_card_count": 0,
                "review_required": True,
                "not_legal_advice": True,
                "matter_context_used": False,
                "metadata": {
                    "fast_path": {
                        "route_id": route_id,
                        "retrieval_skipped": True,
                        "reason": "narrow_product_navigation_only",
                        "legal_or_case_content": False,
                        "artifact_reference": f"workbench_drawer:{panel}",
                    },
                    "fast_path_actions": [{"panel": panel, "label": action_label}],
                    "intake": intake.to_dict(),
                    "missing_information": [
                        "This is product-navigation help only; no legal authority or private matter records were reviewed."
                    ],
                },
            }
        return None

    def _answer_intent_receipt(payload: AskRequest, intake: IntakeSummary, response_kind: str) -> dict[str, Any]:
        """Classify a request conservatively without changing substantive routing."""

        text = str(payload.question or "").casefold()
        signals = {
            "navigate": bool(response_kind == "local_help_fast_path" or re.search(r"\bhow do i|where (?:is|are|can)\b", text)),
            "locate": bool(intake.task in {"record_search", "corpus_inventory", "source_card_followup"}),
            "compare": bool(re.search(r"\bcompare|difference|versus|vs\.?\b", text)),
            "draft": bool(re.search(r"\bdraft|write|prepare a (?:motion|letter|affidavit)\b", text)),
            "review": bool(re.search(r"\breview|verify|check|support\b", text)),
            "calculate": bool(re.search(r"\bcalculate|deadline|due date|business day\b", text)),
            "prepare": bool(re.search(r"\bhearing|packet|exhibit|filing package\b", text)),
        }
        candidates = [name for name, matched in signals.items() if matched]
        primary = candidates[0] if len(candidates) == 1 else ("explain" if not candidates else "mixed")
        ambiguity = len(candidates) > 1
        return {
            "schema_version": "answer_intent_v2",
            "primary_intent": primary,
            "candidate_intents": candidates or ["explain"],
            "ambiguity": ambiguity,
            "clarification_required": ambiguity,
            "routing_changed": False,
            "review_required": True,
            "boundary": "Intent is a UI and workflow hint only. It does not establish facts, law, deadlines, jurisdiction, or a filing decision.",
        }

    def _clarification_minimizer(intent: dict[str, Any]) -> dict[str, Any]:
        """Ask at most one generic question when a choice changes the workflow."""

        candidates = [str(item) for item in list(intent.get("candidate_intents") or [])]
        if not bool(intent.get("ambiguity")):
            return {"schema_version": "clarification_minimizer_v1", "required": False, "questions": [], "review_required": True}
        labels = {"compare": "compare source-bound records", "calculate": "identify a rule-based deadline trigger", "draft": "prepare a review-required draft", "review": "verify support and blockers", "prepare": "assemble a review workspace", "locate": "locate a specific record", "navigate": "open a workbench area"}
        options = [
            {"intent": item, "label": labels.get(item, item.replace("_", " ")), "prompt": f"Help me {labels.get(item, item.replace('_', ' '))}."}
            for item in candidates[:4]
        ]
        return {
            "schema_version": "clarification_minimizer_v1",
            "required": True,
            "questions": [{
                "question_id": "workflow_priority",
                "question": "Which one task should be handled first?",
                "why_needed": "The choice changes the retrieval, procedure, drafting, or safety workflow. The app will not assume one.",
                "options": options,
            }],
            "review_required": True,
            "boundary": "This clarification selects a workflow only. It does not establish facts, law, deadlines, jurisdiction, or filing readiness.",
        }

    def _assumption_ledger(intake: IntakeSummary, citations: list[dict[str, Any]]) -> dict[str, Any]:
        """Expose only bounded classification, never a silently promoted matter fact."""

        entries = [
            {"entry_id": "source_basis", "label": "Source basis", "state": "source_bound" if citations else "unknown", "detail": f"{len(citations)} source card(s) are attached to this answer." if citations else "No source card supports a substantive conclusion yet.", "correctable": False},
            {"entry_id": "procedural_posture", "label": "Procedural posture", "state": "unknown" if intake.procedural_posture == "unknown" else "user_provided", "detail": "No procedural posture was inferred." if intake.procedural_posture == "unknown" else "The posture label came from the current request and needs review against records.", "correctable": True},
            {"entry_id": "matter_facts", "label": "Matter facts", "state": "unknown", "detail": "No unverified statement was promoted to a fact or finding.", "correctable": True},
        ]
        return {"schema_version": "assumption_ledger_v1", "entries": entries, "review_required": True, "boundary": "Correcting a ledger item starts a new review request only; it does not alter records, facts, orders, or legal conclusions."}

    def _question_decomposition(question: str, citations: list[dict[str, Any]]) -> dict[str, Any]:
        """Expose compound requests without pretending each part was separately researched."""

        normalized = " ".join(str(question or "").split()).strip()
        candidates = [part.strip(" ,;:") for part in re.split(r"\?+|\s*;\s*|\s+and\s+(?=(?:I|we|the|my|what|how|whether)\b)", normalized, flags=re.IGNORECASE) if part.strip(" ,;:")]
        if len(candidates) < 2 and " and " in normalized.casefold():
            candidates = [part.strip(" ,;:") for part in re.split(r"\s+and\s+", normalized, maxsplit=3, flags=re.IGNORECASE) if part.strip(" ,;:")]
        candidates = candidates[:4]
        is_compound = len(candidates) > 1
        source_ids = sorted(str(item.get("source_id") or "") for item in citations if str(item.get("source_id") or ""))
        return {"schema_version": "question_decomposition_v1", "is_compound": is_compound, "components": [{"component_id": f"question_part_{index + 1}", "question": part, "source_status": "shares_answer_source_basis" if source_ids else "no_admitted_source_basis", "independent_resolution": "not_yet_verified", "review_required": True} for index, part in enumerate(candidates if is_compound else [])], "unresolved_parts_explicit": is_compound, "source_basis_sha256": hashlib.sha256(json.dumps(source_ids, separators=(",", ":")).encode("utf-8")).hexdigest(), "private_question_persisted": False, "boundary": "Each part is a review queue, not a separate legal answer. Ask a part separately to retrieve and verify it independently.", "review_required": True}

    def _contradiction_aware_followup(question: str, case_root: Path | None) -> dict[str, Any]:
        """Detect a narrow date conflict with a source-bound pin; never decide truth."""

        receipt: dict[str, Any] = {"schema_version": "contradiction_followup_v1", "candidates": [], "review_required": True, "private_question_persisted": False, "boundary": "A conflict candidate means the new statement and a pinned source need human source review. It does not decide which is accurate, current, operative, or legally material."}
        if case_root is None:
            return receipt
        question_dates = set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", str(question or "")))
        if not question_dates:
            return receipt
        try:
            pins = FactPinStore(case_root).inventory().get("pins") or []
        except IntakeWorkbenchError:
            receipt["store_status"] = "unavailable"
            return receipt
        question_words = {word for word in re.findall(r"[a-z]{5,}", str(question).casefold()) if word not in {"about", "should", "could", "would", "there", "their", "which", "where"}}
        for pin in pins[:100]:
            pin_date = str(pin.get("effective_date") or "")
            pin_words = set(re.findall(r"[a-z]{5,}", str(pin.get("label") or "").casefold()))
            if pin_date and pin_date not in question_dates and len(question_words & pin_words) >= 1:
                receipt["candidates"].append({"candidate_id": f"pinned_date_{pin.get('pin_id')}", "kind": "different_effective_date", "pin_id": str(pin.get("pin_id") or ""), "pinned_date": pin_date, "new_date_candidates": sorted(question_dates), "dispute_status": str(pin.get("dispute_status") or "unclear"), "source_ref": dict(pin.get("source_ref") or {}), "review_required": True})
        receipt["candidates"] = receipt["candidates"][:10]
        receipt["candidate_count"] = len(receipt["candidates"])
        return receipt

    def _temporal_authority_receipt(question: str, citations: list[dict[str, Any]]) -> dict[str, Any]:
        match = re.search(r"\b(?:as\s+of|on)\s+(\d{4}-\d{2}-\d{2})\b", str(question or ""), re.IGNORECASE)
        receipt: dict[str, Any] = {"schema_version": "temporal_authority_review_v1", "requested_date": match.group(1) if match else None, "sources": [], "status": "not_requested", "review_required": True, "historical_law_determined": False, "boundary": "Effective dates and freshness markers are source metadata, not a complete historical-law or supersession determination."}
        if not match:
            return receipt
        requested = match.group(1)
        blockers: list[str] = []
        for item in citations:
            meta = dict(item.get("metadata") or {})
            if str(meta.get("source_lane") or "") != "legal_authority":
                continue
            effective = str(meta.get("effective_date") or "")
            freshness = str(meta.get("freshness_status") or "unknown")
            source_status = "date_metadata_missing"
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", effective):
                source_status = "effective_on_or_before_requested_date" if effective <= requested else "effective_after_requested_date"
            if source_status != "effective_on_or_before_requested_date" or freshness in {"stale", "superseded", "stale_or_superseded", "unknown"}:
                blockers.append(source_status if source_status != "effective_on_or_before_requested_date" else "freshness_not_current")
            receipt["sources"].append({"source_id": str(item.get("source_id") or ""), "effective_date": effective or None, "freshness_status": freshness, "status": source_status, "review_required": True})
        receipt["blockers"] = sorted(set(blockers))
        receipt["status"] = "blocked_needs_historical_source_review" if blockers or not receipt["sources"] else "candidate_metadata_only"
        return receipt

    def _authority_conflict_receipt(citations: list[dict[str, Any]]) -> dict[str, Any]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for item in citations:
            meta = dict(item.get("metadata") or {})
            if str(meta.get("source_lane") or "") == "legal_authority" and str(item.get("citation") or "").strip():
                groups.setdefault(str(item.get("citation")).strip().casefold(), []).append(item)
        candidates = []
        for citation, rows in groups.items():
            signatures = {(str((row.get("metadata") or {}).get("freshness_status") or "unknown"), str((row.get("metadata") or {}).get("effective_date") or ""), str((row.get("metadata") or {}).get("source_class") or "")) for row in rows}
            if len(rows) > 1 and len(signatures) > 1:
                candidates.append({"citation": citation, "source_ids": [str(row.get("source_id") or "") for row in rows], "metadata_variants": [{"freshness_status": value[0], "effective_date": value[1] or None, "source_class": value[2]} for value in sorted(signatures)], "review_required": True})
        return {"schema_version": "authority_conflict_review_v1", "candidates": candidates[:10], "candidate_count": len(candidates[:10]), "review_required": True, "controlling_authority_determined": False, "boundary": "Different metadata for the same citation requires source-by-source review. It does not establish conflict, controlling weight, amendment effect, or legal outcome."}

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
                "retrieval_method": str(row.get("method") or "unknown"),
                "retrieval_rank": int(row.get("rank") or 0),
                "retrieval_component_scores": {
                    str(key): float(value)
                    for key, value in dict(row.get("component_scores") or {}).items()
                    if isinstance(value, (int, float))
                },
                "retrieval_explanation": str(row.get("explanation") or "Rank explanation unavailable."),
                "negative_treatment_status": str(document_metadata.get("negative_treatment_status") or card.get("negative_treatment_status") or "negative_treatment_unknown"),
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
                "retrieval_stack": dict(payload.get("retrieval_stack") or {}),
                "human_review_required": True,
            },
        )

    def _answer_review_context() -> str:
        return json.dumps({
            "identity": _record_capability_identity.get(),
            "matter": str(active_case_root() or ""),
        }, sort_keys=True)

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
                "_answer_assertions": AnswerAssertions(
                    text=primary.snippet,
                    authority_build_id=str(retrieval.diagnostics.get("authority_build_id") or ""),
                    source_ids=tuple(item.source_id for item in retrieval.results),
                    quotes=((primary.source_id, primary.snippet),),
                    basis="server_exact_authority_quote",
                ),
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

        if (retrieval.diagnostics.get("authority_product_active") is True
                and retrieval.results and "_answer_assertions" not in result):
            result["_answer_assertions"] = AnswerAssertions(
                text=str(result.get("answer") or ""),
                authority_build_id=str(retrieval.diagnostics.get("authority_build_id") or ""),
                source_ids=tuple(item.source_id for item in retrieval.results),
            )

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
        case_root = active_case_root()
        identity = _record_capability_identity.get()
        refs = []
        if case_root is not None and identity.get("client_session_id") != "legacy-local-session":
            refs = _local_agent_context_service().references_from_cards(citations)
        result["local_agent_source_refs"] = [ref.model_dump() for ref in refs]
        result["local_agent_matter_id"] = _case_id(Path(case_root)) if case_root else ""
        result["local_agent_task"] = "evidence_review" if any(ref.lane == "private_record" for ref in refs) else "authority_review"
        result["local_agent_available"] = bool(refs)
        result["local_agent_unavailable_reason"] = "" if refs else "An active matter and exact verified source excerpts are required for a local model preview."
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

        assertion_input = result.pop("_answer_assertions", None)
        mode = _normalize_search_mode(str(result.get("search_mode") or payload.search_mode))
        # Combined/private answers retain full-text review. This scope only
        # separates this producer's public-law body from its own UI templates.
        if mode != "maine_law":
            assertion_input = None
        raw_citations = _attach_record_open_capabilities(
            active_case_root(), list(result.get("citations") or [])
        )
        citations = _redact_citation_paths(raw_citations)
        default_lane = "private_record" if mode == "my_records" else "legal_authority"
        citations = _dedupe_citations(_annotate_source_lanes(citations, default_lane))
        citations = annotate_grounding_metadata(citations)
        for citation in citations:
            rank_metadata = dict(citation.get("metadata") or {})
            method = str(citation.get("method") or rank_metadata.get("retrieval_method") or "unknown")
            scores = citation.get("component_scores") or rank_metadata.get("retrieval_component_scores") or {}
            rank_metadata["retrieval_method"] = method
            rank_metadata["retrieval_rank"] = citation.get("rank") or rank_metadata.get("retrieval_rank") or 0
            rank_metadata["retrieval_component_scores"] = {
                str(key): float(value) for key, value in dict(scores).items() if isinstance(value, (int, float))
            }
            rank_metadata["retrieval_explanation"] = str(citation.get("explanation") or rank_metadata.get("retrieval_explanation") or "Rank explanation unavailable.")
            rank_metadata["negative_treatment_status"] = str(rank_metadata.get("negative_treatment_status") or "negative_treatment_unknown")
            citation["metadata"] = rank_metadata
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
        metadata["answer_intent"] = _answer_intent_receipt(
            payload,
            intake,
            str(result.get("response_kind") or "family_answer"),
        )
        metadata["clarification_minimizer"] = _clarification_minimizer(metadata["answer_intent"])
        metadata["assumption_ledger"] = _assumption_ledger(intake, citations)
        metadata["question_decomposition"] = _question_decomposition(payload.question, citations)
        metadata["contradiction_followup"] = _contradiction_aware_followup(payload.question, active_case_root())
        metadata["temporal_authority_review"] = _temporal_authority_receipt(payload.question, citations)
        metadata["authority_conflict_review"] = _authority_conflict_receipt(citations)
        metadata["retrieval_rank_explainability"] = {
            "source_card_count": len(citations),
            "contribution_detail_count": sum(1 for item in citations if bool((item.get("metadata") or {}).get("retrieval_component_scores"))),
            "boundary": "Rank details explain retrieval signals only; they do not prove relevance, correctness, legal weight, or currentness.",
            "review_required": True,
        }
        metadata["query_expansion_guardrails"] = dict(
            (metadata.get("retrieval_diagnostics") or {}).get("retrieval_stack", {}).get("query_expansion") or {}
        )
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
            assertion_input.text if isinstance(assertion_input, AnswerAssertions) else str(result.get("answer") or ""),
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
        source_basis = [
            {
                "source_id": str(item.get("source_id") or ""),
                "citation": str(item.get("citation") or ""),
                "lane": str((item.get("metadata") or {}).get("source_lane") or ""),
                "locator": str((item.get("metadata") or {}).get("source_locator") or ""),
            }
            for item in citations
        ]
        # The compact first view and optional details must always refer to the
        # same already-finalized source set. This fingerprint is a receipt for
        # that invariant, not a claim that sources alone verify every sentence.
        metadata["progressive_response"] = {
            "schema_version": "progressive_response_v1",
            "compact_view": "what_this_means_and_exact_source_cards",
            "expandable_sections": [
                "critical_dates",
                "what_to_do_right_now",
                "next_three_steps",
                "what_to_gather",
                "what_may_be_missing",
                "suggested_questions",
            ],
            "same_cited_basis": True,
            "source_card_count": len(citations),
            "source_basis_sha256": hashlib.sha256(
                json.dumps(source_basis, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "review_required": True,
        }
        metadata["response_depth"] = _normalize_response_depth(payload.response_depth)
        audience = _normalize_audience(payload.audience)
        framing = {
            "self_represented": "Plain-language orientation and safe next steps; this does not decide what applies to the matter.",
            "legal_aid_intake": "Intake-oriented issue and record framing; this does not establish eligibility, representation, or legal conclusions.",
            "paralegal": "Source and task organization framing; legal judgment and client advice remain for authorized attorney review.",
            "attorney_review": "Citation-forward review framing; it does not substitute for attorney judgment or current-law verification.",
        }
        metadata["audience_presentation"] = {"audience": audience, "framing": framing[audience], "legal_truth_changed": False, "review_required": True}
        blockers = list(answer_support_integrity.get("blockers") or [])
        failure_class = str(result.get("failure_class") or "none")
        if failure_class != "none":
            blockers.append(failure_class)
        if result.get("response_kind") == "local_help_fast_path":
            footer_action = dict((metadata.get("fast_path_actions") or [{}])[0])
        elif failure_class in {"no_active_matter", "no_active_matter_for_combined_search"}:
            footer_action = {"panel": "setup", "label": "Choose a matter", "action_id": "choose_matter"}
        elif citations:
            footer_action = {"panel": "evidence", "label": "Open exact evidence", "action_id": "open_evidence"}
        else:
            footer_action = {"panel": "starters", "label": "Open starter questions", "action_id": "open_starters"}
        if "action_id" not in footer_action:
            footer_action["action_id"] = f"open_{footer_action.get('panel') or 'starters'}"
        metadata["actionable_footer"] = {
            "schema_version": "actionable_footer_v1",
            "next_action": footer_action,
            "blockers": list(dict.fromkeys(str(item) for item in blockers if item)),
            "review_required": True,
            "boundary": "The next action opens a local review workspace only; it does not file, send, decide, or certify anything.",
        }
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
        if isinstance(assertion_input, AnswerAssertions):
            result["answer_review_scope"] = _answer_review_scopes.issue(
                answer=result["answer"], context=_answer_review_context(), assertions=assertion_input,
            )
            result["answer_review_basis"] = assertion_input.basis
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

    @app.get("/api/runtime/idempotency-status")
    def runtime_idempotency_status(request: Request) -> dict[str, Any]:
        """Expose the local duplicate-suppression boundary without state content."""

        identity = _require_local_dashboard_identity(request)
        try:
            return {
                **IdempotencyRegistry().status(),
                "actor_role": identity["role"],
                "tenant_scope": "current_local_tenant_only",
                "matter_scope": "request-bound; no matter records returned",
            }
        except Exception as exc:
            raise HTTPException(status_code=503, detail="idempotency_registry_unavailable") from exc

    @app.get("/api/runtime/database-integrity")
    def runtime_database_integrity(request: Request) -> dict[str, Any]:
        """Run a bounded, read-only integrity check and preserve a receipt.

        This endpoint is intentionally incapable of repair. It returns no
        database name, path, table rows, payloads, prompts, or record text.
        A failed check leaves the original runtime state untouched and supplies
        only conservative recovery guidance for a human reviewer.
        """

        identity = _require_local_dashboard_identity(request)
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            report = run_database_integrity_check(get_runtime_kernel().path)
            return DatabaseIntegrityReceiptStore(case_root).record(
                report,
                actor_role=identity["role"],
                tenant_id=identity["tenant_id"],
            )
        except DatabaseIntegrityError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc

    @app.post("/api/runtime/power-loss-drill")
    def runtime_power_loss_drill(request: Request) -> dict[str, Any]:
        """Run an admin-approved, synthetic fault-injection drill only.

        The drill creates no user record, does not interrupt the running
        process, and never claims physical power-cut qualification. Its only
        durable result is an encrypted active-matter review receipt.
        """

        identity = _require_local_dashboard_identity(request)
        if identity["role"] != "admin":
            raise HTTPException(status_code=403, detail="admin_role_required")
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            report = run_power_loss_resilience_drill(
                workspace_parent=Path(case_root) / "40_RUNTIME"
            )
            return PowerLossResilienceReceiptStore(case_root).record(
                report,
                actor_role=identity["role"],
                tenant_id=identity["tenant_id"],
            )
        except PowerLossResilienceError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc

    @app.get("/api/runtime/storage-pressure")
    def runtime_storage_pressure(request: Request) -> dict[str, Any]:
        identity = _require_local_dashboard_identity(request)
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return StoragePressureReceiptStore(case_root).record(
                forecast_storage_pressure(case_root), actor_role=identity["role"], tenant_id=identity["tenant_id"]
            )
        except StoragePressureError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc

    @app.get("/api/runtime/clock-skew")
    def runtime_clock_skew(request: Request) -> dict[str, Any]:
        identity = _require_local_dashboard_identity(request)
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return ClockSkewMonitor(case_root).check(actor_role=identity["role"], tenant_id=identity["tenant_id"])
        except ClockSkewError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc

    @app.get("/api/runtime/performance-gates")
    def runtime_performance_gate_catalog(request: Request) -> dict[str, Any]:
        """Expose local review budgets without creating a measurement receipt."""

        identity = _require_local_dashboard_identity(request)
        return {
            **performance_budget_catalog(),
            "actor_role": identity["role"],
            "tenant_scope": "current_local_tenant_only",
            "matter_scope": "an active matter is required when saving a review receipt",
        }

    @app.post("/api/runtime/performance-gates")
    async def record_runtime_performance_gates(request: Request) -> dict[str, Any]:
        """Save a bounded local budget review for the active matter.

        The caller can submit only allow-listed numeric values and a declared
        evidence kind.  No prompt, record, path, package inventory, or machine
        identifier can enter the receipt through this route.
        """

        identity = _require_local_dashboard_identity(request)
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=422, detail="performance_payload_invalid") from exc
        if not isinstance(payload, dict) or set(payload) - {"observations", "evidence_kind"}:
            raise HTTPException(status_code=422, detail="performance_payload_invalid")
        try:
            report = evaluate_performance_gates(
                payload.get("observations") or {},
                evidence_kind=str(payload.get("evidence_kind") or "operator_supplied_unverified"),
            )
            return PerformanceGateReceiptStore(case_root).record(
                report,
                actor_role=identity["role"],
                tenant_id=identity["tenant_id"],
            )
        except PerformanceGateError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc

    @app.get("/api/runtime/failure-replay")
    def runtime_failure_replay_catalog(request: Request) -> dict[str, Any]:
        """List replayable safe-error contracts; no failure state is created."""

        identity = _require_local_dashboard_identity(request)
        return {
            **failure_replay_catalog(),
            "actor_role": identity["role"],
            "tenant_scope": "current_local_tenant_only",
            "matter_scope": "an active matter is required when recording a replay receipt",
        }

    @app.post("/api/runtime/failure-replay")
    async def record_runtime_failure_replay(request: Request) -> dict[str, Any]:
        """Replay one allow-listed safe envelope without rerunning an operation."""

        identity = _require_local_dashboard_identity(request)
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=422, detail="failure_replay_payload_invalid") from exc
        if not isinstance(payload, dict) or set(payload) - {"scenario_id", "confirmed"}:
            raise HTTPException(status_code=422, detail="failure_replay_payload_invalid")
        if payload.get("confirmed") is not True:
            raise HTTPException(status_code=422, detail="failure_replay_confirmation_required")
        try:
            report = replay_sanitized_failure(payload.get("scenario_id"))
            return FailureReplayReceiptStore(case_root).record(
                report,
                actor_role=identity["role"],
                tenant_id=identity["tenant_id"],
            )
        except FailureReplayError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc

    @app.get("/api/runtime/cross-device-transfer")
    def runtime_cross_device_transfer_status(request: Request) -> dict[str, Any]:
        identity = _require_local_dashboard_identity(request)
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            store = CrossDeviceTransferStore(case_root)
            return {**store.status(), **store.list_bundles(), "actor_role": identity["role"]}
        except CrossDeviceTransferError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc

    @app.post("/api/runtime/cross-device-transfer/export")
    async def export_runtime_cross_device_transfer(request: Request) -> dict[str, Any]:
        identity = _require_local_dashboard_identity(request)
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=422, detail="transfer_payload_invalid") from exc
        if not isinstance(payload, dict) or set(payload) - {"transfer_id", "passphrase", "confirmed"} or payload.get("confirmed") is not True:
            raise HTTPException(status_code=422, detail="transfer_confirmation_required")
        try:
            return CrossDeviceTransferStore(case_root).create_bundle(transfer_id=payload.get("transfer_id"), passphrase=payload.get("passphrase"), actor_role=identity["role"], tenant_id=identity["tenant_id"])
        except CrossDeviceTransferError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc

    @app.post("/api/runtime/cross-device-transfer/import")
    async def import_runtime_cross_device_transfer(request: Request) -> dict[str, Any]:
        identity = _require_local_dashboard_identity(request)
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=422, detail="transfer_payload_invalid") from exc
        if not isinstance(payload, dict) or set(payload) - {"transfer_id", "passphrase", "confirmed"} or payload.get("confirmed") is not True:
            raise HTTPException(status_code=422, detail="transfer_confirmation_required")
        try:
            return CrossDeviceTransferStore(case_root).import_bundle(transfer_id=payload.get("transfer_id"), passphrase=payload.get("passphrase"), actor_role=identity["role"], tenant_id=identity["tenant_id"])
        except CrossDeviceTransferError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc

    @app.get("/api/runtime/schema-migration-lab")
    def runtime_schema_migration_lab_status(request: Request) -> dict[str, Any]:
        identity = _require_local_dashboard_identity(request)
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return {**SchemaMigrationLab(case_root).status(tenant_id=identity["tenant_id"]), "actor_role": identity["role"]}
        except SchemaMigrationLabError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc

    @app.post("/api/runtime/schema-migration-lab/run")
    async def run_runtime_schema_migration_lab(request: Request) -> dict[str, Any]:
        identity = _require_local_dashboard_identity(request)
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=422, detail="migration_lab_payload_invalid") from exc
        if not isinstance(payload, dict) or set(payload) - {"source_schema", "scenario", "confirmed"} or payload.get("confirmed") is not True:
            raise HTTPException(status_code=422, detail="migration_lab_confirmation_required")
        try:
            return SchemaMigrationLab(case_root).run(source_schema=payload.get("source_schema"), scenario=payload.get("scenario"), actor_role=identity["role"], tenant_id=identity["tenant_id"])
        except SchemaMigrationLabError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc

    @app.get("/api/runtime/health-dashboard")
    def runtime_health_dependency_dashboard(request: Request) -> dict[str, Any]:
        """Record and return a content-free readiness view for the active matter.

        This is deliberately a local, protected diagnostic action: the response
        contains component states and safe counters only, while its receipt is
        encrypted in the active matter.  It does not contact providers, download
        engines, inspect record text, or reveal local filesystem paths.
        """

        identity = _require_local_dashboard_identity(request)
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            dashboard = collect_health_dependency_dashboard(
                case_root=case_root,
                runtime_health=runtime_health_snapshot,
                authority_status=lambda: AuthorityProductService().status(),
                ocr_status=ocr_prerequisite_status,
                backup_status=lambda: MatterBackupRestoreDrill(
                    case_root, repo_root=Path(__file__).resolve().parents[2]
                ).status(),
                runtime_kernel=get_runtime_kernel(),
                matter_id=_case_id(Path(case_root)),
            )
            return HealthDependencyDashboardStore(case_root).record(
                dashboard,
                actor_role=identity["role"],
                tenant_id=identity["tenant_id"],
            )
        except HealthDashboardError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc

    @app.get("/api/runtime/job-journal")
    def runtime_job_journal(request: Request) -> dict[str, Any]:
        """Return a receipt-backed, content-free active-matter job journal."""

        identity = _require_local_dashboard_identity(request)
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            journal = collect_job_journal(
                kernel=get_runtime_kernel(), matter_id=_case_id(Path(case_root))
            )
            return JobJournalReceiptStore(case_root).record(
                journal,
                actor_role=identity["role"],
                tenant_id=identity["tenant_id"],
            )
        except JobJournalError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc

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
                {
                    "provider_id": "fast_interchange_local",
                    "default_endpoint": "http://127.0.0.1:8105",
                    "default_model": "admitted-release-model",
                    "requires_host_worker_token": True,
                    "bundled_model_artifacts": False,
                    "external_admission_required": True,
                },
            ],
            "exact_manifest_approval_required": True,
            "server_rehydrated_sources_required": True,
            "single_use_session_approval_required": True,
            "review_required": True,
        }

    @app.exception_handler(RequestValidationError)
    async def local_agent_validation_error(request: Request, exc: RequestValidationError):
        if request.url.path.startswith(("/api/local-agent/", "/api/model-packs")):
            return JSONResponse(status_code=422, content={"detail": "local_agent_request_invalid", "review_required": True})
        return await request_validation_exception_handler(request, exc)

    def _local_agent_record_source(token: str) -> dict[str, Any]:
        try:
            resolved = _resolve_record_capability(token, 0, expected_action="record_local_agent")
            if not re.fullmatch(r"[a-fA-F0-9]{64}", str(resolved["root"].get("source_hash") or "")):
                raise LocalAgentContextError("local_agent_record_hash_required")
            if len(resolved["data"]) > 50 * 1024 * 1024:
                raise LocalAgentContextError("local_agent_record_too_large")
            parsed = parse_bytes(resolved["data"], suffix=resolved["suffix"], locator=resolved["filename"])
            if not parsed.text or not parsed.text.strip():
                raise LocalAgentContextError("local_agent_verified_text_required")
            return {
                "source_id": str(resolved["binding"]["resource_id"]),
                "source_sha256": resolved["source_hash"], "text": parsed.text,
                "title": resolved["filename"], "source_class": "private_record",
            }
        except LocalAgentContextError:
            raise
        except Exception as exc:
            raise LocalAgentContextError("local_agent_record_unavailable") from exc

    def _local_agent_context_service() -> LocalAgentContextService:
        return LocalAgentContextService(authority=AuthorityProductService(), record_loader=_local_agent_record_source)

    def _local_agent_scope(payload: LocalAgentPreviewRequest, request: Request) -> tuple[dict[str, str], Path]:
        identity = _require_local_dashboard_identity(request)
        case_root = active_case_root()
        if case_root is None or payload.matter_id != _case_id(Path(case_root)):
            raise HTTPException(status_code=409, detail="local_agent_active_matter_mismatch")
        return {**identity, "matter_id": payload.matter_id}, Path(case_root)

    def _local_agent_audit_store(root: Path) -> LocalAgentAuditStore:
        return LocalAgentAuditStore(root, encryption_key=os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")

    register_model_pack_routes(app, scope_resolver=_local_agent_scope, audit_factory=_local_agent_audit_store)

    def _local_agent_binding(payload: LocalAgentPreviewRequest, scope: dict[str, str], runtime: LocalAgentRuntime) -> dict[str, Any]:
        return {
            "scope": scope, "question": payload.question, "task": payload.task,
            "provider": payload.provider, "endpoint": payload.endpoint, "model": payload.model,
            "run_id": payload.run_id, "source_refs": [ref.model_dump() for ref in payload.source_refs],
            "model_admission": getattr(runtime.client, "model_binding", {}),
        }

    def _local_agent_runtime_from_request(payload: LocalAgentPreviewRequest) -> LocalAgentRuntime:
        try:
            client = build_local_client(
                provider=payload.provider,
                endpoint=payload.endpoint,
                model_name=payload.model,
                timeout_seconds=120,
                capability=payload.task,
            )
        except (ValueError, LocalModelError) as exc:
            detail = getattr(exc, "code", None) or str(exc)
            raise HTTPException(
                status_code=400, detail={"error": detail, "code": detail, "loopback_only": True}
            ) from exc
        return LocalAgentRuntime(client)

    @app.post("/api/local-agent/preview")
    def local_agent_preview(payload: LocalAgentPreviewRequest, request: Request) -> dict[str, Any]:
        scope, root = _local_agent_scope(payload, request)
        runtime = _local_agent_runtime_from_request(payload)
        try:
            sources, cards = _local_agent_context_service().resolve(payload.source_refs)
            # The host owns run identity. The returned value is required on run.
            payload = payload.model_copy(update={"run_id": uuid.uuid4().hex})
            manifest, _, injection_report = runtime.preview(
                question=payload.question,
                sources=sources,
                run_id=payload.run_id,
            )
            binding = _local_agent_binding(payload, scope, runtime)
            audit = _local_agent_audit_store(root).record("preview", scope=scope, binding_sha256=local_agent_digest(binding))
            token = _local_agent_approvals.issue(binding, manifest.to_dict())
            if hasattr(runtime.client, "model_binding") and callable(getattr(runtime.client, "cancel", None)):
                _local_agent_runs.register(payload.run_id, scope, runtime.client)
        except LocalAgentContextError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="local_agent_context_invalid") from exc
        return {
            "schema_version": "local_agent_preview_response_v2",
            "status": "approval_required",
            "approval_token": token,
            "approval_expires_in_seconds": 300,
            "matter_id": scope["matter_id"],
            "task": payload.task,
            "source_refs": [ref.model_dump() for ref in payload.source_refs],
            "audit_receipt": audit,
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
            "source_cards": cards,
            "review_required": True,
            "model_admission": getattr(runtime.client, "model_binding", {}),
            "cancellation_supported": hasattr(runtime.client, "model_binding") and callable(getattr(runtime.client, "cancel", None)),
        }

    @app.post("/api/local-agent/cancel")
    def local_agent_cancel(payload: LocalAgentCancelRequest, request: Request) -> dict[str, Any]:
        scope, root = _local_agent_scope(payload, request)
        try:
            audit = _local_agent_audit_store(root).record("cancel_requested", scope=scope,
                                                         binding_sha256=local_agent_digest({"run_id": payload.run_id}))
            result = _local_agent_runs.cancel(payload.run_id, scope)
        except LocalAgentContextError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc
        except LocalModelError as exc:
            raise HTTPException(status_code=503, detail=exc.code) from exc
        return {**result, "run_id": payload.run_id, "audit_receipt": audit, "review_required": True}

    @app.post("/api/local-agent/run")
    def local_agent_run(payload: LocalAgentExecuteRequest, request: Request) -> dict[str, Any]:
        scope, root = _local_agent_scope(payload, request)
        if payload.tool_invocations or payload.permitted_tools or payload.retrieval_diagnostics:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "local_agent_ui_tool_execution_not_enabled",
                    "message": "The browser flow uses approved source context only. Host tools require a separately registered handler.",
                },
            )
        runtime = _local_agent_runtime_from_request(payload)
        controlled_run = False
        try:
            sources, cards = _local_agent_context_service().resolve(payload.source_refs)
            binding = _local_agent_binding(payload, scope, runtime)
            manifest = _local_agent_approvals.consume(payload.approval_token, binding, payload.approved_manifest_sha256)
            audit_store = _local_agent_audit_store(root)
            audit_store.record("dispatch", scope=scope, binding_sha256=local_agent_digest(binding))
            # Audit I/O and model selection cannot bypass a late matter/source change.
            current_root = active_case_root()
            if current_root is None or _case_id(Path(current_root)) != payload.matter_id:
                raise LocalAgentContextError("local_agent_active_matter_mismatch")
            sources, cards = _local_agent_context_service().resolve(payload.source_refs)
            if hasattr(runtime.client, "model_binding") and callable(getattr(runtime.client, "cancel", None)):
                runtime = LocalAgentRuntime(_local_agent_runs.claim(payload.run_id, scope, runtime.client.model_binding))
                controlled_run = True
            result = runtime.run(LocalAgentRunRequest(
                question=payload.question, sources=sources,
                approved_manifest_sha256=payload.approved_manifest_sha256,
                matter_id=payload.matter_id, run_id=payload.run_id,
                manifest_created_at=manifest["created_at"],
            ))
            audit = audit_store.record("result", scope=scope, binding_sha256=local_agent_digest(binding),
                                       receipt_sha256=result.provenance_receipt.receipt_sha256)
            current_root = active_case_root()
            if current_root is None or _case_id(Path(current_root)) != payload.matter_id:
                raise LocalAgentContextError("local_agent_active_matter_changed_result_withheld")
            # A completed worker request does not override revocation or a source
            # generation change that happened while it was running.
            _local_agent_context_service().resolve(payload.source_refs)
            if controlled_run:
                canceled = _local_agent_runs.finish(payload.run_id, scope, failed=result.status != "completed_review_required")
                controlled_run = False
                if canceled or "fast_interchange_generation_canceled" in result.warnings:
                    _local_agent_audit_store(root).record("canceled", scope=scope, binding_sha256=local_agent_digest(binding))
                    raise LocalAgentContextError("fast_interchange_generation_canceled")
        except LocalAgentContextError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc
        finally:
            if controlled_run:
                _local_agent_runs.finish(payload.run_id, scope, failed=True)
        if result.status == "blocked":
            raise HTTPException(status_code=409, detail=result.to_dict())
        return {
            **result.to_dict(),
            "citations": cards,
            "audit_receipt": audit,
            "matter_id": payload.matter_id,
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

    @app.get("/api/authority/gaps")
    def local_authority_gaps(issue: str = "") -> dict[str, Any]:
        try:
            return AuthorityProductService().authority_gap_review(issue=str(issue or "")[:500])
        except (FileNotFoundError, ValueError, OSError):
            return {"status": "blocked", "blockers": ["active_authority_product_unavailable_or_unverified"], "review_required": True}

    @app.get("/api/authority/gaps/sources/{source_id}")
    def local_authority_gap_source(source_id: str, build_id: str) -> dict[str, Any]:
        try:
            return AuthorityProductService().authority_gap_source(source_id, build_id=build_id)
        except (FileNotFoundError, ValueError, OSError):
            return {"status": "blocked", "blockers": ["active_authority_product_unavailable_or_unverified"], "review_required": True}

    @app.get("/api/authority/freshness")
    def local_authority_freshness_dashboard() -> dict[str, Any]:
        try:
            return AuthorityLibraryService().freshness_dashboard()
        except (FileNotFoundError, ValueError, OSError):
            return {
                "status": "blocked",
                "blockers": ["authority_freshness_metadata_unavailable"],
                "review_required": True,
                "current_law_determined": False,
            }

    @app.get("/api/authority/availability")
    def local_authority_availability_monitor() -> dict[str, Any]:
        try:
            return AuthorityLibraryService().availability_monitor()
        except (FileNotFoundError, ValueError, OSError):
            return {
                "status": "blocked",
                "blockers": ["authority_availability_metadata_unavailable"],
                "review_required": True,
                "availability_determined": False,
                "network_used": False,
                "mirror_substitution": False,
            }

    @app.get("/api/authority/parser-regression")
    def local_authority_parser_regression() -> dict[str, Any]:
        try:
            return AuthorityLibraryService().parser_regression_corpus()
        except (FileNotFoundError, ValueError, OSError):
            return {
                "status": "blocked",
                "blockers": ["parser_regression_corpus_unavailable"],
                "review_required": True,
                "corpus_is_legal_authority": False,
                "network_used": False,
            }

    @app.get("/api/authority/parser-regression/{fixture_id}")
    def local_authority_parser_regression_fixture(fixture_id: str) -> dict[str, Any]:
        try:
            return AuthorityLibraryService().parser_regression_fixture(fixture_id)
        except (FileNotFoundError, ValueError, OSError):
            return {
                "status": "blocked",
                "fixture_id": fixture_id[:160],
                "blockers": ["parser_regression_fixture_unavailable"],
                "review_required": True,
                "can_support_legal_claim": False,
            }

    @app.get("/api/authority/lineage/{source_id}")
    def local_authority_lineage(source_id: str) -> dict[str, Any]:
        try:
            return AuthorityProductService().authority_lineage(source_id)
        except (FileNotFoundError, ValueError, OSError):
            return {
                "status": "blocked",
                "source_id": source_id[:256],
                "blockers": ["active_authority_product_unavailable_or_unverified"],
                "review_required": True,
                "network_used": False,
                "current_law_determined": False,
            }

    @app.post("/api/authority/forms/synchronize")
    def local_authority_forms_synchronize(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return AuthorityProductService().synchronize_forms(payload.get("installed_forms"))
        except (FileNotFoundError, ValueError, OSError):
            return {
                "status": "blocked",
                "blockers": ["active_authority_form_catalog_unavailable_or_unverified"],
                "review_required": True,
                "completion_blocked": True,
                "network_used": False,
            }

    @app.get("/api/authority/opinions/{source_id}/enrichment")
    def local_authority_law_court_opinion_enrichment(source_id: str) -> dict[str, Any]:
        try:
            return AuthorityProductService().law_court_opinion_enrichment(source_id)
        except (FileNotFoundError, ValueError, OSError):
            return {
                "status": "blocked",
                "source_id": source_id[:256],
                "blockers": ["active_law_court_opinion_unavailable_or_unverified"],
                "review_required": True,
                "network_used": False,
                "current_law_determined": False,
                "treatment_determined": False,
            }

    @app.get("/api/authority/rules/history")
    def local_authority_rule_history_timeline(query: str = "") -> dict[str, Any]:
        try:
            return AuthorityProductService().rule_history_timeline(query)
        except (FileNotFoundError, ValueError, OSError):
            return {
                "status": "blocked",
                "query": query[:256],
                "timeline": [],
                "blockers": ["active_rule_history_unavailable_or_unverified"],
                "review_required": True,
                "network_used": False,
                "as_of_determined": False,
            }

    @app.get("/api/authority/graph/{source_id}")
    def local_authority_graph(source_id: str) -> dict[str, Any]:
        try:
            return AuthorityProductService().citation_graph_neighbors(source_id)
        except Exception as exc:
            raise HTTPException(status_code=409, detail="authority_graph_unavailable") from exc

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

    class AuthorityBuildActivationRequest(BaseModel):
        build_id: str = Field(min_length=24, max_length=24)
        acknowledged: StrictBool = False

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

    @app.get("/api/authority/builds/{build_id}/diff")
    def local_authority_build_diff(build_id: str) -> dict[str, Any]:
        return AuthorityLibraryService().compare_builds(build_id)

    @app.post("/api/authority/activate")
    def local_authority_activate(payload: AuthorityBuildActivationRequest) -> dict[str, Any]:
        if not payload.acknowledged:
            return {"status": "blocked", "build_id": payload.build_id, "blockers": ["authority_activation_acknowledgement_required"], "review_required": True}
        return AuthorityLibraryService().activate_build(payload.build_id, operation="activate")

    @app.post("/api/authority/rollback")
    def local_authority_rollback(payload: AuthorityBuildActivationRequest) -> dict[str, Any]:
        if not payload.acknowledged:
            return {"status": "blocked", "build_id": payload.build_id, "blockers": ["authority_rollback_acknowledgement_required"], "review_required": True}
        return AuthorityLibraryService().activate_build(payload.build_id, operation="rollback")

    @app.post("/api/authority/citations/resolve")
    @app.post("/api/authority/pinpoints/resolve")
    def resolve_active_authority_pinpoints(payload: dict) -> dict[str, Any]:
        """Resolve immutable public authority; no matter text is retained here."""
        text = harden_text_input(str(payload.get("text") or ""), max_length=100_000).value
        try:
            result = AuthorityProductService().resolve_citations(text)
        except (FileNotFoundError, ValueError, OSError):
            result = {
                "status": "blocked",
                "blockers": ["active_authority_product_unavailable_or_unverified"],
                "resolutions": [],
                "review_required": True,
            }
        result["boundary"] = (
            "A pinpoint locates admitted source text only. It does not determine legal effect, "
            "currentness, controlling authority, or a result in any matter."
        )
        return result

    @app.post("/api/authority/verify-answer")
    def verify_answer_against_active_authority(
        payload: AuthorityVerifyAnswerRequest,
    ) -> dict[str, Any]:
        text_result = harden_text_input(payload.text, max_length=200_000, preserve_newlines=True)
        review_scope = None
        if payload.answer_review_scope:
            try:
                review_scope = _answer_review_scopes.resolve(
                    payload.answer_review_scope, answer=payload.text, context=_answer_review_context(),
                )
            except ValueError:
                return {
                    "status": "blocked", "blockers": ["answer_review_scope_expired_or_mismatch"],
                    "review_required": True,
                    "recovery_hint": "Ask again to refresh the answer-bound review, or verify the complete text without a saved scope.",
                }
        try:
            result = AuthorityProductService().verify_output(
                text=payload.text if review_scope else text_result.value,
                source_ids=payload.source_ids,
                quotes=payload.quotes,
                claims=payload.claims,
                expected_jurisdiction=str(payload.expected_jurisdiction or "maine")[:64],
                auto_extract_claims=bool(payload.auto_extract_claims),
                review_scope=review_scope,
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
            result = operation()
            if isinstance(result, dict):
                # Specialized matter workbenches always return local working
                # data. Service methods cannot accidentally suppress the
                # human-review boundary on a comparison, inventory, or receipt.
                result["review_required"] = True
                result["local_only"] = True
            return result
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

    def _order_calendar_store() -> OrderCalendarExtractionStore:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return OrderCalendarExtractionStore(case_root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.post("/api/calendar/order-term-extractions")
    def order_calendar_extraction_create(payload: dict[str, Any]) -> dict[str, Any]:
        def create() -> dict[str, Any]:
            case_root = active_case_root()
            if case_root is None:
                raise IntakeWorkbenchError("no_active_matter", 409)
            return _order_calendar_store().create(
                payload,
                terms=_order_store().terms().get("terms", []),
                records=_review_records(case_root),
            )

        return _intake_call(create)

    @app.get("/api/calendar/order-term-extractions/{extraction_id}")
    def order_calendar_extraction_get(extraction_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _order_calendar_store().get(extraction_id))

    @app.get("/api/calendar/order-term-extractions/{extraction_id}/source")
    def order_calendar_extraction_source(extraction_id: str) -> dict[str, Any]:
        def resolve() -> dict[str, Any]:
            case_root = active_case_root()
            if case_root is None:
                raise IntakeWorkbenchError("no_active_matter", 409)
            payload = _order_calendar_store().source(extraction_id)
            source = dict(payload.get("source") or {})
            source_hash = str(source.get("source_hash") or "").casefold()
            record_id = str(source.get("record_id") or "")
            row = next(
                (item for item in _review_records(case_root) if str(item.get("evidence_id") or item.get("source_id") or "").casefold() == record_id.casefold()),
                None,
            )
            if row is None or not re.fullmatch(r"[a-f0-9]{64}", source_hash) or str(row.get("source_hash") or row.get("sha256") or "").casefold() != source_hash:
                raise IntakeWorkbenchError("order_calendar_source_not_in_active_matter", 404)
            locator = str(row.get("source_locator") or row.get("title") or record_id)
            source["source_token"] = _record_open_token(case_root, record_id, locator)
            return {**payload, "source": source}

        return _intake_call(resolve)

    @app.post("/api/calendar/rules")
    def calendar_add_rules(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _calendar_store().add_rules(payload))

    @app.post("/api/calendar/deadline-candidates")
    def calendar_deadline_candidate(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _calendar_store().calculate(payload))

    @app.post("/api/calendar/deadline-dependencies")
    def calendar_deadline_dependency(payload: dict[str, Any]) -> dict[str, Any]:
        def create() -> dict[str, Any]:
            store = _calendar_store()
            trigger_id = str(payload.get("trigger_event_id") or "")
            event = next((row for row in store.inventory().get("events", []) if str(row.get("event_id") or "") == trigger_id), None)
            source = dict((event or {}).get("source_ref") or {})
            record_id = str(source.get("record_id") or "")
            source_hash = str(source.get("source_hash") or "").casefold()
            case_root = active_case_root()
            row = next((item for item in load_case_search_records(case_root) if str(item.get("evidence_id") or item.get("source_id") or "").casefold() == record_id.casefold()), None) if case_root is not None else None
            if row is None or str(row.get("source_hash") or row.get("sha256") or "").casefold() != source_hash:
                raise IntakeWorkbenchError("deadline_dependency_trigger_not_in_active_matter", 404)
            return store.calculate_dependency(payload)
        return _intake_call(create)

    @app.get("/api/calendar/deadline-dependencies/{dependency_id}")
    def calendar_deadline_dependency_get(dependency_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _calendar_store().dependency(dependency_id))

    @app.get("/api/calendar/deadline-dependencies/{dependency_id}/trigger-source")
    def calendar_deadline_dependency_trigger_source(dependency_id: str) -> dict[str, Any]:
        """Return a short-lived, matter-scoped capability for the active trigger record."""
        def resolve() -> dict[str, Any]:
            case_root = active_case_root()
            if case_root is None:
                raise IntakeWorkbenchError("no_active_matter", 409)
            graph = _calendar_store().dependency(dependency_id)
            candidate = dict(graph.get("active_candidate") or {})
            trigger_id = str(candidate.get("trigger_event") or "")
            event = next(
                (item for item in _calendar_store().inventory().get("events", []) if str(item.get("event_id") or "") == trigger_id),
                None,
            )
            source = dict((event or {}).get("source_ref") or {})
            record_id = str(source.get("record_id") or "")
            source_hash = str(source.get("source_hash") or "").casefold()
            row = next(
                (
                    item
                    for item in load_case_search_records(case_root)
                    if str(item.get("evidence_id") or item.get("source_id") or "").casefold() == record_id.casefold()
                ),
                None,
            )
            if (
                row is None
                or not re.fullmatch(r"[a-f0-9]{64}", source_hash)
                or str(row.get("source_hash") or row.get("sha256") or "").casefold() != source_hash
            ):
                raise IntakeWorkbenchError("deadline_dependency_trigger_not_in_active_matter", 404)
            locator = str(row.get("source_locator") or row.get("title") or record_id)
            return {
                "dependency_id": graph["dependency_id"],
                "candidate_id": str(candidate.get("candidate_id") or ""),
                "source": {
                    "record_id": record_id,
                    "source_hash": source_hash,
                    "page": max(0, int(source.get("page") or 0)),
                    "source_token": _record_open_token(case_root, record_id, locator),
                },
                "review_required": True,
                "filing_ready": False,
            }

        return _intake_call(resolve)

    @app.get("/api/calendar/receipt")
    def calendar_receipt() -> dict[str, Any]:
        return _intake_call(lambda: _calendar_store().receipt())

    @app.post("/api/calendar/ics-export")
    def calendar_ics_export(payload: dict[str, Any], request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="comment")
        return _intake_call(lambda: _calendar_store().ics_export(payload))

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

    @app.post("/api/exhibits/admission-checklists")
    def exhibit_admission_checklist(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _exhibit_store().create_admission_checklist(payload))

    @app.get("/api/exhibits/admission-checklists/{checklist_id}")
    def exhibit_admission_checklist_get(checklist_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _exhibit_store().admission_checklist(checklist_id))

    @app.get("/api/exhibits/admission-checklists/{checklist_id}/source")
    def exhibit_admission_checklist_source(checklist_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _exhibit_store().admission_checklist_source(checklist_id))

    @app.post("/api/exhibits/custody-events")
    def exhibit_custody_event(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _exhibit_store().record_custody_event(payload))

    @app.get("/api/exhibits/custody-events/verify")
    def exhibit_custody_verify() -> dict[str, Any]:
        return _intake_call(lambda: _exhibit_store().verify_custody_chain())

    @app.get("/api/exhibits/custody-events/{event_id}")
    def exhibit_custody_event_get(event_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _exhibit_store().custody_event(event_id))

    @app.get("/api/exhibits/custody-events/{event_id}/source")
    def exhibit_custody_event_source(event_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _exhibit_store().custody_event_source(event_id))

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

    def _fact_pin_store() -> FactPinStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return FactPinStore(root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/fact-pins/inventory")
    def fact_pin_inventory() -> dict[str, Any]:
        return _intake_call(lambda: _fact_pin_store().inventory())

    @app.post("/api/fact-pins")
    def fact_pin_add(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _fact_pin_store().add(payload))

    @app.get("/api/fact-pins/receipt")
    def fact_pin_receipt() -> dict[str, Any]:
        return _intake_call(lambda: _fact_pin_store().receipt())

    @app.get("/api/fact-pins/{pin_id}")
    def fact_pin_get(pin_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _fact_pin_store().get(pin_id))

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

    @app.post("/api/parenting-schedule/simulations-v2")
    def schedule_simulation_v2(payload: dict[str, Any]) -> dict[str, Any]:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        return _intake_call(lambda: _schedule_store().simulate_v2(payload, records=_review_records(root)))

    @app.get("/api/parenting-schedule/simulations-v2/{simulation_id}")
    def schedule_simulation_v2_get(simulation_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _schedule_store().simulation_v2(simulation_id))

    @app.get("/api/parenting-schedule/simulations-v2/{simulation_id}/sources/{record_id}")
    def schedule_simulation_v2_source(simulation_id: str, record_id: str) -> dict[str, Any]:
        def resolve() -> dict[str, Any]:
            case_root = active_case_root()
            if case_root is None:
                raise IntakeWorkbenchError("no_active_matter", 409)
            payload = _schedule_store().simulation_v2_source(simulation_id, record_id)
            source = dict(payload.get("source") or {})
            source_hash = str(source.get("source_hash") or "").casefold()
            row = next(
                (item for item in _review_records(case_root) if str(item.get("evidence_id") or item.get("source_id") or "") == str(source.get("record_id") or "")),
                None,
            )
            if row is None or not re.fullmatch(r"[a-f0-9]{64}", source_hash) or str(row.get("source_hash") or row.get("sha256") or "").casefold() != source_hash:
                raise IntakeWorkbenchError("schedule_simulation_source_not_in_active_matter", 404)
            locator = str(row.get("source_locator") or row.get("title") or source["record_id"])
            source["source_token"] = _record_open_token(case_root, str(source["record_id"]), locator)
            return {**payload, "source": source}

        return _intake_call(resolve)

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

    @app.post("/api/email-integrity/handoff-package")
    def email_handoff_package(payload: dict[str, Any], request: Request) -> dict[str, Any]:
        """Build a local review package only; this endpoint never delivers email."""
        _require_reviewer_bundle_role(request, action="export")
        return _intake_call(lambda: _email_store().build_handoff_package(payload))

    def _archival_pdf_store() -> ArchivalPdfExportStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return ArchivalPdfExportStore(root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/archival-pdf/exports")
    def archival_pdf_inventory(request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="source")
        return _intake_call(lambda: _archival_pdf_store().inventory())

    @app.post("/api/archival-pdf/exports")
    def archival_pdf_create(payload: dict[str, Any], request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="export")
        return _intake_call(lambda: _archival_pdf_store().create(payload))

    def _structured_evidence_export_store() -> StructuredEvidenceExportStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return StructuredEvidenceExportStore(root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/evidence-exports/structured")
    def structured_evidence_export_inventory(request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="source")
        return _intake_call(lambda: _structured_evidence_export_store().inventory())

    @app.post("/api/evidence-exports/structured")
    def structured_evidence_export_create(payload: dict[str, Any], request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="export")
        return _intake_call(lambda: _structured_evidence_export_store().create(payload))

    def _print_review_store() -> PrintReviewStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return PrintReviewStore(root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/print-review/previews")
    def print_review_inventory(request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="source")
        return _intake_call(lambda: _print_review_store().inventory())

    @app.post("/api/print-review/previews")
    def print_review_create(payload: dict[str, Any], request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="export")
        return _intake_call(lambda: _print_review_store().create(payload))

    @app.get("/api/print-review/previews/{preview_id}")
    def print_review_get(preview_id: str, request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="source")
        return _intake_call(lambda: _print_review_store().get(preview_id))

    @app.post("/api/print-review/previews/{preview_id}/request-print")
    def print_review_request_print(preview_id: str, payload: dict[str, Any], request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="export")
        return _intake_call(lambda: _print_review_store().request_print(preview_id, payload))

    def _external_tool_boundary_store() -> ExternalToolBoundaryStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return ExternalToolBoundaryStore(root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/external-tool-boundaries")
    def external_tool_boundary_inventory(request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="source")
        return _intake_call(lambda: _external_tool_boundary_store().inventory())

    @app.post("/api/external-tool-boundaries")
    def external_tool_boundary_record(payload: dict[str, Any], request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="export")
        return _intake_call(lambda: _external_tool_boundary_store().record(payload))

    @app.get("/api/external-tool-boundaries/{receipt_id}")
    def external_tool_boundary_get(receipt_id: str, request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="source")
        return _intake_call(lambda: _external_tool_boundary_store().get(receipt_id))

    def _handoff_store() -> ReviewerHandoffStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return ReviewerHandoffStore(root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    def _require_reviewer_bundle_role(request: Request, *, action: str) -> str:
        """Apply the local role boundary before a reviewer-bundle mutation.

        The original manifest endpoint keeps its legacy local-desktop behavior
        for existing matters.  The round-trip endpoints are new and explicit:
        a viewer may inspect a source locator but cannot export, comment,
        attest, or reimport on behalf of a reviewer.
        """

        role = str(request.headers.get("X-User-Role") or "reviewer").strip().lower()
        allowed = {"admin", "attorney", "paralegal", "reviewer"}
        if action == "source":
            allowed.add("viewer")
        if role not in allowed:
            raise HTTPException(status_code=403, detail="reviewer_bundle_role_required")
        return role

    @app.get("/api/reviewer-handoff/inventory")
    def handoff_inventory() -> dict[str, Any]:
        return _intake_call(lambda: _handoff_store().inventory())

    @app.post("/api/reviewer-handoff")
    def handoff_add(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _handoff_store().add(payload))

    @app.get("/api/reviewer-handoff/receipt")
    def handoff_receipt() -> dict[str, Any]:
        return _intake_call(lambda: _handoff_store().receipt())

    @app.post("/api/reviewer-handoff/{handoff_id}/export")
    def handoff_export(handoff_id: str, payload: dict[str, Any], request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="export")
        return _intake_call(lambda: _handoff_store().export_bundle(handoff_id, payload))

    @app.post("/api/reviewer-handoff/{handoff_id}/comments")
    def handoff_comment(handoff_id: str, payload: dict[str, Any], request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="comment")
        return _intake_call(lambda: _handoff_store().add_comment(handoff_id, payload))

    @app.post("/api/reviewer-handoff/{handoff_id}/attest")
    def handoff_attest(handoff_id: str, payload: dict[str, Any], request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="attest")
        return _intake_call(lambda: _handoff_store().attest(handoff_id, payload))

    @app.post("/api/reviewer-handoff/{handoff_id}/reimport")
    def handoff_reimport(handoff_id: str, payload: dict[str, Any], request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="reimport")
        return _intake_call(lambda: _handoff_store().reimport(handoff_id, payload))

    @app.get("/api/reviewer-handoff/{handoff_id}/reconcile")
    def handoff_reconcile(handoff_id: str, request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="source")
        return _intake_call(lambda: _handoff_store().reconcile(handoff_id))

    @app.get("/api/reviewer-handoff/{handoff_id}/records/{record_id}/source")
    def handoff_record_source(handoff_id: str, record_id: str, request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="source")
        return _intake_call(lambda: _handoff_store().source_reference(handoff_id, record_id))

    def _structured_comment_store() -> StructuredCommentThreadStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return StructuredCommentThreadStore(root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/review-comments/inventory")
    def structured_comment_inventory(request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="source")
        return _intake_call(lambda: _structured_comment_store().inventory())

    @app.post("/api/review-comments/threads")
    def structured_comment_create(payload: dict[str, Any], request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="comment")
        return _intake_call(lambda: _structured_comment_store().create_thread(payload))

    @app.get("/api/review-comments/threads/{thread_id}")
    def structured_comment_get(thread_id: str, request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="source")
        return _intake_call(lambda: _structured_comment_store().get(thread_id))

    @app.post("/api/review-comments/threads/{thread_id}/comments")
    def structured_comment_add(thread_id: str, payload: dict[str, Any], request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="comment")
        return _intake_call(lambda: _structured_comment_store().add_comment(thread_id, payload))

    @app.post("/api/review-comments/threads/{thread_id}/resolve")
    def structured_comment_resolve(thread_id: str, payload: dict[str, Any], request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="comment")
        return _intake_call(lambda: _structured_comment_store().resolve(thread_id, payload))

    def _review_assignment_store() -> ReviewAssignmentStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        try:
            return ReviewAssignmentStore(root)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/review-assignments")
    def review_assignments(request: Request, include_completed: bool = False) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="source")
        return _intake_call(lambda: _review_assignment_store().inventory(include_completed=include_completed))

    @app.post("/api/review-assignments")
    def review_assignment_create(payload: dict[str, Any], request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="comment")
        return _intake_call(lambda: _review_assignment_store().create(payload))

    @app.get("/api/review-assignments/{assignment_id}")
    def review_assignment_get(assignment_id: str, request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="source")
        return _intake_call(lambda: _review_assignment_store().get(assignment_id))

    @app.post("/api/review-assignments/{assignment_id}/claim")
    def review_assignment_claim(assignment_id: str, payload: dict[str, Any], request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="comment")
        return _intake_call(lambda: _review_assignment_store().claim(assignment_id, payload))

    @app.post("/api/review-assignments/{assignment_id}/complete")
    def review_assignment_complete(assignment_id: str, payload: dict[str, Any], request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="comment")
        return _intake_call(lambda: _review_assignment_store().complete(assignment_id, payload))

    def _bundle_merge_store() -> BundleMergeStore:
        root = active_case_root()
        if root is None: raise HTTPException(status_code=409, detail="no_active_matter")
        try: return BundleMergeStore(root)
        except IntakeWorkbenchError as exc: raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/bundle-merges")
    def bundle_merges(request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="source"); return _intake_call(lambda: _bundle_merge_store().inventory())

    @app.post("/api/bundle-merges")
    def bundle_merge_create(payload: dict[str, Any], request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="comment"); return _intake_call(lambda: _bundle_merge_store().create(payload))

    @app.get("/api/bundle-merges/{merge_id}")
    def bundle_merge_get(merge_id: str, request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="source"); return _intake_call(lambda: _bundle_merge_store().get(merge_id))

    @app.post("/api/bundle-merges/{merge_id}/resolve")
    def bundle_merge_resolve(merge_id: str, payload: dict[str, Any], request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="comment"); return _intake_call(lambda: _bundle_merge_store().resolve(merge_id, payload))

    @app.post("/api/bundle-merges/{merge_id}/finalize")
    def bundle_merge_finalize(merge_id: str, payload: dict[str, Any], request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="comment"); return _intake_call(lambda: _bundle_merge_store().finalize(merge_id, payload))

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

    def _resolve_record_capability(
        token: str,
        page: int = 0,
        *,
        expected_action: str = "record_inspect",
    ) -> dict[str, Any]:
        """Resolve an opaque token to a verified active-corpus file or member."""

        token = str(token or "").strip().lower()
        if not re.fullmatch(r"[a-f0-9]{64}", token):
            raise HTTPException(status_code=404, detail="record_open_not_available")
        if expected_action not in _RECORD_CAPABILITY_ACTIONS:
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
        identity = dict(_record_capability_identity.get())
        if (
            binding.get("resource_type") != "matter_record"
            or str(binding.get("resource_id") or "") != str(binding.get("evidence_id") or "")
            or expected_action not in set(binding.get("allowed_actions") or [])
            or any(
                str(binding.get(key) or "") != str(identity.get(key) or "")
                for key in ("role", "tenant_id", "client_session_id")
            )
        ):
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
            page = max(1, page)
            # Unknown counts are supplied by the timed raster worker. Do not
            # parse an untrusted PDF in the API merely to prepare its metadata.
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
            "source_hash": str(resolved.get("source_hash") or "").casefold(),
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
            "preview_url": f"/api/records/preview/{resolved['token']}{query}" if viewer_kind == "pdf" else "",
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
                **_artifact_capability_binding(
                    resource_type="document_intelligence_artifact",
                    resource_id=actual,
                ),
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
                **_artifact_capability_binding(
                    resource_type="document_intelligence_artifact",
                    resource_id=str(record_id or row.get("sha256") or token),
                ),
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
        resolved = _resolve_record_capability(
            source_token, 0, expected_action="record_document_intelligence"
        )
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
            _record_open_token(case_root, evidence_id, locator),
            int(row.get("page_number") or 0),
            expected_action="record_inspect",
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
        if (
            case_root is None
            or not binding
            or binding.get("case_id") != _case_id(case_root)
            or not _artifact_capability_allowed(
                binding,
                resource_type="document_intelligence_artifact",
                expected_action="artifact_receipt",
            )
        ):
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
        if (
            case_root is None
            or not binding
            or binding.get("case_id") != _case_id(case_root)
            or not _artifact_capability_allowed(
                binding, resource_type="document_intelligence_artifact"
            )
        ):
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

    @app.post("/api/records/{record_id}/safe-review-copy")
    def record_document_safe_review_copy(
        record_id: str, payload: DocumentIntelligenceContentDisarmRequest
    ) -> dict[str, Any]:
        if payload.approved is not True:
            raise HTTPException(status_code=409, detail="content_disarm_consent_required")
        case_root, _rows, row = _resolve_record_rows(record_id)
        resolved = _record_capability_for_row(case_root, row)
        supplied = _document_intelligence_input(payload.source_token)
        if (
            Path(supplied["case_root"]).resolve() != case_root.resolve()
            or str(supplied["source_hash"]) != str(resolved["source_hash"])
        ):
            raise HTTPException(status_code=403, detail="record_source_capability_mismatch")
        try:
            result = create_content_disarm_copy(
                case_root=case_root,
                source_path=Path(resolved["path"]),
                source_hash=str(resolved["source_hash"]),
                approved=True,
                reviewer=str(payload.reviewer or "local_operator"),
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
        output["local_only"] = True
        output["review_required"] = True
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
        return _record_inspection_payload(
            _resolve_record_capability(token, page, expected_action="record_inspect")
        )

    @app.get("/api/records/preview/{token}")
    def preview_record_pdf(token: str, request: Request, page: int = 1) -> Response:
        from legal.document_intelligence.pdf_preview import PdfPreviewError, render_pdf_preview

        # Explicit identity for audited access; never let an image URL alone
        # bypass session, role, active matter, expiry or original hash checks.
        identity = _require_local_dashboard_identity(request)
        resolved = _resolve_record_capability(token, page, expected_action="record_inspect")
        if str(resolved["suffix"]).lower() != ".pdf":
            raise HTTPException(status_code=415, detail="record_preview_pdf_required")
        recorded_hash = str(resolved["root"].get("source_hash") or "").lower()
        if not re.fullmatch(r"[a-f0-9]{64}", recorded_hash) or recorded_hash != resolved["source_hash"]:
            raise HTTPException(status_code=409, detail="record_preview_source_hash_required")
        # LocalAgentAuditStore resolves the standard per-user OS-protected
        # vault when no explicit key is configured. Never require a QA-only
        # environment secret or bypass that managed key provider.
        case_root = Path(resolved["case_root"])
        # Do not follow redirected audit sidecars outside this matter.
        for relative in ("40_RUNTIME", "40_RUNTIME/local-agent", "40_RUNTIME/local-agent/audit.json.enc", "40_RUNTIME/local-agent/.audit.lock"):
            if (case_root / relative).is_symlink():
                raise HTTPException(status_code=409, detail="record_preview_audit_unsafe")
        try:
            raster = render_pdf_preview(bytes(resolved["data"]), page)
            # Rendering may be slow: revalidate source and active matter before
            # releasing any bytes or writing an access receipt.
            current = _resolve_record_capability(token, page, expected_action="record_inspect")
            if current["source_hash"] != recorded_hash or str(current["root"].get("source_hash") or "").lower() != recorded_hash:
                raise HTTPException(status_code=409, detail="record_open_source_hash_mismatch")
            scope = {**identity, "matter_id": _case_id(case_root)}
            receipt = _local_agent_audit_store(case_root).record(
                "record_pdf_preview", scope=scope,
                binding_sha256=local_agent_digest({"source_sha256": resolved["source_hash"], "page": page}),
                receipt_sha256=local_agent_digest({name: value for name, value in raster.items() if name != "data"}),
            )
        except PdfPreviewError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=503, detail="record_preview_audit_unavailable") from None
        return Response(content=raster["data"], media_type="image/png", headers={
            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "X-MFL-Hash-Verified": "true", "X-MFL-Source-Hash": resolved["source_hash"],
            "X-MFL-Preview-Hash": raster["sha256"], "X-MFL-Page": str(page),
            "X-MFL-Page-Count": str(raster["page_count"]), "X-MFL-Review-Required": "true",
            "X-MFL-Audit-Receipt": receipt["event_sha256"],
        })

    @app.get("/api/records/open/{token}")
    def open_record(token: str, page: int = 0, download: bool = False):  # type: ignore[no-untyped-def]
        """Open or download a hash-verified active-corpus source without exposing paths."""
        resolved = _resolve_record_capability(token, page, expected_action="record_open")
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

    def _assert_workspace_delete_allowed(case_root: Path, document_id: str) -> None:
        """Block document-workspace deletion when an active legal hold exists."""

        try:
            result = LegalHoldStore().deletion_check(
                matter_scope=_case_id(case_root), artifact_id=document_id
            )
        except LegalHoldError:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "legal_hold_check_unavailable",
                    "message": "Deletion was preserved because legal-hold status could not be verified.",
                    "review_required": True,
                },
            ) from None
        if not result["allowed"]:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "legal_hold_active",
                    "message": "This document is preserved by an active legal hold. No deletion request or deletion was performed.",
                    "affected_scope": "active_matter_document",
                    "review_required": True,
                },
            )

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
            case_root = _workspace_case_root()
            _assert_workspace_delete_allowed(case_root, document_id)
            return request_soft_delete(case_root, document_id)
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)

    @app.post("/api/document-workspace/documents/{document_id}/delete")
    def document_workspace_delete(
        document_id: str,
        payload: WorkspaceDeleteCommitRequest,
    ) -> dict[str, Any]:
        try:
            case_root = _workspace_case_root()
            _assert_workspace_delete_allowed(case_root, document_id)
            return commit_soft_delete(
                case_root,
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
            resolved = _resolve_record_capability(
                payload.source_token,
                payload.page,
                expected_action="record_workspace_import",
            )
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

    @app.post("/api/document-workspace/documents/{document_id}/export-sessions")
    def document_workspace_export_session(
        document_id: str, format: str = "txt"
    ) -> dict[str, Any]:  # type: ignore[no-untyped-def,redefined-builtin]
        """Mint an opaque local-session capability before exporting a draft."""

        try:
            case_root = _workspace_case_root()
            requested = str(format or "txt").lower()
            if requested not in {"txt", "md", "docx"}:
                raise DocumentWorkspaceError(
                    "unsupported_export_format",
                    "Supported export formats are txt, md, and docx.",
                )
            document = get_workspace_document(case_root, document_id)
            token = secrets.token_hex(32)
            _prune_document_workspace_artifacts()
            with _document_workspace_artifact_lock:
                _document_workspace_artifacts[token] = {
                    "case_id": _case_id(case_root),
                    **_artifact_capability_binding(
                        resource_type="document_workspace_export",
                        resource_id=f"{document_id}:{requested}:{token}",
                        allowed_actions={"artifact_download"},
                    ),
                    "document_id": str(document["document_id"]),
                    "format": requested,
                    "created_at": time.time(),
                }
            return {
                "status": "export_session_ready",
                "download_url": f"/api/document-workspace/exports/{token}",
                "review_required": True,
                "filing_ready": False,
            }
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)

    @app.get("/api/document-workspace/exports/{token}")
    def document_workspace_export(token: str):  # type: ignore[no-untyped-def]
        try:
            token = str(token or "").strip().lower()
            if not re.fullmatch(r"[a-f0-9]{64}", token):
                raise DocumentWorkspaceError(
                    "artifact_not_found", "The artifact was not found.", status_code=404
                )
            _prune_document_workspace_artifacts()
            case_root = _workspace_case_root()
            with _document_workspace_artifact_lock:
                binding = dict(_document_workspace_artifacts.get(token) or {})
            if (
                not binding
                or binding.get("case_id") != _case_id(case_root)
                or not _artifact_capability_allowed(
                    binding, resource_type="document_workspace_export"
                )
            ):
                raise DocumentWorkspaceError(
                    "artifact_not_found", "The artifact was not found.", status_code=404
                )
            document_id = str(binding.get("document_id") or "")
            requested = str(binding.get("format") or "").lower()
            if requested not in {"txt", "md", "docx"} or not document_id:
                raise DocumentWorkspaceError(
                    "artifact_not_found", "The artifact was not found.", status_code=404
                )
            document = get_workspace_document(case_root, document_id)
            gate_headers = _document_workspace_filing_gate_headers(case_root, document_id)
            provenance = ExportProvenanceStore(case_root)
            receipt = provenance.start(document, product_version=__version__, format_name=requested)
            footer = str(receipt.get("footer_text") or "")
            if requested in {"txt", "md"}:
                path = export_text_artifact(case_root, document_id, format_name=requested, provenance_footer=footer)
            elif requested == "docx":
                paths = workspace_paths(case_root)
                slug = (
                    re.sub(r"[^A-Za-z0-9._-]+", "-", str(document["title"])).strip("-.")[:80]
                    or "document"
                )
                path = paths.exports / f"{slug}-{str(document['current_revision_id'])[:8]}.docx"
                result = create_docx_from_text(
                    title=str(document["title"]),
                    content=f"{str(document.get('content') or '').rstrip()}\n\n{footer}",
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
                    provenance_receipt_id=str(receipt["receipt_id"]),
                )
            completed_receipt = provenance.complete(
                str(receipt["receipt_id"]),
                artifact_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                size_bytes=path.stat().st_size,
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
                    "X-MFLL-Export-Provenance-Receipt": str(completed_receipt["receipt_id"]),
                    "X-MFLL-Export-Review-State": "review_required_not_filing_ready",
                    **gate_headers,
                },
            )
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=int(exc.status_code), detail=exc.code) from None

    @app.get("/api/document-workspace/documents/{document_id}/export-provenance")
    def document_workspace_export_provenance(document_id: str) -> dict[str, Any]:
        try:
            case_root = _workspace_case_root()
            document = get_workspace_document(case_root, document_id)
            return ExportProvenanceStore(case_root).receipts(str(document.get("document_id") or document_id))
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=int(exc.status_code), detail=exc.code) from None

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
                **_artifact_capability_binding(
                    resource_type="evidence_work_product_artifact",
                    resource_id=f"{build_id}:{Path(filename).name}",
                ),
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
        if (
            case_root is None
            or not binding
            or binding.get("case_id") != _case_id(case_root)
            or not _artifact_capability_allowed(
                binding, resource_type="evidence_work_product_artifact"
            )
        ):
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

    @app.get("/api/matters/{matter_id}/command-center/health-history")
    def matter_command_center_health_history(matter_id: str) -> dict[str, Any]:
        try:
            return _matter_command_center_store().health_history(matter_id)
        except MatterCommandCenterError as exc:
            _raise_matter_command_center_error(exc)

    @app.get("/api/matters/{matter_id}/command-center/records/{record_id}/source")
    def matter_command_center_record_source(matter_id: str, record_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        row = next(
            (
                item
                for item in _matter_command_center_records()
                if str(item.get("evidence_id") or "") == str(record_id or "")
            ),
            None,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="command_center_record_not_found_in_active_matter")
        source_hash = str(row.get("source_hash") or row.get("sha256") or "").lower()
        if len(source_hash) != 64:
            raise HTTPException(status_code=409, detail="command_center_record_source_hash_unavailable")
        locator = str(row.get("source_locator") or row.get("title") or record_id)
        return {
            "status": "pass",
            "matter_id": str(matter_id or "")[:240],
            "source": {
                "record_id": str(record_id or "")[:256],
                "source_hash": source_hash,
                "page_number": max(0, int(row.get("page_number") or 0)),
                "source_token": _record_open_token(case_root, str(record_id), locator),
            },
            "review_required": True,
        }

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
        detail = str(exc.args[0]) if isinstance(exc, KeyError) and exc.args else (str(exc) or exc.__class__.__name__)
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
            return _review_store(case_root).create_event(
                payload.model_dump(), records=_review_records(case_root)
            )
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
            return _review_store(case_root).patch_event(
                event_id, data, records=_review_records(case_root)
            )
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

    @app.get("/api/timeline/events/{event_id}/source")
    def timeline_event_source(event_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            event = _review_store(case_root).get_event_history(event_id).get("event") or {}
            source_record_id = str(event.get("source_record_id") or "")
            source_hash = str(event.get("source_hash") or "").lower()
            if not source_record_id or not source_hash:
                raise ValueError("event_source_binding_required")
            row = next(
                (
                    item
                    for item in _review_records(case_root)
                    if str(item.get("evidence_id") or "") == source_record_id
                ),
                None,
            )
            if row is None:
                raise ValueError("event_source_record_not_found_in_active_matter")
            if str(row.get("source_hash") or "").lower() != source_hash:
                raise ValueError("event_source_hash_mismatch")
            locator = str(row.get("source_locator") or row.get("title") or source_record_id)
            return {
                "status": "pass",
                "event_id": event_id,
                "source": {
                    "record_id": source_record_id,
                    "source_hash": source_hash,
                    "source_block": event.get("source_block") or {},
                    "source_token": _record_open_token(case_root, source_record_id, locator),
                },
                "review_required": True,
            }
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

    @app.get("/api/evidence/claims/{claim_id}/cards/{card_kind}/{card_index}/source")
    def evidence_claim_card_source(
        claim_id: str, card_kind: str, card_index: int
    ) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            card = _review_store(case_root).get_claim_source_card(
                claim_id, card_kind, card_index
            )
            record_id = str(card["record_id"])
            source_hash = str(card["source_hash"]).lower()
            row = next(
                (
                    item
                    for item in _review_records(case_root)
                    if str(item.get("evidence_id") or "") == record_id
                ),
                None,
            )
            if row is None:
                raise ValueError("claim_source_record_not_found_in_active_matter")
            if str(row.get("source_hash") or "").lower() != source_hash:
                raise ValueError("claim_source_hash_mismatch")
            locator = str(row.get("source_locator") or row.get("title") or record_id)
            return {
                **card,
                "source": {
                    "record_id": record_id,
                    "source_hash": source_hash,
                    "source_span": card["card"].get("source_span") or {},
                    "source_token": _record_open_token(case_root, record_id, locator),
                },
                "review_required": True,
            }
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.post("/api/evidence/attachment-coverage")
    def evidence_attachment_coverage_create(
        payload: AttachmentCoverageCreateRequest,
    ) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).create_attachment_coverage(
                payload.model_dump(), records=_review_records(case_root)
            )
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.get("/api/evidence/attachment-coverage")
    def evidence_attachment_coverage_list() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).attachment_coverage()
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.get("/api/evidence/attachment-coverage/{attachment_id}")
    def evidence_attachment_coverage_get(attachment_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).attachment_coverage(attachment_id)
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.post("/api/evidence/attachment-coverage/{attachment_id}/review")
    def evidence_attachment_coverage_review(
        attachment_id: str, payload: AttachmentCoverageReviewRequest
    ) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).review_attachment_coverage(
                attachment_id, payload.model_dump(), records=_review_records(case_root)
            )
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.get("/api/evidence/attachment-coverage/{attachment_id}/source")
    def evidence_attachment_coverage_source(attachment_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            item = _review_store(case_root).attachment_coverage(attachment_id).get("attachment") or {}
            record_id = str(item.get("source_record_id") or "")
            source_hash = str(item.get("source_hash") or "").lower()
            row = next((entry for entry in _review_records(case_root) if str(entry.get("evidence_id") or "") == record_id), None)
            if row is None:
                raise ValueError("attachment_source_record_not_found_in_active_matter")
            if not source_hash or str(row.get("source_hash") or "").lower() != source_hash:
                raise ValueError("attachment_source_hash_mismatch")
            locator = str(row.get("source_locator") or row.get("title") or record_id)
            return {
                "status": "pass",
                "attachment_id": attachment_id,
                "source": {
                    "record_id": record_id,
                    "source_hash": source_hash,
                    "source_block": item.get("source_block") or {},
                    "source_token": _record_open_token(case_root, record_id, locator),
                },
                "review_required": True,
            }
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.get("/api/evidence/fact-graph")
    def evidence_fact_graph() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        return _review_store(case_root).fact_graph()

    @app.post("/api/evidence/fact-graph/nodes")
    def evidence_fact_graph_node(payload: FactGraphNodeRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).create_fact_graph_node(payload.model_dump(), records=_review_records(case_root))
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.post("/api/evidence/fact-graph/edges")
    def evidence_fact_graph_edge(payload: FactGraphEdgeRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).create_fact_graph_edge(payload.model_dump(), records=_review_records(case_root))
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.get("/api/evidence/fact-graph/{entity_kind}/{entity_id}/source")
    def evidence_fact_graph_source(entity_kind: str, entity_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        if entity_kind not in {"nodes", "edges"}:
            raise HTTPException(status_code=400, detail="fact_graph_entity_kind_invalid")
        try:
            entity = _review_store(case_root).fact_graph_source(entity_kind, entity_id).get("entity") or {}
            record_id = str(entity.get("source_record_id") or "")
            source_hash = str(entity.get("source_hash") or "").lower()
            row = next((entry for entry in _review_records(case_root) if str(entry.get("evidence_id") or "") == record_id), None)
            if row is None:
                raise ValueError("fact_graph_source_record_not_found_in_active_matter")
            if not source_hash or str(row.get("source_hash") or "").lower() != source_hash:
                raise ValueError("fact_graph_source_hash_mismatch")
            locator = str(row.get("source_locator") or row.get("title") or record_id)
            return {"status": "pass", "entity_kind": entity_kind, "entity_id": entity_id, "source": {"record_id": record_id, "source_hash": source_hash, "source_block": entity.get("source_block") or {}, "source_token": _record_open_token(case_root, record_id, locator)}, "review_required": True}
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.post("/api/evidence/issue-proof-matrix/items")
    def evidence_issue_proof_matrix_create(
        payload: IssueProofMatrixCreateRequest,
    ) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).create_issue_proof_item(
                payload.model_dump(), records=_review_records(case_root)
            )
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.get("/api/evidence/issue-proof-matrix")
    def evidence_issue_proof_matrix_list() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).issue_proof_matrix()
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.get("/api/evidence/issue-proof-matrix/items/{item_id}")
    def evidence_issue_proof_matrix_get(item_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).issue_proof_matrix(item_id)
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.post("/api/evidence/issue-proof-matrix/items/{item_id}/review")
    def evidence_issue_proof_matrix_review(
        item_id: str, payload: IssueProofMatrixReviewRequest
    ) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).review_issue_proof_item(
                item_id, payload.model_dump(), records=_review_records(case_root)
            )
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.get("/api/evidence/issue-proof-matrix/items/{item_id}/source")
    def evidence_issue_proof_matrix_source(item_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            item = _review_store(case_root).issue_proof_matrix_source(item_id).get("item") or {}
            record_id = str(item.get("source_record_id") or "")
            source_hash = str(item.get("source_hash") or "").lower()
            row = next((entry for entry in _review_records(case_root) if str(entry.get("evidence_id") or "") == record_id), None)
            if row is None:
                raise ValueError("issue_proof_source_record_not_found_in_active_matter")
            if not source_hash or str(row.get("source_hash") or "").lower() != source_hash:
                raise ValueError("issue_proof_source_hash_mismatch")
            locator = str(row.get("source_locator") or row.get("title") or record_id)
            return {"status": "pass", "item_id": item_id, "source": {"record_id": record_id, "source_hash": source_hash, "source_block": item.get("source_block") or {}, "source_token": _record_open_token(case_root, record_id, locator)}, "review_required": True}
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.post("/api/evidence/matter-change-digest/checkpoints")
    def evidence_matter_change_digest_checkpoint(
        payload: MatterChangeDigestCheckpointRequest,
    ) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).create_change_digest_checkpoint(
                payload.model_dump(), records=_review_records(case_root)
            )
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.get("/api/evidence/matter-change-digest/checkpoints")
    def evidence_matter_change_digest_checkpoints() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        return _review_store(case_root).change_digest_checkpoints()

    @app.post("/api/evidence/matter-change-digest/{checkpoint_id}/generate")
    def evidence_matter_change_digest_generate(checkpoint_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).matter_change_digest(
                checkpoint_id, records=_review_records(case_root)
            )
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.get("/api/evidence/matter-change-digest/{checkpoint_id}/records/{record_id}/source")
    def evidence_matter_change_digest_record_source(
        checkpoint_id: str, record_id: str
    ) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            binding = _review_store(case_root).change_digest_record_source(
                checkpoint_id, record_id, records=_review_records(case_root)
            )
            row = next((entry for entry in _review_records(case_root) if str(entry.get("evidence_id") or "") == record_id), None)
            if row is None:
                raise ValueError("change_digest_source_record_not_found_in_active_matter")
            if str(row.get("source_hash") or "").lower() != str(binding.get("source_hash") or "").lower():
                raise ValueError("change_digest_source_hash_mismatch")
            locator = str(row.get("source_locator") or row.get("title") or record_id)
            return {"status": "pass", "checkpoint_id": checkpoint_id, "source": {"record_id": record_id, "source_hash": binding["source_hash"], "source_token": _record_open_token(case_root, record_id, locator)}, "review_required": True}
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.post("/api/evidence/record-lineage/links")
    def evidence_record_lineage_create(payload: RecordLineageCreateRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).create_record_lineage_link(
                payload.model_dump(), records=_review_records(case_root)
            )
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.get("/api/evidence/record-lineage")
    def evidence_record_lineage_list() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        return _review_store(case_root).record_lineage()

    @app.get("/api/evidence/record-lineage/links/{link_id}")
    def evidence_record_lineage_get(link_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).record_lineage(link_id)
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.get("/api/evidence/record-lineage/links/{link_id}/{side}/source")
    def evidence_record_lineage_source(link_id: str, side: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            binding = _review_store(case_root).record_lineage_source(link_id, side).get("binding") or {}
            record_id = str(binding.get("record_id") or "")
            source_hash = str(binding.get("source_hash") or "").lower()
            row = next((entry for entry in _review_records(case_root) if str(entry.get("evidence_id") or "") == record_id), None)
            if row is None:
                raise ValueError("record_lineage_source_record_not_found_in_active_matter")
            if not source_hash or str(row.get("source_hash") or "").lower() != source_hash:
                raise ValueError("record_lineage_source_hash_mismatch")
            locator = str(row.get("source_locator") or row.get("title") or record_id)
            return {"status": "pass", "link_id": link_id, "side": side, "source": {"record_id": record_id, "source_hash": source_hash, "source_block": binding.get("source_block") or {}, "source_token": _record_open_token(case_root, record_id, locator)}, "review_required": True}
        except Exception as exc:
            _raise_evidence_review_error(exc)

    @app.post("/api/evidence/entity-resolution/candidates")
    def evidence_entity_resolution_create(payload: EntityResolutionCandidateRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None: raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try: return _review_store(case_root).create_entity_resolution_candidate(payload.model_dump(), records=_review_records(case_root))
        except Exception as exc: _raise_evidence_review_error(exc)

    @app.get("/api/evidence/entity-resolution")
    def evidence_entity_resolution_list() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None: raise HTTPException(status_code=404, detail="active_matter_unavailable")
        return _review_store(case_root).entity_resolution()

    @app.get("/api/evidence/entity-resolution/candidates/{candidate_id}")
    def evidence_entity_resolution_get(candidate_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None: raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try: return _review_store(case_root).entity_resolution(candidate_id)
        except Exception as exc: _raise_evidence_review_error(exc)

    @app.post("/api/evidence/entity-resolution/candidates/{candidate_id}/confirm")
    def evidence_entity_resolution_confirm(candidate_id: str, payload: EntityResolutionConfirmationRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None: raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try: return _review_store(case_root).confirm_entity_resolution(candidate_id, payload.model_dump(), records=_review_records(case_root))
        except Exception as exc: _raise_evidence_review_error(exc)

    @app.post("/api/evidence/entity-resolution/candidates/{candidate_id}/revoke")
    def evidence_entity_resolution_revoke(candidate_id: str, payload: EntityResolutionRevokeRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None: raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try: return _review_store(case_root).revoke_entity_resolution(candidate_id, payload.model_dump())
        except Exception as exc: _raise_evidence_review_error(exc)

    @app.get("/api/evidence/entity-resolution/candidates/{candidate_id}/{side}/source")
    def evidence_entity_resolution_source(candidate_id: str, side: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None: raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            binding = _review_store(case_root).entity_resolution_source(candidate_id, side).get("binding") or {}; record_id = str(binding.get("record_id") or ""); source_hash = str(binding.get("source_hash") or "").lower()
            row = next((entry for entry in _review_records(case_root) if str(entry.get("evidence_id") or "") == record_id), None)
            if row is None: raise ValueError("entity_resolution_source_record_not_found_in_active_matter")
            if not source_hash or str(row.get("source_hash") or "").lower() != source_hash: raise ValueError("entity_resolution_source_hash_mismatch")
            locator = str(row.get("source_locator") or row.get("title") or record_id)
            return {"status": "pass", "candidate_id": candidate_id, "side": side, "source": {"record_id": record_id, "source_hash": source_hash, "source_token": _record_open_token(case_root, record_id, locator)}, "review_required": True}
        except Exception as exc: _raise_evidence_review_error(exc)

    @app.get("/api/evidence/coverage")
    def evidence_coverage(selected_record_ids: str = "") -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        selected = [item.strip() for item in selected_record_ids.split(",") if item.strip()]
        return _review_store(case_root).coverage(
            records=_review_records(case_root, selected), selected_record_ids=selected
        )

    @app.get("/api/evidence/matter-completeness")
    def evidence_matter_completeness() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        return _review_store(case_root).matter_completeness(records=_review_records(case_root))

    @app.post("/api/evidence/watch-folder/scan")
    def evidence_watch_folder_scan(payload: WatchFolderScanRequest) -> dict[str, Any]:
        if active_case_root() is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return scan_watch_folder_candidates(payload.folder, limit=payload.limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    @app.post("/api/evidence/scanner-review/plan")
    def evidence_scanner_review_plan(payload: ScannerReviewRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).create_scanner_review_plan(
                payload.model_dump(), records=_review_records(case_root)
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
    @app.post("/api/evidence/handwriting-review")
    def evidence_handwriting_review(payload: HandwritingReviewRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).create_handwriting_review_routing(
                payload.model_dump(), records=_review_records(case_root)
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
    @app.post("/api/evidence/document-type-review")
    def evidence_document_type_review(payload: DocumentTypeReviewRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).create_document_type_review(
                payload.model_dump(), records=_review_records(case_root)
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
    @app.post("/api/evidence/page-quality-review")
    def evidence_page_quality_review(payload: PageQualityReviewRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).create_page_quality_review(
                payload.model_dump(), records=_review_records(case_root)
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
    @app.post("/api/evidence/table-lineage-review")
    def evidence_table_lineage_review(payload: TableLineageRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _review_store(case_root).create_table_lineage_review(
                payload.model_dump(), records=_review_records(case_root)
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    @app.post("/api/evidence/document-comparisons")
    def evidence_document_comparison_create(payload: DocumentComparisonCreateRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        rows = {str(row.get("evidence_id") or ""): row for row in _review_records(case_root)}
        left = rows.get(payload.left_record_id)
        right = rows.get(payload.right_record_id)
        if left is None or right is None:
            raise HTTPException(status_code=404, detail="document_comparison_record_not_found_in_active_matter")
        try:
            return DocumentComparisonStore(case_root).create(
                comparison_id=payload.comparison_id,
                left_record=left,
                right_record=right,
            )
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/evidence/document-comparisons")
    def evidence_document_comparison_list() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return DocumentComparisonStore(case_root).get()
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/evidence/document-comparisons/{comparison_id}")
    def evidence_document_comparison_get(comparison_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return DocumentComparisonStore(case_root).get(comparison_id)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/evidence/document-comparisons/{comparison_id}/source/{side}")
    def evidence_document_comparison_source(comparison_id: str, side: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            binding = DocumentComparisonStore(case_root).source_binding(comparison_id, side).get("binding") or {}
            record_id = str(binding.get("record_id") or "")
            source_hash = str(binding.get("source_hash") or "").lower()
            row = next((entry for entry in _review_records(case_root) if str(entry.get("evidence_id") or "") == record_id), None)
            if row is None:
                raise IntakeWorkbenchError("document_comparison_source_record_not_found_in_active_matter", 404)
            if str(row.get("source_hash") or "").lower() != source_hash:
                raise IntakeWorkbenchError("document_comparison_source_hash_mismatch", 409)
            locator = str(row.get("source_locator") or row.get("title") or record_id)
            return {
                "status": "pass",
                "comparison_id": comparison_id,
                "side": side,
                "source": {
                    "record_id": record_id,
                    "source_hash": source_hash,
                    "source_token": _record_open_token(case_root, record_id, locator),
                },
                "review_required": True,
            }
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.post("/api/evidence/metadata-review/batches")
    def evidence_metadata_review_apply(payload: MetadataReviewBatchRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return MetadataReviewStore(case_root).apply_batch(payload.model_dump(), records=_review_records(case_root))
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/evidence/metadata-review/batches")
    def evidence_metadata_review_list() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return MetadataReviewStore(case_root).inventory()
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/evidence/metadata-review/batches/{batch_id}/source/{record_id}")
    def evidence_metadata_review_source(batch_id: str, record_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            binding = MetadataReviewStore(case_root).source_binding(batch_id, record_id)
            row = next((entry for entry in _review_records(case_root) if str(entry.get("evidence_id") or "") == binding["record_id"]), None)
            if row is None:
                raise IntakeWorkbenchError("metadata_review_source_record_not_found_in_active_matter", 404)
            if str(row.get("source_hash") or "").lower() != binding["source_hash"]:
                raise IntakeWorkbenchError("metadata_review_source_hash_mismatch", 409)
            locator = str(row.get("source_locator") or row.get("title") or binding["record_id"])
            return {"status": "pass", "batch_id": batch_id, "source": {**binding, "source_token": _record_open_token(case_root, binding["record_id"], locator)}, "review_required": True}
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.post("/api/evidence/import-policy/profiles")
    def evidence_import_policy_create(payload: ImportPolicyProfileRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return ImportPolicyStore(case_root).create(payload.model_dump())
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

    @app.get("/api/evidence/import-policy/profiles")
    def evidence_import_policy_inventory() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return ImportPolicyStore(case_root).inventory()
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None

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
    def retrieval_workbench_evaluate(payload: RetrievalWorkbenchEvalRequest, request: Request) -> dict[str, Any]:
        _require_reviewer_bundle_role(request, action="source")
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
                    **_artifact_capability_binding(
                        resource_type="attorney_sandbox_operations_artifact",
                        resource_id=f"{generation_id}:{filename}",
                    ),
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
        if (
            not binding
            or binding.get("scope") != _sandbox_operations_scope(store)
            or not _artifact_capability_allowed(
                binding, resource_type="attorney_sandbox_operations_artifact"
            )
        ):
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
                    **_artifact_capability_binding(
                        resource_type="limited_real_matter_pilot_artifact",
                        resource_id=f"{generation_id}:{filename}",
                    ),
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
        if (
            not binding
            or binding.get("scope") != _real_matter_pilot_scope(store)
            or not _artifact_capability_allowed(
                binding, resource_type="limited_real_matter_pilot_artifact"
            )
        ):
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
                    **_artifact_capability_binding(
                        resource_type="ga_release_candidate_artifact",
                        resource_id=f"{generation_id}:{filename}",
                    ),
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
        if (
            not binding
            or binding.get("scope") != _ga_release_candidate_scope(store)
            or not _artifact_capability_allowed(
                binding, resource_type="ga_release_candidate_artifact"
            )
        ):
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
                    **_artifact_capability_binding(
                        resource_type="findings_form_artifact",
                        resource_id=f"{build_id}:{completion_id}:{name}",
                    ),
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

    def _guided_form_session_store(case_root: Path) -> GuidedFormSessionStore:
        return GuidedFormSessionStore(case_root)

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
            return _guided_form_session_store(case_root).get(session_id)
        except IntakeWorkbenchError as exc:
            if exc.code != "forms_session_not_found":
                raise HTTPException(status_code=int(exc.status_code), detail=exc.code) from None
        try:
            session = _load_json(_findings_session_path(case_root, session_id))
        except (FileNotFoundError, ValueError):
            raise HTTPException(status_code=404, detail="forms_session_not_found") from None
        if str(session.get("session_id") or "") != session_id:
            raise HTTPException(status_code=409, detail="forms_session_invalid") from None
        try:
            return _guided_form_session_store(case_root).create(session)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=int(exc.status_code), detail=exc.code) from None

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
        if (
            case_root is None
            or not binding
            or binding.get("case_id") != _case_id(case_root)
            or not _artifact_capability_allowed(binding, resource_type="findings_form_artifact")
        ):
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
        try:
            build = store.build_review(
                payload.document_id,
                authority_forms=forms,
                selected_form_ids=payload.selected_form_ids,
                posture=payload.proceeding_type or payload.posture,
                evidence_records=load_case_search_records(case_root),
                approved=payload.approved,
            )
        except MaineFindingsFormsError as exc:
            _raise_findings_forms_error(exc)
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
        try:
            session = _guided_form_session_store(case_root).create(session)
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=int(exc.status_code), detail=exc.code) from None
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

    @app.get("/api/forms/session/{session_id}")
    def forms_session_get(session_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        session = _session_payload(case_root, session_id)
        return {"status": "pass", "session": session, "review_required": True, "filing_ready": False}

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
        try:
            session = _guided_form_session_store(case_root).replace(session, action="patch_guided_form_session")
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=int(exc.status_code), detail=exc.code) from None
        return {"status": "pass", "session": session, "review_required": True, "filing_ready": False}

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
        try:
            result = MaineFindingsFormsStore(case_root).complete_forms(
                session["build_id"], form_values=merged_values, confirmed=True
            )
        except MaineFindingsFormsError as exc:
            _raise_findings_forms_error(exc)
        session["form_values"] = merged_values
        session["completion_id"] = result.get("completion_id") or ""
        session["updated_at"] = _utc_now()
        try:
            _guided_form_session_store(case_root).replace(session, action="validate_guided_form_session")
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=int(exc.status_code), detail=exc.code) from None
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
        try:
            result = MaineFindingsFormsStore(case_root).complete_forms(
                session["build_id"], form_values=merged_values, confirmed=True
            )
        except MaineFindingsFormsError as exc:
            _raise_findings_forms_error(exc)
        session["form_values"] = merged_values
        session["completion_id"] = result.get("completion_id") or ""
        session["updated_at"] = _utc_now()
        try:
            _guided_form_session_store(case_root).replace(session, action="generate_guided_form_session")
        except IntakeWorkbenchError as exc:
            raise HTTPException(status_code=int(exc.status_code), detail=exc.code) from None
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
                    **_artifact_capability_binding(
                        resource_type="reviewed_filing_packet_artifact",
                        resource_id=f"{build_id}:{name}",
                    ),
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
        if (
            case_root is None
            or not binding
            or binding.get("case_id") != _case_id(case_root)
            or not _artifact_capability_allowed(
                binding, resource_type="reviewed_filing_packet_artifact"
            )
        ):
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
                    **_artifact_capability_binding(
                        resource_type="authority_change_impact_artifact",
                        resource_id=f"{build_id}:{name}",
                    ),
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

    @app.post("/api/authority-change-impact/matter/analyze")
    def authority_change_impact_matter_analyze(payload: AuthorityImpactMatterRequest) -> dict[str, Any]:
        """Create a source-overlap revalidation queue for the active matter.

        This is deliberately an analysis-only path: it never decides that a
        rule, form, deadline, or legal conclusion changed because a source hash
        changed.  The durable access receipt contains no document prose.
        """
        try:
            case_root = _workspace_case_root()
            store = _authority_impact_store(case_root)
            result = store.analyze_matter(payload.base_build_id, payload.target_build_id)
            result["access_receipt"] = store.record_access(
                action="matter_impact_analyze",
                actor_role="local_owner",
                tenant_id="local",
                audit_event_id=secrets.token_hex(16),
            )
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
        if (
            case_root is None
            or not binding
            or binding.get("case_id") != _case_id(case_root)
            or not _artifact_capability_allowed(
                binding, resource_type="authority_change_impact_artifact"
            )
        ):
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
            _prune_document_workspace_artifacts()
            with _document_workspace_artifact_lock:
                _document_workspace_artifacts[artifact_id] = {
                    "case_id": _case_id(case_root),
                    **_artifact_capability_binding(
                        resource_type="document_workspace_tracked_edit_artifact",
                        resource_id=artifact_id,
                        allowed_actions={"artifact_download"},
                    ),
                    "document_id": str(document_id),
                    "revision_id": str(document["current_revision_id"]),
                    "filename": output.name,
                    "sha256": str(result["sha256"]),
                    "created_at": time.time(),
                }
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
            _prune_document_workspace_artifacts()
            case_root = _workspace_case_root()
            with _document_workspace_artifact_lock:
                binding = dict(_document_workspace_artifacts.get(artifact_id) or {})
            if (
                not binding
                or binding.get("case_id") != _case_id(case_root)
                or not _artifact_capability_allowed(
                    binding, resource_type="document_workspace_tracked_edit_artifact"
                )
            ):
                raise DocumentWorkspaceError(
                    "artifact_not_found", "The artifact was not found.", status_code=404
                )
            paths = workspace_paths(case_root)
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
            if (
                artifact.name != str(binding.get("filename") or "")
                or hashlib.sha256(artifact.read_bytes()).hexdigest()
                != str(binding.get("sha256") or "")
            ):
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

    @app.post("/api/conversation/context/compact")
    def compact_conversation_context(
        payload: ConversationContextCompactionRequest,
    ) -> dict[str, Any]:
        """Persist only a no-prose, matter-scoped conversation continuity receipt."""

        session_id, session_report = normalize_session_id(payload.session_id)
        expected_search_id, search_report = normalize_search_id(payload.expected_search_id)
        if not session_report["accepted"]:
            raise HTTPException(status_code=422, detail="conversation_session_required")
        if search_report["provided"] and not search_report["accepted"]:
            raise HTTPException(status_code=422, detail="invalid_search_identifier")
        matter_scope = _conversation_matter_scope()
        session_key = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
        with _recent_search_lock:
            _prune_recent_sources()
            entry = dict(_recent_record_searches.get(session_key) or {})
        if not entry:
            raise HTTPException(status_code=404, detail="conversation_context_unavailable")
        if str(entry.get("matter_scope") or "") != matter_scope:
            raise HTTPException(status_code=409, detail="conversation_context_matter_scope_mismatch")
        if expected_search_id and expected_search_id != str(entry.get("search_id") or ""):
            raise HTTPException(status_code=409, detail="conversation_context_stale_search")

        case_root = active_case_root()
        audit_status = "not_applicable_general_workspace"
        if case_root is not None:
            try:
                PrivacySafeObservabilityStore(case_root).record(
                    "api_request",
                    metrics={"count": 1, "result_count": len(entry.get("citations") or [])},
                    labels={
                        "component": "conversation",
                        "operation": "context_compaction",
                        "status": "ok",
                    },
                )
                audit_status = "privacy_safe_audit_recorded"
            except ReleasePilotHardeningError as exc:
                raise HTTPException(status_code=409, detail="conversation_context_audit_unavailable") from exc

        receipt = _context_compaction_receipt(
            session_id=session_id,
            entry=entry,
            matter_scope=matter_scope,
        )
        receipt["audit_status"] = audit_status
        with _recent_search_lock:
            current = dict(_recent_record_searches.get(session_key) or {})
            if not current or str(current.get("search_id") or "") != str(entry.get("search_id") or ""):
                raise HTTPException(status_code=409, detail="conversation_context_changed_retry")
            current["context_compaction"] = dict(receipt)
            _recent_record_searches[session_key] = current
        return receipt

    @app.get("/api/conversation/context/{session_id}")
    def inspect_conversation_context(session_id: str) -> dict[str, Any]:
        """Return the current safe receipt only when it belongs to this matter."""

        normalized, report = normalize_session_id(session_id)
        if not report["accepted"]:
            raise HTTPException(status_code=422, detail="conversation_session_required")
        session_key = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        with _recent_search_lock:
            _prune_recent_sources()
            entry = dict(_recent_record_searches.get(session_key) or {})
        receipt = dict(entry.get("context_compaction") or {})
        if not receipt:
            raise HTTPException(status_code=404, detail="conversation_context_not_compacted")
        if str(entry.get("matter_scope") or "") != _conversation_matter_scope():
            raise HTTPException(status_code=409, detail="conversation_context_matter_scope_mismatch")
        return receipt

    def _correction_verification_summary(text: str, citations: list[dict[str, Any]]) -> dict[str, Any]:
        """Expose verifier states and exact source locators without retaining prose."""

        report = assess_answer_support_integrity(text, citations)
        claim_results = []
        for item in list(report.get("claim_results") or [])[:8]:
            source_trace = dict(item.get("source_trace") or {})
            claim_results.append(
                {
                    "claim_sha256": str(item.get("claim_sha256") or ""),
                    "status": str(item.get("status") or "not_verifiable"),
                    "supported": bool(item.get("supported")),
                    "source_trace": {
                        "source_id": str(source_trace.get("best_source_id") or ""),
                        "start_offset": source_trace.get("start_offset"),
                        "end_offset": source_trace.get("end_offset"),
                    },
                }
            )
        return {
            "status": str(report.get("status") or "review_blocked"),
            "status_counts": dict(report.get("status_counts") or {}),
            "blockers": [str(item) for item in list(report.get("blockers") or [])],
            "claim_results": claim_results,
            "review_required": True,
            "filing_ready": False,
        }

    def _correction_entry(
        *,
        session_id: str,
        expected_search_id: str,
    ) -> tuple[str, dict[str, Any]]:
        normalized, session_report = normalize_session_id(session_id)
        search_id, search_report = normalize_search_id(expected_search_id)
        if not session_report["accepted"]:
            raise HTTPException(status_code=422, detail="conversation_session_required")
        if not search_report["accepted"]:
            raise HTTPException(status_code=422, detail="valid_search_identifier_required")
        session_key = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        with _recent_search_lock:
            _prune_recent_sources()
            entry = dict(_recent_record_searches.get(session_key) or {})
        if not entry:
            raise HTTPException(status_code=404, detail="conversation_correction_unavailable")
        if str(entry.get("matter_scope") or "") != _conversation_matter_scope():
            raise HTTPException(status_code=409, detail="conversation_correction_matter_scope_mismatch")
        if str(entry.get("search_id") or "") != search_id:
            raise HTTPException(status_code=409, detail="conversation_correction_stale_search")
        return session_key, entry

    def _record_correction_audit(entry: dict[str, Any], correction_id: str, operation: str) -> str:
        case_root = active_case_root()
        if case_root is None:
            return "not_applicable_general_workspace"
        try:
            PrivacySafeObservabilityStore(case_root).record(
                "api_request",
                metrics={"count": 1, "result_count": len(entry.get("citations") or [])},
                labels={"component": "conversation", "operation": operation, "correction_id": correction_id[:16], "status": "ok"},
            )
        except ReleasePilotHardeningError as exc:
            raise HTTPException(status_code=409, detail="conversation_correction_audit_unavailable") from exc
        return "privacy_safe_audit_recorded"

    @app.post("/api/conversation/corrections")
    def create_conversation_correction(
        payload: ConversationAnswerCorrectionRequest,
    ) -> dict[str, Any]:
        """Record only immutable hashes; correction prose is verified transiently."""

        session_key, entry = _correction_entry(
            session_id=payload.session_id, expected_search_id=payload.expected_search_id
        )
        original = str(payload.original_sentence or "").strip()
        proposed = str(payload.proposed_correction or "").strip()
        if not original or not proposed:
            raise HTTPException(status_code=422, detail="original_and_proposed_sentence_required")
        if len(original) > 4000 or len(proposed) > 4000:
            raise HTTPException(status_code=422, detail="correction_sentence_too_long")
        if original == proposed:
            raise HTTPException(status_code=422, detail="proposed_correction_must_change_sentence")
        allowed_reasons = {"source_mismatch", "missing_context", "outdated", "wording", "other"}
        reason_code = str(payload.reason_code or "other").strip().lower()
        if reason_code not in allowed_reasons:
            reason_code = "other"
        reason_note = str(payload.reason_note or "").strip()
        if len(reason_note) > 1000:
            raise HTTPException(status_code=422, detail="correction_reason_too_long")
        original_sha256 = hashlib.sha256(original.encode("utf-8")).hexdigest()
        proposed_sha256 = hashlib.sha256(proposed.encode("utf-8")).hexdigest()
        reason_sha256 = hashlib.sha256(reason_note.encode("utf-8")).hexdigest() if reason_note else ""
        now = time.time()
        correction_id = hashlib.sha256(
            f"{session_key}|{entry['search_id']}|{original_sha256}|{proposed_sha256}|{reason_code}|{now}".encode("utf-8")
        ).hexdigest()[:32]
        receipt = {
            "schema_version": "conversation_answer_correction_v1",
            "correction_id": correction_id,
            "search_id": str(entry["search_id"]),
            "matter_scope": str(entry["matter_scope"]),
            "original_sentence_sha256": original_sha256,
            "proposed_correction_sha256": proposed_sha256,
            "reason_code": reason_code,
            "reason_note_sha256": reason_sha256,
            "source_basis_sha256": hashlib.sha256(
                json.dumps(sorted(str(item.get("source_id") or "") for item in entry.get("citations") or []), separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "raw_correction_text_stored": False,
            "immutable": True,
            "review_required": True,
            "filing_ready": False,
            "created_at": now,
        }
        receipt["audit_status"] = _record_correction_audit(entry, correction_id, "answer_correction_create")
        with _recent_search_lock:
            current = dict(_recent_record_searches.get(session_key) or {})
            if not current or str(current.get("search_id") or "") != str(entry.get("search_id") or ""):
                raise HTTPException(status_code=409, detail="conversation_correction_changed_retry")
            corrections = list(current.get("answer_corrections") or [])
            corrections.append(dict(receipt))
            current["answer_corrections"] = corrections[-20:]
            _recent_record_searches[session_key] = current
        citations = _bounded_citations(list(entry.get("citations") or []))
        return {
            **receipt,
            "response_kind": "conversation_answer_correction",
            "original_sentence": original,
            "proposed_correction": proposed,
            "original_verification": _correction_verification_summary(original, citations),
            "proposed_verification": _correction_verification_summary(proposed, citations),
            "citations": citations,
            "source_card_count": len(citations),
            "rerun_required": True,
        }

    @app.post("/api/conversation/corrections/{correction_id}/rerun")
    def rerun_conversation_correction(
        correction_id: str,
        payload: ConversationAnswerCorrectionRerunRequest,
    ) -> dict[str, Any]:
        """Re-run verifier states only after the immutable hash receipt matches."""

        session_key, entry = _correction_entry(
            session_id=payload.session_id, expected_search_id=payload.expected_search_id
        )
        original = str(payload.original_sentence or "").strip()
        proposed = str(payload.proposed_correction or "").strip()
        if not original or not proposed or len(original) > 4000 or len(proposed) > 4000:
            raise HTTPException(status_code=422, detail="valid_correction_sentences_required")
        correction_id = str(correction_id or "").strip().lower()
        receipt = next(
            (dict(item) for item in list(entry.get("answer_corrections") or []) if str(item.get("correction_id") or "") == correction_id),
            None,
        )
        if receipt is None:
            raise HTTPException(status_code=404, detail="conversation_correction_not_found")
        if (
            receipt.get("original_sentence_sha256") != hashlib.sha256(original.encode("utf-8")).hexdigest()
            or receipt.get("proposed_correction_sha256") != hashlib.sha256(proposed.encode("utf-8")).hexdigest()
        ):
            raise HTTPException(status_code=409, detail="conversation_correction_hash_mismatch")
        receipt["audit_status"] = _record_correction_audit(entry, correction_id, "answer_correction_rerun")
        citations = _bounded_citations(list(entry.get("citations") or []))
        return {
            **receipt,
            "response_kind": "conversation_answer_correction_rerun",
            "original_verification": _correction_verification_summary(original, citations),
            "proposed_verification": _correction_verification_summary(proposed, citations),
            "citations": citations,
            "source_card_count": len(citations),
            "review_required": True,
            "filing_ready": False,
        }

    @app.post("/api/conversation/latency")
    def record_conversation_latency(
        payload: ConversationLatencyObservationRequest,
    ) -> dict[str, Any]:
        """Store a bounded, no-prose local timing receipt for the current answer."""

        session_key, entry = _correction_entry(
            session_id=payload.session_id, expected_search_id=payload.expected_search_id
        )
        cache_state = str(payload.cache_state or "unknown").lower()
        if cache_state not in {"unknown", "miss", "local_hit", "bypassed"}:
            cache_state = "unknown"
        def bounded_ms(value: int | None) -> int | None:
            if value is None:
                return None
            return max(0, min(int(value), 3_600_000))
        receipt = {
            "schema_version": "chat_latency_observation_v1",
            "observation_id": uuid.uuid4().hex,
            "search_id": str(entry.get("search_id") or ""),
            "matter_scope": str(entry.get("matter_scope") or ""),
            "first_feedback_ms": bounded_ms(payload.first_feedback_ms),
            "total_duration_ms": bounded_ms(payload.total_duration_ms) or 0,
            "server_duration_ms": bounded_ms(payload.server_duration_ms),
            "queue_delay_ms": bounded_ms(payload.queue_delay_ms),
            "cache_state": cache_state,
            "model_output_tokens": max(0, min(int(payload.model_output_tokens or 0), 1_000_000)),
            "hardware_concurrency": max(0, min(int(payload.hardware_concurrency or 0), 256)),
            "device_memory_gib": max(0.0, min(float(payload.device_memory_gib or 0.0), 4096.0)),
            "prompt_text_stored": False,
            "matter_text_stored": False,
            "review_required": True,
            "created_at": time.time(),
        }
        case_root = active_case_root()
        receipt["audit_status"] = "not_applicable_general_workspace"
        if case_root is not None:
            try:
                PrivacySafeObservabilityStore(case_root).record(
                    "api_request",
                    metrics={"count": 1, "duration_ms": receipt["total_duration_ms"]},
                    labels={"component": "conversation", "operation": "latency_observation", "cache_state": cache_state, "status": "ok"},
                )
                receipt["audit_status"] = "privacy_safe_audit_recorded"
            except ReleasePilotHardeningError as exc:
                raise HTTPException(status_code=409, detail="conversation_latency_audit_unavailable") from exc
        with _recent_search_lock:
            current = dict(_recent_record_searches.get(session_key) or {})
            if not current or str(current.get("search_id") or "") != str(entry.get("search_id") or ""):
                raise HTTPException(status_code=409, detail="conversation_latency_changed_retry")
            observations = list(current.get("latency_observations") or [])
            observations.append(dict(receipt))
            current["latency_observations"] = observations[-30:]
            _recent_record_searches[session_key] = current
        return receipt

    @app.get("/api/conversation/latency/{session_id}")
    def inspect_conversation_latency(session_id: str, expected_search_id: str) -> dict[str, Any]:
        session_key, entry = _correction_entry(session_id=session_id, expected_search_id=expected_search_id)
        del session_key
        observations = [dict(item) for item in list(entry.get("latency_observations") or [])]
        totals = sorted(int(item.get("total_duration_ms") or 0) for item in observations)
        return {
            "schema_version": "chat_latency_observatory_v1",
            "search_id": str(entry.get("search_id") or ""),
            "observation_count": len(observations),
            "average_total_duration_ms": round(sum(totals) / len(totals)) if totals else None,
            "p95_total_duration_ms": totals[max(0, int(len(totals) * 0.95) - 1)] if totals else None,
            "observations": observations,
            "prompt_text_stored": False,
            "matter_text_stored": False,
            "review_required": True,
        }

    @app.post("/api/conversation/compare")
    def compare_conversation_approaches(payload: ConversationAnswerComparisonRequest) -> dict[str, Any]:
        """Compare transient candidate wording against one immutable source basis."""

        _session_key_value, entry = _correction_entry(session_id=payload.session_id, expected_search_id=payload.expected_search_id)
        approach_a = str(payload.approach_a or "").strip()
        approach_b = str(payload.approach_b or "").strip()
        if not approach_a or not approach_b or len(approach_a) > 6000 or len(approach_b) > 6000:
            raise HTTPException(status_code=422, detail="two_bounded_comparison_approaches_required")
        citations = _bounded_citations(list(entry.get("citations") or []))
        source_basis_sha256 = hashlib.sha256(json.dumps(sorted(str(item.get("source_id") or "") for item in citations), separators=(",", ":")).encode("utf-8")).hexdigest()
        return {
            "schema_version": "conversation_answer_comparison_v1",
            "response_kind": "conversation_answer_comparison",
            "search_id": str(entry.get("search_id") or ""),
            "matter_scope": str(entry.get("matter_scope") or ""),
            "source_basis_sha256": source_basis_sha256,
            "approach_a": {"sha256": hashlib.sha256(approach_a.encode("utf-8")).hexdigest(), "verification": _correction_verification_summary(approach_a, citations)},
            "approach_b": {"sha256": hashlib.sha256(approach_b.encode("utf-8")).hexdigest(), "verification": _correction_verification_summary(approach_b, citations)},
            "candidate_text_stored": False,
            "citations": citations,
            "source_card_count": len(citations),
            "review_required": True,
            "filing_ready": False,
            "boundary": "This compares review aids against the same source set. It does not select an approach, establish facts or law, or create a filing-ready draft.",
        }

    @app.post("/api/conversation/branch")
    def branch_conversation(payload: ConversationBranchRequest) -> dict[str, Any]:
        """Create a new session with source lineage but no copied conversation prose."""

        parent_key, entry = _correction_entry(session_id=payload.session_id, expected_search_id=payload.expected_search_id)
        branch_session_id = str(uuid.uuid4())
        branch_key = hashlib.sha256(branch_session_id.encode("utf-8")).hexdigest()
        source_ids = sorted(str(item.get("source_id") or "") for item in list(entry.get("citations") or []) if str(item.get("source_id") or "") )
        receipt = {
            "schema_version": "conversation_branch_v1",
            "branch_id": uuid.uuid4().hex,
            "branch_session_id": branch_session_id,
            "parent_session_sha256": parent_key,
            "parent_search_id": str(entry.get("search_id") or ""),
            "matter_scope": str(entry.get("matter_scope") or ""),
            "source_basis_sha256": hashlib.sha256(json.dumps(source_ids, separators=(",", ":")).encode("utf-8")).hexdigest(),
            "source_card_count": len(source_ids),
            "raw_conversation_text_copied": False,
            "raw_matter_text_copied": False,
            "review_required": True,
        }
        receipt["audit_status"] = "not_applicable_general_workspace"
        case_root = active_case_root()
        if case_root is not None:
            try:
                PrivacySafeObservabilityStore(case_root).record(
                    "api_request",
                    metrics={"count": 1, "result_count": len(source_ids)},
                    labels={"component": "conversation", "operation": "branch", "status": "ok"},
                )
                receipt["audit_status"] = "privacy_safe_audit_recorded"
            except ReleasePilotHardeningError as exc:
                raise HTTPException(status_code=409, detail="conversation_branch_audit_unavailable") from exc
        branch_entry = dict(entry)
        branch_entry["branch_lineage"] = {key: value for key, value in receipt.items() if key != "branch_session_id"}
        branch_entry["context_compaction"] = {}
        branch_entry["answer_corrections"] = []
        branch_entry["latency_observations"] = []
        branch_entry["created_at"] = time.time()
        with _recent_search_lock:
            _prune_recent_sources()
            _recent_record_searches[branch_key] = branch_entry
        return receipt

    @app.post("/api/conversation/usefulness")
    def evaluate_conversation_usefulness(payload: ConversationUsefulnessRequest) -> dict[str, Any]:
        """Return a deterministic, non-substantive usefulness receipt for one answer."""

        _, entry = _correction_entry(session_id=payload.session_id, expected_search_id=payload.expected_search_id)
        citations = _bounded_citations(list(entry.get("citations") or []))
        intake_anchor = dict(entry.get("intake_anchor") or {})
        intent = dict(entry.get("answer_intent") or {})
        checks = [
            {"criterion": "citation_sufficiency", "status": "present" if citations else "needs_sources", "basis": "source_card_count"},
            {"criterion": "actionability", "status": "review_path_present" if str(intent.get("primary_intent") or "") else "needs_intent_review", "basis": "workflow_intent"},
            {"criterion": "scope_restraint", "status": "review_required", "basis": "no_automated_quality_clearance"},
            {"criterion": "matter_context", "status": "available" if intake_anchor else "not_provided", "basis": "bounded_intake_anchor"},
        ]
        case_root = active_case_root()
        audit_status = "not_applicable_general_workspace"
        if case_root is not None:
            try:
                PrivacySafeObservabilityStore(case_root).record(
                    "api_request", metrics={"count": 1, "result_count": len(checks)},
                    labels={"component": "conversation", "operation": "usefulness_evaluation", "status": "ok"},
                )
                audit_status = "privacy_safe_audit_recorded"
            except ReleasePilotHardeningError as exc:
                raise HTTPException(status_code=409, detail="conversation_usefulness_audit_unavailable") from exc
        return {
            "schema_version": "conversation_usefulness_v1", "response_kind": "conversation_usefulness",
            "search_id": str(entry.get("search_id") or ""), "checks": checks,
            "human_review_rubric": ["correctness against exact source spans", "actionability for the selected workflow", "clarity for the selected audience", "restraint and visible uncertainty", "citation sufficiency and freshness"],
            "synthetic_or_human_review": "deterministic_structural_checks_only",
            "answer_text_stored": False, "matter_text_stored": False, "citations": citations,
            "review_required": True, "filing_ready": False, "audit_status": audit_status,
            "boundary": "This is not attorney review, a quality certification, or a conclusion that the answer is correct. Human source review remains required.",
        }

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
        payload.response_depth = _normalize_response_depth(payload.response_depth)
        payload.audience = _normalize_audience(payload.audience)
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

            fast_help = _fast_local_help_payload(payload, intake)
            if fast_help is not None:
                return _finalize_family_response(fast_help, payload)

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

    @app.post("/ask/stream")
    def ask_stream(payload: AskRequest) -> Any:
        """Return canonical `/ask` output over a local-only SSE response.

        The existing answer builder remains the single source of legal and
        review truth.  Early events provide honest UI feedback while it runs;
        the `result` event contains the same completed payload that `/ask`
        returns.  This keeps streaming cancellable without splitting or
        weakening source, review, or matter protections.
        """

        return StreamingResponse(
            iter_stream_answer_events(payload, ask),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

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

    def _raise_outline_error(exc: IntakeWorkbenchError) -> None:
        raise HTTPException(status_code=int(exc.status_code), detail=exc.code) from None

    def _outline_store(case_root: Path) -> OutlineWorkbenchStore:
        return OutlineWorkbenchStore(case_root)

    @app.get("/api/drafting/outline-evidence-candidates")
    def drafting_outline_evidence_candidates() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        candidates = []
        for row in _review_records(case_root):
            record_id = str(row.get("evidence_id") or "").strip()
            source_hash = str(row.get("source_hash") or row.get("sha256") or "").casefold()
            if record_id and re.fullmatch(r"[a-f0-9]{64}", source_hash):
                candidates.append({
                    "record_id": record_id,
                    "source_hash": source_hash,
                    "title": str(row.get("title") or row.get("source_locator") or record_id)[:300],
                    "source_type": str(row.get("source_type") or "record")[:80],
                    "lane": "private_matter_record",
                })
        return {"status": "pass", "candidates": candidates[:200], "review_required": True, "local_only": True}

    @app.get("/api/drafting/outline-authority-candidate/{source_id}")
    def drafting_outline_authority_candidate(source_id: str) -> dict[str, Any]:
        source_id = str(source_id or "").strip()
        if not source_id or len(source_id) > 240 or "/" in source_id or "\\" in source_id:
            raise HTTPException(status_code=400, detail="authority_source_id_invalid")
        try:
            resolved = inspect_source(source_id)
        except HTTPException:
            raise HTTPException(status_code=404, detail="authority_source_not_found") from None
        card = dict(resolved.get("source_card") or resolved)
        source_span = card.get("source_span") if isinstance(card.get("source_span"), dict) else {}
        pinpoint = str(
            source_span.get("pinpoint") or source_span.get("section") or source_span.get("paragraph")
            or card.get("pinpoint") or ""
        )[:240]
        source_hash = str(card.get("source_hash") or card.get("hash") or "").casefold()
        if not re.fullmatch(r"[a-f0-9]{64}", source_hash):
            raise HTTPException(status_code=409, detail="authority_source_hash_unavailable")
        candidate = {
            "authority_id": f"authority_{hashlib.sha256(source_id.encode()).hexdigest()[:16]}",
            "source_id": source_id,
            "source_hash": source_hash,
            "citation": str(card.get("citation") or card.get("citation_hint") or source_id)[:500],
            "title": str(card.get("title") or source_id)[:500],
            "exact_span": str(card.get("source_span_preview") or "")[:2_000],
            "pinpoint": pinpoint,
            "lane": "official_authority",
            "freshness_status": str(card.get("freshness_status") or "unknown")[:80],
        }
        pinpoint_candidates: list[dict[str, Any]] = []
        if str(card.get("authority_kind") or "") in {
            "statute_section", "court_rule", "court_form", "law_court_opinion"
        }:
            try:
                precise = AuthorityProductService().drafting_source_candidates(source_id)
                pinpoint_candidates = list(precise.get("candidates") or [])
                if len(pinpoint_candidates) == 1:
                    candidate = dict(pinpoint_candidates[0])
            except (FileNotFoundError, OSError, ValueError):
                # The generic authority card remains useful for discovery/outline
                # review. Exact drafting stays blocked unless an admitted precise
                # candidate was actually available above.
                pinpoint_candidates = []
        return {
            "status": "pass",
            "candidate": candidate,
            "pinpoint_candidates": pinpoint_candidates,
            "review_required": True,
        }

    def _resolver_verified_drafting_authority(raw: Any, *, workflow: str) -> dict[str, Any]:
        """Re-resolve an authority selected in the UI before a drafting store can use it.

        Source cards are useful client-side selection aids, not an authority grant.  The
        canonical API must replace all client-supplied citation, pinpoint, span, and
        freshness fields with the locally resolved card so a direct API caller cannot
        manufacture a seemingly source-bound proposal.
        """
        if not isinstance(raw, dict):
            raise IntakeWorkbenchError(f"{workflow}_authority_required")
        source_id = str(raw.get("source_id") or "").strip()
        if not source_id:
            raise IntakeWorkbenchError(f"{workflow}_authority_source_required")
        resolved = drafting_outline_authority_candidate(source_id)
        candidate = dict(resolved.get("candidate") or {})
        precise_candidates = [
            dict(item)
            for item in list(resolved.get("pinpoint_candidates") or [])
            if isinstance(item, dict)
        ]
        requested_authority_id = str(raw.get("authority_id") or "").strip()
        if precise_candidates:
            if requested_authority_id:
                candidate = next(
                    (
                        item
                        for item in precise_candidates
                        if str(item.get("authority_id") or "") == requested_authority_id
                    ),
                    {},
                )
                if not candidate:
                    raise IntakeWorkbenchError(f"{workflow}_authority_selection_invalid", 409)
            elif len(precise_candidates) > 1:
                raise IntakeWorkbenchError(f"{workflow}_authority_selection_required", 409)
        if not candidate:
            raise IntakeWorkbenchError(f"{workflow}_authority_not_found", 404)
        supplied_hash = str(raw.get("source_hash") or "").strip().casefold()
        verified_hash = str(candidate.get("source_hash") or "").strip().casefold()
        if supplied_hash and supplied_hash != verified_hash:
            raise IntakeWorkbenchError(f"{workflow}_authority_hash_mismatch", 409)
        return candidate

    @app.post("/api/drafting/outlines")
    def drafting_outline_create(payload: DraftOutlineCreateRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return {
                "status": "pass",
                "outline": _outline_store(case_root).create_outline(
                    payload.model_dump(), records=_review_records(case_root)
                ),
                "review_required": True,
            }
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/drafting/outlines")
    def drafting_outline_list() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _outline_store(case_root).outlines()
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/drafting/outlines/{outline_id}")
    def drafting_outline_get(outline_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _outline_store(case_root).outlines(outline_id)
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/drafting/outlines/{outline_id}/evidence/{record_id}/source")
    def drafting_outline_evidence_source(outline_id: str, record_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            payload = _outline_store(case_root).evidence_source(outline_id, record_id)
            source = dict(payload.get("source") or {})
            row = next((item for item in _review_records(case_root) if str(item.get("evidence_id") or "") == str(source.get("record_id") or "")), None)
            if row is None or str(row.get("source_hash") or row.get("sha256") or "").casefold() != str(source.get("source_hash") or "").casefold():
                raise IntakeWorkbenchError("outline_evidence_source_not_in_active_matter", 404)
            locator = str(row.get("source_locator") or row.get("title") or source.get("record_id") or "")
            source["source_token"] = _record_open_token(case_root, str(source.get("record_id") or ""), locator)
            return {**payload, "source": source, "review_required": True}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/drafting/outlines/{outline_id}/authority/{authority_id}/source")
    def drafting_outline_authority_source(outline_id: str, authority_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _outline_store(case_root).authority_source(outline_id, authority_id)
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    def _argument_matrix_store(case_root: Path) -> ArgumentMatrixStore:
        return ArgumentMatrixStore(case_root)

    def _verified_argument_matrix_payload(payload: ArgumentMatrixRequest) -> dict[str, Any]:
        """Replace client-supplied authority fields with resolver-verified source cards."""
        value = payload.model_dump()
        for position in list(value.get("positions") or []):
            if not isinstance(position, dict):
                continue
            verified: list[dict[str, Any]] = []
            for raw in list(position.get("supporting_authority") or []):
                if not isinstance(raw, dict):
                    raise IntakeWorkbenchError("position_authority_invalid")
                verified.append(
                    _resolver_verified_drafting_authority(raw, workflow="argument_matrix")
                )
            position["supporting_authority"] = verified
        return value

    @app.post("/api/drafting/argument-matrices")
    def drafting_argument_matrix_create(payload: ArgumentMatrixRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            matrix = _argument_matrix_store(case_root).create(
                _verified_argument_matrix_payload(payload), records=_review_records(case_root)
            )
            return {"status": "pass", "matrix": matrix, "review_required": True, "filing_ready": False}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/drafting/argument-matrices")
    def drafting_argument_matrix_list() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _argument_matrix_store(case_root).matrices()
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/drafting/argument-matrices/{matrix_id}")
    def drafting_argument_matrix_get(matrix_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _argument_matrix_store(case_root).matrices(matrix_id)
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/drafting/argument-matrices/{matrix_id}/positions/{position_id}/{lane}/{source_id}/source")
    def drafting_argument_matrix_source(matrix_id: str, position_id: str, lane: str, source_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            payload = _argument_matrix_store(case_root).source(matrix_id, position_id, lane, source_id)
            source = dict(payload.get("source") or {})
            if source.get("lane") == "private_matter_record":
                row = next(
                    (item for item in _review_records(case_root) if str(item.get("evidence_id") or item.get("source_id") or "") == str(source.get("record_id") or "")),
                    None,
                )
                if row is None or str(row.get("source_hash") or row.get("sha256") or "").casefold() != str(source.get("source_hash") or "").casefold():
                    raise IntakeWorkbenchError("argument_matrix_evidence_not_in_active_matter", 404)
                locator = str(row.get("source_locator") or row.get("title") or source.get("record_id") or "")
                source["source_token"] = _record_open_token(case_root, str(source.get("record_id") or ""), locator)
            else:
                source["source_token"] = ""
            return {**payload, "source": source, "review_required": True}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    def _procedure_pathway_store(case_root: Path) -> ProcedurePathwayStore:
        return ProcedurePathwayStore(case_root)

    @app.post("/api/procedure-pathways")
    def procedure_pathway_create(payload: ProcedurePathwayRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            authority = dict(drafting_outline_authority_candidate(payload.authority_source_id).get("candidate") or {})
            pathway = _procedure_pathway_store(case_root).create(
                payload.model_dump(), records=_review_records(case_root), authority=authority
            )
            return {"status": "pass", "pathway": pathway, "review_required": True, "filing_ready": False}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/procedure-pathways")
    def procedure_pathway_list() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _procedure_pathway_store(case_root).pathways()
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/procedure-pathways/{pathway_id}")
    def procedure_pathway_get(pathway_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _procedure_pathway_store(case_root).pathways(pathway_id)
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/procedure-pathways/{pathway_id}/{lane}/{source_id}/source")
    def procedure_pathway_source(pathway_id: str, lane: str, source_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            payload = _procedure_pathway_store(case_root).source(pathway_id, lane, source_id)
            source = dict(payload.get("source") or {})
            if source.get("lane") == "private_matter_record":
                row = next((item for item in _review_records(case_root) if str(item.get("evidence_id") or item.get("source_id") or "") == str(source.get("record_id") or "")), None)
                if row is None or str(row.get("source_hash") or row.get("sha256") or "").casefold() != str(source.get("source_hash") or "").casefold():
                    raise IntakeWorkbenchError("existing_order_not_in_active_matter", 404)
                source["source_token"] = _record_open_token(case_root, str(source.get("record_id") or ""), str(row.get("source_locator") or row.get("title") or ""))
            else:
                source["source_token"] = ""
            return {**payload, "source": source, "review_required": True}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    def _service_method_matrix_store(case_root: Path) -> ServiceMethodMatrixStore:
        return ServiceMethodMatrixStore(case_root)

    @app.post("/api/service-method-matrices")
    def service_method_matrix_create(payload: ServiceMethodMatrixRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            authority = dict(
                drafting_outline_authority_candidate(payload.authority_source_id).get("candidate") or {}
            )
            matrix = _service_method_matrix_store(case_root).create(
                payload.model_dump(), records=_review_records(case_root), authority=authority
            )
            return {"status": "pass", "matrix": matrix, "review_required": True, "filing_ready": False}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/service-method-matrices")
    def service_method_matrix_list() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _service_method_matrix_store(case_root).matrices()
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/service-method-matrices/{matrix_id}")
    def service_method_matrix_get(matrix_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _service_method_matrix_store(case_root).matrices(matrix_id)
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/service-method-matrices/{matrix_id}/{lane}/source")
    def service_method_matrix_source(matrix_id: str, lane: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            payload = _service_method_matrix_store(case_root).source(matrix_id, lane)
            source = dict(payload.get("source") or {})
            if source.get("lane") == "private_matter_record":
                row = next(
                    (
                        item
                        for item in _review_records(case_root)
                        if str(item.get("evidence_id") or item.get("source_id") or "")
                        == str(source.get("record_id") or "")
                    ),
                    None,
                )
                if row is None or str(row.get("source_hash") or row.get("sha256") or "").casefold() != str(source.get("source_hash") or "").casefold():
                    raise IntakeWorkbenchError("service_proof_not_in_active_matter", 404)
                locator = str(row.get("source_locator") or row.get("title") or source.get("record_id") or "")
                source["source_token"] = _record_open_token(case_root, str(source.get("record_id") or ""), locator)
            else:
                source["source_token"] = ""
            return {**payload, "source": source, "review_required": True}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    def _business_day_store(case_root: Path) -> BusinessDayReviewStore:
        return BusinessDayReviewStore(case_root)

    @app.post("/api/business-day-calendar-inputs")
    def business_day_calendar_input_create(payload: BusinessDayCalendarInputRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            authority = dict(
                drafting_outline_authority_candidate(payload.authority_source_id).get("candidate") or {}
            )
            entry = _business_day_store(case_root).create_input(payload.model_dump(), authority=authority)
            return {"status": "pass", "input": entry, "review_required": True, "filing_ready": False}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/business-day-calendar-inputs")
    def business_day_calendar_input_list() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _business_day_store(case_root).inputs()
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/business-day-calendar-inputs/{input_id}")
    def business_day_calendar_input_get(input_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _business_day_store(case_root).inputs(input_id)
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/business-day-calendar-inputs/{input_id}/authority/source")
    def business_day_calendar_input_authority(input_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _business_day_store(case_root).authority_source(input_id)
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.post("/api/business-day-calculations")
    def business_day_calculation_create(payload: BusinessDayCalculationRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            calculation = _business_day_store(case_root).calculate(payload.model_dump())
            return {"status": "pass", "calculation": calculation, "review_required": True, "filing_ready": False}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/business-day-calculations/{calculation_id}")
    def business_day_calculation_get(calculation_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _business_day_store(case_root).calculations(calculation_id)
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    def _hearing_countdown_store(case_root: Path) -> HearingCountdownStore:
        return HearingCountdownStore(case_root)

    @app.post("/api/hearing-countdowns")
    def hearing_countdown_create(payload: HearingCountdownRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            countdown = _hearing_countdown_store(case_root).create(
                payload.model_dump(), records=_review_records(case_root)
            )
            return {"status": "pass", "countdown": countdown, "review_required": True, "filing_ready": False}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/hearing-countdowns")
    def hearing_countdown_list() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _hearing_countdown_store(case_root).countdowns()
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/hearing-countdowns/{countdown_id}")
    def hearing_countdown_get(countdown_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _hearing_countdown_store(case_root).countdowns(countdown_id)
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/hearing-countdowns/{countdown_id}/notice-source")
    def hearing_countdown_notice_source(countdown_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            payload = _hearing_countdown_store(case_root).source(countdown_id)
            source = dict(payload.get("source") or {})
            row = next(
                (
                    item
                    for item in _review_records(case_root)
                    if str(item.get("evidence_id") or item.get("source_id") or "")
                    == str(source.get("record_id") or "")
                ),
                None,
            )
            if row is None or str(row.get("source_hash") or row.get("sha256") or "").casefold() != str(source.get("source_hash") or "").casefold():
                raise IntakeWorkbenchError("hearing_countdown_notice_not_in_active_matter", 404)
            locator = str(row.get("source_locator") or row.get("title") or source.get("record_id") or "")
            source["source_token"] = _record_open_token(case_root, str(source.get("record_id") or ""), locator)
            return {**payload, "source": source, "review_required": True}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    def _filing_preflight_store(case_root: Path) -> FilingPreflightStore:
        return FilingPreflightStore(case_root)

    def _verified_preflight_forms(source_ids: list[str]) -> list[dict[str, Any]]:
        if len(source_ids) > 50 or len(set(source_ids)) != len(source_ids):
            raise IntakeWorkbenchError("preflight_forms_invalid")
        result: list[dict[str, Any]] = []
        for source_id in source_ids:
            candidate = dict(drafting_outline_authority_candidate(str(source_id)).get("candidate") or {})
            if not candidate:
                raise IntakeWorkbenchError("preflight_form_not_found", 404)
            result.append(candidate)
        return result

    @app.post("/api/filing-preflights")
    def filing_preflight_create(payload: FilingPreflightRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            canonical_packet_gate_seen = False
            document_id = str(payload.document_id or "").strip()
            if document_id:
                try:
                    packet = ReviewedFilingPacketStore(case_root).active(document_id=document_id)
                    canonical_packet_gate_seen = str(packet.get("status") or "") == "pass"
                except (ReviewedFilingPacketError, DocumentWorkspaceError):
                    canonical_packet_gate_seen = False
            value = payload.model_dump() | {"canonical_packet_gate_seen": canonical_packet_gate_seen}
            preflight = _filing_preflight_store(case_root).create(
                value,
                records=_review_records(case_root),
                forms=_verified_preflight_forms(list(payload.form_source_ids or [])),
            )
            return {"status": "pass", "preflight": preflight, "review_required": True, "filing_ready": False}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/filing-preflights")
    def filing_preflight_list() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _filing_preflight_store(case_root).preflights()
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/filing-preflights/{preflight_id}")
    def filing_preflight_get(preflight_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _filing_preflight_store(case_root).preflights(preflight_id)
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/filing-preflights/{preflight_id}/{lane}/{source_id}/source")
    def filing_preflight_source(preflight_id: str, lane: str, source_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            payload = _filing_preflight_store(case_root).source(preflight_id, lane, source_id)
            source = dict(payload.get("source") or {})
            if source.get("lane") == "private_matter_record":
                row = next((item for item in _review_records(case_root) if str(item.get("evidence_id") or item.get("source_id") or "") == str(source.get("record_id") or "")), None)
                if row is None or str(row.get("source_hash") or row.get("sha256") or "").casefold() != str(source.get("source_hash") or "").casefold():
                    raise IntakeWorkbenchError("preflight_attachment_not_in_active_matter", 404)
                source["source_token"] = _record_open_token(case_root, str(source.get("record_id") or ""), str(row.get("source_locator") or row.get("title") or ""))
            else:
                source["source_token"] = ""
            return {**payload, "source": source, "review_required": True}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    def _fee_waiver_workspace_store(case_root: Path) -> FeeWaiverWorkspaceStore:
        return FeeWaiverWorkspaceStore(case_root)

    @app.post("/api/fee-waiver-workspaces")
    def fee_waiver_workspace_create(payload: FeeWaiverWorkspaceRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            authority = dict(drafting_outline_authority_candidate(payload.authority_source_id).get("candidate") or {})
            workspace = _fee_waiver_workspace_store(case_root).create(payload.model_dump(), authority=authority)
            return {"status": "pass", "workspace": workspace, "review_required": True, "filing_ready": False}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/fee-waiver-workspaces/{workspace_id}")
    def fee_waiver_workspace_get(workspace_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _fee_waiver_workspace_store(case_root).workspaces(workspace_id)
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/fee-waiver-workspaces/{workspace_id}/authority/source")
    def fee_waiver_workspace_source(workspace_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _fee_waiver_workspace_store(case_root).source(workspace_id)
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    def _child_support_worksheet_store(case_root: Path) -> ChildSupportWorksheetStore:
        return ChildSupportWorksheetStore(case_root)

    @app.post("/api/child-support-worksheets")
    def child_support_worksheet_create(payload: ChildSupportWorksheetRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            authority = dict(drafting_outline_authority_candidate(payload.authority_source_id).get("candidate") or {})
            workspace = _child_support_worksheet_store(case_root).create(payload.model_dump(), authority=authority)
            return {"status": "pass", "workspace": workspace, "review_required": True, "filing_ready": False}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/child-support-worksheets/{workspace_id}")
    def child_support_worksheet_get(workspace_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _child_support_worksheet_store(case_root).get(workspace_id)
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/child-support-worksheets/{workspace_id}/authority/source")
    def child_support_worksheet_source(workspace_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _child_support_worksheet_store(case_root).authority_source(workspace_id)
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    def _financial_affidavit_store(case_root: Path) -> FinancialAffidavitStore:
        return FinancialAffidavitStore(case_root)

    @app.post("/api/financial-affidavit-workspaces")
    def financial_affidavit_create(payload: FinancialAffidavitRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            workspace = _financial_affidavit_store(case_root).create(payload.model_dump(), records=_review_records(case_root))
            return {"status": "pass", "workspace": workspace, "review_required": True, "filing_ready": False}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/financial-affidavit-workspaces/{workspace_id}")
    def financial_affidavit_get(workspace_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _financial_affidavit_store(case_root).get(workspace_id)
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/financial-affidavit-workspaces/{workspace_id}/entries/{entry_id}/source")
    def financial_affidavit_source(workspace_id: str, entry_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            payload = _financial_affidavit_store(case_root).source(workspace_id, entry_id)
            source = dict(payload.get("source") or {})
            record_id = str(source.get("record_id") or "")
            source_hash = str(source.get("source_hash") or "").casefold()
            row = next((item for item in _review_records(case_root) if str(item.get("evidence_id") or item.get("source_id") or "").casefold() == record_id.casefold()), None)
            if row is None or not re.fullmatch(r"[a-f0-9]{64}", source_hash) or str(row.get("source_hash") or row.get("sha256") or "").casefold() != source_hash:
                raise IntakeWorkbenchError("financial_affidavit_source_not_in_active_matter", 404)
            source["source_token"] = _record_open_token(case_root, str(row.get("evidence_id") or row.get("source_id") or record_id), str(row.get("source_locator") or row.get("title") or record_id))
            return {**payload, "source": source}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    def _asset_tracing_store(case_root: Path) -> AssetTracingStore:
        return AssetTracingStore(case_root)

    @app.post("/api/asset-tracing-ledgers")
    def asset_tracing_create(payload: AssetTracingRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            ledger = _asset_tracing_store(case_root).create(payload.model_dump(), records=_review_records(case_root))
            return {"status": "pass", "ledger": ledger, "review_required": True, "filing_ready": False}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/asset-tracing-ledgers/{ledger_id}")
    def asset_tracing_get(ledger_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _asset_tracing_store(case_root).get(ledger_id)
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/asset-tracing-ledgers/{ledger_id}/assets/{asset_id}/sources/{record_id}")
    def asset_tracing_source(ledger_id: str, asset_id: str, record_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            payload = _asset_tracing_store(case_root).source(ledger_id, asset_id, record_id)
            source = dict(payload.get("source") or {})
            source_hash = str(source.get("source_hash") or "").casefold()
            row = next((item for item in _review_records(case_root) if str(item.get("evidence_id") or item.get("source_id") or "").casefold() == str(source.get("record_id") or "").casefold()), None)
            if row is None or not re.fullmatch(r"[a-f0-9]{64}", source_hash) or str(row.get("source_hash") or row.get("sha256") or "").casefold() != source_hash:
                raise IntakeWorkbenchError("asset_tracing_source_not_in_active_matter", 404)
            source["source_token"] = _record_open_token(case_root, str(row.get("evidence_id") or row.get("source_id") or source.get("record_id") or ""), str(row.get("source_locator") or row.get("title") or ""))
            return {**payload, "source": source}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    def _debt_reconciliation_store(case_root: Path) -> DebtReconciliationStore:
        return DebtReconciliationStore(case_root)

    @app.post("/api/debt-reconciliation-workspaces")
    def debt_reconciliation_create(payload: DebtReconciliationRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            workspace = _debt_reconciliation_store(case_root).create(payload.model_dump(), records=_review_records(case_root))
            return {"status": "pass", "workspace": workspace, "review_required": True, "filing_ready": False}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/debt-reconciliation-workspaces/{workspace_id}")
    def debt_reconciliation_get(workspace_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _debt_reconciliation_store(case_root).get(workspace_id)
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/debt-reconciliation-workspaces/{workspace_id}/statements/{statement_id}/source")
    def debt_reconciliation_source(workspace_id: str, statement_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            payload = _debt_reconciliation_store(case_root).source(workspace_id, statement_id)
            source = dict(payload.get("source") or {})
            source_hash = str(source.get("source_hash") or "").casefold()
            row = next((item for item in _review_records(case_root) if str(item.get("evidence_id") or item.get("source_id") or "").casefold() == str(source.get("record_id") or "").casefold()), None)
            if row is None or not re.fullmatch(r"[a-f0-9]{64}", source_hash) or str(row.get("source_hash") or row.get("sha256") or "").casefold() != source_hash:
                raise IntakeWorkbenchError("debt_reconciliation_source_not_in_active_matter", 404)
            source["source_token"] = _record_open_token(case_root, str(row.get("evidence_id") or row.get("source_id") or source.get("record_id") or ""), str(row.get("source_locator") or row.get("title") or ""))
            return {**payload, "source": source}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    def _settlement_scenario_store(case_root: Path) -> SettlementScenarioStore:
        return SettlementScenarioStore(case_root)

    @app.post("/api/settlement-scenario-comparisons")
    def settlement_scenario_create(payload: SettlementScenarioRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            comparison = _settlement_scenario_store(case_root).create(payload.model_dump(), records=_review_records(case_root))
            return {"status": "pass", "comparison": comparison, "review_required": True, "filing_ready": False}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/settlement-scenario-comparisons/{comparison_id}")
    def settlement_scenario_get(comparison_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _settlement_scenario_store(case_root).get(comparison_id)
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/settlement-scenario-comparisons/{comparison_id}/scenarios/{scenario_id}/source")
    def settlement_scenario_source(comparison_id: str, scenario_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            payload = _settlement_scenario_store(case_root).source(comparison_id, scenario_id)
            source = dict(payload.get("source") or {})
            source_hash = str(source.get("source_hash") or "").casefold()
            row = next((item for item in _review_records(case_root) if str(item.get("evidence_id") or item.get("source_id") or "").casefold() == str(source.get("record_id") or "").casefold()), None)
            if row is None or not re.fullmatch(r"[a-f0-9]{64}", source_hash) or str(row.get("source_hash") or row.get("sha256") or "").casefold() != source_hash:
                raise IntakeWorkbenchError("settlement_scenario_source_not_in_active_matter", 404)
            source["source_token"] = _record_open_token(case_root, str(row.get("evidence_id") or row.get("source_id") or source.get("record_id") or ""), str(row.get("source_locator") or row.get("title") or ""))
            return {**payload, "source": source}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    def _implementation_feasibility_store(case_root: Path) -> ImplementationFeasibilityStore:
        return ImplementationFeasibilityStore(case_root)

    @app.post("/api/implementation-feasibility-reviews")
    def implementation_feasibility_create(payload: ImplementationFeasibilityRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            review = _implementation_feasibility_store(case_root).create(payload.model_dump(), records=_review_records(case_root))
            return {"status": "pass", "review": review, "review_required": True, "filing_ready": False}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/implementation-feasibility-reviews/{review_id}")
    def implementation_feasibility_get(review_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _implementation_feasibility_store(case_root).get(review_id)
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/implementation-feasibility-reviews/{review_id}/clauses/{clause_id}/source")
    def implementation_feasibility_source(review_id: str, clause_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            payload = _implementation_feasibility_store(case_root).source(review_id, clause_id)
            source = dict(payload.get("source") or {})
            source_hash = str(source.get("source_hash") or "").casefold()
            row = next((item for item in _review_records(case_root) if str(item.get("evidence_id") or item.get("source_id") or "").casefold() == str(source.get("record_id") or "").casefold()), None)
            if row is None or not re.fullmatch(r"[a-f0-9]{64}", source_hash) or str(row.get("source_hash") or row.get("sha256") or "").casefold() != source_hash:
                raise IntakeWorkbenchError("implementation_feasibility_source_not_in_active_matter", 404)
            source["source_token"] = _record_open_token(case_root, str(row.get("evidence_id") or row.get("source_id") or source.get("record_id") or ""), str(row.get("source_locator") or row.get("title") or ""))
            return {**payload, "source": source}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    def _communication_plan_store(case_root: Path) -> CommunicationPlanStore:
        return CommunicationPlanStore(case_root)

    @app.post("/api/communication-plans")
    def communication_plan_create(payload: CommunicationPlanRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            plan = _communication_plan_store(case_root).create(payload.model_dump(), records=_review_records(case_root))
            return {"status": "pass", "plan": plan, "review_required": True, "filing_ready": False}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/communication-plans/{plan_id}")
    def communication_plan_get(plan_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _communication_plan_store(case_root).get(plan_id)
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/communication-plans/{plan_id}/sources/{record_id}")
    def communication_plan_source(plan_id: str, record_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            payload = _communication_plan_store(case_root).source(plan_id, record_id)
            source = dict(payload.get("source") or {})
            source_hash = str(source.get("source_hash") or "").casefold()
            row = next((item for item in _review_records(case_root) if str(item.get("evidence_id") or item.get("source_id") or "").casefold() == str(source.get("record_id") or "").casefold()), None)
            if row is None or not re.fullmatch(r"[a-f0-9]{64}", source_hash) or str(row.get("source_hash") or row.get("sha256") or "").casefold() != source_hash:
                raise IntakeWorkbenchError("communication_plan_source_not_in_active_matter", 404)
            source["source_token"] = _record_open_token(case_root, str(row.get("evidence_id") or row.get("source_id") or source.get("record_id") or ""), str(row.get("source_locator") or row.get("title") or ""))
            return {**payload, "source": source}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    def _compliance_log_store(case_root: Path) -> ComplianceLogStore:
        return ComplianceLogStore(case_root)

    @app.post("/api/compliance-logs")
    def compliance_log_create(payload: ComplianceLogRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            log = _compliance_log_store(case_root).create(payload.model_dump(), terms=_order_store().terms().get("terms", []), records=_review_records(case_root))
            return {"status": "pass", "log": log, "review_required": True, "filing_ready": False}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/compliance-logs/{log_id}")
    def compliance_log_get(log_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _compliance_log_store(case_root).get(log_id)
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/compliance-logs/{log_id}/event-source")
    def compliance_log_source(log_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            payload = _compliance_log_store(case_root).source(log_id)
            source = dict(payload.get("source") or {})
            source_hash = str(source.get("source_hash") or "").casefold()
            row = next((item for item in _review_records(case_root) if str(item.get("evidence_id") or item.get("source_id") or "").casefold() == str(source.get("record_id") or "").casefold()), None)
            if row is None or not re.fullmatch(r"[a-f0-9]{64}", source_hash) or str(row.get("source_hash") or row.get("sha256") or "").casefold() != source_hash:
                raise IntakeWorkbenchError("compliance_log_event_source_not_in_active_matter", 404)
            source["source_token"] = _record_open_token(case_root, str(row.get("evidence_id") or row.get("source_id") or source.get("record_id") or ""), str(row.get("source_locator") or row.get("title") or ""))
            return {**payload, "source": source}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    def _hardware_benchmark_store() -> HardwareBenchmarkStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        return HardwareBenchmarkStore(root)

    @app.post("/api/runtime/hardware-benchmarks")
    def hardware_benchmark_create(payload: HardwareBenchmarkRequest) -> dict[str, Any]:
        return _intake_call(lambda: _hardware_benchmark_store().run(payload.model_dump()))

    @app.get("/api/runtime/hardware-benchmarks/{benchmark_id}")
    def hardware_benchmark_get(benchmark_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _hardware_benchmark_store().get(benchmark_id))

    def _model_admission_benchmark_store() -> ModelAdmissionBenchmarkStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        return ModelAdmissionBenchmarkStore(root)

    @app.post("/api/runtime/model-admission-benchmarks")
    def model_admission_benchmark_create(payload: ModelAdmissionBenchmarkRequest) -> dict[str, Any]:
        preview = LocalAgentPreviewRequest(
            question="Local benchmark setup.", provider=payload.provider, endpoint=payload.endpoint, model=payload.model
        )
        return _intake_call(lambda: _model_admission_benchmark_store().run(payload.model_dump(), _local_agent_runtime_from_request(preview)))

    def _warm_model_pool_store() -> WarmModelPoolStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        return WarmModelPoolStore(root)

    @staticmethod
    def _warm_model_worker_from_record(model: dict[str, Any] | None) -> LocalAgentRuntime | None:
        if not model:
            return None
        provider = str(model.get("runtime_provider") or "").strip()
        endpoint = str(model.get("runtime_endpoint") or "").strip()
        runtime_model_name = str(model.get("runtime_model_name") or "").strip()
        if not provider or not endpoint or not runtime_model_name:
            return None
        try:
            return LocalAgentRuntime(
                build_local_client(
                    provider=provider,
                    endpoint=endpoint,
                    model_name=runtime_model_name,
                    timeout_seconds=30,
                )
            )
        except (ValueError, LocalModelError):
            return None

    @app.post("/api/runtime/warm-model-pool/warm")
    def warm_model_pool_warm(payload: WarmModelPoolWarmRequest) -> dict[str, Any]:
        service = _local_workbench_service()
        route = service.route_model(
            {"task": payload.task, "preferred_model_id": payload.preferred_model_id}
        )
        selected = route.get("selected_model")
        result = _intake_call(
            lambda: _warm_model_pool_store().warm(
                payload.model_dump(),
                model=selected if isinstance(selected, dict) else None,
                worker=_warm_model_worker_from_record(selected if isinstance(selected, dict) else None),
            )
        )
        result["route"] = {
            "status": route.get("status"),
            "selected_model_id": (selected or {}).get("model_id") if isinstance(selected, dict) else None,
            "admission_boundary": route.get("admission_boundary"),
        }
        return result

    @app.post("/api/runtime/warm-model-pool/release")
    def warm_model_pool_release(payload: WarmModelPoolReleaseRequest) -> dict[str, Any]:
        model = _local_workbench_service().admitted_model_for_warm_pool(payload.model_id)
        return _intake_call(
            lambda: _warm_model_pool_store().release(
                payload.model_dump(), worker=_warm_model_worker_from_record(model)
            )
        )

    @app.get("/api/runtime/warm-model-pool")
    def warm_model_pool_status(thermal_state: str = "unknown") -> dict[str, Any]:
        return _intake_call(lambda: _warm_model_pool_store().status(thermal_state=thermal_state))

    def _context_cache_store() -> ContextCacheStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        return ContextCacheStore(root)

    @app.post("/api/runtime/context-cache")
    def context_cache_put(payload: ContextCacheEntryRequest) -> dict[str, Any]:
        return _intake_call(lambda: _context_cache_store().put(payload.model_dump()))

    @app.post("/api/runtime/context-cache/invalidate")
    def context_cache_invalidate(payload: ContextCacheInvalidationRequest) -> dict[str, Any]:
        return _intake_call(lambda: _context_cache_store().invalidate(payload.model_dump()))

    @app.get("/api/runtime/context-cache")
    def context_cache_status() -> dict[str, Any]:
        return _intake_call(lambda: _context_cache_store().status())

    @app.get("/api/runtime/context-cache/{cache_id}")
    def context_cache_get(cache_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _context_cache_store().get(cache_id))

    @app.get("/api/runtime/context-cache/{cache_id}/sources/{source_id}")
    def context_cache_source(cache_id: str, source_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _context_cache_store().source(cache_id, source_id))

    def _speculative_retrieval_store() -> SpeculativeRetrievalStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        return SpeculativeRetrievalStore(root)

    @app.post("/api/runtime/speculative-retrieval")
    def speculative_retrieval_stage(payload: SpeculativeRetrievalRequest) -> dict[str, Any]:
        def retrieve_local(query: str) -> list[dict[str, Any]]:
            response = _retrieve_official_authority(query, limit=5)
            return [item.to_dict() for item in response.results]

        return _intake_call(
            lambda: _speculative_retrieval_store().stage(
                payload.model_dump(), retriever=retrieve_local
            )
        )

    @app.get("/api/runtime/speculative-retrieval/{preview_id}")
    def speculative_retrieval_get(preview_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _speculative_retrieval_store().get(preview_id))

    @app.get("/api/runtime/speculative-retrieval/{preview_id}/candidates/{source_id}")
    def speculative_retrieval_candidate(preview_id: str, source_id: str) -> dict[str, Any]:
        return _intake_call(
            lambda: _speculative_retrieval_store().candidate(preview_id, source_id)
        )

    @app.post("/api/runtime/speculative-retrieval/{preview_id}/discard")
    def speculative_retrieval_discard(preview_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _speculative_retrieval_store().discard(preview_id))

    def _context_budget_store() -> ContextBudgetStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        return ContextBudgetStore(root)

    @app.post("/api/runtime/context-budgets")
    def context_budget_create(payload: ContextBudgetRequest) -> dict[str, Any]:
        return _intake_call(lambda: _context_budget_store().create(payload.model_dump()))

    @app.get("/api/runtime/context-budgets/{budget_id}")
    def context_budget_get(budget_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _context_budget_store().get(budget_id))

    @app.get("/api/runtime/context-budgets/{budget_id}/sources/{source_id}")
    def context_budget_source(budget_id: str, source_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _context_budget_store().source(budget_id, source_id))

    def _batch_inference_scheduler() -> BatchInferenceScheduler:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        return BatchInferenceScheduler(root, kernel=get_runtime_kernel(), matter_id=_case_id(root))

    @app.post("/api/runtime/batch-inference")
    def batch_inference_schedule(payload: BatchInferenceScheduleRequest) -> dict[str, Any]:
        return _intake_call(lambda: _batch_inference_scheduler().create(payload.model_dump()))

    @app.get("/api/runtime/batch-inference/{batch_id}")
    def batch_inference_get(batch_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _batch_inference_scheduler().get(batch_id))

    @app.get("/api/runtime/batch-inference/{batch_id}/items/{item_id}/source")
    def batch_inference_source(batch_id: str, item_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _batch_inference_scheduler().source(batch_id, item_id))

    @app.post("/api/runtime/batch-inference/{batch_id}/items/{item_id}/cancel")
    def batch_inference_cancel(batch_id: str, item_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _batch_inference_scheduler().cancel_item(batch_id, item_id))

    def _low_memory_mode_store() -> LowMemoryModeStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        return LowMemoryModeStore(root)

    @app.get("/api/runtime/low-memory-mode")
    def low_memory_mode_status() -> dict[str, Any]:
        return _intake_call(lambda: _low_memory_mode_store().status())

    @app.put("/api/runtime/low-memory-mode")
    def low_memory_mode_set(payload: LowMemoryModeRequest) -> dict[str, Any]:
        return _intake_call(lambda: _low_memory_mode_store().set_active(payload.model_dump()))

    def _runtime_crash_recovery() -> RuntimeCrashRecovery:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        return RuntimeCrashRecovery(get_runtime_kernel(), matter_id=_case_id(root))

    @app.post("/api/runtime/crash-recovery")
    def runtime_crash_recovery_run() -> dict[str, Any]:
        return _runtime_crash_recovery().recover()

    @app.get("/api/runtime/crash-recovery/jobs/{job_id}")
    def runtime_crash_recovery_job(job_id: str) -> dict[str, Any]:
        try:
            return _runtime_crash_recovery().job(job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="runtime_recovery_job_not_found") from None

    @app.get("/api/command-bar/search")
    def command_bar_search(q: str = "", limit: int = 30) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            return search_command_bar(q, matter=None, records=[], sources=[], drafts=[], limit=limit)
        records = []
        for row in _review_records(case_root)[:200]:
            record_id = str(row.get("evidence_id") or row.get("source_id") or "").strip()
            if not record_id:
                continue
            records.append({
                "evidence_id": record_id,
                "title": str(row.get("title") or row.get("safe_filename") or record_id),
                "source_token": _record_open_token(case_root, record_id, str(row.get("source_locator") or row.get("title") or "")),
            })
        try:
            drafts = list((_outline_store(case_root).outlines().get("outlines") or []))[:100]
        except Exception:
            drafts = []
        try:
            retrieval = _retrieve_official_authority(q, limit=8)
            sources = [item.to_dict() for item in retrieval.results]
        except Exception:
            sources = []
        return search_command_bar(
            q,
            matter={"case_id": _case_id(case_root), "label": "Active local matter"},
            records=records,
            sources=sources,
            drafts=drafts,
            limit=limit,
        )

    @app.get("/api/matter-search")
    def matter_search(q: str = "", limit: int = 100) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            return {"status": "blocked", "blockers": ["active_matter_unavailable"], "results": [], "review_required": True}
        results = unified_matter_search(q, _review_records(case_root), limit=limit)
        for row in results.get("results") or []:
            record_id = str(row.get("record_id") or "")
            source = next((item for item in _review_records(case_root) if str(item.get("evidence_id") or item.get("source_id") or "") == record_id), None)
            if source is not None:
                row["source_token"] = _record_open_token(case_root, record_id, str(source.get("source_locator") or source.get("title") or ""))
        return results

    def _smart_view_store() -> SmartViewStore:
        root = active_case_root()
        if root is None: raise HTTPException(status_code=409, detail="no_active_matter")
        return SmartViewStore(root)

    @app.post("/api/smart-views")
    def smart_view_create(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _smart_view_store().create(payload))

    @app.get("/api/smart-views")
    def smart_view_list() -> dict[str, Any]:
        return _intake_call(lambda: _smart_view_store().list())

    @app.get("/api/smart-views/{view_id}/run")
    def smart_view_run(view_id: str) -> dict[str, Any]:
        root=active_case_root()
        if root is None: raise HTTPException(status_code=409, detail="no_active_matter")
        result=_intake_call(lambda: _smart_view_store().run(view_id,_review_records(root)))
        for row in result.get("results") or []:
            rid=str(row.get("record_id") or "")
            source=next((item for item in _review_records(root) if str(item.get("evidence_id") or item.get("source_id") or "")==rid),None)
            if source: row['source_token']=_record_open_token(root,rid,str(source.get('source_locator') or source.get('title') or ''))
        return result

    def _recent_work_store() -> RecentWorkStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        return RecentWorkStore(root)

    @app.put("/api/recent-work")
    def recent_work_save(payload: dict[str, Any]) -> dict[str, Any]:
        """Save only an encrypted, active-matter UI restore point."""
        return _intake_call(lambda: _recent_work_store().save(payload))

    @app.get("/api/recent-work")
    def recent_work_get(workspace_id: str = "chat") -> dict[str, Any]:
        return _intake_call(lambda: _recent_work_store().get(workspace_id))

    @app.delete("/api/recent-work")
    def recent_work_clear(workspace_id: str = "chat") -> dict[str, Any]:
        return _intake_call(lambda: _recent_work_store().clear(workspace_id))

    @app.get("/api/recent-work/{workspace_id}/sources/{index}")
    def recent_work_source(workspace_id: str, index: int) -> dict[str, Any]:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        result = _intake_call(lambda: _recent_work_store().source(workspace_id, index))
        source = dict(result.get("source") or {})
        if source.get("lane") != "private_matter_record":
            return result
        record_id = str(source.get("record_id") or "")
        source_hash = str(source.get("source_hash") or "").casefold()
        record = next(
            (
                row for row in _review_records(root)
                if str(row.get("evidence_id") or row.get("source_id") or "") == record_id
                and str(row.get("source_hash") or row.get("sha256") or "").casefold() == source_hash
            ),
            None,
        )
        if record is None:
            raise HTTPException(status_code=404, detail="recent_work_source_not_in_active_matter")
        source["source_token"] = _record_open_token(
            root, record_id, str(record.get("source_locator") or record.get("title") or "")
        )
        result["source"] = source
        return result

    def _workspace_tabs_store() -> WorkspaceTabsStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        return WorkspaceTabsStore(root)

    def _workspace_tab_record_is_active(root: Path, target: dict[str, Any]) -> dict[str, Any]:
        record_id = str(target.get("record_id") or "")
        source_hash = str(target.get("source_hash") or "").casefold()
        record = next(
            (
                row for row in _review_records(root)
                if str(row.get("evidence_id") or row.get("source_id") or "") == record_id
                and str(row.get("source_hash") or row.get("sha256") or "").casefold() == source_hash
            ),
            None,
        )
        if record is None:
            raise HTTPException(status_code=404, detail="workspace_tab_record_not_in_active_matter")
        return record

    @app.post("/api/workspace-tabs")
    def workspace_tab_create(payload: dict[str, Any]) -> dict[str, Any]:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        if str(payload.get("kind") or "").strip().casefold() == "record":
            target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
            _workspace_tab_record_is_active(root, target)
        return _intake_call(lambda: _workspace_tabs_store().create(payload))

    @app.get("/api/workspace-tabs")
    def workspace_tab_list() -> dict[str, Any]:
        return _intake_call(lambda: _workspace_tabs_store().list())

    @app.post("/api/workspace-tabs/{tab_id}/activate")
    def workspace_tab_activate(tab_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _workspace_tabs_store().activate(tab_id))

    @app.delete("/api/workspace-tabs/{tab_id}")
    def workspace_tab_close(tab_id: str) -> dict[str, Any]:
        return _intake_call(lambda: _workspace_tabs_store().close(tab_id))

    @app.get("/api/workspace-tabs/{tab_id}/target")
    def workspace_tab_target(tab_id: str) -> dict[str, Any]:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        result = _intake_call(lambda: _workspace_tabs_store().target(tab_id))
        tab = dict(result.get("tab") or {})
        target = dict(result.get("target") or {})
        if tab.get("kind") == "record":
            record = _workspace_tab_record_is_active(root, target)
            target["source_token"] = _record_open_token(
                root,
                str(target.get("record_id") or ""),
                str(record.get("source_locator") or record.get("title") or ""),
            )
        result["target"] = target
        return result

    def _command_history_store() -> CommandHistoryStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        return CommandHistoryStore(root)

    @app.post("/api/command-history")
    def command_history_record(payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _command_history_store().record(payload))

    @app.get("/api/command-history")
    def command_history_list() -> dict[str, Any]:
        return _intake_call(lambda: _command_history_store().list())

    @app.post("/api/command-history/{command_id}/replay")
    def command_history_replay(command_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        replay = _intake_call(
            lambda: _command_history_store().replay(command_id, reconfirmed=bool((payload or {}).get("reconfirmed", False)))
        )
        if not replay.get("execute"):
            return replay
        command = dict(replay.get("command") or {})
        params = dict(command.get("parameters") or {})
        operation = str(command.get("operation") or "")
        if operation == "matter_search":
            result = unified_matter_search(str(params.get("query") or ""), _review_records(root))
            for row in result.get("results") or []:
                record_id = str(row.get("record_id") or "")
                source = next((item for item in _review_records(root) if str(item.get("evidence_id") or item.get("source_id") or "") == record_id), None)
                if source is not None:
                    row["source_token"] = _record_open_token(root, record_id, str(source.get("source_locator") or source.get("title") or ""))
            replay["result"] = result
        elif operation == "authority_search":
            authority = _retrieve_official_authority(str(params.get("query") or ""), limit=20)
            replay["result"] = {
                "status": "pass",
                "sources": [item.to_dict() for item in authority.results],
                "review_required": True,
                "local_only": True,
                "network_used": False,
            }
        elif operation == "smart_view_run":
            result = _smart_view_store().run(str(params.get("view_id") or ""), _review_records(root))
            for row in result.get("results") or []:
                record_id = str(row.get("record_id") or "")
                source = next((item for item in _review_records(root) if str(item.get("evidence_id") or item.get("source_id") or "") == record_id), None)
                if source is not None:
                    row["source_token"] = _record_open_token(root, record_id, str(source.get("source_locator") or source.get("title") or ""))
            replay["result"] = result
        else:
            raise HTTPException(status_code=409, detail="command_history_replay_not_allowed")
        return replay

    def _bulk_review_queue_store() -> BulkReviewQueueStore:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        return BulkReviewQueueStore(root)

    def _bulk_review_source_in_active_matter(root: Path, source: dict[str, Any]) -> dict[str, Any]:
        record_id = str(source.get("record_id") or "")
        source_hash = str(source.get("source_hash") or "").casefold()
        record = next((row for row in _review_records(root) if str(row.get("evidence_id") or row.get("source_id") or "") == record_id and str(row.get("source_hash") or row.get("sha256") or "").casefold() == source_hash), None)
        if record is None:
            raise HTTPException(status_code=404, detail="bulk_review_source_not_in_active_matter")
        return record

    @app.post("/api/bulk-review-queue")
    def bulk_review_create(payload: dict[str, Any]) -> dict[str, Any]:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        source = payload.get("source_ref") if isinstance(payload.get("source_ref"), dict) else {}
        _bulk_review_source_in_active_matter(root, source)
        return _intake_call(lambda: _bulk_review_queue_store().create(payload))

    @app.get("/api/bulk-review-queue")
    def bulk_review_list() -> dict[str, Any]:
        return _intake_call(lambda: _bulk_review_queue_store().list())

    @app.post("/api/bulk-review-queue/{item_id}/triage")
    def bulk_review_triage(item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return _intake_call(lambda: _bulk_review_queue_store().triage(item_id, payload))

    @app.get("/api/bulk-review-queue/{item_id}/source")
    def bulk_review_source(item_id: str) -> dict[str, Any]:
        root = active_case_root()
        if root is None:
            raise HTTPException(status_code=409, detail="no_active_matter")
        result = _intake_call(lambda: _bulk_review_queue_store().source(item_id))
        source = dict(result.get("source") or {})
        record = _bulk_review_source_in_active_matter(root, source)
        source["source_token"] = _record_open_token(root, str(source.get("record_id") or ""), str(record.get("source_locator") or record.get("title") or ""))
        result["source"] = source
        return result

    def _favorites_store() -> FavoritesStore:
        root = active_case_root()
        if root is None: raise HTTPException(status_code=409, detail="no_active_matter")
        return FavoritesStore(root)

    @app.post("/api/favorites")
    def favorite_create(payload: dict[str, Any]) -> dict[str, Any]:
        root = active_case_root()
        if root is None: raise HTTPException(status_code=409, detail="no_active_matter")
        if str(payload.get("kind") or "").strip().casefold() == "record":
            target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
            _workspace_tab_record_is_active(root, target)
        return _intake_call(lambda: _favorites_store().create(payload))

    @app.get("/api/favorites")
    def favorite_list(viewer_role: str = "other_reviewer") -> dict[str, Any]:
        return _intake_call(lambda: _favorites_store().list(viewer_role))

    @app.get("/api/favorites/{favorite_id}")
    def favorite_get(favorite_id: str, viewer_role: str = "other_reviewer") -> dict[str, Any]:
        return _intake_call(lambda: _favorites_store().get(favorite_id, viewer_role))

    @app.delete("/api/favorites/{favorite_id}")
    def favorite_remove(favorite_id: str, owner_role: str = "other_reviewer") -> dict[str, Any]:
        return _intake_call(lambda: _favorites_store().remove(favorite_id, owner_role))

    @app.get("/api/favorites/{favorite_id}/open")
    def favorite_open(favorite_id: str, viewer_role: str = "other_reviewer") -> dict[str, Any]:
        root = active_case_root()
        if root is None: raise HTTPException(status_code=409, detail="no_active_matter")
        result = _intake_call(lambda: _favorites_store().get(favorite_id, viewer_role))
        favorite = dict(result.get("favorite") or {})
        target = dict(result.get("target") or {})
        if favorite.get("kind") == "record":
            record = _workspace_tab_record_is_active(root, target)
            target["source_token"] = _record_open_token(root, str(target.get("record_id") or ""), str(record.get("source_locator") or record.get("title") or ""))
        result["target"] = target
        return result

    def _user_labels_store() -> UserLabelsStore:
        root = active_case_root()
        if root is None: raise HTTPException(status_code=409, detail="no_active_matter")
        return UserLabelsStore(root)

    @app.post("/api/user-labels")
    def user_label_create(payload: dict[str, Any]) -> dict[str, Any]: return _intake_call(lambda: _user_labels_store().create(payload))

    @app.get("/api/user-labels")
    def user_label_list() -> dict[str, Any]: return _intake_call(lambda: _user_labels_store().list())

    @app.post("/api/user-labels/{label_id}/assignments")
    def user_label_assign(label_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        root=active_case_root()
        if root is None: raise HTTPException(status_code=409, detail="no_active_matter")
        _workspace_tab_record_is_active(root,payload)
        return _intake_call(lambda: _user_labels_store().assign(label_id,payload))

    @app.post("/api/user-labels/export")
    def user_label_export(payload: dict[str, Any]) -> dict[str, Any]: return _intake_call(lambda: _user_labels_store().export(payload))

    @app.post("/api/user-labels/import")
    def user_label_import(payload: dict[str, Any]) -> dict[str, Any]: return _intake_call(lambda: _user_labels_store().import_export(payload))

    def _daily_matter_brief_store() -> DailyMatterBriefStore:
        root=active_case_root()
        if root is None: raise HTTPException(status_code=409,detail="no_active_matter")
        return DailyMatterBriefStore(root)

    @app.post("/api/daily-matter-briefs")
    def daily_matter_brief_build(payload:dict[str,Any])->dict[str,Any]:
        root=active_case_root()
        if root is None: raise HTTPException(status_code=409,detail="no_active_matter")
        return _intake_call(lambda:_daily_matter_brief_store().build(payload,_review_records(root)))

    @app.get("/api/daily-matter-briefs/{brief_id}")
    def daily_matter_brief_get(brief_id:str)->dict[str,Any]:return _intake_call(lambda:_daily_matter_brief_store().get(brief_id))

    def _venue_location_store(case_root: Path) -> VenueLocationNavigatorStore:
        return VenueLocationNavigatorStore(case_root)

    @app.post("/api/venue-location-workspaces")
    def venue_location_workspace_create(payload: VenueLocationWorkspaceRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            authority = dict(drafting_outline_authority_candidate(payload.authority_source_id).get("candidate") or {})
            workspace = _venue_location_store(case_root).create(payload.model_dump(), authority=authority)
            return {"status":"pass","workspace":workspace,"review_required":True,"filing_ready":False}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/venue-location-workspaces/{workspace_id}")
    def venue_location_workspace_get(workspace_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _venue_location_store(case_root).workspaces(workspace_id)
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/venue-location-workspaces/{workspace_id}/authority/source")
    def venue_location_workspace_source(workspace_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _venue_location_store(case_root).source(workspace_id)
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    def _post_filing_store(case_root: Path) -> PostFilingReconciliationStore:
        return PostFilingReconciliationStore(case_root)

    @app.post("/api/post-filing-reconciliations")
    def post_filing_reconciliation_create(payload: PostFilingReconciliationRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            result = _post_filing_store(case_root).create(payload.model_dump(), records=_review_records(case_root))
            return {"status":"pass","reconciliation":result,"review_required":True,"filing_ready":False}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/post-filing-reconciliations/{reconciliation_id}")
    def post_filing_reconciliation_get(reconciliation_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            return _post_filing_store(case_root).get(reconciliation_id)
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    @app.get("/api/post-filing-reconciliations/{reconciliation_id}/sources/{record_id}")
    def post_filing_reconciliation_source(reconciliation_id: str, record_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            payload = _post_filing_store(case_root).source(reconciliation_id, record_id)
            source = dict(payload.get("source") or {})
            row = next((item for item in _review_records(case_root) if str(item.get("evidence_id") or item.get("source_id") or "") == str(source.get("record_id") or "")), None)
            if row is None or str(row.get("source_hash") or row.get("sha256") or "").casefold() != str(source.get("source_hash") or "").casefold():
                raise IntakeWorkbenchError("post_filing_source_not_in_active_matter", 404)
            source["source_token"] = _record_open_token(case_root, str(source.get("record_id") or ""), str(row.get("source_locator") or row.get("title") or ""))
            return {**payload, "source": source, "review_required": True}
        except IntakeWorkbenchError as exc:
            _raise_outline_error(exc)

    def _raise_sentence_support_error(exc: IntakeWorkbenchError) -> None:
        raise HTTPException(status_code=int(exc.status_code), detail=exc.code) from None

    def _sentence_support_store(case_root: Path) -> SentenceSupportMapStore:
        return SentenceSupportMapStore(case_root)

    def _mark_sentence_map_revision(payload: dict[str, Any], document: dict[str, Any]) -> dict[str, Any]:
        current_revision_id = str(document.get("current_revision_id") or "")
        def mark(row: dict[str, Any]) -> dict[str, Any]:
            value = dict(row)
            value["current_document_revision_id"] = current_revision_id
            value["current_revision_match"] = bool(current_revision_id) and str(value.get("revision_id") or "") == current_revision_id
            value["stale_for_current_draft"] = not value["current_revision_match"]
            value["review_required"] = True
            return value
        result = dict(payload)
        if isinstance(result.get("map"), dict):
            result["map"] = mark(dict(result["map"]))
        if isinstance(result.get("maps"), list):
            result["maps"] = [mark(dict(row)) for row in result["maps"] if isinstance(row, dict)]
        return result

    @app.post("/api/drafting/documents/{document_id}/sentence-support-maps")
    def drafting_sentence_support_create(
        document_id: str, payload: SentenceSupportMapRequest
    ) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            document = get_workspace_document(case_root, document_id)
            value = payload.model_dump()
            value["selected_authority"] = [
                _resolver_verified_drafting_authority(item, workflow="sentence_support")
                for item in list(value.get("selected_authority") or [])
            ]
            result = _sentence_support_store(case_root).create_map(
                value, document=document, records=_review_records(case_root)
            )
            return _mark_sentence_map_revision({"status": "pass", "map": result, "review_required": True, "filing_ready": False}, document)
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)
        except IntakeWorkbenchError as exc:
            _raise_sentence_support_error(exc)

    @app.get("/api/drafting/documents/{document_id}/sentence-support-maps")
    def drafting_sentence_support_list(document_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            document = get_workspace_document(case_root, document_id)
            return _mark_sentence_map_revision(_sentence_support_store(case_root).maps(str(document.get("document_id") or document_id)), document)
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)
        except IntakeWorkbenchError as exc:
            _raise_sentence_support_error(exc)

    @app.get("/api/drafting/documents/{document_id}/sentence-support-maps/{map_id}")
    def drafting_sentence_support_get(document_id: str, map_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            document = get_workspace_document(case_root, document_id)
            return _mark_sentence_map_revision(_sentence_support_store(case_root).maps(str(document.get("document_id") or document_id), map_id), document)
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)
        except IntakeWorkbenchError as exc:
            _raise_sentence_support_error(exc)

    @app.get("/api/drafting/documents/{document_id}/sentence-support-maps/{map_id}/sentences/{sentence_id}/{lane}/{card_index}/source")
    def drafting_sentence_support_source(
        document_id: str, map_id: str, sentence_id: str, lane: str, card_index: int
    ) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            document = get_workspace_document(case_root, document_id)
            payload = _sentence_support_store(case_root).sentence_source(
                str(document.get("document_id") or document_id), map_id, sentence_id, lane, card_index
            )
            source = dict(payload.get("source") or {})
            if source.get("lane") == "private_matter_record":
                record_id = str(source.get("record_id") or "")
                source_hash = str(source.get("source_hash") or "").casefold()
                row = next((item for item in _review_records(case_root) if str(item.get("evidence_id") or "") == record_id), None)
                if row is None or str(row.get("source_hash") or row.get("sha256") or "").casefold() != source_hash:
                    raise IntakeWorkbenchError("sentence_support_record_not_in_active_matter", 404)
                locator = str(row.get("source_locator") or row.get("title") or record_id)
                source["source_token"] = _record_open_token(case_root, record_id, locator)
            else:
                source["source_token"] = ""
            return {**payload, "source": source, "review_required": True}
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)
        except IntakeWorkbenchError as exc:
            _raise_sentence_support_error(exc)

    def _citation_insertion_store(case_root: Path) -> CitationInsertionStore:
        return CitationInsertionStore(case_root)

    @app.post("/api/drafting/documents/{document_id}/citation-insertions")
    def drafting_citation_insertion_create(
        document_id: str, payload: CitationInsertionRequest
    ) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            document = get_workspace_document(case_root, document_id)
            value = payload.model_dump()
            value["authority"] = _resolver_verified_drafting_authority(
                value.get("authority"), workflow="citation_insertion"
            )
            receipt = _citation_insertion_store(case_root).create(value, document=document)
            return {"status": "pass", "receipt": receipt, "review_required": True, "filing_ready": False}
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)
        except IntakeWorkbenchError as exc:
            _raise_sentence_support_error(exc)

    @app.get("/api/drafting/documents/{document_id}/citation-insertions/{receipt_id}")
    def drafting_citation_insertion_get(document_id: str, receipt_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            document = get_workspace_document(case_root, document_id)
            receipt = _citation_insertion_store(case_root).receipt(str(document.get("document_id") or document_id), receipt_id)
            receipt["current_revision_match"] = str(receipt.get("revision_id") or "") == str(document.get("current_revision_id") or "")
            receipt["stale_for_current_draft"] = not receipt["current_revision_match"]
            return {"receipt": receipt, "review_required": True}
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)
        except IntakeWorkbenchError as exc:
            _raise_sentence_support_error(exc)

    @app.post("/api/drafting/documents/{document_id}/citation-insertions/{receipt_id}/propose")
    def drafting_citation_insertion_propose(document_id: str, receipt_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            document = get_workspace_document(case_root, document_id)
            receipt = _citation_insertion_store(case_root).receipt(str(document.get("document_id") or document_id), receipt_id)
            if str(receipt.get("revision_id") or "") != str(document.get("current_revision_id") or ""):
                raise IntakeWorkbenchError("citation_insertion_stale_for_current_draft", 409)
            proposal = propose_workspace_revision(
                case_root,
                str(document.get("document_id") or document_id),
                content=str(receipt.get("proposed_content") or ""),
                base_revision_id=str(document.get("current_revision_id") or ""),
                note=f"Source-bound citation insertion receipt {receipt_id}; explicit revision review remains required.",
            )
            return {"status": "proposal_ready", "receipt_id": receipt_id, "proposal": proposal, "review_required": True, "filing_ready": False, "original_preserved": True}
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)
        except IntakeWorkbenchError as exc:
            _raise_sentence_support_error(exc)

    def _quote_safe_store(case_root: Path) -> QuoteSafeDraftStore:
        return QuoteSafeDraftStore(case_root)

    @app.post("/api/drafting/documents/{document_id}/quote-receipts")
    def drafting_quote_safe_create(document_id: str, payload: QuoteSafeDraftRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            document = get_workspace_document(case_root, document_id)
            value = payload.model_dump()
            value["authority"] = _resolver_verified_drafting_authority(
                value.get("authority"), workflow="quote_safe"
            )
            return {"status": "pass", "receipt": _quote_safe_store(case_root).create(value, document=document), "review_required": True, "filing_ready": False}
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)
        except IntakeWorkbenchError as exc:
            _raise_sentence_support_error(exc)

    @app.post("/api/drafting/documents/{document_id}/quote-receipts/{receipt_id}/propose")
    def drafting_quote_safe_propose(document_id: str, receipt_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None:
            raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try:
            document = get_workspace_document(case_root, document_id)
            receipt = _quote_safe_store(case_root).receipt(str(document.get("document_id") or document_id), receipt_id)
            if str(receipt.get("revision_id") or "") != str(document.get("current_revision_id") or ""):
                raise IntakeWorkbenchError("quote_receipt_stale_for_current_draft", 409)
            proposal = propose_workspace_revision(case_root, str(document.get("document_id") or document_id), content=str(receipt.get("proposed_content") or ""), base_revision_id=str(document.get("current_revision_id") or ""), note=f"Quote-safe drafting receipt {receipt_id}; explicit revision review remains required.")
            return {"status": "proposal_ready", "receipt_id": receipt_id, "proposal": proposal, "original_preserved": True, "review_required": True, "filing_ready": False}
        except DocumentWorkspaceError as exc:
            _raise_workspace_error(exc)
        except IntakeWorkbenchError as exc:
            _raise_sentence_support_error(exc)

    def _requirement_profile_store(case_root: Path) -> DraftRequirementProfileStore:
        return DraftRequirementProfileStore(case_root)

    @app.post("/api/drafting/requirement-profiles")
    def drafting_requirement_profile_create(payload: DraftRequirementProfileRequest) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None: raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try: return {"status":"pass","profile":_requirement_profile_store(case_root).create(payload.model_dump()),"review_required":True,"filing_ready":False}
        except IntakeWorkbenchError as exc: _raise_sentence_support_error(exc)

    @app.get("/api/drafting/requirement-profiles")
    def drafting_requirement_profile_list() -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None: raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try: return _requirement_profile_store(case_root).profiles()
        except IntakeWorkbenchError as exc: _raise_sentence_support_error(exc)

    @app.post("/api/drafting/documents/{document_id}/requirement-profiles/{profile_id}/evaluate")
    def drafting_requirement_profile_evaluate(document_id: str, profile_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is None: raise HTTPException(status_code=404, detail="active_matter_unavailable")
        try: return _requirement_profile_store(case_root).evaluate(profile_id, get_workspace_document(case_root, document_id))
        except DocumentWorkspaceError as exc: _raise_workspace_error(exc)
        except IntakeWorkbenchError as exc: _raise_sentence_support_error(exc)

    @app.post("/api/drafting/documents/{document_id}/revision-rationales")
    def drafting_revision_rationale_record(document_id: str, payload: RevisionRationaleRequest) -> dict[str, Any]:
        case_root=active_case_root()
        if case_root is None: raise HTTPException(status_code=404,detail="active_matter_unavailable")
        try:return {"status":"pass","rationale":RevisionRationaleStore(case_root).record(payload.model_dump(),document=get_workspace_document(case_root,document_id)),"review_required":True,"filing_ready":False}
        except DocumentWorkspaceError as exc:_raise_workspace_error(exc)
        except IntakeWorkbenchError as exc:_raise_sentence_support_error(exc)

    @app.get("/api/drafting/documents/{document_id}/revision-rationales")
    def drafting_revision_rationale_list(document_id: str) -> dict[str, Any]:
        case_root=active_case_root()
        if case_root is None: raise HTTPException(status_code=404,detail="active_matter_unavailable")
        try:
            document=get_workspace_document(case_root,document_id);return RevisionRationaleStore(case_root).list(str(document.get("document_id") or document_id))
        except DocumentWorkspaceError as exc:_raise_workspace_error(exc)
        except IntakeWorkbenchError as exc:_raise_sentence_support_error(exc)

    @app.post("/api/drafting/documents/{document_id}/dual-views")
    def drafting_dual_view_create(document_id: str,payload:DualViewRequest)->dict[str,Any]:
        root=active_case_root()
        if root is None:raise HTTPException(status_code=404,detail="active_matter_unavailable")
        try:return {"status":"pass","view":DualViewStore(root).create(payload.model_dump(),get_workspace_document(root,document_id)),"review_required":True,"filing_ready":False}
        except DocumentWorkspaceError as exc:_raise_workspace_error(exc)
        except IntakeWorkbenchError as exc:_raise_sentence_support_error(exc)

    @app.get("/api/drafting/documents/{document_id}/dual-views/{view_id}")
    def drafting_dual_view_get(document_id:str,view_id:str)->dict[str,Any]:
        root=active_case_root()
        if root is None:raise HTTPException(status_code=404,detail="active_matter_unavailable")
        try:
            d=get_workspace_document(root,document_id);return {"view":DualViewStore(root).get(str(d.get('document_id') or document_id),view_id,str(d.get('current_revision_id') or '')),"review_required":True}
        except DocumentWorkspaceError as exc:_raise_workspace_error(exc)
        except IntakeWorkbenchError as exc:_raise_sentence_support_error(exc)

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
                    **_artifact_capability_binding(
                        resource_type="ga_shipment_artifact",
                        resource_id=f"{result.get('generation_id')}:{filename}",
                    ),
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
        if (
            not binding
            or binding.get("scope") != _ga_shipment_scope(store)
            or not _artifact_capability_allowed(binding, resource_type="ga_shipment_artifact")
        ):
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
