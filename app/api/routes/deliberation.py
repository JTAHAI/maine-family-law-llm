from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from app.api.security import review_response
from legal.deliberation.host import DeliberationHost, DeliberationHostError
from legal.provider_connections import ProviderConnectionService
from legal.provider_connections.service import ProviderConnectionError
from legal.security.local_request_firewall import evaluate_local_request

router = APIRouter(tags=["deliberation"])
HOST = DeliberationHost(project_root=Path(__file__).resolve().parents[3])
PROVIDER_SERVICE = ProviderConnectionService(project_root=Path(__file__).resolve().parents[3], store_root=os.environ.get("MFL_PROVIDER_STORE_ROOT") or None)


def _handle_error(exc: DeliberationHostError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail={"error": exc.code, "message": exc.message})


def _handle_provider_error(exc: ProviderConnectionError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail={"error": exc.code, "message": exc.message})


def _enforce_local_request(request: Request) -> None:
    decision = evaluate_local_request(
        method=request.method,
        path=request.url.path,
        client_host=request.client.host if request.client else None,
        host_header=request.headers.get("host", ""),
        origin_header=request.headers.get("origin", ""),
        sec_fetch_site=request.headers.get("sec-fetch-site", ""),
        content_length=request.headers.get("content-length", ""),
    )
    if not decision.allowed:
        raise HTTPException(status_code=decision.status_code, detail=decision.code)


def _invoke(handler, *args, action: str, endpoint: str, **kwargs) -> dict[str, Any]:
    try:
        result = handler(*args, **kwargs)
    except DeliberationHostError as exc:
        raise _handle_error(exc) from exc
    return review_response(endpoint, action, result)


@router.get("/deliberation/presets", summary="List deliberation presets")
def list_presets(x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    presets = HOST.list_presets()
    return review_response(
        "GET /api/deliberation/presets",
        "deliberation_list_presets",
        {"presets": presets, "count": len(presets), "review_required": True, "audience_hint": x_user_role},
    )


@router.get("/deliberation/tools", summary="List deliberation tools")
def list_tools(x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    tools = HOST.list_tools()
    return review_response(
        "GET /api/deliberation/tools",
        "deliberation_list_tools",
        {"tools": tools, "count": len(tools), "review_required": True, "audience_hint": x_user_role},
    )


@router.post("/deliberation/runs", summary="Create a deliberation run")
def create_run(payload: dict[str, Any], x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    return _invoke(HOST.create_run, payload, action="deliberation_run_create", endpoint="POST /api/deliberation/runs")


@router.get("/deliberation/runs/{run_id}", summary="Fetch a deliberation run")
def get_run(run_id: str, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    return _invoke(HOST.get_run, run_id, action="deliberation_run_get", endpoint="GET /api/deliberation/runs/{run_id}")


@router.post("/deliberation/runs/{run_id}/confirm", summary="Confirm a frozen local scope")
def confirm_run(run_id: str, payload: dict[str, Any], x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    return _invoke(HOST.confirm_run, run_id, payload, action="deliberation_run_confirm", endpoint="POST /api/deliberation/runs/{run_id}/confirm")


@router.post("/deliberation/runs/{run_id}/start", summary="Start a deliberation run")
def start_run(run_id: str, payload: dict[str, Any] | None = None, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    return _invoke(HOST.start_run, run_id, payload, action="deliberation_run_start", endpoint="POST /api/deliberation/runs/{run_id}/start")


@router.post("/deliberation/runs/{run_id}/cancel", summary="Cancel a deliberation run")
def cancel_run(run_id: str, payload: dict[str, Any], request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    try:
        host_result = HOST.cancel_run(run_id, payload)
        provider_result = PROVIDER_SERVICE.cancel(run_id)
    except DeliberationHostError as exc:
        raise _handle_error(exc) from exc
    except ProviderConnectionError as exc:
        raise _handle_provider_error(exc) from exc
    host_result["provider_cancellation"] = provider_result
    return review_response("POST /api/deliberation/runs/{run_id}/cancel", "deliberation_run_cancel", host_result)


@router.get("/deliberation/runs/{run_id}/events", summary="List deliberation events")
def list_events(run_id: str, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    return _invoke(HOST.get_events, run_id, action="deliberation_run_events", endpoint="GET /api/deliberation/runs/{run_id}/events")


@router.get("/deliberation/runs/{run_id}/claims", summary="List deliberation claims")
def list_claims(run_id: str, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    return _invoke(HOST.get_claims, run_id, action="deliberation_run_claims", endpoint="GET /api/deliberation/runs/{run_id}/claims")


@router.get("/deliberation/runs/{run_id}/positions", summary="List worker positions")
def list_positions(run_id: str, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    return _invoke(HOST.get_positions, run_id, action="deliberation_run_positions", endpoint="GET /api/deliberation/runs/{run_id}/positions")


@router.get("/deliberation/runs/{run_id}/synthesis", summary="Fetch the final synthesis")
def get_synthesis(run_id: str, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    return _invoke(HOST.get_synthesis, run_id, action="deliberation_run_synthesis", endpoint="GET /api/deliberation/runs/{run_id}/synthesis")


@router.post("/deliberation/runs/{run_id}/outbound-preview", summary="Preview exact outbound provider consent")
def outbound_preview(
    run_id: str,
    payload: dict[str, Any],
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    try:
        run = HOST.get_run(run_id)
        scope = run.get("scope_freeze") or {}
        preview_payload = {
            **payload,
            "question": str(payload.get("question") or scope.get("exact_question") or run.get("question") or ""),
            "source_lanes": list(payload.get("source_lanes") or run.get("source_lanes") or []),
            "allowed_tools": list(payload.get("allowed_tools") or scope.get("allowed_tools") or []),
            "retention_data_control_summary": str(payload.get("retention_data_control_summary") or "BYOK provider retention stays under the provider's own policy surface."),
        }
        manifest = PROVIDER_SERVICE.build_manifest(run_id=run_id, provider_id=str(payload.get("provider_id") or ""), payload=preview_payload)
    except DeliberationHostError as exc:
        raise _handle_error(exc) from exc
    except ProviderConnectionError as exc:
        raise _handle_provider_error(exc) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return review_response(
        "POST /api/deliberation/runs/{run_id}/outbound-preview",
        "deliberation_outbound_preview",
        {"manifest": manifest.as_dict(), "review_required": True, "local_only": True},
    )


@router.post("/deliberation/runs/{run_id}/approve-outbound", summary="Approve an outbound provider manifest")
def approve_outbound(
    run_id: str,
    payload: dict[str, Any],
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    manifest_id = str(payload.get("manifest_id") or "").strip()
    actor = str(payload.get("approval_actor") or x_user_role or "reviewer")
    try:
        approval = PROVIDER_SERVICE.approve_manifest(manifest_id, actor=actor, run_id=run_id)
    except ProviderConnectionError as exc:
        raise _handle_provider_error(exc) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return review_response(
        "POST /api/deliberation/runs/{run_id}/approve-outbound",
        "deliberation_approve_outbound",
        {"run_id": run_id, "approval": approval.as_dict(), "review_required": True},
    )


@router.post("/deliberation/runs/{run_id}/start-external", summary="Start an approved external provider run")
def start_external(
    run_id: str,
    payload: dict[str, Any],
    request: Request,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    _enforce_local_request(request)
    manifest_id = str(payload.get("manifest_id") or "").strip()
    try:
        result = PROVIDER_SERVICE.start_external(manifest_id, run_id=run_id)
    except ProviderConnectionError as exc:
        raise _handle_provider_error(exc) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return review_response(
        "POST /api/deliberation/runs/{run_id}/start-external",
        "deliberation_start_external",
        {"run_id": run_id, **result, "review_required": True},
    )


@router.get("/deliberation/runs/{run_id}/usage", summary="Fetch provider usage for a run")
def usage(run_id: str, request: Request, x_user_role: str | None = Header(default=None, alias="X-User-Role")):
    _enforce_local_request(request)
    result = PROVIDER_SERVICE.usage(run_id)
    return review_response("GET /api/deliberation/runs/{run_id}/usage", "deliberation_run_usage", result)


@router.post("/deliberation/runs/{run_id}/tools/{tool_name}", summary="Invoke an allowed deliberation tool")
def invoke_tool(
    run_id: str,
    tool_name: str,
    payload: dict[str, Any],
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    return _invoke(HOST.invoke_tool, run_id, tool_name, payload, action="deliberation_tool_invoke", endpoint="POST /api/deliberation/runs/{run_id}/tools/{tool_name}")
