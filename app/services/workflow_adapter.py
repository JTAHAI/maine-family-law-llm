from __future__ import annotations

from typing import Any

from legal.conversation.start_here import StartHereBuilder
from legal.conversation.workflow_router import WorkflowRouter
from legal.conversation.workflow_steps import WorkflowStepPlanner


class WorkflowAdapter:
    def __init__(self) -> None:
        self.start_here = StartHereBuilder()
        self.router = WorkflowRouter()
        self.steps = WorkflowStepPlanner()

    def start(self, *, audience: str = "unknown") -> dict[str, Any]:
        return self.start_here.menu(audience=audience)

    def route(self, text: str, *, audience: str = "unknown") -> dict[str, Any]:
        route = self.router.infer(text, audience=audience).as_dict()
        route["first_step"] = self.steps.first_step(route["workflow_id"])
        return route

    def next_questions(self, workflow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "workflow_id": workflow_id,
            "questions": self.steps.next_questions(workflow_id, payload),
            "review_required": True,
        }
