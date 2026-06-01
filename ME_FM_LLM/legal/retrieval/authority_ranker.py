from __future__ import annotations

DEFAULT_AUTHORITY_PRIORITY = [
    "verified_official_maine",
    "verified_maine_law_court",
    "verified_federal",
    "verified_public_api",
    "user_provided_only",
    "stale_unknown",
    "not_found",
]


class AuthorityRanker:
    def __init__(self, priority_order: list[str] | None = None) -> None:
        self.priority_order = priority_order or DEFAULT_AUTHORITY_PRIORITY
        self._rank = {status: index for index, status in enumerate(self.priority_order)}

    def score(self, authority_status: str) -> int:
        return self._rank.get(authority_status, len(self.priority_order) + 1)

    def rank(self, sources: list[dict]) -> list[dict]:
        return sorted(
            sources,
            key=lambda source: (
                self.score(source.get("authority_status", "not_found")),
                source.get("freshness_status", ""),
                source.get("source_id", ""),
            ),
        )
