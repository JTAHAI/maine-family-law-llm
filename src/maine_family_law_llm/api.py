"""Local-only FastAPI backend for the Maine Family Law LLM workbench."""

from __future__ import annotations

from typing import Any

from .answer import compose_answer
from .draft import draft_from_sources
from .safety import classify_prompt
from .sources import get_source, load_seed_manifest
from .workbench import retrieve_fixture_sources

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
except Exception:  # pragma: no cover - lets CLI import without API extras
    FastAPI = None  # type: ignore[assignment]
    HTTPException = Exception  # type: ignore[assignment]

    class BaseModel:  # type: ignore[no-redef]
        pass


class QueryRequest(BaseModel):
    query: str
    limit: int = 5


class AskRequest(BaseModel):
    question: str


class DraftRequest(BaseModel):
    request: str
    mode: str = "checklist"


if FastAPI is None:  # pragma: no cover
    app = None
else:
    app = FastAPI(
        title="Maine Family Law LLM Local Workbench",
        version="1.0.0",
        description="Local legal-information workbench. No legal advice, no cloud deploy, source receipts required.",
    )


if FastAPI is not None:

    def _health_payload() -> dict[str, str]:
        return {"status": "ok", "mode": "local-workbench"}

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return _health_payload()

    @app.get("/api/health")
    def api_health() -> dict[str, str]:
        return _health_payload()

    @app.get("/api/version")
    def api_version() -> dict[str, str]:
        return {"version": "1.45.0", "api_mode": "local-workbench"}

    @app.get("/sources")
    def sources() -> list[dict[str, Any]]:
        return [entry.to_dict() for entry in load_seed_manifest()]

    @app.post("/retrieve")
    def retrieve(payload: QueryRequest) -> dict[str, Any]:
        response = retrieve_fixture_sources(payload.query, limit=payload.limit)
        return {
            "query": response.query,
            "failure_class": response.failure_class,
            "recovery_hint": response.recovery_hint,
            "results": [result.to_dict() for result in response.results],
        }

    @app.post("/ask")
    def ask(payload: AskRequest) -> dict[str, Any]:
        safety = classify_prompt(payload.question)
        retrieval = retrieve_fixture_sources(payload.question)
        answer = compose_answer(payload.question, retrieval.results, safety)
        return {"safety": safety.to_dict(), **answer.to_dict()}

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
