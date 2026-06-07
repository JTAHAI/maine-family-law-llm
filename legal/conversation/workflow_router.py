from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "maine_guided_workflows.json"


@dataclass(frozen=True)
class WorkflowDefinition:
    workflow_id: str
    intended_audience: tuple[str, ...]
    keywords: tuple[str, ...]
    required_inputs: tuple[str, ...]
    optional_inputs: tuple[str, ...]
    first_question: str
    next_questions: tuple[str, ...]
    source_requirements: tuple[str, ...]
    output_template: str
    hard_blockers: tuple[str, ...]
    red_flags: tuple[str, ...]
    review_required_default: bool
    filing_ready_policy: str
    handoff_to_human_review_policy: str

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "WorkflowDefinition":
        return cls(
            workflow_id=str(row["workflow_id"]),
            intended_audience=tuple(str(item) for item in row.get("intended_audience", [])),
            keywords=tuple(str(item) for item in row.get("keywords", [])),
            required_inputs=tuple(str(item) for item in row.get("required_inputs", [])),
            optional_inputs=tuple(str(item) for item in row.get("optional_inputs", [])),
            first_question=str(row.get("first_question") or ""),
            next_questions=tuple(str(item) for item in row.get("next_questions", [])),
            source_requirements=tuple(str(item) for item in row.get("source_requirements", [])),
            output_template=str(row.get("output_template") or "plain_language_answer"),
            hard_blockers=tuple(str(item) for item in row.get("hard_blockers", [])),
            red_flags=tuple(str(item) for item in row.get("red_flags", [])),
            review_required_default=bool(row.get("review_required_default", True)),
            filing_ready_policy=str(row.get("filing_ready_policy") or ""),
            handoff_to_human_review_policy=str(row.get("handoff_to_human_review_policy") or ""),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "intended_audience": list(self.intended_audience),
            "required_inputs": list(self.required_inputs),
            "optional_inputs": list(self.optional_inputs),
            "first_question": self.first_question,
            "next_questions": list(self.next_questions),
            "source_requirements": list(self.source_requirements),
            "output_template": self.output_template,
            "hard_blockers": list(self.hard_blockers),
            "red_flags": list(self.red_flags),
            "review_required_default": self.review_required_default,
            "filing_ready_policy": self.filing_ready_policy,
            "handoff_to_human_review_policy": self.handoff_to_human_review_policy,
        }


@dataclass(frozen=True)
class WorkflowRoute:
    workflow_id: str
    confidence: float
    ambiguous: bool
    first_question: str
    clarification_question: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "confidence": self.confidence,
            "ambiguous": self.ambiguous,
            "first_question": self.first_question,
            "clarification_question": self.clarification_question,
        }


class GuidedWorkflowCatalog:
    def __init__(self, config_path: str | Path = CONFIG_PATH) -> None:
        self.config_path = Path(config_path)
        payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.workflows = [WorkflowDefinition.from_dict(row) for row in payload.get("workflows", [])]
        self.by_id = {workflow.workflow_id: workflow for workflow in self.workflows}

    def get(self, workflow_id: str) -> WorkflowDefinition:
        return self.by_id[workflow_id]

    def for_audience(self, audience: str) -> list[WorkflowDefinition]:
        normalized = audience or "unknown"
        return [workflow for workflow in self.workflows if normalized in workflow.intended_audience or "unknown" in workflow.intended_audience]


class WorkflowRouter:
    def __init__(self, catalog: GuidedWorkflowCatalog | None = None) -> None:
        self.catalog = catalog or GuidedWorkflowCatalog()

    def infer(self, text: str, *, audience: str = "unknown") -> WorkflowRoute:
        low = (text or "").lower()
        if audience == "attorney" and any(
            phrase in low for phrase in ("research memo", "attorney memo", "legal research")
        ):
            workflow = self.catalog.get("attorney_research_workflow")
            return WorkflowRoute(
                workflow.workflow_id,
                0.95,
                False,
                workflow.first_question,
            )
        if any(phrase in low for phrase in ("filing ready", "file this", "ready to file")):
            workflow = self.catalog.get("check_filing_readiness")
            return WorkflowRoute(workflow.workflow_id, 0.95, False, workflow.first_question)
        if "draft" in low and any(
            phrase in low for phrase in ("motion", "affidavit", "proposed order", "findings")
        ):
            workflow = self.catalog.get("draft_or_review_a_motion")
            return WorkflowRoute(workflow.workflow_id, 0.95, False, workflow.first_question)
        candidates = self.catalog.for_audience(audience)
        scored: list[tuple[int, WorkflowDefinition]] = []
        for workflow in candidates:
            score = sum(1 for keyword in workflow.keywords if keyword.lower() in low)
            if score:
                scored.append((score, workflow))
        if not scored:
            workflow = self.catalog.get("self_represented_start_here" if audience in {"unknown", "self_represented"} else "ask_a_maine_family_law_question")
            return WorkflowRoute(workflow.workflow_id, 0.25, True, workflow.first_question, "Which workflow best fits what you want to do?")
        scored.sort(key=lambda item: (-item[0], item[1].workflow_id))
        top_score, top_workflow = scored[0]
        tied = [workflow for score, workflow in scored if score == top_score]
        ambiguous = len(tied) > 1 and top_score < 3
        return WorkflowRoute(
            workflow_id=top_workflow.workflow_id,
            confidence=round(min(0.95, 0.35 + (top_score * 0.2)), 2),
            ambiguous=ambiguous,
            first_question=top_workflow.first_question,
            clarification_question="I can help route this. Are you asking for drafting, review, sources, evidence, or plain-language explanation?" if ambiguous else None,
        )
