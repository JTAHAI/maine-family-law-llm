"""Local-only FastAPI backend for the Maine Family Law LLM workbench."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import __version__
from .answer import compose_answer
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
        return {
            "status": "ok",
            "version": __version__,
            "ui_version": "1.86.0-classic-desktop-focaf-workbench",
            "mode": "local-workbench",
            "enter_to_submit": True,
            "branding": "FOCAF brand kit assets served from /brand-assets",
            "brand_assets_mounted": _brand_assets_dir().is_dir(),
            "appeals_routing_fix": True,
            "brand_kit": "assets/brand/focaf_family_law_llm_brand_kit",
            "appeals_test_question": "What court handles appeals?",
            "workbench_url": "/",
            "review_required": True,
            "not_legal_advice": True,
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
        return [entry.to_dict() for entry in load_seed_manifest()]

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
        entry = get_source(load_seed_manifest(), source_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="source_not_found")
        return entry.to_dict()
