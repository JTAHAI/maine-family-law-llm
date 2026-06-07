from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "maine_reviewer_feedback_schema.json"


class ReviewerFeedbackValidator:
    def __init__(self, config_path: str | Path = CONFIG_PATH) -> None:
        self.config = json.loads(Path(config_path).read_text(encoding="utf-8"))

    def validate(self, feedback: dict[str, Any]) -> dict[str, Any]:
        missing = [field for field in self.config.get("required_fields", []) if field not in feedback]
        blockers = [f"missing_field:{field}" for field in missing]
        for field in ("legal_accuracy_rating", "citation_accuracy_rating", "usability_rating", "safety_concern_rating"):
            value = feedback.get(field)
            if value is not None and not (self.config["rating_min"] <= int(value) <= self.config["rating_max"]):
                blockers.append(f"rating_out_of_range:{field}")
        may_count = bool(feedback.get("may_count_for_attorney_review"))
        if may_count:
            for field in self.config.get("may_count_for_attorney_review_requires", []):
                if not feedback.get(field):
                    blockers.append(f"attorney_review_evidence_missing:{field}")
            if not blockers:
                may_count = bool(feedback.get("attorney_licensed_in_maine"))
        return {
            "status": "pass" if not blockers else "blocked",
            "blockers": blockers,
            "may_count_for_attorney_review": may_count and not blockers,
            "does_not_mark_outreach_complete": True,
            "does_not_mark_ga_complete": True,
        }
