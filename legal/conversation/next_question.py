from __future__ import annotations

from typing import Any

from legal.conversation.missing_information import MissingInformationEngine, MissingInformationItem


SEVERITY_ORDER = {"red_flag": 0, "required": 1, "warning": 2, "recommended": 3}


class NextQuestionGenerator:
    def __init__(self, engine: MissingInformationEngine | None = None) -> None:
        self.engine = engine or MissingInformationEngine()

    def choose(
        self,
        *,
        workflow: str,
        payload: dict[str, Any],
        audience: str,
        text: str = "",
        missing_information: list[MissingInformationItem] | None = None,
    ) -> dict[str, Any]:
        items = missing_information or self.engine.analyze(
            workflow=workflow,
            payload=payload,
            audience=audience,
            text=text,
        )
        if not items:
            return {
                "field": None,
                "question": "No follow-up question is needed yet.",
                "severity": "none",
                "reason": "No missing information was detected.",
            }
        ordered = sorted(items, key=lambda item: (SEVERITY_ORDER.get(item.severity, 99), item.field))
        first = ordered[0]
        question = first.audience_prompt
        if audience == "attorney":
            question = question.rstrip(".") + " Please answer with only the missing point."
        elif audience == "self_represented":
            question = question.rstrip(".") + " We can take this one step at a time."
        return {
            "field": first.field,
            "question": question,
            "severity": first.severity,
            "reason": first.reason,
        }
