from __future__ import annotations

from typing import Any

from legal.evals.user_journey_eval import UserJourneyEvalRunner


class UserJourneyAdapter:
    def summary(self) -> dict[str, Any]:
        report = UserJourneyEvalRunner().run().as_dict()
        return {
            "status": report["status"],
            "case_count": report["case_count"],
            "metrics": report["metrics"],
            "ready_for_reviewer_demo": report["status"] == "pass",
            "does_not_count_for_ga": True,
        }
