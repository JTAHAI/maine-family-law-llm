from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/version", summary="Application version and readiness")
def version():
    return {
        "application": "maine-family-law-llm",
        "version": "1.14.0-pass39-pass40-api-ui-completion",
        "build_stage": "enterprise_pass_39_40_production_api_and_web_ui_completion",
        "completed_passes": [39, 40],
        "legal_readiness": "not_release_ready_until_external_authority_build_attorney_gold_metrics_security_audit_and_pilot_are_complete",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
