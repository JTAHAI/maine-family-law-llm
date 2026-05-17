from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health", summary="Service health")
def health_check():
    return {
        "status": "ok",
        "service": "maine-family-law-llm",
        "version": "1.14.0-pass39-pass40-api-ui-completion",
        "legal_readiness": "production_api_ui_completion_foundation_installed_review_required",
        "rbac": {"enforced_for_protected_routes": True, "public_endpoint": True},
        "audit_events": "headers_emitted_for_all_api_routes",
    }
