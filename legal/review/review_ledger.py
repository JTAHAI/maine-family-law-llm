"""Revision-bound, append-only human review ledger.

A reviewer decision is bound to the current document revision, the deterministic
Maine-authority verification report, the local fact-to-record mapping, and the
filing-gate preflight.  Review completion cannot override a failed gate.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import uuid
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path, PureWindowsPath
from typing import Any, Iterable

from legal.documents.workspace import get_document, workspace_paths
from legal.drafting.filing_ready_gate import FilingReadyGate
from legal.drafting.findings_engine import Rule52BestInterestFindingsEngine
from .procedure_intelligence import build_form_freshness_report, build_procedure_posture_report

REVIEW_FOLDER = "reviews"
SCHEMA_VERSION = "document_review_ledger_v2"
MAX_FACTS = 128
MAX_FACT_CHARS = 2_000
MAX_NOTE_CHARS = 4_000
MAX_DECISIONS = 500
MAX_PENDING_REQUESTS = 50
MAX_CLAIMS = 256
MAX_ANNOTATION_NOTE_CHARS = 2_000
MAX_ANNOTATION_SOURCES = 20
MAX_FILE_BYTES = 32 * 1024 * 1024
ALLOWED_DECISIONS = {"approve_review", "request_changes", "reject"}
ALLOWED_ROLES = {"attorney", "paralegal", "advocate", "self_represented", "other_reviewer"}
ALLOWED_CLAIM_ANNOTATIONS = {"accepted", "not_material", "needs_revision", "unsupported", "contradicted", "needs_authority", "needs_fact_support"}
BLOCKING_CLAIM_ANNOTATIONS = {"needs_revision", "unsupported", "contradicted", "needs_authority", "needs_fact_support"}
_ID_RE = re.compile(r"^[a-f0-9]{32}$")
_TOKEN_RE = re.compile(r"^[a-f0-9]{64}$")
_LOCK = threading.RLock()


class ReviewLedgerError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha(payload: Any) -> str:
    data = payload if isinstance(payload, bytes) else _canonical(payload)
    return hashlib.sha256(data).hexdigest()


def _validate_id(value: str, label: str) -> str:
    candidate = str(value or "").strip().lower()
    if not _ID_RE.fullmatch(candidate):
        raise ReviewLedgerError(f"invalid_{label}", f"Invalid {label}.", status_code=404)
    return candidate


def _safe_text(value: Any, limit: int) -> str:
    return str(value or "").replace("\x00", "").strip()[:limit]




def _synchronized(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        with _LOCK:
            return func(*args, **kwargs)

    return wrapped


def _safe_basename(value: Any) -> str:
    raw = _safe_text(value, 1_000)
    if "\\" in raw:
        return PureWindowsPath(raw).name
    return Path(raw).name


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    if path.exists() and path.is_symlink():
        raise ReviewLedgerError("review_symlink_refused", "A review-ledger symlink was refused.", status_code=409)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp = path.parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
    data = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")
    try:
        with temp.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _read(path: Path) -> dict[str, Any]:
    if not path.exists() or path.is_symlink():
        raise ReviewLedgerError("review_record_not_found", "The review record was not found.", status_code=404)
    raw = path.read_bytes()
    if len(raw) > MAX_FILE_BYTES:
        raise ReviewLedgerError("review_record_too_large", "The review record is unexpectedly large.", status_code=409)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewLedgerError("review_record_invalid", "The review record is invalid.", status_code=409) from exc
    if not isinstance(payload, dict):
        raise ReviewLedgerError("review_record_invalid", "The review record is invalid.", status_code=409)
    return payload


def _roots(case_root: Path, document_id: str) -> tuple[Path, Path, Path]:
    paths = workspace_paths(case_root)
    document_id = _validate_id(document_id, "document_id")
    root = paths.root / REVIEW_FOLDER / document_id
    resolved_parent = root.parent.resolve(strict=False)
    resolved_workspace = paths.root.resolve(strict=True)
    if resolved_parent != resolved_workspace / REVIEW_FOLDER and resolved_workspace not in resolved_parent.parents:
        raise ReviewLedgerError("review_path_escape", "The review ledger escaped the workspace.", status_code=409)
    requests = root / "requests"
    decisions = root / "decisions"
    for folder in (root, requests, decisions):
        if folder.exists() and folder.is_symlink():
            raise ReviewLedgerError("review_symlink_refused", "A review-ledger symlink was refused.", status_code=409)
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root, requests, decisions


def _normalize_facts(facts: Iterable[str] | None) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for raw in facts or []:
        value = " ".join(_safe_text(raw, MAX_FACT_CHARS).split())
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            rows.append(value)
        if len(rows) >= MAX_FACTS:
            break
    return rows


def _record_text(row: dict[str, Any]) -> str:
    for key in ("text_excerpt", "snippet", "text", "derived_text", "content"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _tokens(text: str) -> set[str]:
    stop = {"a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is", "it", "of", "on", "or", "that", "the", "to", "was", "were", "with"}
    return {token for token in re.findall(r"[a-z0-9]+", text.casefold()) if token not in stop}


def build_fact_evidence_report(facts: Iterable[str] | None, records: Iterable[dict[str, Any]] | None) -> dict[str, Any]:
    """Map asserted facts to bounded, already-indexed private-record text.

    The result is a review aid. A private record can support that text appears in
    a record, but it does not prove authenticity, credibility, intent, or a legal
    conclusion.
    """
    normalized_facts = _normalize_facts(facts)
    safe_records: list[dict[str, Any]] = []
    for raw in records or []:
        if not isinstance(raw, dict):
            continue
        evidence_id = _safe_text(raw.get("evidence_id"), 256)
        text = _record_text(raw)
        if not evidence_id or not text:
            continue
        safe_records.append({
            "evidence_id": evidence_id,
            "title": _safe_text(raw.get("title") or raw.get("subject") or evidence_id, 300),
            "source_locator": _safe_basename(raw.get("source_locator") or raw.get("source_path")),
            "source_hash": _safe_text(raw.get("source_hash"), 128),
            "page_number": int(raw.get("page_number") or 0),
            "text": text[:200_000],
        })
        if len(safe_records) >= 10_000:
            break

    mappings: list[dict[str, Any]] = []
    for index, fact in enumerate(normalized_facts):
        fact_tokens = _tokens(fact)
        candidates: list[dict[str, Any]] = []
        for record in safe_records:
            text = record["text"]
            exact_start = text.casefold().find(fact.casefold())
            overlap = len(fact_tokens & _tokens(text)) / max(len(fact_tokens), 1) if fact_tokens else 0.0
            if exact_start < 0 and overlap < 0.45:
                continue
            start = exact_start if exact_start >= 0 else max(0, text.casefold().find(next(iter(sorted(fact_tokens)), "")))
            if start < 0:
                start = 0
            end = min(len(text), start + max(len(fact), 240))
            candidates.append({
                "evidence_id": record["evidence_id"],
                "title": record["title"],
                "source_locator": record["source_locator"],
                "source_hash": record["source_hash"],
                "page_number": record["page_number"],
                "span_start": start,
                "span_end": end,
                "text": text[start:end],
                "match_type": "exact" if exact_start >= 0 else "lexical_overlap",
                "confidence": 1.0 if exact_start >= 0 else round(overlap, 3),
            })
        candidates.sort(key=lambda item: (-float(item["confidence"]), str(item["evidence_id"])))
        mappings.append({
            "fact_id": f"fact-{index + 1:03d}",
            "fact": fact,
            "status": "record_text_found" if candidates else "unsupported",
            "supporting_records": candidates[:10],
            "review_required": True,
            "does_not_prove": "Record text does not by itself prove authenticity, credibility, intent, contempt, or another legal conclusion.",
        })
    return {
        "schema_version": "fact_evidence_review_v1",
        "facts": mappings,
        "fact_count": len(mappings),
        "supported_count": sum(1 for item in mappings if item["status"] == "record_text_found"),
        "unsupported_count": sum(1 for item in mappings if item["status"] != "record_text_found"),
        "records_considered": len(safe_records),
        "review_required": True,
    }




def _claim_rows(authority_result: dict[str, Any]) -> list[dict[str, Any]]:
    verification = authority_result.get("verification_report") or {}
    raw_claims = verification.get("claims") or authority_result.get("claims") or []
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_claims):
        if isinstance(raw, str):
            raw = {"statement": raw}
        if not isinstance(raw, dict):
            continue
        statement = _safe_text(raw.get("statement") or raw.get("claim") or raw.get("text"), MAX_FACT_CHARS)
        if not statement:
            continue
        claim_id = _safe_text(raw.get("claim_id") or raw.get("id"), 128) or f"claim-{index + 1:03d}"
        claim_id = re.sub(r"[^A-Za-z0-9_.:-]+", "-", claim_id).strip("-")[:128] or f"claim-{index + 1:03d}"
        if claim_id in seen:
            claim_id = f"{claim_id}-{index + 1}"
        seen.add(claim_id)
        rows.append({
            "claim_id": claim_id,
            "statement": statement,
            "support_status": _safe_text(raw.get("support_status") or raw.get("status"), 80) or "unverified",
            "claim_type": _safe_text(raw.get("claim_type"), 80) or "legal",
            "material": bool(raw.get("material", True)),
            "source_ids": [
                _safe_text(value, 256)
                for value in (raw.get("source_ids") or raw.get("source_refs") or [])[:MAX_ANNOTATION_SOURCES]
                if _safe_text(value, 256)
            ],
        })
        if len(rows) >= MAX_CLAIMS:
            break
    return rows


def _normalize_claim_annotations(annotations: Iterable[dict[str, Any]] | None, claim_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    allowed_ids = {str(row.get("claim_id")) for row in claim_rows}
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    blockers: list[str] = []
    for raw in annotations or []:
        if not isinstance(raw, dict):
            continue
        claim_id = _safe_text(raw.get("claim_id"), 128)
        if claim_id not in allowed_ids:
            raise ReviewLedgerError("unknown_review_claim", f"The review annotation references an unknown claim: {claim_id or 'missing' }.", status_code=409)
        if claim_id in seen:
            raise ReviewLedgerError("duplicate_review_claim_annotation", f"The claim was annotated more than once: {claim_id}.", status_code=409)
        status = str(raw.get("status") or "").strip().lower()
        if status not in ALLOWED_CLAIM_ANNOTATIONS:
            raise ReviewLedgerError("invalid_claim_annotation_status", f"Unsupported claim annotation status for {claim_id}.")
        seen.add(claim_id)
        row = {
            "claim_id": claim_id,
            "status": status,
            "note": _safe_text(raw.get("note"), MAX_ANNOTATION_NOTE_CHARS),
            "source_ids": [
                _safe_text(value, 256)
                for value in (raw.get("source_ids") or [])[:MAX_ANNOTATION_SOURCES]
                if _safe_text(value, 256)
            ],
        }
        rows.append(row)
        if status in BLOCKING_CLAIM_ANNOTATIONS:
            blockers.append(f"review_annotation:{claim_id}:{status}")
    return rows, blockers


def _gate_payload(
    document: dict[str, Any],
    authority_result: dict[str, Any],
    fact_report: dict[str, Any],
    *,
    human_review_complete: bool,
    procedure_report: dict[str, Any],
    forms_report: dict[str, Any],
    findings_report: dict[str, Any],
    review_annotation_blockers: list[str] | None = None,
) -> dict[str, Any]:
    verification = authority_result.get("verification_report") or {}
    authority_cards = authority_result.get("sources") or authority_result.get("source_cards") or []
    citation_report = verification.get("citations") or []
    quote_report = verification.get("quotes") or []
    claim_report = {"claims": verification.get("claims") or []}
    fact_map = []
    for item in fact_report.get("facts") or []:
        records = item.get("supporting_records") or []
        fact_map.append({
            "fact_id": item.get("fact_id"),
            "fact": item.get("fact"),
            "source_document_id": records[0].get("evidence_id") if records else None,
            "source_document_ids": [row.get("evidence_id") for row in records],
            "support_status": "supported" if records else "unsupported",
            "start_offset": records[0].get("span_start") if records else None,
            "end_offset": records[0].get("span_end") if records else None,
        })
    authority_gate = authority_result.get("filing_gate") or {}
    authority_checks = authority_gate.get("mandatory_checks") or {}
    fact_complete = bool(fact_map) and all(row.get("support_status") == "supported" for row in fact_map)
    procedure_checked = procedure_report.get("status") == "checked" and not procedure_report.get("blockers")
    forms_current = forms_report.get("status") == "checked" and not forms_report.get("stale_forms") and not forms_report.get("unknown_forms")
    return {
        "review_required": True,
        "human_review_complete": human_review_complete,
        "authority_verified": bool(authority_checks.get("authority_verified")),
        "citations_resolved": bool(authority_checks.get("citations_resolved")),
        "quotes_found": bool(authority_checks.get("quotes_found")),
        "legal_claims_supported": bool(authority_checks.get("legal_claims_supported")),
        "facts_mapped_to_evidence": fact_complete,
        "procedure_posture_checked": procedure_checked,
        "forms_current": forms_current,
        "authority_matrix": authority_cards,
        "citation_report": citation_report,
        "quote_report": quote_report,
        "claim_support_report": claim_report,
        "fact_to_evidence_map": fact_map,
        "procedure_posture_report": procedure_report,
        "forms_report": forms_report,
        "findings_review": findings_report,
        "verification_report": verification,
        "review_annotation_blockers": list(review_annotation_blockers or []),
    }


@_synchronized
def prepare_review_request(
    case_root: Path,
    document_id: str,
    *,
    authority_result: dict[str, Any],
    facts: Iterable[str] | None = None,
    records: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    document = get_document(case_root, document_id)
    revision_id = _validate_id(str(document.get("current_revision_id") or ""), "revision_id")
    document_id = _validate_id(document_id, "document_id")
    fact_report = build_fact_evidence_report(facts, records)
    procedure_report = build_procedure_posture_report(
        title=str(document.get("title") or ""),
        content=str(document.get("content") or ""),
        document_type=str(document.get("document_type") or "draft"),
    )
    forms_report = build_form_freshness_report(
        content=str(document.get("content") or ""),
        authority_result=authority_result,
        procedure_report=procedure_report,
    )
    findings_report = Rule52BestInterestFindingsEngine().review_order(
        str(document.get("content") or ""),
        posture=str(procedure_report.get("procedural_posture") or "final_order"),
        evidence_records=records,
    ).to_dict()
    claim_rows = _claim_rows(authority_result)
    gate_payload = _gate_payload(
        document,
        authority_result,
        fact_report,
        human_review_complete=False,
        procedure_report=procedure_report,
        forms_report=forms_report,
        findings_report=findings_report,
    )
    preflight = FilingReadyGate().evaluate(gate_payload)
    request_id = uuid.uuid4().hex
    token = secrets.token_hex(32)
    packet = {
        "schema_version": "document_review_packet_v2",
        "document_id": document_id,
        "revision_id": revision_id,
        "document_title": _safe_text(document.get("title"), 240),
        "document_type": _safe_text(document.get("document_type"), 64),
        "document_content_sha256": _safe_text(document.get("content_sha256"), 64),
        "authority_verification": authority_result,
        "fact_evidence_report": fact_report,
        "procedure_posture_report": procedure_report,
        "forms_report": forms_report,
        "findings_review": findings_report,
        "claims_for_review": claim_rows,
        "filing_gate_preflight": preflight,
        "review_required": True,
        "generated_at": _utc_now(),
    }
    packet["packet_sha256"] = _sha(packet)
    request = {
        "schema_version": SCHEMA_VERSION,
        "request_id": request_id,
        "document_id": document_id,
        "revision_id": revision_id,
        "status": "pending",
        "created_at": _utc_now(),
        "confirmation_token_sha256": hashlib.sha256(token.encode("utf-8")).hexdigest(),
        "packet": packet,
        "gate_payload": gate_payload,
    }
    _, requests, _ = _roots(case_root, document_id)
    pending_count = sum(
        1
        for path in requests.glob("*.json")
        if path.is_file() and not path.is_symlink() and _read(path).get("status") == "pending"
    )
    if pending_count >= MAX_PENDING_REQUESTS:
        raise ReviewLedgerError("pending_review_request_limit", "Too many pending review packets exist for this document.", status_code=409)
    request["request_sha256"] = _sha(request)
    _atomic_write(requests / f"{request_id}.json", request)
    return {
        "status": "review_prepared",
        "request_id": request_id,
        "confirmation_token": token,
        "packet": packet,
        "review_required": True,
        "filing_ready": False,
    }


def _decision_rows(decisions: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in decisions.glob("*.json"):
        if path.is_file() and not path.is_symlink():
            rows.append(_read(path))
    rows.sort(key=lambda row: (int(row.get("sequence") or 0), str(row.get("decision_id") or "")))
    return rows


def _request_integrity_valid(request: dict[str, Any]) -> bool:
    stored = str(request.get("request_sha256") or "")
    payload = dict(request)
    payload.pop("request_sha256", None)
    return bool(stored) and hmac.compare_digest(stored, _sha(payload))


@_synchronized
def commit_review_decision(
    case_root: Path,
    document_id: str,
    *,
    request_id: str,
    confirmation_token: str,
    confirmed: bool,
    decision: str,
    reviewer_name: str,
    reviewer_role: str,
    attested: bool,
    notes: str = "",
    claim_annotations: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if confirmed is not True:
        raise ReviewLedgerError("explicit_confirmation_required", "Explicit confirmation is required.", status_code=409)
    request_id = _validate_id(request_id, "request_id")
    document_id = _validate_id(document_id, "document_id")
    token = str(confirmation_token or "").strip().lower()
    if not _TOKEN_RE.fullmatch(token):
        raise ReviewLedgerError("invalid_confirmation_token", "The confirmation token is invalid.", status_code=409)
    decision = str(decision or "").strip().lower()
    if decision not in ALLOWED_DECISIONS:
        raise ReviewLedgerError("invalid_review_decision", "Unsupported review decision.")
    role = str(reviewer_role or "other_reviewer").strip().lower()
    if role not in ALLOWED_ROLES:
        raise ReviewLedgerError("invalid_reviewer_role", "Unsupported reviewer role.")
    name = " ".join(_safe_text(reviewer_name, 160).split())
    if not name:
        raise ReviewLedgerError("reviewer_name_required", "A reviewer name or local identifier is required.")
    if decision == "approve_review" and attested is not True:
        raise ReviewLedgerError("review_attestation_required", "Approval requires the review attestation.", status_code=409)

    _, requests, decisions = _roots(case_root, document_id)
    request_path = requests / f"{request_id}.json"
    request = _read(request_path)
    if not _request_integrity_valid(request):
        raise ReviewLedgerError("review_request_hash_mismatch", "The review request failed its integrity check.", status_code=409)
    existing_decisions = _decision_rows(decisions)
    if any(str(row.get("request_id") or "") == request_id for row in existing_decisions):
        raise ReviewLedgerError("review_request_consumed", "The review request has already been used.", status_code=409)
    if len(existing_decisions) >= MAX_DECISIONS:
        raise ReviewLedgerError("review_decision_limit", "The review decision limit was reached for this document.", status_code=409)
    if request.get("status") != "pending":
        raise ReviewLedgerError("review_request_consumed", "The review request has already been used.", status_code=409)
    expected = str(request.get("confirmation_token_sha256") or "")
    if not hmac.compare_digest(expected, hashlib.sha256(token.encode("utf-8")).hexdigest()):
        raise ReviewLedgerError("invalid_confirmation_token", "The confirmation token is invalid.", status_code=409)
    document = get_document(case_root, document_id)
    if str(document.get("current_revision_id") or "") != str(request.get("revision_id") or ""):
        raise ReviewLedgerError("review_request_stale", "The document changed after this review packet was prepared.", status_code=409)

    claim_rows = list((request.get("packet") or {}).get("claims_for_review") or [])
    normalized_annotations, annotation_blockers = _normalize_claim_annotations(claim_annotations, claim_rows)
    if decision == "approve_review" and claim_rows:
        annotated_ids = {row["claim_id"] for row in normalized_annotations}
        for claim in claim_rows:
            if bool(claim.get("material", True)) and str(claim.get("claim_id")) not in annotated_ids:
                annotation_blockers.append(f"review_annotation_missing:{claim.get('claim_id')}")
    human_complete = decision == "approve_review"
    gate_payload = dict(request.get("gate_payload") or {})
    gate_payload["human_review_complete"] = human_complete
    gate_payload["review_annotation_blockers"] = sorted(set(annotation_blockers))
    gate = FilingReadyGate().evaluate(gate_payload)
    status = {
        "approve_review": "review_complete" if gate.get("filing_ready") else "review_complete_blocked",
        "request_changes": "changes_requested",
        "reject": "rejected",
    }[decision]
    decision_id = uuid.uuid4().hex
    record = {
        "schema_version": SCHEMA_VERSION,
        "decision_id": decision_id,
        "request_id": request_id,
        "document_id": document_id,
        "revision_id": request["revision_id"],
        "packet_sha256": request["packet"]["packet_sha256"],
        "decision": decision,
        "status": status,
        "reviewer": {"name": name, "role": role, "attested": bool(attested)},
        "notes": _safe_text(notes, MAX_NOTE_CHARS),
        "claim_annotations": normalized_annotations,
        "review_annotation_blockers": sorted(set(annotation_blockers)),
        "filing_gate": gate,
        "sequence": (int(existing_decisions[-1].get("sequence") or 0) + 1) if existing_decisions else 1,
        "previous_decision_sha256": str(existing_decisions[-1].get("decision_sha256") or "0" * 64) if existing_decisions else "0" * 64,
        "committed_at": _utc_now(),
        "review_required": not bool(gate.get("filing_ready")),
    }
    record["decision_sha256"] = _sha(record)
    _atomic_write(decisions / f"{decision_id}.json", record)
    request["status"] = "consumed"
    request["consumed_at"] = record["committed_at"]
    request["decision_id"] = decision_id
    request.pop("confirmation_token_sha256", None)
    request.pop("request_sha256", None)
    request["request_sha256"] = _sha(request)
    _atomic_write(request_path, request)
    return record


@_synchronized
def list_review_history(case_root: Path, document_id: str) -> dict[str, Any]:
    document_id = _validate_id(document_id, "document_id")
    _, requests, decisions = _roots(case_root, document_id)
    rows = list(reversed(_decision_rows(decisions)))
    pending = 0
    for path in requests.glob("*.json"):
        if path.is_file() and not path.is_symlink() and _read(path).get("status") == "pending":
            pending += 1
    return {
        "schema_version": SCHEMA_VERSION,
        "document_id": document_id,
        "decisions": rows[:MAX_DECISIONS],
        "decision_count": len(rows),
        "pending_request_count": pending,
        "latest": rows[0] if rows else None,
        "review_required": not bool(rows and rows[0].get("filing_gate", {}).get("filing_ready")),
    }


@_synchronized
def list_pending_review_packets(case_root: Path, document_id: str) -> dict[str, Any]:
    document_id = _validate_id(document_id, "document_id")
    _, requests, _ = _roots(case_root, document_id)
    packets: list[dict[str, Any]] = []
    for path in sorted(requests.glob("*.json")):
        if not path.is_file() or path.is_symlink():
            continue
        request = _read(path)
        if request.get("status") != "pending":
            continue
        if not _request_integrity_valid(request):
            raise ReviewLedgerError("review_request_hash_mismatch", "A pending review request failed its integrity check.", status_code=409)
        packet = request.get("packet") or {}
        preflight = packet.get("filing_gate_preflight") or {}
        packets.append({
            "request_id": request.get("request_id"),
            "revision_id": request.get("revision_id"),
            "created_at": request.get("created_at"),
            "packet_sha256": packet.get("packet_sha256"),
            "claim_count": len(packet.get("claims_for_review") or []),
            "fact_count": int((packet.get("fact_evidence_report") or {}).get("fact_count") or 0),
            "procedural_posture": (packet.get("procedure_posture_report") or {}).get("procedural_posture"),
            "form_status": (packet.get("forms_report") or {}).get("status"),
            "blockers": list(preflight.get("blockers") or [])[:100],
        })
    packets.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("request_id") or "")), reverse=True)
    return {"document_id": document_id, "packets": packets[:MAX_PENDING_REQUESTS], "count": len(packets)}


@_synchronized
def verify_review_ledger(case_root: Path, document_id: str) -> dict[str, Any]:
    document_id = _validate_id(document_id, "document_id")
    _, _, decisions = _roots(case_root, document_id)
    rows = _decision_rows(decisions)
    expected_previous = "0" * 64
    expected_sequence = 1
    blockers: list[str] = []
    for row in rows:
        stored = str(row.get("decision_sha256") or "")
        payload = dict(row)
        payload.pop("decision_sha256", None)
        if not hmac.compare_digest(stored, _sha(payload)):
            blockers.append(f"decision_hash_mismatch:{row.get('decision_id')}")
        if int(row.get("sequence") or 0) != expected_sequence:
            blockers.append(f"decision_sequence_mismatch:{row.get('decision_id')}")
        if str(row.get("previous_decision_sha256") or "") != expected_previous:
            blockers.append(f"decision_chain_mismatch:{row.get('decision_id')}")
        expected_previous = stored
        expected_sequence += 1
    return {
        "status": "pass" if not blockers else "fail",
        "valid": not blockers,
        "document_id": document_id,
        "decision_count": len(rows),
        "head_sha256": expected_previous,
        "blockers": blockers,
        "review_required": True,
    }
