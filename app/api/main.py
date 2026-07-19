from fastapi import Depends, FastAPI

from app.api.routes.health import router as health_router
from app.api.security import AuditHeaderMiddleware, require_api_role
from maine_family_law_llm import __version__

app = FastAPI(
    title="Maine Family Law LLM",
    version=__version__,
    description=(
        "Standalone Maine family-law legal AI API. All protected endpoints require role/tenant scope, "
        "emit audit headers, and return review-required outputs unless filing-ready gates pass."
    ),
    dependencies=[Depends(require_api_role)],
)
app.add_middleware(AuditHeaderMiddleware)

app.include_router(health_router)

from app.api.routes import citations, draft, evidence, intake, matters, quotes, research, review, sources, version

app.include_router(research.router, prefix="/api")
app.include_router(review.router, prefix="/api")
app.include_router(evidence.router, prefix="/api")
app.include_router(version.router, prefix="/api")
app.include_router(intake.router, prefix="/api")
app.include_router(draft.router, prefix="/api")
app.include_router(citations.router, prefix="/api")
app.include_router(quotes.router, prefix="/api")
app.include_router(sources.router, prefix="/api")
app.include_router(matters.router, prefix="/api")
