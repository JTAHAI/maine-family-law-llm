"""Local-only FastAPI backend for the Maine Family Law LLM workbench."""

from __future__ import annotations

import hashlib
import mimetypes
import re
import threading
import time
import uuid
from pathlib import Path, PureWindowsPath
from typing import Any

from legal.product.family_justice_workbench_v205 import build_workbench_packet
from legal.security.prompt_injection import PromptInjectionScanner

from . import __version__
from .answer import compose_answer
from .case_corpus_builder import answer_case_question, load_case_search_records
from .case_library import active_case_root, describe_case_root, list_registered_case_roots, set_active_case_root
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
from .workbench import retrieve_fixture_sources
from .version import UI_VERSION
from .runtime_resilience import runtime_health_snapshot

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
except Exception:  # pragma: no cover - lets CLI import without API extras
    FastAPI = None  # type: ignore[assignment]
    HTTPException = Exception  # type: ignore[assignment]
    HTMLResponse = None  # type: ignore[assignment]
    JSONResponse = None  # type: ignore[assignment]
    FileResponse = None  # type: ignore[assignment]
    StaticFiles = None  # type: ignore[assignment]
    Request = object  # type: ignore[assignment]

    class BaseModel:  # type: ignore[no-redef]
        pass


class QueryRequest(BaseModel):
    query: str
    limit: int = 5


class AskRequest(BaseModel):
    question: str
    answer_style: str = "plain_language"
    matter_context: str = ""
    search_mode: str = "maine_law"
    child_impact_lens: bool = False
    session_id: str = ""
    last_search_id: str = ""
    input_integrity: dict[str, Any] | None = None


class DraftRequest(BaseModel):
    request: str
    mode: str = "checklist"


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
    approved: bool = False
    language: str = "eng"


class InstallOcrPrerequisitesRequest(BaseModel):
    approved: bool = False


class ClearSessionRequest(BaseModel):
    session_id: str = ""


if FastAPI is None:  # pragma: no cover
    app = None
else:
    app = FastAPI(
        title="Maine Family Law LLM Local Workbench",
        version=__version__,
        description="Local legal-information workbench. No legal advice, no cloud deploy, source receipts required.",
    )


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
    _record_open_tokens: dict[str, tuple[str, str, str]] = {}




    def _public_ocr_prerequisite_job() -> dict[str, Any]:
        with _ocr_prerequisite_lock:
            state = dict(_ocr_prerequisite_job)
        state.pop("thread", None)
        state["prerequisites"] = ocr_prerequisite_status()
        return state


    def _public_ocr_progress(state: dict[str, Any]) -> dict[str, Any]:
        """Return progress without exposing a matter path or document contents."""

        public = {key: value for key, value in state.items() if key not in {"cancel_event", "source_locator"}}
        source_locator = str(state.get("source_locator") or "")
        current_file = PureWindowsPath(source_locator).name if "\\" in source_locator else Path(source_locator).name
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
            _ocr_prerequisite_job.update({"status": "running", "running": True, "message": "Installing Tesseract through Windows Package Manager…"})
        result = install_local_ocr_prerequisites(approved=True)
        with _ocr_prerequisite_lock:
            _ocr_prerequisite_job.clear()
            _ocr_prerequisite_job.update({
                **result,
                "running": False,
                "completed_at": time.time(),
            })

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

    def _record_open_token(case_root: Path, evidence_id: str, source_locator: str = "") -> str:
        token = hashlib.sha256(f"{case_root.resolve()}\0{evidence_id}\0{source_locator}".encode("utf-8")).hexdigest()
        _record_open_tokens[token] = (_case_id(case_root), evidence_id, source_locator)
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


    def _group_record_cards(case_root: Path, citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        seen: set[tuple[str, str, int, str]] = set()
        for citation in citations:
            meta = dict(citation.get("metadata") or {})
            parent, member = _record_identity(citation)
            if not parent:
                continue
            page = int(meta.get("page_number") or 0)
            snippet = " ".join(str(citation.get("snippet") or "").split())[:500]
            key = (parent, member, page, snippet.casefold())
            if key in seen:
                continue
            seen.add(key)
            group_id = f"{parent}\0{member}"
            card = grouped.setdefault(group_id, {
                "source_token": _record_open_token(case_root, parent, str(meta.get("source_locator") or "")),
                "basename": _safe_record_basename(citation),
                "document_type": str(meta.get("source_type") or "record"),
                "match_count": 0,
                "pages": [],
                "snippets": [],
            })
            card["match_count"] += 1
            if page and page not in card["pages"]:
                card["pages"].append(page)
            if snippet and snippet not in card["snippets"]:
                card["snippets"].append(snippet)
        return sorted(grouped.values(), key=lambda row: (-int(row["match_count"]), str(row["basename"]).casefold()))


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
                "search_mode": _normalize_search_mode(str(entry.get("search_mode") or payload.search_mode)),
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
                "search_mode": _normalize_search_mode(str(entry.get("search_mode") or payload.search_mode)),
                "response_kind": "source_card_followup",
                "answer": f"The prior answer has {available_count} source card" + ("s" if available_count != 1 else "") + f" in the requested lane, so source card {resolved_selection} is not available. No new search was run.",
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
            citations = citations[resolved_selection - 1:resolved_selection]
        original_mode = _normalize_search_mode(str(entry.get("search_mode") or payload.search_mode))
        direct_record_search = bool(entry.get("direct_record_search"))
        selected_note = f" Source card {resolved_selection} was selected." if resolved_selection else ""
        lane_note = {
            "legal_authority": " Maine-law source filtering was applied.",
            "private_record": " Private-record source filtering was applied.",
        }.get(requested_lane, "")
        return {
            "question": payload.question,
            "answer_style": payload.answer_style,
            "search_mode": original_mode,
            "response_kind": "source_card_followup",
            "answer": f"{len(citations)} source card" + ("s" if len(citations) != 1 else "") + (" is" if len(citations) == 1 else " are") + " ready in the Evidence drawer from the most recent answer. No new search was run." + lane_note + selected_note,
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
        app.mount("/brand-assets", StaticFiles(directory=str(_brand_assets_dir())), name="brand-assets")

    if StaticFiles is not None and _ui_assets_dir().is_dir():
        app.mount("/ui-assets", StaticFiles(directory=str(_ui_assets_dir())), name="ui-assets")

    @app.middleware("http")
    async def local_security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "connect-src 'self'; "
            "img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; "
            "font-src 'self'; "
            "object-src 'none'; "
            "frame-src 'none'; "
            "base-uri 'none'; "
            "form-action 'self'"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["X-DNS-Prefetch-Control"] = "off"
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
        snippets = answer_payload.get("evidence_relied_on", [])
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
                lines.append(f'- No searchable content match for "{target}" in the selected matter.')
            if match_count:
                detail = f"- {match_count} result" + ("s" if match_count != 1 else "")
                if document_count:
                    detail += f" across {document_count} document" + ("s" if document_count != 1 else "")
                if page_count:
                    detail += f" and {page_count} page" + ("s" if page_count != 1 else "")
                lines.append(detail + ".")
                lines.append("- Open the source cards to review the locator, page, match type, and surrounding snippet.")
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
                "missing_information": [] if grounded else ["Confirm the right client/family corpus is active for this install."],
                "follow_up_questions": [] if grounded else ["Do you need to switch to another family or client corpus first?"],
                "intake": _parse_payload_intake(payload).to_dict(),
            },
        }
        # Always group record cards for private-corpus responses so the UI can render
        # clickable drill-down cards instead of repeating raw snippet text.
        result["record_groups"] = _group_record_cards(case_root, list(result["citations"]))
        result["search_summary"] = dict(result["search_summary"]) | {"unique_document_count": len(result["record_groups"])}
        result["family_printables"] = suggest_printables(payload.question) if not direct_search else []
        return _finalize_family_response(result, payload) if finalize else result



    SEARCH_MODES = {"maine_law", "my_records", "both"}

    ANSWER_STYLES = {
        "plain_language",
        "checklist",
        "source_first",
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
        "all", "and", "answer", "do", "give", "it", "legal", "me", "now", "outcome",
        "please", "tell", "that", "the", "this", "what",
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
            query_text = (
                f"{retrieval_question}\n\n"
                f"Context: {payload.matter_context.strip()}"
            )

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

        retrieval = retrieve_fixture_sources(
            expand_query_for_library(query_text)
        )

        answer = compose_answer(
            retrieval_question or question,
            retrieval.results,
            safety,
            answer_style=payload.answer_style,
            matter_context=payload.matter_context,
        )

        result = {
            "question": question,
            "answer_style": payload.answer_style,
            "search_mode": "maine_law",
            "response_kind": "family_answer",
            "intake": intake.to_dict(),
            "intake_label": concise_intake_label(intake),
            "matter_context_used": bool(
                payload.matter_context.strip()
            ),
            "safety": safety.to_dict(),
            **answer.to_dict(),
        }

        result["source_card_count"] = len(
            result.get("citations", [])
        )
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
                metadata.setdefault("proposition", "Supports a statement of Maine law or court process.")
            else:
                metadata["official"] = False
                metadata.setdefault("proposition", "Shows text from the active private matter only; it is not legal authority and does not prove a disputed fact.")
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


    def _finalize_family_response(result: dict[str, Any], payload: AskRequest) -> dict[str, Any]:
        """Attach the canonical v3 answer contract and derive the legacy text from it."""

        mode = _normalize_search_mode(str(result.get("search_mode") or payload.search_mode))
        citations = _redact_citation_paths(list(result.get("citations") or []))
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
            metadata["security_warnings"] = list(dict.fromkeys([
                *metadata["security_warnings"],
                "Invisible controls, invalid identifiers, or oversized input were neutralized at the local request boundary. Review the normalized question before relying on the answer.",
            ]))
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
                1 for item in handoff_safe_source_cards
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
            lane_grounding = {"legal_authority": legal_count > 0, "private_record": record_count > 0}
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
            response_kind=str(result.get("response_kind") or ("local_search_results" if result.get("direct_record_search") else "family_answer")),
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
        if result.get("direct_record_search") or str(result.get("response_kind") or "") == "corpus_inventory":
            result["structured_answer"] = contract
            result["intake"] = intake.to_dict()
            result["intake_label"] = concise_intake_label(intake)
            result["source_lanes"] = lane_grounding
            result["metadata"] = metadata
            return _remember_record_search(payload, result)
        result["structured_answer"] = contract
        result["answer"] = render_legacy_answer(contract)
        result["source_lanes"] = contract["lane_grounding"]
        result["metadata"] = metadata
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

    @app.get("/api/runtime-diagnostics")
    def runtime_diagnostics() -> dict[str, Any]:
        return _runtime_diagnostics_payload()



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
            kind = str(dict(row.get("parser_metadata") or {}).get("document_kind") or source_type or "unknown")
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
        top_level.sort(key=lambda row: (str(row.get("source_type") or ""), str(row.get("source_locator") or row.get("title") or "").casefold()))
        citations: list[dict[str, Any]] = []
        for row in top_level[:24]:
            view = public_record_view(row)
            citations.append({
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
            })
        warnings = sum(parser_statuses.get(key, 0) for key in ("unreadable", "unsupported", "metadata_only"))
        names = [str((item.get("metadata") or {}).get("source_locator") or item.get("title") or "") for item in citations]
        lines = [
            "Indexed corpus inventory:",
            f"- Matter: {describe_case_root(case_root)['label']}",
            f"- {len(top_level)} top-level record(s); {len(records)} total index row(s), including page and attachment rows.",
            f"- {metrics['searchable_records']} searchable record(s); {metrics['searchable_pages']} searchable page(s).",
            f"- {metrics['ocr_candidate_documents']} document(s) contain {metrics['ocr_candidate_pages']} scanned or image-only page(s) awaiting local OCR.",
            f"- {warnings} record(s) need parser or readability review.",
        ]
        if names:
            lines.append("- First indexed records: " + "; ".join(names[:12]) + ("; …" if len(top_level) > 12 else "."))
        lines.append("- Open the record source cards for the first 24 entries, or search for a word or phrase to narrow the corpus.")
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
            parser_statuses[str(row.get("parser_status") or "unknown")] = parser_statuses.get(str(row.get("parser_status") or "unknown"), 0) + 1
            source_types[str(row.get("source_type") or "unknown")] = source_types.get(str(row.get("source_type") or "unknown"), 0) + 1
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
            count for status, count in parser_statuses.items() if status in {"unreadable", "unsupported", "metadata_only"}
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
            "inventory_state": "ocr_choice_required" if ocr_candidate_pages else ("ready_with_warnings" if warnings else "ready"),
            "ocr_engine": local_ocr_engine_status(),
            "index": "local SQLite FTS5 when available",
            "source_evidence_modified": False,
            "local_only": True,
            "network_used": False,
        }



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
            raise HTTPException(status_code=409, detail={
                "code": "one_click_install_unavailable",
                "message": "One-click installation is unavailable. Open the manual Tesseract install page, then recheck.",
                "manual_install_url": status.get("manual_install_url"),
                "windows_installer_url": status.get("windows_installer_url"),
            })
        with _ocr_prerequisite_lock:
            already_running = bool(_ocr_prerequisite_job.get("running"))
            if not already_running:
                _ocr_prerequisite_job.clear()
                _ocr_prerequisite_job.update({
                    "status": "queued",
                    "running": True,
                    "message": "OCR prerequisite installation queued.",
                    "started_at": time.time(),
                })
        if already_running:
            return _public_ocr_prerequisite_job()
        thread = threading.Thread(target=_run_ocr_prerequisite_install, name="mfl-ocr-prerequisite-install", daemon=True)
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
        with _ocr_job_lock:
            existing = _ocr_jobs.get(case_key)
            if existing and existing.get("status") in {"queued", "running"}:
                return {key: value for key, value in existing.items() if key != "cancel_event"}
            cancel_event = threading.Event()
            job_id = uuid.uuid4().hex
            state: dict[str, Any] = {
                "job_id": job_id,
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
                    current_state["processed_documents"] = int(safe_update.get("current") or safe_update.get("completed") or current_state.get("processed_documents") or 0)
                    current_state["processed_pages"] = int(safe_update.get("processed_pages") or current_state.get("processed_pages") or 0)

        def worker() -> None:
            update_progress({"status": "running"})
            try:
                result = run_local_ocr(
                    case_root,
                    language=(payload.language or "eng").strip() or "eng",
                    progress=update_progress,
                    should_cancel=cancel_event.is_set,
                )
                update_progress(result)
            except Exception as exc:
                update_progress(
                    {
                        "status": "failed",
                        "error": "Local OCR could not complete. Review the engine status and source-page readability, then retry.",
                            }
                )

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

    @app.get("/api/records/open/{token}")
    def open_record(token: str, page: int = 0):  # type: ignore[no-untyped-def]
        """Open only a currently indexed, hash-verified active-corpus source."""
        case_root = active_case_root()
        binding = _record_open_tokens.get(str(token))
        if case_root is None or not binding or binding[0] != _case_id(case_root):
            raise HTTPException(status_code=404, detail="record_open_not_available")
        if page < 0 or page > 100_000:
            raise HTTPException(status_code=422, detail="record_open_invalid_page")
        evidence_id, source_locator = binding[1], binding[2]
        rows = load_case_search_records(case_root)
        by_id = {str(item.get("evidence_id") or ""): item for item in rows}
        row = by_id.get(evidence_id)
        if row is None:
            raise HTTPException(status_code=404, detail="record_open_not_indexed")
        # Page and attachment rows inherit the source from their root record.
        root = row
        visited: set[str] = set()
        while str(root.get("parent_evidence_id") or ""):
            parent_id = str(root.get("parent_evidence_id") or "")
            if parent_id in visited or parent_id not in by_id:
                raise HTTPException(status_code=404, detail="record_open_not_indexed")
            visited.add(parent_id)
            root = by_id[parent_id]
        staged_rel = str(root.get("private_copy_relpath") or "")
        if not staged_rel or Path(staged_rel).is_absolute() or ".." in Path(staged_rel).parts:
            raise HTTPException(status_code=404, detail="record_open_not_available")
        path = (case_root / staged_rel).resolve()
        try:
            path.relative_to(case_root.resolve())
        except ValueError:
            raise HTTPException(status_code=404, detail="record_open_not_available") from None
        if not path.is_file():
            raise HTTPException(status_code=404, detail="record_open_source_missing")
        expected = str(root.get("source_hash") or "").lower()
        if expected:
            actual = hashlib.sha256(path.read_bytes()).hexdigest().lower()
            if actual != expected:
                raise HTTPException(status_code=409, detail="record_open_source_hash_mismatch")
        candidate = dict(root)
        candidate["source_path"] = str(path)
        # A #page fragment is presentation metadata, never part of an archive member name.
        candidate["source_locator"] = source_locator.split("#page=", 1)[0] or str(root.get("source_locator") or path.name)
        try:
            data, suffix = _candidate_bytes(candidate)
        except (FileNotFoundError, ValueError, KeyError):
            raise HTTPException(status_code=404, detail="record_open_source_missing") from None
        if "!" in str(candidate["source_locator"]):
            cache = case_root / "04_INDEXES" / "open_cache"
            cache.mkdir(parents=True, exist_ok=True)
            safe_name = hashlib.sha256(data).hexdigest() + (suffix if re.fullmatch(r"\.[a-z0-9]{1,12}", suffix) else "")
            path = cache / safe_name
            if not path.exists():
                path.write_bytes(data)
        mime_type = mimetypes.guess_type(f"record{suffix}")[0] or "application/octet-stream"
        headers = {"X-MFL-Page": str(int(page or 0)), "Cache-Control": "no-store"}
        return FileResponse(path, media_type=mime_type, filename=_safe_record_basename({"metadata": {"source_locator": candidate["source_locator"]}}), headers=headers, content_disposition_type="inline")

    @app.get("/api/import-guidance")
    def import_guidance() -> dict[str, Any]:
        return {
            "local_only": True,
            "sources": ["files", "folders", "ZIP archives", "email exports", "phone exports"],
            "formats": ["PDF", "DOCX", "TXT", "MD", "HTML", "RTF", "EML", "CSV", "XLSX", "PPTX", "ZIP", "images", "audio/video metadata"],
            "how_to_start": "Open the desktop launcher and choose Create New Case Corpus or Reopen Intake / Add More Evidence.",
            "focaf_links": ["https://focaf.jtforme.com/", "https://focaf.jtforme.com/download-library/"],
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
        facts_integrity = harden_text_input(payload.facts_context, max_length=8000, preserve_newlines=True)
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
        response = retrieve_fixture_sources(expanded_query, limit=safe_limit)
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
        context_result = harden_text_input(payload.matter_context, max_length=4000, preserve_newlines=True)
        session_id, session_report = normalize_session_id(payload.session_id)
        last_search_id, search_id_report = normalize_search_id(payload.last_search_id)
        payload.question = question_result.value
        payload.matter_context = context_result.value
        payload.session_id = session_id
        payload.last_search_id = last_search_id if search_id_report["accepted"] else ("__invalid__" if search_id_report["provided"] else "")
        payload.answer_style = _normalize_answer_style(payload.answer_style)
        question = payload.question
        security_flags = [
            flag
            for report in (question_result.report(), context_result.report())
            for flag in report.get("flags", [])
            if flag in {
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
                "matter_context_used": bool(
                    (payload.matter_context or "").strip()
                ),
                "safety": {
                    "category": "general",
                    "requires_citations": False,
                    "requires_disclaimer": True,
                    "requires_emergency_language": False,
                },
                "answer": (
                    "Type a Maine family-law question, "
                    "then press Enter or click Ask."
                ),
                "grounded": False,
                "failure_class": "empty_question",
                "recovery_hint": (
                    "Enter a question such as: "
                    "What are Maine's best-interest factors?"
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
                    inventory["mode_routing_note"] = "Corpus inventory command routed to My records; no Maine-law search was run."
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
                    "metadata": {"intake": intake.to_dict(), "missing_information": ["Select the intended local matter/corpus."]},
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
                    records["mode_routing_note"] = "Direct content-search command routed to My records; no Maine-law search was run."
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
                    "metadata": {"intake": intake.to_dict(), "missing_information": ["Select the intended local matter/corpus."]},
                }
                return _finalize_family_response(unavailable_search, payload)

            if mode == "my_records":
                records = _active_case_chat_payload(payload)

                if records is None:
                    unavailable = {
                        "question": question,
                        "answer_style": payload.answer_style,
                        "search_mode": "my_records",
                        "matter_context_used": bool(
                            payload.matter_context.strip()
                        ),
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
                        "recovery_hint": (
                            "Choose a matter in the corpus library."
                        ),
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
                result["failure_class"] = (
                    "no_active_matter_for_combined_search"
                )
                result["recovery_hint"] = (
                    "Choose a matter to add private-record analysis."
                )
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

            legal_citations = _annotate_source_lanes(list(legal.get("citations", [])), "legal_authority")
            record_citations = _annotate_source_lanes(list(records.get("citations", [])), "private_record")
            citations = legal_citations + record_citations

            legal_grounded = bool(legal.get("grounded"))
            records_grounded = bool(records.get("grounded"))

            combined = {
                "question": question,
                "answer_style": payload.answer_style,
                "search_mode": "both",
                "matter_context_used": bool(
                    payload.matter_context.strip()
                ),
                "safety": legal.get("safety", {}),
                "answer": (
                    "Maine-law lane: "
                    + _first_answer_paragraph(str(legal.get("answer", "")))
                    + "\n\nMatter-record lane: "
                    + _first_answer_paragraph(str(records.get("answer", "")))
                    + "\n\nThe law lane can support legal information. The record lane only shows what appears in the selected files."
                ),
                "response_kind": "combined_lane_answer",
                "grounded": (
                    legal_grounded or records_grounded
                ),
                "failure_class": (
                    "none"
                    if legal_grounded and records_grounded
                    else "combined_search_requires_review"
                ),
                "recovery_hint": (
                    "Review Maine-law source cards separately "
                    "from private-record source cards."
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

        except Exception as exc:
            return {
                "question": question,
                "answer_style": payload.answer_style,
                "search_mode": mode,
                "matter_context_used": bool(
                    (payload.matter_context or "").strip()
                ),
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
                "failure_class": (
                    "local_workbench_internal_error"
                ),
                "recovery_hint": (
                    "Restart the desktop app, refresh, and retry."
                ),
                "citations": [],
                "source_card_count": 0,
                "request_integrity": dict(payload.input_integrity or {}),
            }


    @app.post("/draft")
    def draft(payload: DraftRequest) -> dict[str, Any]:
        request_integrity = harden_text_input(payload.request, max_length=MAX_INTAKE_CHARS, preserve_newlines=True)
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
            retrieval = retrieve_fixture_sources(expand_query_for_library(retrieval_query))
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
    def inspect_source(source_id: str) -> dict[str, Any]:
        source_id = str(source_id or "").strip()[:240]
        if not source_id:
            raise HTTPException(status_code=400, detail="source_id_required")
        case_root = active_case_root()
        if case_root is not None:
            for row in load_case_search_records(case_root):
                if str(row.get("evidence_id", "")) == source_id:
                    return public_record_view(row)
        entry = get_source(load_seed_manifest(), source_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="source_not_found")
        return entry.to_dict()
