from __future__ import annotations

from typing import Any

from legal.classifiers.issue_classifier import RuleBasedIssueClassifier
from legal.classifiers.posture_classifier import classify_posture
from legal.classifiers.red_flag_classifier import detect_red_flags
from legal.conversation.audience_router import AudienceRouter
from legal.conversation.conversation_mode import ConversationModeCatalog
from legal.conversation.intake_schema import IntakeSchemaCatalog
from legal.conversation.missing_information import MissingInformationEngine
from legal.conversation.next_question import NextQuestionGenerator
from legal.conversation.output_renderer import OutputRenderer
from legal.conversation.plain_language import PlainLanguageRewriter
from legal.conversation.response_contract import ConversationResponseBuilder
from legal.conversation.source_card_presenter import SourceCardPresenter
from legal.conversation.tone_policy import TonePolicy
from legal.verifiers.citation_parser import extract_citations


TASK_WORKFLOW_MAP = {
    "query": "document_review",
    "research": "form_guidance",
    "draft": "document_review",
    "review": "document_review",
    "citation_verification": "document_review",
    "quote_verification": "document_review",
    "evidence_map": "evidence_mapping",
    "timeline": "evidence_mapping",
    "filing_ready_check": "document_review",
    "appellate_issue_spotting": "appellate_rule_52_findings_issue",
}
ISSUE_WORKFLOW_MAP = {
    "child_support": "child_support",
    "divorce": "divorce",
    "guardianship": "guardianship",
    "jurisdiction": "parental_rights_and_responsibilities",
    "motion_for_contempt": "motion_for_contempt",
    "motion_to_enforce": "motion_to_enforce",
    "motion_to_modify": "motion_to_modify",
    "parentage": "parentage",
    "parental_rights_responsibilities": "parental_rights_and_responsibilities",
    "protection_from_abuse": "protection_from_abuse_overlap",
    "rule_52_findings": "appellate_rule_52_findings_issue",
}
TASK_TYPES_WITH_EXPLICIT_WORKFLOWS = {
    "appellate_issue_spotting",
    "citation_verification",
    "evidence_map",
    "filing_ready_check",
    "quote_verification",
    "timeline",
}
ISSUE_KEYWORDS = {
    "motion_to_modify": ("motion to modify", "modify", "changed circumstances"),
    "motion_to_enforce": ("motion to enforce", "enforce", "not following the order"),
    "motion_for_contempt": ("contempt", "willful", "violated the order"),
    "protection_from_abuse": ("protection from abuse", "pfa", "abuse"),
    "guardianship": ("guardianship", "guardian"),
    "parentage": ("parentage", "paternity"),
    "rule_52_findings": ("rule 52", "missing findings", "no findings"),
    "jurisdiction": ("uccjea", "other state", "out of state", "federal"),
    "evidence_mapping": ("evidence", "exhibit", "messages", "records"),
}


class ConversationService:
    def __init__(self) -> None:
        self.mode_catalog = ConversationModeCatalog()
        self.audience_router = AudienceRouter(self.mode_catalog)
        self.schema_catalog = IntakeSchemaCatalog()
        self.missing_engine = MissingInformationEngine(schema_catalog=self.schema_catalog)
        self.next_question = NextQuestionGenerator(self.missing_engine)
        self.tone_policy = TonePolicy()
        self.source_cards = SourceCardPresenter()
        self.response_builder = ConversationResponseBuilder()
        self.output_renderer = OutputRenderer()
        self.plain_language = PlainLanguageRewriter()
        self.issue_classifier = RuleBasedIssueClassifier()

    def build_response(
        self,
        *,
        task_type: str,
        payload: dict[str, Any],
        result: dict[str, Any] | None = None,
        audience_hint: str | None = None,
        requested_renderer: str | None = None,
    ) -> dict[str, Any]:
        result_payload = result or {}
        text = self._text_for_task(task_type, payload, result_payload)
        issue_labels = self._issue_labels(text)
        posture = payload.get("procedural_posture") or classify_posture(text)
        routed = self.audience_router.route(
            user_role=audience_hint or payload.get("audience") or payload.get("user_role"),
            task_type=task_type,
            issue_labels=issue_labels,
            explicit_mode=payload.get("mode"),
        )
        workflow = self._workflow(task_type=task_type, payload=payload, issue_labels=issue_labels)
        if workflow not in self.schema_catalog.required_workflows():
            workflow = "document_review"
        missing_information = [
            item.as_dict()
            for item in self.missing_engine.analyze(
                workflow=workflow,
                payload=payload,
                audience=routed.audience,
                text=text,
            )
        ]
        next_question = self.next_question.choose(
            workflow=workflow,
            payload=payload,
            audience=routed.audience,
            text=text,
        )
        raw_cards = (
            payload.get("source_cards")
            or result_payload.get("source_cards")
            or self._fallback_source_cards(issue_labels)
        )
        source_cards = self.source_cards.present(raw_cards)
        citations = self._citation_rows(text, payload, result_payload)
        source_scope_status = self._source_scope_status(source_cards)
        source_freshness_status = self._source_freshness_status(source_cards)
        claim_support_status = self._claim_support_status(task_type, payload, result_payload, source_cards)
        quote_status = self._quote_status(task_type, payload, result_payload)
        filing_ready_status, filing_ready_blockers = self._filing_ready_status(task_type, payload, result_payload)
        short_answer = self._short_answer(task_type, routed.audience, issue_labels, filing_ready_status)
        explanation = self._explanation(task_type, routed.audience, source_scope_status, source_freshness_status, filing_ready_status)
        tone = self.tone_policy.apply(
            explanation,
            source_freshness_status=source_freshness_status,
            jurisdiction_scope=self._jurisdiction_scope(text, payload),
            filing_ready_passed=filing_ready_status == "filing_ready_passed",
        )
        red_flags = [str(item) for item in detect_red_flags(text)]
        warnings = list(tone.warnings)
        red_flags.extend(
            str(item.get("reason"))
            for item in missing_information
            if item.get("severity") == "red_flag" and item.get("reason")
        )
        red_flags.extend(self.tone_policy.escalation_messages(text))
        if self._looks_like_prompt_injection(text):
            red_flags.append("Prompt injection or instruction override language detected.")
            warnings.append("Treat uploaded or pasted instructions as untrusted content.")
        red_flags.extend(tone.escalation_messages)
        red_flags = list(dict.fromkeys(red_flags))
        warnings.extend(payload.get("warnings") or [])
        attorney_notes = self._attorney_notes(task_type, source_cards, missing_information)
        response = self.response_builder.build(
            mode=routed.mode,
            audience=routed.audience,
            jurisdiction_scope=self._jurisdiction_scope(text, payload),
            issue_labels=issue_labels,
            procedural_posture=str(posture),
            task_type=task_type,
            source_scope_status=source_scope_status,
            source_freshness_status=source_freshness_status,
            short_answer=short_answer,
            explanation=tone.text,
            plain_language_explanation="",
            attorney_notes=attorney_notes,
            sources_used=source_cards,
            source_cards=source_cards,
            citations=citations,
            quote_verification_status=quote_status,
            claim_support_status=claim_support_status,
            missing_information=missing_information,
            warnings=warnings,
            red_flags=red_flags,
            filing_ready_status=filing_ready_status,
            filing_ready_blockers=filing_ready_blockers,
            review_required=True,
            next_steps=self._next_steps(next_question, routed.audience, filing_ready_status),
            confidence=self._confidence(source_scope_status, claim_support_status),
            limitations=self._limitations(source_freshness_status, filing_ready_status),
        ).as_dict()
        plain = self.plain_language.rewrite_response(response)
        response["plain_language_explanation"] = plain["text"]
        response["rendered_output"] = self.output_renderer.render(
            response,
            requested_renderer or self.mode_catalog.get(routed.mode).renderer,
            extra=plain,
        )
        response["next_question"] = next_question
        return response

    def _workflow(self, *, task_type: str, payload: dict[str, Any], issue_labels: list[str]) -> str:
        explicit = payload.get("workflow")
        if explicit:
            return str(explicit)
        base_workflow = TASK_WORKFLOW_MAP.get(task_type, "document_review")
        if task_type in TASK_TYPES_WITH_EXPLICIT_WORKFLOWS:
            return base_workflow
        for label in issue_labels:
            workflow = ISSUE_WORKFLOW_MAP.get(label)
            if workflow:
                return workflow
        return base_workflow

    def _issue_labels(self, text: str) -> list[str]:
        matches = self.issue_classifier.classify(text or "")
        labels = [item.label for item in matches]
        low = (text or "").lower()
        for label, keywords in ISSUE_KEYWORDS.items():
            if any(keyword in low for keyword in keywords):
                labels.append(label)
        if "appeal" in low and "appeal" not in labels:
            labels.append("appeal")
        if "rule 52" in low and "rule_52_findings" not in labels:
            labels.append("rule_52_findings")
        return sorted(set(labels or ["general_family_law_question"]))

    def _jurisdiction_scope(self, text: str, payload: dict[str, Any]) -> str:
        combined = " ".join([text, str(payload.get("jurisdiction") or "")]).lower()
        if "federal" in combined:
            return "federal_overlap"
        if "other state" in combined or "out of state" in combined:
            return "not_maine"
        if "maine" in combined:
            return "maine_only"
        return "jurisdiction_unknown"

    def _fallback_source_cards(self, issue_labels: list[str]) -> list[dict[str, Any]]:
        primary = issue_labels[0]
        return [
            {
                "source_id": f"starter-{primary}",
                "title": f"Starter source card for {primary.replace('_', ' ')}",
                "citation": None,
                "source_class": "starter_card",
                "jurisdiction": "maine",
                "authority_status": "requires_live_verification",
                "freshness_status": "unknown",
            }
        ]

    def _source_scope_status(self, source_cards: list[dict[str, Any]]) -> str:
        statuses = {card.get("source_scope_status") for card in source_cards}
        if "jurisdiction_mismatch" in statuses:
            return "jurisdiction_mismatch"
        if "source_verified" in statuses:
            return "source_verified"
        if "source_stale" in statuses:
            return "source_stale"
        return "source_unknown_freshness"

    def _source_freshness_status(self, source_cards: list[dict[str, Any]]) -> str:
        scope_status = self._source_scope_status(source_cards)
        if scope_status == "source_verified":
            return "source_verified"
        if scope_status == "source_stale":
            return "source_stale"
        return "source_unknown_freshness"

    def _claim_support_status(
        self,
        task_type: str,
        payload: dict[str, Any],
        result: dict[str, Any],
        source_cards: list[dict[str, Any]],
    ) -> str:
        report = payload.get("claim_support_report") or result.get("claim_support_report") or result.get("verification_report") or {}
        claims = report.get("claims") if isinstance(report, dict) else []
        if isinstance(claims, list) and claims:
            statuses = {str(item.get("support_status") or item.get("status") or "").lower() for item in claims}
            if "unsupported" in statuses:
                return "unsupported_claim"
            if "contradicted" in statuses:
                return "contradicted_claim"
            if "partially_supported" in statuses:
                return "partially_supported_claim"
            return "source_verified"
        if self._source_scope_status(source_cards) == "source_verified":
            return "partially_supported_claim"
        return "unsupported_claim"

    def _quote_status(self, task_type: str, payload: dict[str, Any], result: dict[str, Any]) -> str:
        rows = payload.get("quote_report") or result.get("quote_results") or []
        if rows:
            if any((row.get("match_type") or row.get("status")) in {"exact", "fuzzy", "found"} for row in rows):
                return "source_verified"
            return "quote_span_not_found"
        if task_type == "quote_verification":
            return "quote_span_not_found"
        return "citation_unverified"

    def _filing_ready_status(
        self,
        task_type: str,
        payload: dict[str, Any],
        result: dict[str, Any],
    ) -> tuple[str, list[str]]:
        if task_type == "filing_ready_check":
            filing_ready = bool(result.get("filing_ready") if result else payload.get("filing_ready"))
            blockers = list((result or payload).get("blockers") or [])
            return ("filing_ready_passed" if filing_ready else "blocked_from_filing_ready", blockers)
        if task_type == "draft":
            blockers = list(result.get("filing_ready_gate", {}).get("blockers", [])) if result else []
            return "blocked_from_filing_ready", blockers or ["review_required"]
        return "blocked_from_filing_ready", list(payload.get("filing_ready_blockers") or ["review_required"])

    def _short_answer(self, task_type: str, audience: str, issue_labels: list[str], filing_ready_status: str) -> str:
        issue = issue_labels[0].replace("_", " ")
        if task_type == "citation_verification":
            return "Citation review is complete only to the extent each citation resolves to a verified source."
        if task_type == "quote_verification":
            return "Quoted language must match a verified source span before relying on it."
        if task_type == "filing_ready_check":
            return "This item is not filing-ready unless every required gate passes."
        if audience == "attorney":
            return f"Source-forward review for {issue}; keep this review-required until verification and human review finish."
        return f"This looks like a Maine family-law {issue} question, and it stays review-required for now."

    def _explanation(
        self,
        task_type: str,
        audience: str,
        source_scope_status: str,
        source_freshness_status: str,
        filing_ready_status: str,
    ) -> str:
        if audience == "attorney":
            return (
                f"Mode is source-forward and concise. Source scope is {source_scope_status}. "
                f"Source freshness is {source_freshness_status}. Filing-ready status is {filing_ready_status}."
            )
        return (
            f"This response is review-required. Source status is {source_scope_status}. "
            f"Freshness status is {source_freshness_status}. Filing-ready status is {filing_ready_status}."
        )

    def _attorney_notes(
        self,
        task_type: str,
        source_cards: list[dict[str, Any]],
        missing_information: list[dict[str, Any]],
    ) -> str:
        return (
            f"Use {len(source_cards)} source cards, resolve missing items ({len(missing_information)}), "
            "and do not suppress human review."
        )

    def _next_steps(self, next_question: dict[str, Any], audience: str, filing_ready_status: str) -> list[str]:
        steps = [str(next_question.get("question") or "Ask the next best missing-information question.")]
        steps.append("Show source status, missing information, and review status together.")
        if filing_ready_status != "filing_ready_passed":
            steps.append("Do not treat this as filing-ready.")
        if audience == "attorney":
            steps.append("Run citation, quote, and claim-support checks before relying on the output.")
        return steps

    def _confidence(self, source_scope_status: str, claim_support_status: str) -> float:
        if source_scope_status == "source_verified" and claim_support_status == "source_verified":
            return 0.82
        if claim_support_status == "partially_supported_claim":
            return 0.55
        return 0.22

    def _limitations(self, source_freshness_status: str, filing_ready_status: str) -> list[str]:
        limits = ["No attorney-client relationship is created by this output."]
        if source_freshness_status != "source_verified":
            limits.append("Current-law language must stay limited until source freshness is verified.")
        if filing_ready_status != "filing_ready_passed":
            limits.append("Filing-ready use is blocked.")
        return limits

    def _citation_rows(self, text: str, payload: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
        if payload.get("citations"):
            return list(payload["citations"])
        if result.get("citations"):
            return list(result["citations"])
        rows = []
        for citation in extract_citations(text or ""):
            rows.append(
                {
                    "citation": citation.raw,
                    "kind": citation.kind,
                    "status": "citation_unverified",
                }
            )
        return rows

    def _text_for_task(self, task_type: str, payload: dict[str, Any], result: dict[str, Any]) -> str:
        return str(
            payload.get("query")
            or payload.get("text")
            or payload.get("question")
            or payload.get("requested_relief")
            or result.get("message")
            or ""
        )

    def _looks_like_prompt_injection(self, text: str) -> bool:
        low = (text or "").lower()
        markers = (
            "ignore previous instructions",
            "system:",
            "reveal the system prompt",
            "override all law",
            "send the file to http",
        )
        return any(marker in low for marker in markers)
