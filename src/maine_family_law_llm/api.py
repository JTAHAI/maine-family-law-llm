"""Local-only FastAPI backend for the Maine Family Law LLM workbench."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from legal.product.family_justice_workbench_v205 import build_workbench_packet

from . import __version__
from .answer import compose_answer
from .case_corpus_builder import answer_case_question, load_case_search_records
from .case_library import active_case_root, describe_case_root, list_registered_case_roots, set_active_case_root
from .chat_library import expand_query_for_library, public_library, public_missing_information_prompts, public_prompt_packs, public_topics
from .local_workbench_ui import render_local_workbench_html
from .draft import draft_from_sources
from .safety import classify_prompt
from .sources import get_source, load_seed_manifest
from .workbench import retrieve_fixture_sources

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
except Exception:  # pragma: no cover - lets CLI import without API extras
    FastAPI = None  # type: ignore[assignment]
    HTTPException = Exception  # type: ignore[assignment]
    HTMLResponse = None  # type: ignore[assignment]
    JSONResponse = None  # type: ignore[assignment]
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
    case_root: str


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


    if StaticFiles is not None and _brand_assets_dir().is_dir():
        app.mount("/brand-assets", StaticFiles(directory=str(_brand_assets_dir())), name="brand-assets")

    def _health_payload() -> dict[str, str]:
        return {"status": "ok", "mode": "local-workbench", "version": __version__}


    def _runtime_diagnostics_payload() -> dict[str, Any]:
        active_case = active_case_root()
        case_summary = describe_case_root(active_case) if active_case else None
        return {
            "status": "ok",
            "version": __version__,
            "ui_version": "2.08.0-modern-constitutional-chat",
            "mode": "local-workbench",
            "enter_to_submit": True,
            "enter_submit_clears_input": True,
            "branding": "Constitutional public-service chat shell with local brand assets served from /brand-assets",
            "brand_assets_mounted": _brand_assets_dir().is_dir(),
            "appeals_routing_fix": True,
            "chat_library_routing_v187": True,
            "constitutional_chat_shell_v208": True,
            "chat_panel_primary_layout": True,
            "brand_kit": "assets/brand/focaf_family_law_llm_brand_kit",
            "appeals_test_question": "What court handles appeals?",
            "workbench_url": "/",
            "review_required": True,
            "not_legal_advice": True,
            "active_case_root": str(active_case) if active_case else "",
            "active_case_label": case_summary["label"] if case_summary else "",
            "registered_case_count": len(list_registered_case_roots()),
        }


    def _active_case_chat_payload(payload: AskRequest) -> dict[str, Any] | None:
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
        if snippets:
            answer_text += "\n\nRelevant record slices:\n" + "\n".join(f"- {snippet}" for snippet in snippets)
        return {
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
            "grounded": grounded,
            "failure_class": "none" if grounded else "not_found_in_indexed_case_corpus",
            "recovery_hint": "Switch the active corpus, broaden the question, or inspect the case search portal if the answer stayed empty.",
            "citations": answer_payload.get("citations", []),
            "source_card_count": len(answer_payload.get("citations", [])),
            "review_required": True,
            "not_legal_advice": True,
            "corpus_mode": "active_case_corpus",
            "active_case_root": str(case_root),
            "active_case_label": case_summary["label"],
            "metadata": {
                "active_case_root": str(case_root),
                "active_case_label": case_summary["label"],
                "indexed_records": case_summary["indexed_records"],
                "pdf_pages": case_summary["pdf_pages"],
                "missing_information": [] if grounded else ["Confirm the right client/family corpus is active for this install."],
                "follow_up_questions": [] if grounded else ["Do you need to switch to another family or client corpus first?"],
            },
        }


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
                return records[:200]
        return [entry.to_dict() for entry in load_seed_manifest()]

    @app.get("/api/corpus-library")
    def api_corpus_library() -> dict[str, Any]:
        active_case = active_case_root()
        case_summary = describe_case_root(active_case) if active_case else None
        return {
            "active_case_root": str(active_case) if active_case else "",
            "active_case_label": case_summary["label"] if case_summary else "",
            "cases": list_registered_case_roots(),
        }

    @app.post("/api/activate-corpus")
    def api_activate_corpus(payload: ActivateCorpusRequest) -> dict[str, Any]:
        case_root = Path(payload.case_root).expanduser()
        if not case_root.exists():
            raise HTTPException(status_code=404, detail="case_corpus_not_found")
        set_active_case_root(case_root)
        summary = describe_case_root(case_root)
        return {
            "status": "ok",
            "active_case_root": str(case_root.resolve()),
            "active_case_label": summary["label"],
        }

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
        if not question:
            return {
                "question": payload.question,
                "answer_style": payload.answer_style,
                "matter_context_used": bool((payload.matter_context or "").strip()),
                "safety": {"category": "general", "requires_citations": False, "requires_disclaimer": True, "requires_emergency_language": False},
                "answer": "Type a Maine family-law question, then press Enter or click Ask.",
                "grounded": False,
                "failure_class": "empty_question",
                "recovery_hint": "Enter a question such as: What are Maine's best-interest factors?",
                "citations": [],
            }
        try:
            active_case_payload = _active_case_chat_payload(payload)
            if active_case_payload is not None:
                return active_case_payload
            query_text = question
            if payload.matter_context.strip():
                query_text = f"{question}\n\nContext: {payload.matter_context.strip()}"
            safety = classify_prompt(query_text)
            retrieval = retrieve_fixture_sources(expand_query_for_library(query_text))
            answer = compose_answer(
                question,
                retrieval.results,
                safety,
                answer_style=payload.answer_style,
                matter_context=payload.matter_context,
            )
            return {
                "question": question,
                "answer_style": payload.answer_style,
                "matter_context_used": bool(payload.matter_context.strip()),
                "safety": safety.to_dict(),
                **answer.to_dict(),
            }
        except Exception as exc:
            return {
                "question": question,
                "answer_style": payload.answer_style,
                "matter_context_used": bool((payload.matter_context or "").strip()),
                "safety": {"category": "error", "requires_citations": False, "requires_disclaimer": True, "requires_emergency_language": False},
                "answer": (
                    "The local workbench hit an internal error, but the browser recovered instead of crashing. "
                    "Restart START_LOCAL_CHAT.ps1 if needed and paste the terminal traceback into the next review pass.\n\n"
                    f"Error class: {exc.__class__.__name__}\nRecovery hint: retry the question, or use a starter prompt from the library."
                ),
                "grounded": False,
                "failure_class": "local_workbench_internal_error",
                "recovery_hint": "Restart START_LOCAL_CHAT.ps1, refresh the browser, and retry. If this persists, paste the terminal traceback into the issue.",
                "citations": [],
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
                    return row
        entry = get_source(load_seed_manifest(), source_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="source_not_found")
        return entry.to_dict()
