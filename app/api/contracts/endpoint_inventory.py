from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EndpointSpec:
    method: str
    path: str
    purpose: str
    review_required: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "path": self.path,
            "purpose": self.purpose,
            "review_required": self.review_required,
        }


REQUIRED_API_ENDPOINTS: tuple[EndpointSpec, ...] = (
    EndpointSpec("POST", "/api/intake/matter", "register a confidential legal matter"),
    EndpointSpec("POST", "/api/intake/document", "ingest a matter document"),
    EndpointSpec("POST", "/api/query", "ask a source-grounded Maine family-law question"),
    EndpointSpec("POST", "/api/research", "retrieve relevant Maine authority"),
    EndpointSpec("POST", "/api/draft", "generate a review-required draft"),
    EndpointSpec("POST", "/api/review", "review a draft or uploaded text"),
    EndpointSpec("POST", "/api/citations/verify", "resolve and verify citations"),
    EndpointSpec("POST", "/api/quotes/verify", "verify quoted source spans"),
    EndpointSpec("POST", "/api/evidence/map", "map facts to evidence"),
    EndpointSpec("POST", "/api/timeline/build", "build a case timeline"),
    EndpointSpec("POST", "/api/filing-ready/check", "evaluate filing-readiness blockers"),
    EndpointSpec("GET", "/api/sources/{source_id}", "fetch an admitted source card or source text"),
    EndpointSpec("GET", "/api/matters/{matter_id}/evidence-packet", "fetch a review-required evidence packet"),
    EndpointSpec("GET", "/api/health", "service health", review_required=False),
    EndpointSpec("GET", "/api/version", "application version and readiness", review_required=False),
)


class EndpointInventory:
    def __init__(self, endpoints: tuple[EndpointSpec, ...] = REQUIRED_API_ENDPOINTS) -> None:
        self.endpoints = endpoints

    def required_paths(self) -> set[tuple[str, str]]:
        return {(endpoint.method, endpoint.path) for endpoint in self.endpoints}

    def as_dict(self) -> dict[str, Any]:
        return {
            "endpoint_count": len(self.endpoints),
            "endpoints": [endpoint.as_dict() for endpoint in self.endpoints],
        }

    def compare_to_registered(self, registered: set[tuple[str, str]]) -> dict[str, Any]:
        missing = sorted(self.required_paths() - registered)
        extra = sorted(registered - self.required_paths())
        return {
            "status": "pass" if not missing else "fail",
            "missing": [{"method": method, "path": path} for method, path in missing],
            "extra": [{"method": method, "path": path} for method, path in extra],
            "required_count": len(self.endpoints),
            "registered_count": len(registered),
        }
