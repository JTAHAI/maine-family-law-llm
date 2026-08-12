"""Revision-diff, reviewer-assignment, and reviewed filing-packet workbench.

The module is deliberately deterministic and fail closed. A prior approval is
historical evidence only: it is never carried forward as approval of a changed
revision. Packet exports remain review work product and never certify legal
correctness or filing readiness.
"""

from __future__ import annotations

import hashlib
import html
import hmac
import json
import os
import re
import secrets
import shutil
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from legal.documents.workspace import get_document, structured_diff, workspace_paths
from legal.drafting.filing_ready_gate import FilingReadyGate
from legal.review.review_ledger import list_review_history, verify_review_ledger

SCHEMA_VERSION = "reviewed_filing_packet_v1"
ALGORITHM_VERSION = "5.14.0-revision-diff-v1"
ROOT_FOLDER = "20_REVIEWED_FILING_PACKET"
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_ASSIGNMENTS = 2_000
MAX_REVIEWER_LABEL = 160
MAX_NOTE_CHARS = 2_000
MAX_CAPABILITIES = 16
ALLOWED_ROLES = {"attorney", "paralegal", "advocate", "self_represented", "other_reviewer"}
ALLOWED_CAPABILITIES = {"review", "annotate_claims", "request_changes", "approve_review", "export_packet"}
_ID_RE = re.compile(r"^[a-f0-9]{32}$")
_BUILD_RE = re.compile(r"^[a-f0-9]{24}$")
_SHA_RE = re.compile(r"^[a-f0-9]{64}$")
_CITATION_RE = re.compile(
    r"\b(?:\d{4}\s+ME\s+\d+|\d{1,2}(?:-A)?\s+M\.R\.S\.\s*§+\s*[\w.-]+|M\.R\.\s+Civ\.\s+P\.\s*\d+[A-Za-z.-]*)\b",
    re.IGNORECASE,
)
_FORM_RE = re.compile(r"\b(?:FM|PA|CV|PB)[ -]?\d{1,4}[A-Z]?\b", re.IGNORECASE)
_LOCK = threading.RLock()


class ReviewedFilingPacketError(RuntimeError):
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
    if isinstance(payload, bytes):
        return hashlib.sha256(payload).hexdigest()
    return hashlib.sha256(_canonical(payload)).hexdigest()


def _scrub_identity_payload(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if key in {"generated_at", "immutable_report_hash"}:
                continue
            cleaned[key] = _scrub_identity_payload(item)
        return cleaned
    if isinstance(value, list):
        return [_scrub_identity_payload(item) for item in value]
    return value


def _safe_text(value: Any, limit: int) -> str:
    return str(value or "").replace("\x00", "").strip()[:limit]


def _validate_id(value: Any, label: str) -> str:
    candidate = str(value or "").strip().lower()
    if not _ID_RE.fullmatch(candidate):
        raise ReviewedFilingPacketError(f"invalid_{label}", f"Invalid {label}.", status_code=404)
    return candidate


def _atomic_write(path: Path, data: bytes) -> None:
    if path.exists() and path.is_symlink():
        raise ReviewedFilingPacketError("filing_packet_symlink_refused", "A filing-packet symlink was refused.", status_code=409)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise ReviewedFilingPacketError("filing_packet_record_unavailable", "A filing-packet record is unavailable.", status_code=404)
    raw = path.read_bytes()
    if len(raw) > MAX_FILE_BYTES:
        raise ReviewedFilingPacketError("filing_packet_record_too_large", "A filing-packet record is unexpectedly large.", status_code=409)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewedFilingPacketError("filing_packet_record_invalid", "A filing-packet record is invalid.", status_code=409) from exc
    if not isinstance(payload, dict):
        raise ReviewedFilingPacketError("filing_packet_record_invalid", "A filing-packet record is invalid.", status_code=409)
    return payload


def _line_tokens(text: str) -> set[str]:
    return {value for value in re.findall(r"[a-z0-9]+", text.casefold()) if len(value) > 2}


def _revision_path(case_root: Path, document_id: str, revision_id: str) -> Path:
    paths = workspace_paths(case_root)
    document_id = _validate_id(document_id, "document_id")
    revision_id = _validate_id(revision_id, "revision_id")
    path = paths.documents / document_id / "revisions" / f"{revision_id}.json"
    resolved = path.resolve(strict=True)
    root = paths.documents.resolve(strict=True)
    if root not in resolved.parents or resolved.is_symlink():
        raise ReviewedFilingPacketError("revision_path_invalid", "The revision path is invalid.", status_code=409)
    return resolved


def _load_revision(case_root: Path, document_id: str, revision_id: str) -> dict[str, Any]:
    payload = _read_json(_revision_path(case_root, document_id, revision_id))
    if payload.get("document_id") != document_id or payload.get("revision_id") != revision_id:
        raise ReviewedFilingPacketError("revision_identity_mismatch", "The revision identity does not match its path.", status_code=409)
    content = str(payload.get("content") or "")
    if _sha(content.encode("utf-8")) != str(payload.get("content_sha256") or ""):
        raise ReviewedFilingPacketError("revision_hash_mismatch", "The revision content failed its integrity check.", status_code=409)
    return payload


def _review_request(case_root: Path, document_id: str, request_id: str) -> dict[str, Any]:
    paths = workspace_paths(case_root)
    document_id = _validate_id(document_id, "document_id")
    request_id = _validate_id(request_id, "request_id")
    path = paths.root / "reviews" / document_id / "requests" / f"{request_id}.json"
    resolved = path.resolve(strict=True)
    review_root = (paths.root / "reviews").resolve(strict=True)
    if review_root not in resolved.parents or resolved.is_symlink():
        raise ReviewedFilingPacketError("review_request_path_invalid", "The review request path is invalid.", status_code=409)
    request = _read_json(resolved)
    stored = str(request.get("request_sha256") or "")
    check = dict(request)
    check.pop("request_sha256", None)
    if not _SHA_RE.fullmatch(stored) or not hmac.compare_digest(stored, _sha(check)):
        raise ReviewedFilingPacketError("review_request_hash_mismatch", "The review request failed its integrity check.", status_code=409)
    return request


def _latest_review_context(case_root: Path, document_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    history = list_review_history(case_root, document_id)
    for decision in history.get("decisions") or []:
        request_id = str(decision.get("request_id") or "")
        if not _ID_RE.fullmatch(request_id):
            continue
        request = _review_request(case_root, document_id, request_id)
        packet = request.get("packet") or {}
        if isinstance(packet, dict):
            return decision, packet
    return None, None


def _changed_text(diff: dict[str, Any]) -> str:
    return "\n".join(str(row.get("content") or "") for row in diff.get("rows") or [] if row.get("type") in {"add", "delete"})


def _unit_map(diff: dict[str, Any], review_packet: dict[str, Any] | None) -> dict[str, Any]:
    changed = _changed_text(diff)
    changed_tokens = _line_tokens(changed)
    rows: list[dict[str, Any]] = []

    def add_units(unit_type: str, items: Iterable[Any], text_keys: tuple[str, ...], id_key: str) -> None:
        for index, raw in enumerate(items or []):
            if not isinstance(raw, dict):
                continue
            text = " ".join(_safe_text(raw.get(key), 4_000) for key in text_keys if raw.get(key))
            tokens = _line_tokens(text)
            overlap = len(changed_tokens & tokens) / max(len(tokens), 1) if tokens else 0.0
            changed_unit = bool(tokens and (overlap >= 0.25 or text.casefold() in changed.casefold() or changed.casefold() in text.casefold()))
            rows.append({
                "unit_id": _safe_text(raw.get(id_key), 128) or f"{unit_type}-{index + 1:03d}",
                "unit_type": unit_type,
                "label": text[:500] or unit_type.replace("_", " "),
                "status": "changed_requires_review" if changed_unit else "unchanged_historical_reference",
                "change_overlap": round(overlap, 3),
                "source_ids": [
                    _safe_text(value, 256)
                    for value in (raw.get("source_ids") or [])[:20]
                    if _safe_text(value, 256)
                ],
                "prior_review_not_carried_forward": True,
            })

    packet = review_packet or {}
    add_units("claim", packet.get("claims_for_review") or [], ("statement",), "claim_id")
    fact_report = packet.get("fact_evidence_report") or {}
    add_units("fact", fact_report.get("facts") or [], ("fact",), "fact_id")
    procedure = packet.get("procedure_posture_report") or {}
    procedure_text = " ".join([str(procedure.get("procedural_posture") or ""), *(procedure.get("review_items") or [])])
    if procedure_text:
        add_units("procedure", [{"id": "procedure-posture", "text": procedure_text}], ("text",), "id")
    forms = packet.get("forms_report") or {}
    form_ids = list(forms.get("current_forms") or []) + list(forms.get("stale_forms") or []) + list(forms.get("unknown_forms") or [])
    add_units("form", [{"form_id": value, "text": value} for value in form_ids], ("text",), "form_id")
    citations = sorted(set(_CITATION_RE.findall(str(packet.get("document_text") or "") + "\n" + changed)))
    add_units("citation", [{"citation": value, "text": value} for value in citations], ("text",), "citation")
    return {
        "schema_version": "incremental_review_units_v1",
        "units": rows,
        "changed_unit_count": sum(1 for row in rows if row["status"] == "changed_requires_review"),
        "unchanged_historical_count": sum(1 for row in rows if row["status"] == "unchanged_historical_reference"),
        "notice": "Unchanged prior findings are historical references only. No approval is carried forward to the new revision.",
    }


def build_incremental_review_diff(
    case_root: Path,
    document_id: str,
    *,
    base_revision_id: str = "",
    target_revision_id: str = "",
) -> dict[str, Any]:
    document = get_document(case_root, document_id)
    current = _validate_id(target_revision_id or document.get("current_revision_id"), "revision_id")
    decision, packet = _latest_review_context(case_root, document_id)
    base = base_revision_id or (str(decision.get("revision_id")) if decision else "")
    if not base:
        history = document.get("revisions") or []
        candidates = [str(row.get("revision_id") or "") for row in history if str(row.get("revision_id") or "") != current]
        base = next((value for value in candidates if _ID_RE.fullmatch(value)), current)
    base = _validate_id(base, "revision_id")
    before = _load_revision(case_root, document_id, base)
    after = _load_revision(case_root, document_id, current)
    diff = structured_diff(str(before.get("content") or ""), str(after.get("content") or ""))
    changed_text = _changed_text(diff)
    citations = sorted(set(_CITATION_RE.findall(changed_text)))[:200]
    form_ids = sorted({re.sub(r"[ -]", "-", value.upper()) for value in _FORM_RE.findall(changed_text)})[:100]
    units = _unit_map(diff, packet)
    return {
        "schema_version": "incremental_revision_review_v1",
        "document_id": document_id,
        "base_revision_id": base,
        "target_revision_id": current,
        "base_content_sha256": before.get("content_sha256"),
        "target_content_sha256": after.get("content_sha256"),
        "prior_review_decision_id": decision.get("decision_id") if decision else None,
        "prior_review_status": decision.get("status") if decision else "not_reviewed",
        "prior_approval_stale": bool(decision and base != current),
        "diff": diff,
        "review_units": units,
        "changed_citations": citations,
        "changed_form_ids": form_ids,
        "review_required": True,
        "filing_ready": False,
    }


class ReviewedFilingPacketStore:
    def __init__(self, case_root: Path):
        paths = workspace_paths(case_root)
        self.case_root = paths.case_root
        self.root = paths.root / ROOT_FOLDER
        self.builds = self.root / "builds"
        self.assignments = self.root / "assignments.jsonl"
        self.active_pointer = self.root / "ACTIVE.json"
        for folder in (self.root, self.builds):
            if folder.exists() and folder.is_symlink():
                raise ReviewedFilingPacketError("filing_packet_symlink_refused", "A filing-packet symlink was refused.", status_code=409)
            folder.mkdir(mode=0o700, parents=True, exist_ok=True)

    def _assignment_rows(self) -> list[dict[str, Any]]:
        if not self.assignments.exists():
            return []
        if self.assignments.is_symlink():
            raise ReviewedFilingPacketError("assignment_ledger_symlink_refused", "The assignment ledger symlink was refused.", status_code=409)
        rows: list[dict[str, Any]] = []
        previous = "0" * 64
        for line_number, line in enumerate(self.assignments.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ReviewedFilingPacketError("assignment_ledger_invalid", "The assignment ledger is invalid.", status_code=409) from exc
            stored = str(row.get("entry_sha256") or "")
            payload = dict(row)
            payload.pop("entry_sha256", None)
            if payload.get("previous_entry_sha256") != previous or not hmac.compare_digest(stored, _sha(payload)):
                raise ReviewedFilingPacketError("assignment_ledger_tampered", f"The assignment ledger failed verification at row {line_number}.", status_code=409)
            previous = stored
            rows.append(row)
        return rows

    def assignments_for(self, document_id: str) -> dict[str, Any]:
        document_id = _validate_id(document_id, "document_id")
        rows = [row for row in self._assignment_rows() if row.get("document_id") == document_id]
        active_by_assignment: dict[str, dict[str, Any]] = {}
        for row in rows:
            assignment_id = str(row.get("assignment_id") or "")
            if row.get("event") == "assigned":
                active_by_assignment[assignment_id] = row
            elif row.get("event") in {"released", "completed"}:
                active_by_assignment.pop(assignment_id, None)
        return {
            "schema_version": "reviewer_assignment_ledger_v1",
            "document_id": document_id,
            "active": list(active_by_assignment.values()),
            "history": list(reversed(rows))[:MAX_ASSIGNMENTS],
            "identity_notice": "Reviewer labels and roles are locally entered metadata; this application does not verify professional identity or licensure.",
            "review_required": True,
        }

    def assign(
        self,
        document_id: str,
        *,
        reviewer_label: str,
        role: str,
        capabilities: Iterable[str],
        expected_revision_id: str,
        exclusive: bool = True,
        note: str = "",
    ) -> dict[str, Any]:
        with _LOCK:
            document_id = _validate_id(document_id, "document_id")
            document = get_document(self.case_root, document_id)
            revision_id = _validate_id(expected_revision_id, "revision_id")
            if revision_id != str(document.get("current_revision_id") or ""):
                raise ReviewedFilingPacketError("assignment_revision_stale", "The document changed before assignment.", status_code=409)
            label = " ".join(_safe_text(reviewer_label, MAX_REVIEWER_LABEL).split())
            if not label:
                raise ReviewedFilingPacketError("reviewer_label_required", "A local reviewer label is required.")
            normalized_role = str(role or "other_reviewer").strip().lower()
            if normalized_role not in ALLOWED_ROLES:
                raise ReviewedFilingPacketError("invalid_reviewer_role", "Unsupported reviewer role.")
            normalized_caps = sorted({str(value).strip().lower() for value in capabilities if str(value).strip().lower() in ALLOWED_CAPABILITIES})[:MAX_CAPABILITIES]
            if "review" not in normalized_caps:
                normalized_caps.insert(0, "review")
            current = self.assignments_for(document_id)["active"]
            conflicts = [row for row in current if row.get("revision_id") == revision_id and bool(row.get("exclusive"))]
            if exclusive and conflicts:
                raise ReviewedFilingPacketError("reviewer_assignment_conflict", "This revision already has an exclusive active reviewer assignment.", status_code=409)
            rows = self._assignment_rows()
            previous = str(rows[-1].get("entry_sha256") or "0" * 64) if rows else "0" * 64
            assignment_id = uuid.uuid4().hex
            entry = {
                "schema_version": "reviewer_assignment_event_v1",
                "event_id": uuid.uuid4().hex,
                "event": "assigned",
                "assignment_id": assignment_id,
                "document_id": document_id,
                "revision_id": revision_id,
                "reviewer_label": label,
                "role": normalized_role,
                "capabilities": normalized_caps,
                "exclusive": bool(exclusive),
                "note": _safe_text(note, MAX_NOTE_CHARS),
                "created_at": _utc_now(),
                "previous_entry_sha256": previous,
                "identity_verified": False,
            }
            entry["entry_sha256"] = _sha(entry)
            with self.assignments.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            return entry

    def _source_lifecycle(
        self,
        document: dict[str, Any],
        review_packet: dict[str, Any] | None,
        *,
        current_authority_build_id: str = "",
        current_forms: Iterable[dict[str, Any]] | None = None,
        current_records: Iterable[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        blockers: list[str] = []
        current_refs = {str(row.get("source_id") or ""): str(row.get("hash") or "") for row in document.get("source_refs") or [] if isinstance(row, dict)}
        prior_authority = (review_packet or {}).get("authority_verification") or {}
        prior_build_id = _safe_text(prior_authority.get("build_id") or prior_authority.get("authority_build_id"), 128)
        current_authority_build_id = _safe_text(current_authority_build_id, 128)
        if prior_build_id and current_authority_build_id and prior_build_id != current_authority_build_id:
            blockers.append(f"authority_generation_changed:{prior_build_id}:{current_authority_build_id}")
        prior_sources = prior_authority.get("sources") or []
        checked: list[dict[str, Any]] = []
        for raw in prior_sources:
            if not isinstance(raw, dict):
                continue
            source_id = _safe_text(raw.get("source_id"), 256)
            status = _safe_text(raw.get("freshness_status") or raw.get("status"), 80).lower()
            if status in {"stale", "superseded", "expired", "unknown", "stale_unknown"}:
                blockers.append(f"authority_source_lifecycle:{source_id or 'unknown'}:{status}")
            checked.append({"source_id": source_id, "freshness_status": status or "unknown", "generation_id": _safe_text(raw.get("generation_id") or raw.get("build_id"), 128)})
        for source_id, source_hash in current_refs.items():
            if not source_hash:
                blockers.append(f"document_source_hash_missing:{source_id or 'unknown'}")
        forms = (review_packet or {}).get("forms_report") or {}
        for value in forms.get("stale_forms") or []:
            blockers.append(f"form_superseded_or_stale:{value}")
        for value in forms.get("unknown_forms") or []:
            blockers.append(f"form_lifecycle_unknown:{value}")
        current_form_map = {
            str(row.get("form_id") or "").upper().replace(" ", "-"): row
            for row in (current_forms or [])
            if isinstance(row, dict) and str(row.get("form_id") or "").strip()
        }
        for form_id in forms.get("current_forms") or []:
            normalized = str(form_id or "").upper().replace(" ", "-")
            current = current_form_map.get(normalized)
            if current_forms is not None and current is None:
                blockers.append(f"form_removed_from_current_generation:{normalized}")
            elif current is not None:
                freshness = str(current.get("freshness_status") or "unknown").lower()
                if freshness not in {"current", "fresh", "verified_current"}:
                    blockers.append(f"form_no_longer_current:{normalized}:{freshness}")
        record_map = {}
        for row in current_records or []:
            if not isinstance(row, dict):
                continue
            record_id = str(row.get("evidence_id") or row.get("record_id") or row.get("source_id") or "")
            if record_id:
                record_map[record_id] = str(row.get("source_hash") or row.get("hash") or "")
        fact_report = (review_packet or {}).get("fact_evidence_report") or {}
        for fact in fact_report.get("facts") or []:
            if not isinstance(fact, dict):
                continue
            for record in fact.get("supporting_records") or []:
                if not isinstance(record, dict):
                    continue
                record_id = str(record.get("evidence_id") or "")
                prior_hash = str(record.get("source_hash") or "")
                if current_records is not None and record_id not in record_map:
                    blockers.append(f"fact_source_deleted_or_unavailable:{record_id or 'unknown'}")
                elif record_id in record_map and prior_hash and record_map[record_id] and prior_hash != record_map[record_id]:
                    blockers.append(f"fact_source_hash_changed:{record_id}")
        return {
            "prior_authority_build_id": prior_build_id,
            "current_authority_build_id": current_authority_build_id,
            "checked_sources": checked,
            "document_source_hashes": current_refs,
            "blockers": sorted(set(blockers)),
            "review_required": True,
        }

    def _render_html(self, packet: dict[str, Any]) -> str:
        def list_items(values: Iterable[Any]) -> str:
            return "".join(f"<li>{html.escape(str(value))}</li>" for value in values)
        diff = packet.get("incremental_review") or {}
        units = (diff.get("review_units") or {}).get("units") or []
        blockers = packet.get("blockers") or []
        unit_rows = "".join(
            "<tr>"
            f"<td>{html.escape(str(row.get('unit_type') or ''))}</td>"
            f"<td>{html.escape(str(row.get('label') or ''))}</td>"
            f"<td>{html.escape(str(row.get('status') or ''))}</td>"
            "</tr>"
            for row in units
        )
        return "<!doctype html><html><head><meta charset='utf-8'><title>Reviewed filing packet</title><style>body{font-family:system-ui;margin:2rem;color:#172b3a}section{border:1px solid #ccd7df;border-radius:10px;padding:1rem;margin:1rem 0}code{overflow-wrap:anywhere}.warn{color:#9a3f00}.ok{color:#126b3a}table{border-collapse:collapse;width:100%}th,td{border:1px solid #d8e1e7;padding:.45rem;text-align:left}</style></head><body>" + \
            f"<h1>{html.escape(str(packet.get('document_title') or 'Reviewed filing packet'))}</h1>" + \
            f"<p><strong>Status:</strong> {html.escape(str(packet.get('status') or 'review_required'))}</p>" + \
            f"<p><strong>Revision:</strong> <code>{html.escape(str(packet.get('revision_id') or ''))}</code></p>" + \
            f"<section><h2>Blockers</h2><ul>{list_items(blockers) or '<li>None recorded; human review still required.</li>'}</ul></section>" + \
            f"<section><h2>Incremental re-review</h2><p>{html.escape(str((diff.get('diff') or {}).get('summary') or ''))}</p><table><tr><th>Type</th><th>Unit</th><th>Status</th></tr>{unit_rows}</table></section>" + \
            f"<section><h2>Review decision</h2><pre>{html.escape(json.dumps(packet.get('review_decision') or {}, indent=2, sort_keys=True))}</pre></section>" + \
            f"<section><h2>Authority, facts, procedure, and forms</h2><pre>{html.escape(json.dumps(packet.get('bound_reports') or {}, indent=2, sort_keys=True))}</pre></section>" + \
            "<p>This packet is review work product. It does not prove facts, verify reviewer identity, or certify filing readiness.</p></body></html>"

    def build(
        self,
        document_id: str,
        *,
        approved: bool = False,
        current_authority_build_id: str = "",
        current_forms: Iterable[dict[str, Any]] | None = None,
        current_records: Iterable[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if approved is not True:
            raise ReviewedFilingPacketError("explicit_packet_approval_required", "Explicit approval is required to build the filing packet.", status_code=409)
        with _LOCK:
            document_id = _validate_id(document_id, "document_id")
            document = get_document(self.case_root, document_id)
            ledger = verify_review_ledger(self.case_root, document_id)
            decision, review_packet = _latest_review_context(self.case_root, document_id)
            incremental = build_incremental_review_diff(self.case_root, document_id)
            assignments = self.assignments_for(document_id)
            lifecycle = self._source_lifecycle(
                document,
                review_packet,
                current_authority_build_id=current_authority_build_id,
                current_forms=current_forms,
                current_records=current_records,
            )
            workflow_blockers: list[str] = []
            if ledger.get("status") != "pass":
                workflow_blockers.extend(ledger.get("blockers") or ["review_ledger_unverified"])
            if not decision:
                workflow_blockers.append("human_review_decision_missing")
            else:
                if str(decision.get("revision_id") or "") != str(document.get("current_revision_id") or ""):
                    workflow_blockers.append("prior_review_stale_after_revision_change")
                if decision.get("decision") != "approve_review":
                    workflow_blockers.append(f"review_decision_not_approval:{decision.get('decision')}")
            workflow_blockers.extend(lifecycle.get("blockers") or [])
            if not assignments.get("active"):
                workflow_blockers.append("active_reviewer_assignment_missing")
            gate_payload = dict((review_packet or {}).get("gate_payload") or {})
            gate_payload["human_review_complete"] = bool(
                decision
                and decision.get("decision") == "approve_review"
                and not workflow_blockers
            )
            gate_payload["workflow_blockers"] = sorted(set(str(value) for value in workflow_blockers if value))
            gate_payload["review_annotation_blockers"] = sorted(set(str(value) for value in (decision or {}).get("review_annotation_blockers") or []))
            filing_gate = FilingReadyGate().evaluate(gate_payload)
            blockers = list(filing_gate.get("blockers") or [])
            packet = {
                "schema_version": SCHEMA_VERSION,
                "algorithm_version": ALGORITHM_VERSION,
                "document_id": document_id,
                "document_title": document.get("title"),
                "document_type": document.get("document_type"),
                "revision_id": document.get("current_revision_id"),
                "document_content_sha256": document.get("content_sha256"),
                "status": "reviewed_packet" if filing_gate.get("filing_ready") else "reviewed_packet_blocked",
                "review_decision": decision,
                "review_packet_sha256": (review_packet or {}).get("packet_sha256"),
                "review_ledger": ledger,
                "incremental_review": incremental,
                "reviewer_assignments": assignments,
                "source_lifecycle": lifecycle,
                "workflow_blockers": sorted(set(workflow_blockers)),
                "filing_gate": filing_gate,
                "bound_reports": {
                    "authority_verification": (review_packet or {}).get("authority_verification"),
                    "fact_evidence_report": (review_packet or {}).get("fact_evidence_report"),
                    "procedure_posture_report": (review_packet or {}).get("procedure_posture_report"),
                    "forms_report": (review_packet or {}).get("forms_report"),
                    "findings_review": (review_packet or {}).get("findings_review"),
                    "claims_for_review": (review_packet or {}).get("claims_for_review"),
                    "filing_gate_preflight": (review_packet or {}).get("filing_gate_preflight"),
                    "canonical_filing_gate": filing_gate,
                },
                "blockers": blockers,
                "generated_at": _utc_now(),
                "review_required": True,
                "filing_ready": bool(filing_gate.get("filing_ready")),
                "notice": "Unchanged prior approvals are historical references only and are never silently carried forward to a new revision.",
            }
            identity_payload = _scrub_identity_payload(packet)
            build_id = _sha(identity_payload)[:24]
            packet["build_id"] = build_id
            packet["packet_sha256"] = _sha(packet)
            build_dir = self.builds / build_id
            if build_dir.exists():
                verification = self.verify(build_id)
                if verification.get("status") != "pass":
                    raise ReviewedFilingPacketError("immutable_packet_collision", "An existing filing packet failed verification.", status_code=409)
                return self.active(build_id)
            staging = self.builds / f".{build_id}.{uuid.uuid4().hex}.staging"
            staging.mkdir(mode=0o700)
            try:
                json_bytes = json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")
                html_bytes = self._render_html(packet).encode("utf-8")
                receipt = {
                    "schema_version": "reviewed_filing_packet_receipt_v1",
                    "build_id": build_id,
                    "packet_sha256": packet["packet_sha256"],
                    "document_id": document_id,
                    "revision_id": packet["revision_id"],
                    "document_content_sha256": packet["document_content_sha256"],
                    "review_decision_sha256": (decision or {}).get("decision_sha256"),
                    "review_ledger_head_sha256": ledger.get("head_sha256"),
                "blockers": packet["blockers"],
                "generated_at": packet["generated_at"],
                "review_required": True,
                "filing_gate_status": filing_gate.get("export_status"),
            }
                receipt["receipt_sha256"] = _sha(receipt)
                files = {
                    "reviewed-filing-packet.json": json_bytes,
                    "reviewed-filing-packet.html": html_bytes,
                    "reviewed-filing-packet-receipt.json": json.dumps(receipt, indent=2, sort_keys=True).encode("utf-8"),
                }
                manifest_rows: list[dict[str, Any]] = []
                for name, data in files.items():
                    _atomic_write(staging / name, data)
                    manifest_rows.append({"name": name, "sha256": _sha(data), "size_bytes": len(data)})
                manifest = {"schema_version": "reviewed_filing_packet_manifest_v1", "build_id": build_id, "packet_sha256": packet["packet_sha256"], "files": manifest_rows}
                _atomic_write(staging / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8"))
                os.replace(staging, build_dir)
            finally:
                shutil.rmtree(staging, ignore_errors=True)
            pointer = {"build_id": build_id, "document_id": document_id, "revision_id": packet["revision_id"], "packet_sha256": packet["packet_sha256"]}
            _atomic_write(self.active_pointer, json.dumps(pointer, indent=2, sort_keys=True).encode("utf-8"))
            _atomic_write(self.root / f"ACTIVE_{document_id}.json", json.dumps(pointer, indent=2, sort_keys=True).encode("utf-8"))
            return self.active(build_id)

    def verify(self, build_id: str) -> dict[str, Any]:
        build_id = str(build_id or "").strip().lower()
        if not _BUILD_RE.fullmatch(build_id):
            raise ReviewedFilingPacketError("invalid_build_id", "The filing-packet build ID is invalid.", status_code=404)
        build_dir = self.builds / build_id
        manifest = _read_json(build_dir / "manifest.json")
        blockers: list[str] = []
        if manifest.get("build_id") != build_id:
            blockers.append("manifest_build_id_mismatch")
        expected_names = {"reviewed-filing-packet.json", "reviewed-filing-packet.html", "reviewed-filing-packet-receipt.json"}
        rows = manifest.get("files") or []
        names = [str(row.get("name") or "") for row in rows if isinstance(row, dict)]
        if set(names) != expected_names or len(names) != len(set(names)):
            blockers.append("manifest_artifact_set_invalid")
        for row in rows:
            name = Path(str(row.get("name") or "")).name
            path = build_dir / name
            if not path.is_file() or path.is_symlink():
                blockers.append(f"artifact_unavailable:{name}")
                continue
            raw = path.read_bytes()
            if _sha(raw) != str(row.get("sha256") or ""):
                blockers.append(f"artifact_hash_mismatch:{name}")
            if len(raw) != int(row.get("size_bytes") or -1):
                blockers.append(f"artifact_size_mismatch:{name}")
        packet = _read_json(build_dir / "reviewed-filing-packet.json")
        stored = str(packet.get("packet_sha256") or "")
        check = dict(packet)
        check.pop("packet_sha256", None)
        if not hmac.compare_digest(stored, _sha(check)):
            blockers.append("packet_hash_mismatch")
        return {"status": "pass" if not blockers else "blocked", "build_id": build_id, "blockers": sorted(set(blockers)), "packet_sha256": stored, "review_required": True}

    def active(self, build_id: str = "", *, document_id: str = "") -> dict[str, Any]:
        if not build_id:
            pointer_path = self.active_pointer
            if document_id:
                document_id = _validate_id(document_id, "document_id")
                pointer_path = self.root / f"ACTIVE_{document_id}.json"
            pointer = _read_json(pointer_path)
            build_id = str(pointer.get("build_id") or "")
        verification = self.verify(build_id)
        if verification["status"] != "pass":
            return verification
        build_dir = self.builds / build_id
        packet = _read_json(build_dir / "reviewed-filing-packet.json")
        artifacts = []
        for name, media_type in {
            "reviewed-filing-packet.json": "application/json",
            "reviewed-filing-packet.html": "text/html",
            "reviewed-filing-packet-receipt.json": "application/json",
        }.items():
            path = build_dir / name
            raw = path.read_bytes()
            artifacts.append({"name": name, "sha256": _sha(raw), "size_bytes": len(raw), "media_type": media_type})
        return {"status": "pass", "build_id": build_id, "packet": packet, "artifacts": artifacts, "verification": verification, "review_required": True}

    def resolve_artifact(self, build_id: str, filename: str) -> tuple[Path, str]:
        allowed = {
            "reviewed-filing-packet.json": "application/json",
            "reviewed-filing-packet.html": "text/html",
            "reviewed-filing-packet-receipt.json": "application/json",
        }
        name = Path(str(filename or "")).name
        if name not in allowed:
            raise ReviewedFilingPacketError("artifact_not_allowed", "The filing-packet artifact is not allowed.", status_code=404)
        verification = self.verify(build_id)
        if verification["status"] != "pass":
            raise ReviewedFilingPacketError("artifact_build_unverified", "The filing-packet build failed verification.", status_code=409)
        path = self.builds / build_id / name
        if not path.is_file() or path.is_symlink():
            raise ReviewedFilingPacketError("artifact_unavailable", "The filing-packet artifact is unavailable.", status_code=404)
        return path, allowed[name]
