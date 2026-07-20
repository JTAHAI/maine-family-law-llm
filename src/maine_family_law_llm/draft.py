"""Review-required drafting helpers with source-scope and bypass diagnostics.

These helpers produce structured working outlines only. They do not invent facts,
certify current law, or mark any output filing-ready. Legal and private-record
sources remain separate, and unsafe instruction clauses cannot weaken the review
or citation gates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from legal.security.prompt_injection import PromptInjectionScanner

from .answer import DISCLAIMER
from .cite import render_citation_appendix
from .grounding_integrity import annotate_grounding_metadata, assess_grounding_integrity
from .retrieve import SearchResult


ALLOWED_DRAFT_MODES = {
    "checklist",
    "question_list",
    "court_form_prep_notes",
    "attorney_review_packet",
    "clerk_question_packet",
}

_MODE_SECTIONS: dict[str, tuple[str, ...]] = {
    "checklist": (
        "Confirm the requested outcome and procedural posture.",
        "List only user-provided facts and identify the record supporting each material fact.",
        "Verify the governing Maine statute, rule, form, and any controlling case law.",
        "Check service, deadlines, jurisdiction, current forms, and required findings.",
    ),
    "question_list": (
        "What order, filing, or court paper controls the immediate next step?",
        "Which facts are known, disputed, or missing?",
        "Which official Maine authorities and current forms must be checked?",
        "What deadline or safety issue requires human confirmation now?",
    ),
    "court_form_prep_notes": (
        "Identify the official form ID and confirm its live version on the Maine Judicial Branch site.",
        "Map each required field to a user-provided fact; leave unknown fields blank and flagged.",
        "Identify attachments, service steps, filing location, fee/waiver issues, and signatures requiring confirmation.",
        "Do not transfer allegations into findings or legal conclusions.",
    ),
    "attorney_review_packet": (
        "Issue and posture summary for attorney confirmation.",
        "Source matrix separating primary authority, official guidance/forms, and private records.",
        "Unsupported-claim, stale-source, jurisdiction, deadline, and missing-record review.",
        "Human decisions and approvals required before any export or filing use.",
    ),
    "clerk_question_packet": (
        "Questions limited to filing process, accepted forms, fees, scheduling, and public docket procedure.",
        "No request for legal advice or prediction of outcome.",
        "List the form/order identifiers the user should have available when contacting the clerk.",
        "Verify all dates and instructions against the current court notice or official page.",
    ),
}


@dataclass(frozen=True)
class DraftResult:
    text: str
    citations: tuple[SearchResult, ...]
    failure_class: str = "none"
    recovery_hint: str = ""
    review_report: dict[str, Any] = field(default_factory=dict)
    structured_sections: tuple[dict[str, Any], ...] = ()



def draft_from_sources(
    request: str,
    retrieval_results: list[SearchResult] | tuple[SearchResult, ...],
    *,
    mode: str = "checklist",
    retrieval_diagnostics: dict[str, Any] | None = None,
) -> DraftResult:
    if mode not in ALLOWED_DRAFT_MODES:
        raise ValueError(f"bad draft mode: {mode}")

    scanner = PromptInjectionScanner()
    findings = scanner.scan_user_prompt(str(request or ""))
    safe_request = scanner.sanitize_user_prompt_for_retrieval(str(request or "")) if findings else str(request or "").strip()
    if findings and len(safe_request.split()) < 3:
        report = _review_report(
            mode=mode,
            legal_cards=[],
            private_cards=[],
            retrieval_diagnostics=retrieval_diagnostics,
            prompt_findings=findings,
            blockers=[
                "substantive_draft_request_required_after_prompt_sanitization",
                "human_review_required",
                "filing_ready_gate_not_run",
            ],
        )
        return DraftResult(
            text=(
                "The instruction-override language was ignored, and no substantive drafting request remained. "
                "Describe the document type, procedural posture, requested outcome, and known facts without asking to bypass sources or review."
            ),
            citations=(),
            failure_class="substantive_draft_request_required_after_prompt_sanitization",
            recovery_hint="Restate the working-draft request without source, safety, citation, or human-review bypass language.",
            review_report=report,
        )

    results = tuple(retrieval_results)
    legal_results = tuple(
        result for result in results
        if str(result.metadata.get("source_lane") or "legal_authority") != "private_record"
    )
    private_results = tuple(
        result for result in results
        if str(result.metadata.get("source_lane") or "legal_authority") == "private_record"
    )
    if not legal_results:
        report = _review_report(
            mode=mode,
            legal_cards=[],
            private_cards=[result.to_dict() for result in private_results],
            retrieval_diagnostics=retrieval_diagnostics,
            prompt_findings=findings,
            blockers=[
                "verified_legal_sources_missing_for_draft",
                "human_review_required",
                "filing_ready_gate_not_run",
            ],
        )
        if private_results:
            text = "I cannot prepare a legal working outline from private records alone. Private records alone are not legal authority."
            failure_class = "legal_sources_missing_for_draft"
        else:
            text = "I cannot draft even an informational outline without retrieved Maine sources."
            failure_class = "sources_missing_for_draft"
        return DraftResult(
            text=text,
            citations=(),
            failure_class=failure_class,
            recovery_hint="Retrieve the applicable Maine statute, rule, official form/process page, or case before drafting.",
            review_report=report,
        )

    raw_cards = [result.to_dict() for result in legal_results]
    annotated_cards = annotate_grounding_metadata(raw_cards)
    grounding = assess_grounding_integrity(annotated_cards, search_mode="maine_law")
    blockers = ["human_review_required", "filing_ready_gate_not_run"]
    if findings:
        blockers.append("instruction_override_clause_ignored")
    if not grounding.get("current_law_verified"):
        blockers.append("current_law_not_verified_from_local_source_bundle")
    if private_results:
        blockers.append("private_records_excluded_from_legal_authority_scope")
    diagnostics = dict(retrieval_diagnostics or {})
    if diagnostics.get("confidence") == "low":
        blockers.append("low_confidence_retrieval_requires_query_refinement")
    if any(str((card.get("metadata") or {}).get("freshness_status")) == "stale_or_superseded" for card in annotated_cards):
        blockers.append("stale_or_superseded_source_present")

    source_rows = []
    for index, result in enumerate(legal_results, start=1):
        source_rows.append(
            {
                "source_number": index,
                "source_id": result.source_id,
                "title": result.title,
                "citation": result.citation,
                "snippet": result.snippet,
                "exact_reference_match": result.exact_reference_match,
                "lexical_coverage": result.lexical_coverage,
                "use_boundary": "Review the cited passage and live official source before converting this note into a legal proposition.",
            }
        )

    sections: tuple[dict[str, Any], ...] = (
        {
            "heading": "Draft status",
            "items": [
                "Working outline only; review required; not filing-ready.",
                "No fact, deadline, current-law status, or legal conclusion is certified by this draft.",
            ],
        },
        {
            "heading": "Requested drafting task",
            "items": [safe_request[:1200] or "No substantive request supplied."],
        },
        {
            "heading": "Proposed review structure",
            "items": list(_MODE_SECTIONS[mode]),
        },
        {
            "heading": "Source-backed review notes",
            "items": [
                f"Source {row['source_number']} — {row['title']} ({row['citation']}): {row['snippet']}"
                for row in source_rows
            ],
        },
        {
            "heading": "Mandatory review blockers",
            "items": list(dict.fromkeys(blockers)),
        },
    )

    lines = [
        f"Draft mode: {mode}",
        "Status: working outline only; review required; not filing-ready.",
        DISCLAIMER,
    ]
    if findings:
        lines.append("Security note: instruction-override language was ignored and did not alter source or review requirements.")
    for section in sections[1:]:
        lines.extend(["", f"{section['heading']}:"])
        lines.extend(f"- {item}" for item in section["items"])
    lines.extend(["", render_citation_appendix(legal_results)])

    report = _review_report(
        mode=mode,
        legal_cards=annotated_cards,
        private_cards=[result.to_dict() for result in private_results],
        retrieval_diagnostics=diagnostics,
        prompt_findings=findings,
        blockers=blockers,
    )
    return DraftResult(
        text="\n".join(lines),
        citations=legal_results,
        review_report=report,
        structured_sections=sections,
    )



def _review_report(
    *,
    mode: str,
    legal_cards: list[dict[str, Any]],
    private_cards: list[dict[str, Any]],
    retrieval_diagnostics: dict[str, Any] | None,
    prompt_findings: list[Any],
    blockers: list[str],
) -> dict[str, Any]:
    grounding = assess_grounding_integrity(legal_cards, search_mode="maine_law") if legal_cards else {
        "source_scope": "no_retrieved_legal_sources",
        "current_law_verified": False,
        "legal_source_count": 0,
        "official_primary_authority_count": 0,
        "stale_or_superseded_count": 0,
    }
    return {
        "schema_version": "draft_integrity_v3",
        "mode": mode,
        "status": "blocked_from_filing_ready",
        "review_required": True,
        "filing_ready": False,
        "legal_source_count": len(legal_cards),
        "private_record_source_count": len(private_cards),
        "source_scope": grounding.get("source_scope"),
        "official_primary_authority_count": grounding.get("official_primary_authority_count", 0),
        "current_law_verified": bool(grounding.get("current_law_verified")),
        "stale_or_superseded_count": grounding.get("stale_or_superseded_count", 0),
        "retrieval_diagnostics": dict(retrieval_diagnostics or {}),
        "prompt_injection_findings": [getattr(finding, "kind", str(finding)) for finding in prompt_findings],
        "blockers": list(dict.fromkeys(blockers)),
        "fact_policy": "Only user-provided or evidence-mapped facts may be inserted; unknown facts remain explicit blanks.",
        "authority_policy": "Every legal proposition requires verified Maine authority, proposition fit, freshness review, and negative-treatment review.",
        "export_policy": "No filing-ready representation is allowed until the separate filing gate and human review pass.",
    }
