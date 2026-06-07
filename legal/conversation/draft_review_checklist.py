from __future__ import annotations


class DraftReviewChecklistBuilder:
    def build(self, *, draft_type: str, blockers: list[str]) -> list[dict[str, str]]:
        checks = [
            ("facts", "Confirm all material facts are user-provided or evidence-supported."),
            ("authority", "Confirm every legal proposition has verified Maine authority or is marked unsupported."),
            ("citations", "Confirm citation placeholders are not presented as real citations."),
            ("quotes", "Confirm quoted text matches a source span."),
            ("filing_ready", "Confirm filing-ready gate and human review before export."),
        ]
        return [
            {
                "check": key,
                "status": "blocked" if blockers else "review_required",
                "instruction": instruction,
                "draft_type": draft_type,
            }
            for key, instruction in checks
        ]
