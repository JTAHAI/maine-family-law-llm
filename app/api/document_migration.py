"""Canonical scoped inspection and explicitly confirmed draft-JSON migration."""

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from legal.documents.migration import execute
from legal.documents.migration_review import review
from legal.documents.workspace import DocumentWorkspaceError


class MigrationReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    matter_id: str = Field(min_length=1, max_length=100)


class MigrationExecuteRequest(MigrationReviewRequest):
    expected_manifest: str = Field(pattern=r"^[a-f0-9]{64}$")
    confirmed: StrictBool


def register_document_migration_routes(app: FastAPI, *, scope_resolver, audit_factory):
    @app.post("/api/document-workspace/migration-execute")
    def migrate(payload: MigrationExecuteRequest, request: Request):
        scope, root = scope_resolver(payload, request)
        if scope["role"] != "admin":
            raise HTTPException(403, detail="workspace_migration_admin_confirmation_required")

        def guard():
            current, current_root = scope_resolver(payload, request)
            if current != scope or current_root != root:
                raise HTTPException(409, detail="workspace_migration_scope_changed")

        try:
            if not payload.confirmed:
                raise HTTPException(422, detail="workspace_migration_confirmation_required")
            audit_factory(root).record(
                "document_migration_confirmed",
                scope=scope,
                binding_sha256=payload.expected_manifest,
            )
            result = execute(
                root,
                expected_manifest=payload.expected_manifest,
                confirmed=payload.confirmed,
                guard=guard,
            )
            guard()
            audit_factory(root).record(
                "document_migration_completed",
                scope=scope,
                binding_sha256=payload.expected_manifest,
            )
            return {**result, "matter_id": payload.matter_id}
        except DocumentWorkspaceError as exc:
            raise HTTPException(
                exc.status_code, detail={"code": exc.code, "message": exc.message}
            ) from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(409, detail="workspace_migration_result_unavailable") from None

    @app.post("/api/document-workspace/migration-review")
    def inspect(payload: MigrationReviewRequest, request: Request):
        scope, root = scope_resolver(payload, request)
        try:
            result = review(root)
            current, current_root = scope_resolver(payload, request)
            if current != scope or current_root != root:
                raise HTTPException(409, detail="workspace_migration_scope_changed")
            audit_factory(root).record(
                "document_migration_reviewed",
                scope=scope,
                binding_sha256=result["manifest_sha256"],
            )
            return {**result, "matter_id": payload.matter_id}
        except DocumentWorkspaceError as exc:
            raise HTTPException(
                exc.status_code, detail={"code": exc.code, "message": exc.message}
            ) from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(409, detail="workspace_migration_review_unavailable") from None
