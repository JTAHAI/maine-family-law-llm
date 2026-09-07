"""One production exclusion policy for dispatch, OpenAPI and contract auditing."""

import os
from contextvars import ContextVar

# Server-owned request context, never a caller header or a development toggle.
# Context propagates into FastAPI's threadpool and resets after dispatch.
production_request_active: ContextVar[bool] = ContextVar("mfl_production_request", default=False)


def official_authority_required() -> bool:
    return (
        production_request_active.get()
        or os.environ.get("MFL_RUNTIME_MODE", "").strip().lower() == "store"
    )


def unsafe_legacy_path(path: str) -> bool:
    # Backend code/data stay intact. These demonstrations and the unscoped job
    # queue are not production features, even when development flags are set.
    normalized = path.rstrip("/")
    return normalized in {"/api/citations/verify", "/api/research", "/api/query"} or (
        normalized == "/api/runtime/jobs" or normalized.startswith("/api/runtime/jobs/")
    )
