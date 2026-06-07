from __future__ import annotations

from typing import Any

from legal.conversation.workflow_router import GuidedWorkflowCatalog


class WorkflowStepPlanner:
    def __init__(self, catalog: GuidedWorkflowCatalog | None = None) -> None:
        self.catalog = catalog or GuidedWorkflowCatalog()

    def first_step(self, workflow_id: str) -> dict[str, Any]:
        workflow = self.catalog.get(workflow_id)
        return {
            "workflow_id": workflow.workflow_id,
            "question": workflow.first_question,
            "required_inputs": list(workflow.required_inputs),
            "review_required": workflow.review_required_default,
            "filing_ready_policy": workflow.filing_ready_policy,
        }

    def next_questions(self, workflow_id: str, payload: dict[str, Any]) -> list[str]:
        workflow = self.catalog.get(workflow_id)
        provided = {key for key, value in payload.items() if value not in (None, "", [], {}, ())}
        missing = [field for field in workflow.required_inputs if field not in provided]
        questions = [f"Please provide {field.replace('_', ' ')}." for field in missing]
        return questions or list(workflow.next_questions[:2])
