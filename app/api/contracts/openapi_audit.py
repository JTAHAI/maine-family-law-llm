from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.api.contracts.endpoint_inventory import REQUIRED_API_ENDPOINTS, EndpointSpec


@dataclass
class OpenAPICompletionReport:
    status: str
    missing: list[dict[str, str]]
    undocumented: list[dict[str, str]]
    documented_count: int
    required_count: int
    public_paths: list[str]
    protected_paths: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "missing": self.missing,
            "undocumented": self.undocumented,
            "documented_count": self.documented_count,
            "required_count": self.required_count,
            "public_paths": self.public_paths,
            "protected_paths": self.protected_paths,
        }


class OpenAPICompletionAuditor:
    def __init__(self, endpoints: tuple[EndpointSpec, ...] = REQUIRED_API_ENDPOINTS) -> None:
        self.endpoints = endpoints

    def audit(self, openapi_schema: dict[str, Any]) -> OpenAPICompletionReport:
        paths = openapi_schema.get("paths", {})
        missing: list[dict[str, str]] = []
        undocumented: list[dict[str, str]] = []
        documented_count = 0
        for endpoint in self.endpoints:
            path_doc = paths.get(endpoint.path)
            if not path_doc:
                missing.append({"method": endpoint.method, "path": endpoint.path})
                continue
            method_doc = path_doc.get(endpoint.method.lower())
            if not method_doc:
                missing.append({"method": endpoint.method, "path": endpoint.path})
                continue
            documented_count += 1
            if not method_doc.get("operationId"):
                undocumented.append({"method": endpoint.method, "path": endpoint.path, "reason": "operationId_missing"})
            if not method_doc.get("responses"):
                undocumented.append({"method": endpoint.method, "path": endpoint.path, "reason": "responses_missing"})
        public_paths = [e.path for e in self.endpoints if not e.review_required]
        protected_paths = [e.path for e in self.endpoints if e.review_required]
        return OpenAPICompletionReport(
            status="pass" if not missing and not undocumented else "fail",
            missing=missing,
            undocumented=undocumented,
            documented_count=documented_count,
            required_count=len(self.endpoints),
            public_paths=public_paths,
            protected_paths=protected_paths,
        )
