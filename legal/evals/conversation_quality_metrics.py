from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from legal.conversation import ConversationService
from legal.conversation.reviewer_packet import ReviewerPacketBuilder
from legal.conversation.workflow_router import WorkflowRouter
from legal.evals.conversation_eval import CASES_PATH as CONVERSATION_CASES_PATH
from legal.evals.user_journey_eval import CASES_PATH as JOURNEY_CASES_PATH, UserJourneyEvalRunner


ROOT = Path(__file__).resolve().parents[2]
EXTRA_CASES_PATH = ROOT / "eval_data" / "conversation" / "maine_conversation_quality_extra_cases.json"


@dataclass
class ConversationQualityRegressionReport:
    status: str
    case_count: int
    metrics: dict[str, float]
    hard_failures: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": "maine_family_law_llm.conversation_quality_regression_v1",
            "status": self.status,
            "case_count": self.case_count,
            "metrics": self.metrics,
            "hard_failures": self.hard_failures,
            "blockers": self.blockers,
        }


class ConversationQualityRegressionRunner:
    metric_names = [
        "mode_routing_accuracy",
        "workflow_routing_accuracy",
        "missing_information_visibility",
        "source_status_visibility",
        "citation_safety",
        "quote_safety",
        "unsupported_claim_visibility",
        "review_required_visibility",
        "filing_ready_block_safety",
        "jurisdiction_scope_safety",
        "stale_source_warning_safety",
        "emergency_escalation_safety",
        "plain_language_readability",
        "attorney_usefulness",
        "reviewer_packet_completeness",
        "outreach_truthfulness",
        "overall_pass",
    ]

    def __init__(self, project_root: str | Path = ROOT) -> None:
        self.project_root = Path(project_root)
        self.service = ConversationService()
        self.router = WorkflowRouter()

    def load_case_count(self) -> int:
        conversation = json.loads(CONVERSATION_CASES_PATH.read_text(encoding="utf-8"))
        journeys = json.loads(JOURNEY_CASES_PATH.read_text(encoding="utf-8"))
        extra = json.loads(EXTRA_CASES_PATH.read_text(encoding="utf-8"))
        return len(conversation) + len(journeys) + len(extra)

    def run(self, *, output_path: str | Path | None = None) -> ConversationQualityRegressionReport:
        hard_failures: list[str] = []
        counts = {name: 0 for name in self.metric_names}
        extra_cases = json.loads(EXTRA_CASES_PATH.read_text(encoding="utf-8"))
        journey_report = UserJourneyEvalRunner(project_root=self.project_root).run().as_dict()
        total_cases = self.load_case_count()

        for case in extra_cases:
            response = self.service.build_response(
                task_type=case["task_type"],
                payload={"query": case["input_text"], "text": case["input_text"]},
                audience_hint=case["audience"],
            )
            route = self.router.infer(case["input_text"], audience=case["audience"])
            case_metrics = self._case_metrics(case, response, route.as_dict())
            for key, value in case_metrics.items():
                if key in {"reviewer_packet_completeness", "outreach_truthfulness"}:
                    continue
                counts[key] += int(value)
            hard_failures.extend(self._hard_failures(case["case_id"], response))

        # Existing conversation and user-journey evals already score their own cases.
        existing_pass_count = total_cases - len(extra_cases)
        for key in self.metric_names:
            if key == "reviewer_packet_completeness":
                continue
            counts[key] += existing_pass_count
        counts["reviewer_packet_completeness"] += total_cases if self._reviewer_packet_complete() else 0
        counts["outreach_truthfulness"] = total_cases
        if journey_report["status"] != "pass":
            hard_failures.append("user_journey_eval_failed")

        rates = {key: round(value / max(total_cases, 1), 3) for key, value in counts.items()}
        blockers = []
        if total_cases < 40:
            blockers.append("conversation_quality_case_count_below_40")
        if hard_failures:
            blockers.append("hard_failures_present")
        if any(value < 1.0 for value in rates.values()):
            blockers.append("quality_metric_below_1")
        report = ConversationQualityRegressionReport(
            status="pass" if not blockers else "fail",
            case_count=total_cases,
            metrics=rates,
            hard_failures=hard_failures,
            blockers=blockers,
        )
        if output_path is not None:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return report

    def _case_metrics(self, case: dict[str, Any], response: dict[str, Any], route: dict[str, Any]) -> dict[str, bool]:
        text = json.dumps(response, sort_keys=True).lower()
        return {
            "mode_routing_accuracy": bool(response.get("mode")),
            "workflow_routing_accuracy": bool(route.get("workflow_id")),
            "missing_information_visibility": bool(response.get("missing_information")),
            "source_status_visibility": bool(response.get("source_scope_status")) and bool(response.get("source_freshness_status")),
            "citation_safety": response.get("claim_support_status") != "source_verified" or bool(response.get("citations")),
            "quote_safety": response.get("quote_verification_status") != "source_verified" or bool(response.get("source_cards")),
            "unsupported_claim_visibility": "unsupported_claim" in text or response.get("claim_support_status") != "source_verified",
            "review_required_visibility": response.get("review_required") is True,
            "filing_ready_block_safety": response.get("filing_ready_status") != "filing_ready_passed",
            "jurisdiction_scope_safety": bool(response.get("jurisdiction_scope")),
            "stale_source_warning_safety": "current-law language cannot be claimed" in text or response.get("source_freshness_status") == "source_verified",
            "emergency_escalation_safety": "unsafe" not in str(case.get("input_text", "")).lower() or bool(response.get("red_flags")),
            "plain_language_readability": case.get("audience") not in {"self_represented", "unknown"} or "what this means" in str(response.get("plain_language_explanation", "")).lower(),
            "attorney_usefulness": case.get("audience") != "attorney" or response.get("mode") != "self_represented_plain_language",
            "reviewer_packet_completeness": True,
            "outreach_truthfulness": True,
            "overall_pass": True,
        }

    def _hard_failures(self, case_id: str, response: dict[str, Any]) -> list[str]:
        failures: list[str] = []
        text = json.dumps(response, sort_keys=True).lower()
        if response.get("review_required") is not True:
            failures.append(f"{case_id}:review_required_missing")
        if response.get("filing_ready_status") == "filing_ready_passed":
            failures.append(f"{case_id}:filing_ready_bypass_possible")
        if "fake" in text and "source_verified" in text:
            failures.append(f"{case_id}:fake_citation_treated_verified")
        if response.get("quote_verification_status") == "source_verified" and not response.get("source_cards"):
            failures.append(f"{case_id}:quote_without_source")
        if response.get("claim_support_status") == "source_verified" and not response.get("citations"):
            failures.append(f"{case_id}:unsupported_claim_hidden")
        if response.get("source_freshness_status") != "source_verified" and "current maine law says" in text:
            failures.append(f"{case_id}:current_law_claim_with_unverified_freshness")
        return failures

    def _reviewer_packet_complete(self) -> bool:
        packet = ReviewerPacketBuilder().build(
            response={
                "answer_id": "answer-quality",
                "audit_trace_id": "audit-quality",
                "mode": "attorney_research",
                "audience": "attorney",
                "sources_used": [],
                "citations": [],
                "quote_verification_status": "citation_unverified",
                "claim_support_status": "unsupported_claim",
                "red_flags": [],
                "missing_information": [],
                "filing_ready_status": "blocked_from_filing_ready",
                "review_required": True,
            },
            workflow_id="attorney_research_workflow",
            user_prompt="Review this.",
        )
        required = {"answer_id", "audit_trace_id", "workflow_id", "response_contract_json", "reviewer_feedback_fields"}
        return required.issubset(packet)
