"""Canonical offline-pack routes, using the existing local identity/audit boundary."""

from __future__ import annotations

import asyncio
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

from app.services.model_pack_service import ModelPackError, ModelPackService, external_root
from legal.fast_interchange.admission import AdmissionAuthority, digest


class PackScope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    matter_id: str = Field(min_length=1, max_length=100)


class PackImport(PackScope):
    total_bytes: StrictInt
    user_confirmed: StrictBool


class PackActivation(PackScope):
    pack_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    user_confirmed: StrictBool


class PackResume(PackScope):
    expected_bytes: StrictInt = Field(ge=0, le=3 * 1024**3)
    prefix_chain: str = Field(pattern=r"^[a-f0-9]{64}$")
    user_confirmed: StrictBool


class PackConsent(PackScope):
    user_confirmed: StrictBool


class PackInstalledActivation(PackConsent):
    expected_active: str = Field(pattern=r"^(?:[a-f0-9]{64})?$")


class PackRecovery(PackConsent):
    transaction_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    action: Literal["finish", "deactivate", "abandon"]


@lru_cache(maxsize=4)
def _service(root: str, trust: str, state: str) -> ModelPackService:
    return ModelPackService(
        Path(root),
        AdmissionAuthority(trust_path=Path(trust), state_root=Path(state)),
        forbidden_roots=(Path(__file__).resolve().parents[2],),
    )


def configured_service(matter_root: Path):
    root = os.environ.get("MFL_FAST_INTERCHANGE_PACK_ROOT", "")
    trust = os.environ.get("MFL_FAST_INTERCHANGE_ADMISSION_TRUST", "")
    state = os.environ.get("MFL_FAST_INTERCHANGE_STATE_ROOT", "")
    if not root or not trust or not state:
        raise ModelPackError("model_pack_operator_setup_required")
    external_root(Path(root), (matter_root, Path(__file__).resolve().parents[2]))
    return _service(root, trust, state)


def register_model_pack_routes(app: FastAPI, *, scope_resolver, audit_factory):
    def context(payload, request, *, mutation=False):
        scope, root = scope_resolver(payload, request)
        if mutation and scope["role"] != "admin":
            raise HTTPException(403, detail="model_pack_local_admin_confirmation_required")
        try:
            service = configured_service(root)
        except ModelPackError as exc:
            raise HTTPException(exc.status_code, detail=exc.code) from exc

        def audit(action, binding):
            # Fail closed if a long verification outlived its active matter.
            scope_resolver(payload, request)
            audit_factory(root).record(action, scope=scope, binding_sha256=binding)

        return service, scope, audit

    def invoke(call):
        try:
            return call()
        except HTTPException:
            raise
        except Exception as exc:
            code = getattr(exc, "code", "")
            if not code.startswith(("model_pack_", "fast_interchange_", "local_agent_")):
                code = "model_pack_operation_failed"
            raise HTTPException(getattr(exc, "status_code", 409), detail=code) from exc

    @app.get("/api/model-packs")
    def inventory(matter_id: str, request: Request):
        service, scope, audit = context(PackScope(matter_id=matter_id), request)

        def run():
            result = service.inventory(scope=scope)
            audit("model_pack_inventory_viewed", digest(result))
            return result

        return invoke(run)

    @app.post("/api/model-packs/imports")
    def begin(payload: PackImport, request: Request):
        service, scope, audit = context(payload, request, mutation=True)
        if not payload.user_confirmed:
            raise HTTPException(422, detail="model_pack_import_consent_required")
        return invoke(
            lambda: service.begin(scope=scope, total_bytes=payload.total_bytes, audit=audit)
        )

    @app.post("/api/model-packs/imports/{job_id}/chunks")
    async def chunk(job_id: str, matter_id: str, offset: int, request: Request):
        service, scope, _ = context(PackScope(matter_id=matter_id), request, mutation=True)
        data = await request.body()  # Canonical firewall has already bounded this body to 2 MiB.
        return await asyncio.to_thread(
            invoke, lambda: service.chunk(job_id, scope=scope, offset=offset, data=data)
        )

    @app.get("/api/model-packs/imports/{job_id}")
    def status(job_id: str, matter_id: str, request: Request):
        service, scope, _ = context(PackScope(matter_id=matter_id), request)
        return invoke(lambda: service.status(job_id, scope=scope))

    @app.post("/api/model-packs/imports/{job_id}/inspect")
    async def inspect(job_id: str, payload: PackScope, request: Request):
        service, scope, audit = context(payload, request, mutation=True)
        return await asyncio.to_thread(
            invoke, lambda: service.inspect(job_id, scope=scope, audit=audit)
        )

    @app.post("/api/model-packs/imports/{job_id}/cancel")
    def cancel(job_id: str, payload: PackScope, request: Request):
        service, scope, audit = context(payload, request, mutation=True)
        return invoke(lambda: service.cancel(job_id, scope=scope, audit=audit))

    @app.post("/api/model-packs/imports/{job_id}/resume")
    async def resume(job_id: str, payload: PackResume, request: Request):
        service, scope, audit = context(payload, request, mutation=True)
        if not payload.user_confirmed:
            raise HTTPException(422, detail="model_pack_resume_consent_required")
        return await asyncio.to_thread(
            invoke,
            lambda: service.resume(
                job_id,
                scope=scope,
                expected_bytes=payload.expected_bytes,
                prefix_chain=payload.prefix_chain,
                audit=audit,
            ),
        )

    @app.post("/api/model-packs/imports/{job_id}/activate")
    def activate(job_id: str, payload: PackActivation, request: Request):
        service, scope, audit = context(payload, request, mutation=True)
        if not payload.user_confirmed:
            raise HTTPException(422, detail="model_pack_activation_consent_required")
        return invoke(
            lambda: service.activate(job_id, scope=scope, audit=audit, pack_id=payload.pack_id)
        )

    @app.post("/api/model-packs/imports/{job_id}/discard")
    def discard(job_id: str, payload: PackScope, request: Request):
        service, scope, audit = context(payload, request, mutation=True)
        return invoke(lambda: service.discard(job_id, scope=scope, audit=audit))

    @app.post("/api/model-packs/recovery")
    async def recover(payload: PackRecovery, request: Request):
        service, scope, audit = context(payload, request, mutation=True)
        if not payload.user_confirmed:
            raise HTTPException(422, detail="model_pack_recovery_consent_required")
        return await asyncio.to_thread(
            invoke,
            lambda: service.recover(
                scope=scope,
                audit=audit,
                transaction_id=payload.transaction_id,
                deactivate=payload.action == "deactivate",
                abandon=payload.action == "abandon",
            ),
        )

    @app.post("/api/model-packs/installed/{pack_id}/activate")
    async def activate_installed(pack_id: str, payload: PackInstalledActivation, request: Request):
        service, scope, audit = context(payload, request, mutation=True)
        if not payload.user_confirmed:
            raise HTTPException(422, detail="model_pack_activation_consent_required")
        return await asyncio.to_thread(
            invoke,
            lambda: service.activate_installed(
                scope=scope,
                audit=audit,
                pack_id=pack_id,
                expected_active=payload.expected_active,
            ),
        )

    @app.post("/api/model-packs/installed/{pack_id}/remove")
    def remove(pack_id: str, payload: PackConsent, request: Request):
        service, scope, audit = context(payload, request, mutation=True)
        if not payload.user_confirmed:
            raise HTTPException(422, detail="model_pack_remove_consent_required")
        return invoke(lambda: service.remove(scope=scope, audit=audit, pack_id=pack_id))

    @app.post("/api/model-packs/removed/{pack_id}/restore")
    async def restore(pack_id: str, payload: PackConsent, request: Request):
        service, scope, audit = context(payload, request, mutation=True)
        if not payload.user_confirmed:
            raise HTTPException(422, detail="model_pack_restore_consent_required")
        return await asyncio.to_thread(
            invoke, lambda: service.restore(scope=scope, audit=audit, pack_id=pack_id)
        )
