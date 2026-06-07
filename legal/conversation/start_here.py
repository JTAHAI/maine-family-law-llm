from __future__ import annotations

from typing import Any

from legal.conversation.workflow_router import GuidedWorkflowCatalog


class StartHereBuilder:
    def __init__(self, catalog: GuidedWorkflowCatalog | None = None) -> None:
        self.catalog = catalog or GuidedWorkflowCatalog()

    def menu(self, *, audience: str = "unknown") -> dict[str, Any]:
        workflows = self.catalog.for_audience(audience)
        return {
            "audience": audience,
            "review_required": True,
            "filing_ready_status": "blocked_from_filing_ready",
            "prompt": "Choose the workflow that best matches what you want to do.",
            "workflows": [
                {
                    "workflow_id": workflow.workflow_id,
                    "first_question": workflow.first_question,
                    "output_template": workflow.output_template,
                }
                for workflow in workflows
            ],
        }
