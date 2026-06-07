from __future__ import annotations

from dataclasses import dataclass

from legal.conversation.conversation_mode import ConversationModeCatalog


AUDIENCE_ALIASES = {
    "lawyer": "attorney",
    "counsel": "attorney",
    "legal_staff": "paralegal",
    "staff": "paralegal",
    "pro_se": "self_represented",
    "pro-se": "self_represented",
    "srl": "self_represented",
    "parent": "self_represented",
    "client": "self_represented",
    "reviewer": "admin",
}
KNOWN_AUDIENCES = {"attorney", "paralegal", "advocate", "self_represented", "admin", "unknown"}


@dataclass(frozen=True)
class RoutedAudience:
    audience: str
    task_type: str
    mode: str


class AudienceRouter:
    def __init__(self, catalog: ConversationModeCatalog | None = None) -> None:
        self.catalog = catalog or ConversationModeCatalog()

    def normalize_audience(self, value: str | None) -> str:
        normalized = (value or "unknown").strip().lower().replace(" ", "_")
        normalized = AUDIENCE_ALIASES.get(normalized, normalized)
        return normalized if normalized in KNOWN_AUDIENCES else "unknown"

    def route(
        self,
        *,
        user_role: str | None,
        task_type: str,
        issue_labels: list[str] | None = None,
        explicit_mode: str | None = None,
    ) -> RoutedAudience:
        audience = self.normalize_audience(user_role)
        mode = self.catalog.route(
            audience=audience,
            task_type=task_type,
            issue_labels=issue_labels,
            explicit_mode=explicit_mode,
        )
        return RoutedAudience(audience=audience, task_type=task_type, mode=mode.mode)
