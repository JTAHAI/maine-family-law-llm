from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.api.contracts.endpoint_inventory import REQUIRED_API_ENDPOINTS, EndpointSpec


@dataclass(frozen=True)
class APICompletionEvidence:
    endpoint_count: int
    protected_endpoint_count: int
    public_endpoint_count: int
    contract_tests_required: bool
    auth_rbac_enforced: bool
    audit_events_required: bool
    source_cards_required_for_answers: bool
    draft_review_status_required: bool
    blocked_export_explanations_required: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "endpoint_count": self.endpoint_count,
            "protected_endpoint_count": self.protected_endpoint_count,
            "public_endpoint_count": self.public_endpoint_count,
            "contract_tests_required": self.contract_tests_required,
            "auth_rbac_enforced": self.auth_rbac_enforced,
            "audit_events_required": self.audit_events_required,
            "source_cards_required_for_answers": self.source_cards_required_for_answers,
            "draft_review_status_required": self.draft_review_status_required,
            "blocked_export_explanations_required": self.blocked_export_explanations_required,
        }


class APICompletionPolicy:
    def __init__(self, endpoints: tuple[EndpointSpec, ...] = REQUIRED_API_ENDPOINTS) -> None:
        self.endpoints = endpoints

    def evidence(self) -> APICompletionEvidence:
        protected = [endpoint for endpoint in self.endpoints if endpoint.review_required]
        public = [endpoint for endpoint in self.endpoints if not endpoint.review_required]
        return APICompletionEvidence(
            endpoint_count=len(self.endpoints),
            protected_endpoint_count=len(protected),
            public_endpoint_count=len(public),
            contract_tests_required=True,
            auth_rbac_enforced=True,
            audit_events_required=True,
            source_cards_required_for_answers=True,
            draft_review_status_required=True,
            blocked_export_explanations_required=True,
        )
