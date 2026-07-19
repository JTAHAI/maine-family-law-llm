"""Local-only FastAPI backend for the Maine Family Law LLM workbench."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib

from legal.product.family_justice_workbench_v205 import build_workbench_packet

from . import __version__
from .version import UI_VERSION
from .answer import compose_answer
from .case_corpus_builder import answer_case_question, load_case_search_records
from .case_library import active_case_root, describe_case_root, list_registered_case_roots, set_active_case_root
from .focaf_library import get_printable, printable_pdf_path, public_printable_view, search_printables, suggest_printables
from .local_corpus_index import INDEX_NAME, INVENTORY_CSV, INVENTORY_JSONL, is_direct_content_search, public_record_view, rebuild_local_content_index
from .chat_library import expand_query_for_library, public_library, public_missing_information_prompts, public_prompt_packs, public_topics
from .family_answer_contract import build_family_answer_contract, render_legacy_answer
from .local_workbench_ui import render_local_workbench_html, ui_asset_root
from .draft import draft_from_sources
from .safety import classify_prompt
from .sources import get_source, load_seed_manifest
from .workbench import retrieve_fixture_sources

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


if FastAPI is None:  # pragma: no cover
    app = None
else:
    app = FastAPI(
        title="Maine Family Law LLM Local Workbench",
        version=__version__,
        description="Local legal-information workbench. No legal advice, no cloud deploy, source receipts required.",
    )


if FastAPI is not None:



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
        return response

    def _health_payload() -> dict[str, str]:
        return {"status": "ok", "mode": "local-workbench", "version": __version__}


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
            "evidence_drawer_default_closed": True,
            "command_palette_shortcut": "Ctrl+K",
            "justice_easter_egg_shortcut": "Ctrl+J",
            "constitutional_bar_pass02": True,
            "privacy_overlay": True,
            "keyboard_shortcuts_overlay": True,
            "command_palette_grouped": True,
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
            exact = any(bool(item.get("metadata", {}).get("exact_content_match")) for item in answer_payload.get("citations", []))
            match_count = len(answer_payload.get("citations", []))
            answer_text = (
                "Search result:\n"
                f"- Exact content match: {'found' if exact else 'not found'} in the selected matter.\n"
                f"- {match_count} matching record{'s' if match_count != 1 else ''} from the local searchable index.\n"
                "- Review the source cards for the file/member locator and matched snippet."
            )
        if snippets and not direct_search:
            answer_text += "\n\nRelevant record slices:\n" + "\n".join(f"- {snippet}" for snippet in snippets)
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
            },
        }
        result["family_printables"] = suggest_printables(payload.question) if not direct_search else []
        return _finalize_family_response(result, payload) if finalize else result



    SEARCH_MODES = {"maine_law", "my_records", "both"}


    def _normalize_search_mode(value: str) -> str:
        mode = str(value or "maine_law").strip().lower()
        return mode if mode in SEARCH_MODES else "maine_law"


    def _general_law_payload(
        payload: AskRequest,
        *,
        finalize: bool = True,
    ) -> dict[str, Any]:
        question = (payload.question or "").strip()
        query_text = question

        if payload.matter_context.strip():
            query_text = (
                f"{question}\n\n"
                f"Context: {payload.matter_context.strip()}"
            )

        safety = classify_prompt(query_text)
        retrieval = retrieve_fixture_sources(
            expand_query_for_library(query_text)
        )

        answer = compose_answer(
            question,
            retrieval.results,
            safety,
            answer_style=payload.answer_style,
            matter_context=payload.matter_context,
        )

        result = {
            "question": question,
            "answer_style": payload.answer_style,
            "search_mode": "maine_law",
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
            }
        )
        result["metadata"] = metadata
        result["family_printables"] = suggest_printables(question)

        return _finalize_family_response(result, payload) if finalize else result


    def _annotate_source_lanes(citations: list[dict[str, Any]], lane: str) -> list[dict[str, Any]]:
        """Make source provenance machine-readable in every response surface."""

        annotated: list[dict[str, Any]] = []
        for item in citations:
            copy = dict(item)
            metadata = dict(copy.get("metadata") or {})
            metadata["source_lane"] = lane
            if lane == "legal_authority":
                metadata.setdefault("official", True)
                metadata.setdefault("jurisdiction", "Maine")
                metadata.setdefault("proposition", "Supports a statement of Maine law or court process.")
            else:
                metadata["official"] = False
                metadata.setdefault("proposition", "Supports a factual statement from the active private matter only.")
            copy["metadata"] = metadata
            annotated.append(copy)
        return annotated


    def _finalize_family_response(result: dict[str, Any], payload: AskRequest) -> dict[str, Any]:
        """Attach the canonical v3 answer contract and derive the legacy text from it."""

        mode = _normalize_search_mode(str(result.get("search_mode") or payload.search_mode))
        citations = list(result.get("citations") or [])
        default_lane = "private_record" if mode == "my_records" else "legal_authority"
        citations = _annotate_source_lanes(citations, default_lane)
        metadata = dict(result.get("metadata") or {})
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
            child_impact_enabled=bool(payload.child_impact_lens),
            lane_grounding=lane_grounding,
        )
        result["citations"] = citations
        result["source_card_count"] = len(citations)
        if result.get("direct_record_search"):
            result["source_lanes"] = lane_grounding
            result["metadata"] = metadata
            return result
        result["structured_answer"] = contract
        result["answer"] = render_legacy_answer(contract)
        result["source_lanes"] = contract["lane_grounding"]
        result["metadata"] = metadata
        return result


    @app.exception_handler(Exception)
    async def json_exception_handler(request: Request, exc: Exception) -> JSONResponse:  # type: ignore[type-arg]
        return JSONResponse(
            status_code=500,
            content={
                "detail": "internal_server_error",
                "message": str(exc) or exc.__class__.__name__,
                "recovery_hint": "Restart START_LOCAL_CHAT.ps1, refresh the browser, and retry. If this persists, paste the terminal traceback into the issue.",
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
    def healthz() -> dict[str, str]:
        return _health_payload()

    @app.get("/api/health")
    def api_health() -> dict[str, str]:
        return _health_payload()

    @app.get("/api/version")
    def api_version() -> dict[str, str]:
        return {"version": __version__, "api_mode": "local-workbench", "workbench_url": "/"}

    @app.get("/api/runtime-diagnostics")
    def runtime_diagnostics() -> dict[str, Any]:
        return _runtime_diagnostics_payload()

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
        ocr_candidates = sum(1 for row in records if row.get("ocr_status") == "ocr_not_run")
        searchable_records = sum(1 for row in records if row.get("text_status") in {"available", "native_text", "ocr_text", "searchable"})
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
            "searchable_records": searchable_records,
            "inventory_state": "ocr_choice_required" if ocr_candidates else ("ready_with_warnings" if warnings else "ready"),
            "index": "local SQLite FTS5 when available",
            "source_evidence_modified": False,
        }

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
        return search_printables(q, limit=limit)

    @app.get("/api/printables/{document_id}")
    def printable_preview(document_id: str) -> dict[str, Any]:
        document = get_printable(document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="printable_not_found")
        return public_printable_view(document) | {
            "headings": document.get("headings", []),
            "warnings": document.get("warnings", []),
        }

    @app.get("/api/printables/{document_id}/open")
    def printable_open(document_id: str):  # type: ignore[no-untyped-def]
        path = printable_pdf_path(document_id)
        if path is None or FileResponse is None:
            raise HTTPException(status_code=404, detail="printable_not_found")
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

    @app.post("/api/family-justice-workbench")
    def family_justice_workbench(payload: FamilyJusticeWorkbenchRequest) -> dict[str, Any]:
        return build_workbench_packet(
            payload.question,
            audience=payload.audience,
            posture=payload.posture,
            facts_context=payload.facts_context,
            requested_output_style=payload.requested_output_style,
        )

    @app.post("/retrieve")
    def retrieve(payload: QueryRequest) -> dict[str, Any]:
        expanded_query = expand_query_for_library(payload.query)
        response = retrieve_fixture_sources(expanded_query, limit=payload.limit)
        return {
            "query": response.query,
            "failure_class": response.failure_class,
            "recovery_hint": response.recovery_hint,
            "results": [result.to_dict() for result in response.results],
        }

    @app.post("/ask")
    def ask(payload: AskRequest) -> dict[str, Any]:
        question = (payload.question or "").strip()
        mode = _normalize_search_mode(payload.search_mode)

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
            }

        try:
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
                return result

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
                    "Maine-law research:\n\n"
                    + str(legal.get("answer", ""))
                    + "\n\nMatter records:\n\n"
                    + "No active indexed matter was available."
                )
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
                    "Maine-law research:\n\n"
                    + str(legal.get("answer", ""))
                    + "\n\nMatter records:\n\n"
                    + str(records.get("answer", ""))
                    + "\n\n"
                    + "Review legal authority and matter facts "
                    + "as separate source lanes."
                ),
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
                    "The local workbench encountered an internal "
                    "error but remained open. "
                    f"Error class: {exc.__class__.__name__}"
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
            }


    @app.post("/draft")
    def draft(payload: DraftRequest) -> dict[str, Any]:
        retrieval = retrieve_fixture_sources(payload.request)
        draft_result = draft_from_sources(payload.request, retrieval.results, mode=payload.mode)
        return {
            "text": draft_result.text,
            "failure_class": draft_result.failure_class,
            "recovery_hint": draft_result.recovery_hint,
            "citations": [item.to_dict() for item in draft_result.citations],
        }

    @app.get("/inspect-source/{source_id}")
    def inspect_source(source_id: str) -> dict[str, Any]:
        case_root = active_case_root()
        if case_root is not None:
            for row in load_case_search_records(case_root):
                if str(row.get("evidence_id", "")) == source_id:
                    return public_record_view(row)
        entry = get_source(load_seed_manifest(), source_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="source_not_found")
        return entry.to_dict()
