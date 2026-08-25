from fastapi import Depends, FastAPI

from app.api.routes.deliberation import router as deliberation_router
from app.api.routes.health import router as health_router
from app.api.routes.evals import router as evals_router
from app.api.routes.models import router as models_router
from app.api.routes.release_control import router as release_control_router
from app.api.routes.release_maintenance import router as release_maintenance_router
from app.api.routes.governance import router as governance_router
from app.api.routes.security_privacy import router as security_privacy_router
from app.api.routes.providers import router as providers_router
from app.api.routes.children import router as children_router
from app.api.routes.communications import router as communications_router
from app.api.routes.multimedia import router as multimedia_router
from app.api.routes.productivity import router as productivity_router
from app.api.routes.addons import router as addons_router
from app.api.routes.privacy import router as privacy_router
from app.api.security import AuditHeaderMiddleware, require_api_role
from maine_family_law_llm import __version__


class _InspectableFastAPI(FastAPI):
    """Expose deferred FastAPI routes to inventory and compliance tooling.

    FastAPI 0.139+ keeps included routers as lightweight route containers.
    Their effective contexts carry the final path and HTTP methods but are not
    returned by ``FastAPI.routes``.  Returning both views preserves normal
    ASGI/OpenAPI behavior while making the complete registered surface
    inspectable by framework-neutral auditors.
    """

    @property
    def routes(self):  # type: ignore[override]
        registered = list(self.router.routes)
        effective = []
        for route in registered:
            contexts = getattr(route, "effective_route_contexts", None)
            if callable(contexts):
                effective.extend(contexts())
        return [*registered, *effective]


app = _InspectableFastAPI(
    title="Maine Family Law LLM",
    version=__version__,
    description=(
        "Standalone Maine family-law legal AI API. All protected endpoints require role/tenant scope, "
        "emit audit headers, and return review-required outputs unless filing-ready gates pass."
    ),
    dependencies=[Depends(require_api_role)],
)
app.add_middleware(AuditHeaderMiddleware)

app.router.include_router(health_router)
app.router.include_router(models_router, prefix="/api")

from app.api.routes import authority, citations, draft, evidence, intake, matters, quotes, research, review, sources, version

app.router.include_router(authority.router, prefix="/api")
app.router.include_router(research.router, prefix="/api")
app.router.include_router(review.router, prefix="/api")
app.router.include_router(evidence.router, prefix="/api")
app.router.include_router(version.router, prefix="/api")
app.router.include_router(intake.router, prefix="/api")
app.router.include_router(draft.router, prefix="/api")
app.router.include_router(citations.router, prefix="/api")
app.router.include_router(quotes.router, prefix="/api")
app.router.include_router(sources.router, prefix="/api")
app.router.include_router(matters.router, prefix="/api")
app.router.include_router(evals_router, prefix="/api")
app.router.include_router(deliberation_router, prefix="/api")
app.router.include_router(release_control_router, prefix="/api")
app.router.include_router(release_maintenance_router, prefix="/api")
app.router.include_router(governance_router, prefix="/api")
app.router.include_router(security_privacy_router, prefix="/api")
app.router.include_router(providers_router, prefix="/api")
app.router.include_router(children_router, prefix="/api")
app.router.include_router(communications_router, prefix="/api")
app.router.include_router(multimedia_router, prefix="/api")
app.router.include_router(productivity_router, prefix="/api")
app.router.include_router(addons_router, prefix="/api")
app.router.include_router(privacy_router, prefix="/api")
