"""Structured, local-only family-justice answer contract.

The contract keeps answers useful and conversational while preventing repeated
boilerplate, nested citation appendices, and generic next steps that ignore the
user's actual request.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from .intake_understanding import IntakeSummary, concise_intake_label, parse_intake


CHILD_TERMS = {
    "child", "children", "parenting", "school", "therapy", "exchange",
    "transportation", "sibling", "routine", "caregiver", "contact",
}


def _clean_lines(values: Iterable[object]) -> list[str]:
    return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def _source_summary(item: dict[str, Any], lane: str) -> dict[str, Any]:
    metadata = dict(item.get("metadata") or {})
    metadata["source_lane"] = lane
    return {
        "source_id": str(item.get("source_id") or metadata.get("id") or "source"),
        "title": str(item.get("title") or metadata.get("title") or "Source"),
        "citation": str(item.get("citation") or metadata.get("citation_hint") or ""),
        "lane": lane,
        "authority_status": "private" if lane == "private_record" else (
            "official" if metadata.get("official", True) else "unofficial"
        ),
        "jurisdiction": str(metadata.get("jurisdiction") or ("Maine" if lane == "legal_authority" else "")),
        "effective_or_retrieved": str(
            metadata.get("effective_date")
            or metadata.get("retrieved_at")
            or metadata.get("version_label")
            or "verify"
        ),
        "freshness": str(metadata.get("freshness") or metadata.get("freshness_status") or "verify"),
        "matched_passage": str(item.get("snippet") or metadata.get("text_excerpt") or ""),
        "proposition": str(
            metadata.get("proposition")
            or (
                "Supports a statement of law."
                if lane == "legal_authority"
                else "Shows text from a selected private record; it does not establish a disputed fact."
            )
        ),
        "page_number": int(metadata.get("page_number") or 0),
        "source_locator": str(metadata.get("source_locator") or ""),
        "match_type": str(metadata.get("match_type") or ""),
        "ocr_derived": bool(metadata.get("ocr_derived")),
        "trust_boundary": str(metadata.get("trust_boundary") or ""),
        "instruction_like_text_detected": bool(
            metadata.get("instruction_like_text_detected")
        ),
        "instruction_like_findings": list(
            metadata.get("instruction_like_findings") or []
        ),
    }


def _strip_legacy_noise(value: str) -> str:
    """Remove answer wrappers that are rendered elsewhere in the v3 UI."""

    text = str(value or "").strip()
    # Source cards already render citations.  Raw appendices are noisy and were
    # causing repeated source metadata in ordinary chat.
    text = re.split(r"\n\s*Citation appendix:\s*", text, maxsplit=1, flags=re.IGNORECASE)[0]
    text = re.sub(
        r"\n{2,}This is legal information(?:.|\n)*?(?=\n{2,}|\Z)",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    # Avoid a nested heading when the contract itself supplies the heading.
    text = re.sub(r"^What this means:\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


def _task_plan(intake: IntakeSummary) -> tuple[list[str], list[str], list[str], list[str]]:
    """Return now, next, gather, human-help sections tailored to the intake."""

    task = intake.task
    now: list[str] = []
    next_steps: list[str] = []
    gather: list[str] = []
    human_help: list[str] = []

    if "immediate_safety" in intake.urgency_flags:
        now.append("If anyone is in immediate danger, call 911 or seek qualified local emergency help now.")
        next_steps.extend(
            [
                "Move to a safer place when you can do so safely.",
                "Use official protection-from-abuse or crisis resources rather than relying on chat alone.",
                "Preserve messages, orders, and incident details without confronting anyone to collect evidence.",
            ]
        )
        gather.extend(["Any current protection order or safety plan.", "Dates, messages, and records already available without increasing risk."])
        human_help.append("Contact emergency services, a qualified advocate, lawyer, or other appropriate local professional promptly.")
        return now, next_steps[:3], gather, human_help

    if task == "served_papers":
        now.extend(
            [
                "Read every page and mark the court, docket number, hearing date, response date, and what the other party is asking for.",
                "Keep the envelope, service paperwork, and complete set together; do not write on the originals.",
            ]
        )
        next_steps.extend(
            [
                "Create a one-page deadline list from the papers and verify each date with the court notice or official docket.",
                "Identify the case type and whether any temporary order is already in effect.",
                "Use current Maine Judicial Branch instructions and get qualified review before filing or missing a hearing.",
            ]
        )
        gather.extend(["The complete served packet and proof or date of service.", "Existing family orders, related case numbers, and upcoming notices.", "A short timeline of the facts relevant to what the papers request."])
        human_help.append("Get qualified local help promptly because service, hearings, and response dates can be time-sensitive.")
    elif task == "hearing_preparation":
        now.append("Confirm the hearing date, time, location or video instructions, and the exact issue listed on the notice.")
        next_steps.extend(
            [
                "Read the current order and the motion or filing the hearing concerns.",
                "Make a short timeline and identify the few records that support each important point.",
                "Prepare questions for a lawyer, advocate, clerk, or navigator; ask the clerk only about logistics.",
            ]
        )
        gather.extend(["Hearing notice, current orders, pending motions, and proof of service.", "A focused exhibit list with dates and source locations.", "Transportation, childcare, accessibility, interpreter, or remote-hearing needs."])
        human_help.append("Seek qualified review when testimony, evidence, safety, or a requested order is involved.")
    elif task == "understand_order":
        now.append("Work from the signed order itself and identify the exact paragraph you are trying to understand.")
        next_steps.extend(
            [
                "Separate what the order says from what someone told you it means.",
                "List the practical question: who must do what, by when, and under what condition.",
                "Get legal review before acting on ambiguous language or treating silence as permission.",
            ]
        )
        gather.extend(["The complete signed order, including attachments and incorporated agreements.", "Any later order that may have changed the same provision."])
        human_help.append("Use a lawyer or qualified navigator when the language is disputed or affects contact, safety, support, or a deadline.")
    elif task in {"enforce_order", "modify_order"}:
        now.append("Start with the exact current order language and a dated description of what has changed or what was not followed.")
        next_steps.extend(
            [
                "Separate each alleged event from conclusions such as contempt, obstruction, or interference.",
                "Link each event to a message, exchange record, school record, payment record, witness, or other source.",
                "Ask a qualified reviewer whether the requested relief fits enforcement, contempt, modification, safety relief, or another procedure.",
            ]
        )
        gather.extend(["Current and later orders affecting the same issue.", "A date-ordered event log with neutral descriptions and source references.", "Records showing impact on the child, schedule, support, or compliance where relevant."])
        human_help.append("Get legal review before choosing a motion or alleging contempt; the legal standard and procedure matter.")
    elif task == "child_support":
        now.append("Identify whether the question is initial support, modification, enforcement, arrears, or understanding an existing order.")
        next_steps.extend(
            [
                "Use current official Maine forms and instructions rather than a chat estimate.",
                "Organize income, benefits, childcare, health-insurance, and payment-history records.",
                "Verify any calculation or requested change with a qualified reviewer before relying on it.",
            ]
        )
        gather.extend(["Current support order and payment history.", "Recent income records and relevant child-related costs."])
        human_help.append("Seek qualified help for deviations, arrears, enforcement, self-employment income, or disputed financial information.")
    elif task == "organize_records":
        now.append("Keep the originals unchanged and build a local searchable inventory from the files you intentionally selected.")
        next_steps.extend(
            [
                "Review unreadable, unsupported, encrypted, and scanned-page counts.",
                "Choose local OCR only for pages that need it and review low-confidence OCR text.",
                "Use the resulting timeline, source cards, and evidence map to prepare focused questions—not conclusions.",
            ]
        )
        gather.extend(["Court papers and signed orders.", "Messages, email exports, attachments, school/provider records, and financial records relevant to the issue.", "A note identifying missing devices, accounts, folders, or paper records."])
        human_help.append("Use a lawyer or qualified reviewer before deciding what should be filed, disclosed, subpoenaed, or withheld.")
    elif task == "find_printable":
        now.append("Use the printable as an organizing aid, not as a court form or statement of law.")
        next_steps.extend(["Open the suggested printable locally.", "Print only the pages useful for the current task.", "Verify any legal or filing step against current official Maine sources."])
        gather.append("The court papers, order, dates, or records the worksheet is meant to help organize.")
        human_help.append("Get qualified help when the worksheet raises a deadline, safety issue, or filing decision.")
    else:
        now.append("Focus on the exact question and review the source card that supports the main point.")
        next_steps.extend(
            [
                "Compare the answer with the cited source text and date or version information.",
                "Write down the fact or document that would change the answer.",
                "Use qualified local help for strategy, disputed facts, filings, deadlines, or safety decisions.",
            ]
        )
        gather.extend(["The original order, notice, filing, or record that prompted the question.", "A short date-ordered timeline of the relevant events."])
        human_help.append("Get qualified local help when the source is unclear, facts are disputed, or a filing or safety decision is involved.")

    return _clean_lines(now), _clean_lines(next_steps)[:3], _clean_lines(gather), _clean_lines(human_help)



def _task_missing_information(intake: IntakeSummary) -> list[str]:
    """Return only the gaps that can materially change this answer.

    The earlier chat contract repeated a six-item generic checklist after nearly
    every response.  These prompts are intentionally task-specific so the user
    sees the next useful unknown rather than boilerplate.
    """

    task = intake.task
    gaps: list[str] = []
    if task == "served_papers":
        if not intake.dates_mentioned:
            gaps.append("The service date and every hearing, response, or filing date printed on the papers.")
        if not intake.docket_number or not intake.court:
            gaps.append("The court and docket number shown on the first page.")
        gaps.append("The case type and the exact relief the other party is requesting.")
    elif task == "hearing_preparation":
        if not intake.dates_mentioned:
            gaps.append("The hearing date, time, location or video instructions, and hearing type.")
        gaps.extend([
            "The motion, notice, or issue the hearing will address.",
            "The current signed order and the few records or witnesses tied to that issue.",
        ])
    elif task == "understand_order":
        gaps.extend([
            "The exact signed-order paragraph, page, and any defined terms it uses.",
            "Any later order or incorporated agreement that may change the same provision.",
            "The practical event that makes the wording unclear right now.",
        ])
    elif task == "enforce_order":
        gaps.extend([
            "The exact order language that may not have been followed.",
            "Dates and neutral descriptions of each event, linked to the record that supports it.",
            "The result you are seeking, without assuming the proper motion or legal label.",
        ])
    elif task == "modify_order":
        gaps.extend([
            "The current order provision you want changed.",
            "What has changed since that order and when the change began.",
            "The requested future arrangement and records supporting the change.",
        ])
    elif task == "child_support":
        gaps.extend([
            "Whether this is initial support, modification, enforcement, or arrears.",
            "The current support order and payment history.",
            "Current income, benefits, childcare, and health-insurance information.",
        ])
    elif task == "organize_records":
        gaps.extend([
            "Which folders, devices, email exports, archives, and paper scans are still missing.",
            "Which pages remain unreadable or unsearchable until the user chooses local OCR.",
        ])
    elif task == "record_search":
        if not intake.search_target:
            gaps.append("The exact word or phrase to search in the selected matter.")
    elif task in {"general_question", "describe_situation", "plain_language_explanation"}:
        gaps.extend([
            "The case stage and any current order or official paper controlling the issue.",
            "The exact question or outcome you are trying to understand.",
        ])
    return _clean_lines(gaps)


def _research_brief(
    *,
    question: str,
    search_mode: str,
    law_sources: list[dict[str, Any]],
    record_sources: list[dict[str, Any]],
    missing: list[str],
    grounding: dict[str, bool],
) -> dict[str, Any]:
    """Build a reviewable research map without turning retrieval into a conclusion.

    The source cards remain the authoritative review surface.  This compact map
    tells a researcher which lane was searched, what is actually available to
    inspect, and which factual or procedural unknowns still matter.
    """

    mode = str(search_mode or "maine_law")
    scope = {
        "maine_law": "Maine-law authorities retrieved from this local source bundle.",
        "my_records": "The selected private matter records only; no Maine-law authority was searched.",
        "both": "Separate Maine-law and selected-private-record lanes; neither lane proves the other.",
    }.get(mode, "The selected local research lane.")
    source_review_order: list[dict[str, str]] = []
    for source in law_sources:
        source_review_order.append(
            {
                "lane": "Maine law",
                "title": str(source.get("title") or "Legal source"),
                "citation": str(source.get("citation") or "Open the source card"),
                "review_focus": str(source.get("proposition") or "Confirm the precise legal proposition and currentness."),
            }
        )
    for source in record_sources:
        source_review_order.append(
            {
                "lane": "Matter record",
                "title": str(source.get("title") or "Private record"),
                "citation": str(source.get("source_locator") or source.get("citation") or "Open the record card"),
                "review_focus": str(source.get("proposition") or "Confirm the original record, date, and context."),
            }
        )

    open_issues = list(missing)
    if not grounding.get("legal_authority") and mode in {"maine_law", "both"}:
        open_issues.append("No retrieved Maine-law authority established the legal proposition; broaden or update the authority research before relying on it.")
    if not grounding.get("private_record") and mode in {"my_records", "both"}:
        open_issues.append("No selected private record established the factual portion of the question.")

    return {
        "schema_version": "research_brief_v1",
        "research_question": str(question or "").strip(),
        "scope": scope,
        "source_review_order": source_review_order,
        "open_issues": _clean_lines(open_issues)[:6],
        "review_standard": "Inspect the original source cards, confirm currentness and context, and do not treat retrieval rank or a source card as filing readiness.",
    }

def render_legacy_answer(contract: dict[str, Any]) -> str:
    """Render the compatibility answer from the structured contract.

    The browser renders the typed fields directly.  This text remains useful to
    API clients, exports, and older tests without reintroducing raw citation
    appendices or duplicate generic sections in the chat UI.
    """

    if contract.get("response_kind") in {"local_search_results", "source_card_followup", "ui_command"}:
        return str(contract.get("what_this_means") or "").strip() or "No result was returned."

    style = str(contract.get("answer_style") or "plain_language")
    sections: list[tuple[str, list[str]]] = []
    meaning = str(contract.get("what_this_means") or "").strip()

    style_title = {
        "intake": "Intake triage",
        "professional_boundary": "Professional-boundary note",
        "research_brief": "Research brief",
        "source_card_table": "Source-card audit table",
        "missing_information": "Missing-information checklist",
        "questions_to_ask": "Questions to ask next",
    }.get(style, "What this means")
    if meaning:
        sections.append((style_title, [meaning]))

    critical_dates = []
    date_labels = {
        "service_date": "Service date",
        "hearing_date": "Hearing or court date",
        "response_or_filing_deadline": "Possible response or filing deadline",
        "mentioned_date": "Date mentioned",
    }
    for item in contract.get("critical_dates") or []:
        if not isinstance(item, dict) or not item.get("raw"):
            continue
        label = date_labels.get(str(item.get("kind") or ""), "Date mentioned")
        normalized = str(item.get("normalized_date") or "")
        suffix = f" (normalized locally as {normalized})" if normalized else ""
        basis = str(item.get("normalization_basis") or "")
        if basis == "year_inferred_from_reference_date":
            suffix += " (year inferred from the local reference date)"
        elif basis == "relative_to_local_reference_date":
            suffix += " (calculated from the local reference date)"
        critical_dates.append(f"{label}: {item['raw']}{suffix}")
    if critical_dates:
        critical_dates.append(
            "Confirm every date against the complete official paper or docket; this extraction is not a deadline calculation."
        )
        sections.append(("Dates and deadlines I heard", critical_dates))

    grounding = dict(contract.get("grounding_integrity") or {})
    grounding_lines: list[str] = []
    if grounding:
        status = str(grounding.get("current_law_status") or "not assessed").replace("_", " ")
        grounding_lines.append(f"Current-law status: {status}.")
        grounding_lines.append(
            "Source cards: "
            f"{int(grounding.get('legal_source_count') or 0)} legal; "
            f"{int(grounding.get('private_record_count') or 0)} private record."
        )
        grounding_lines.extend(_clean_lines(grounding.get("warnings") or []))
    if grounding_lines:
        sections.append(("Grounding and freshness", grounding_lines))

    support = dict(contract.get("answer_support_integrity") or {})
    support_lines: list[str] = []
    if support and int(support.get("candidate_legal_claim_count") or 0):
        support_lines.append(
            f"Candidate legal claims checked: {int(support.get('candidate_legal_claim_count') or 0)}; status: {str(support.get('status') or 'review required').replace('_', ' ')}."
        )
        support_lines.extend(_clean_lines(support.get("blockers") or []))
        support_lines.extend(_clean_lines(support.get("warnings") or []))
    if support_lines:
        sections.append(("Claim-to-source review", support_lines))

    research_brief = dict(contract.get("research_brief") or {})
    if style == "research_brief" and research_brief:
        sections.append(("Research scope", [str(research_brief.get("scope") or "Review the selected local research lane.")]))
        source_review = [
            f"{item.get('lane', 'Source')}: {item.get('title', 'Source')} — {item.get('review_focus', 'Open and inspect the source card.')}"
            for item in research_brief.get("source_review_order") or []
            if isinstance(item, dict)
        ]
        if source_review:
            sections.append(("Source review order", source_review))
        open_issues = _clean_lines(research_brief.get("open_issues") or [])
        if open_issues:
            sections.append(("Open research issues", open_issues))

    for key, title in (
        ("what_to_do_right_now", "What to do right now"),
        ("next_three_steps", "Your next three steps"),
        ("what_to_gather", "What to gather"),
        ("what_may_be_missing", "What may be missing"),
        ("child_impact_lens", "What this may mean for your child"),
        ("when_to_get_human_help", "When to get human help"),
    ):
        values = _clean_lines(contract.get(key) or [])
        if values:
            sections.append((title, values))

    suggested = _clean_lines(contract.get("suggested_questions") or [])
    missing = _clean_lines(contract.get("what_may_be_missing") or [])
    if style == "intake":
        sections.append(("Intake questions to ask next", suggested or missing[:3] or ["What fact, order, or deadline should be confirmed first?"]))
    elif style == "professional_boundary":
        sections.append(
            (
                "Boundary guardrails",
                [
                    "Stay within your professional role and do not choose legal claims, predict outcomes, or present disputed facts as established.",
                    "Use a qualified lawyer, advocate, clerk, counselor, or other appropriate professional for the part outside your role.",
                ],
            )
        )
    elif style == "missing_information":
        # The structured UI already shows these fields separately.  The labels
        # below preserve a useful plain-text handoff for API and export clients.
        checklist = missing or ["Confirm the controlling order, case stage, dates, and the exact requested outcome."]
        sections.append(("Missing-information checklist", checklist))
        sections.append(("Role-specific follow-up questions", suggested or checklist[:3]))
    elif style == "questions_to_ask":
        sections.append(
            (
                "Ask a lawyer / qualified reviewer",
                suggested or [
                    "What legal options fit the current order, facts, deadlines, and requested outcome?",
                    "What should not be filed or relied on until the sources and records are reviewed?",
                ],
            )
        )
        sections.append(
            (
                "Ask a court clerk only about logistics",
                [
                    "Where are the current official forms and instructions?",
                    "What copies, fees, filing method, service instructions, or hearing logistics apply?",
                    "Clerks cannot choose claims, predict outcomes, or give legal strategy.",
                ],
            )
        )

    rendered = "\n\n".join(
        title + ":\n" + "\n".join(f"- {value}" for value in values)
        for title, values in sections
        if values
    )

    if style == "source_card_table":
        sources = list(contract.get("maine_law_sources") or []) + list(contract.get("private_record_sources") or [])
        rows = ["| Source | Type | Citation hint | Why it matters |", "|---|---|---|---|"]
        for source in sources:
            title = str(source.get("title") or "Source").replace("|", "\\|")
            lane = str(source.get("lane") or "source").replace("_", " ")
            citation = str(source.get("citation") or "Open the source card").replace("|", "\\|")
            proposition = str(source.get("proposition") or "Review the matched passage.").replace("|", "\\|")
            rows.append(f"| {title} | {lane} | {citation} | {proposition} |")
        rendered += "\n\n" + "\n".join(rows)

    disclaimer = "This is legal information, not legal advice. Verify current official sources and get qualified help for legal decisions."
    return (rendered + "\n\n" + disclaimer).strip() if rendered else disclaimer


def build_family_answer_contract(
    *,
    question: str,
    legacy_answer: str,
    citations: Iterable[dict[str, Any]],
    search_mode: str,
    safety: dict[str, Any] | None = None,
    missing_information: Iterable[object] = (),
    follow_up_questions: Iterable[object] = (),
    recommended_next_steps: Iterable[object] = (),
    child_impact_enabled: bool = False,
    lane_grounding: dict[str, bool] | None = None,
    intake: dict[str, Any] | IntakeSummary | None = None,
    response_kind: str = "family_answer",
    answer_style: str = "plain_language",
    grounding_integrity: dict[str, Any] | None = None,
    answer_support_integrity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create practical sections that reflect the user's actual intake."""

    if isinstance(intake, IntakeSummary):
        intake_summary = intake
    elif isinstance(intake, dict) and intake:
        intake_summary = IntakeSummary.from_dict(intake)
    else:
        intake_summary = parse_intake(question)
    safety = dict(safety or {})
    law_sources: list[dict[str, Any]] = []
    record_sources: list[dict[str, Any]] = []
    for citation in citations:
        lane = str((citation.get("metadata") or {}).get("source_lane") or "legal_authority")
        summary = _source_summary(citation, lane)
        if lane == "private_record":
            record_sources.append(summary)
        else:
            law_sources.append(summary)

    now, next_steps, gather, human_help = _task_plan(intake_summary)
    source_guided_steps = _clean_lines(recommended_next_steps)
    if source_guided_steps:
        next_steps = source_guided_steps[:3]
    source_missing = _clean_lines(missing_information)
    missing = _task_missing_information(intake_summary)
    for question_text in intake_summary.essential_follow_up_questions:
        if question_text not in missing:
            missing.append(question_text)
    # The dedicated missing-information style is deliberately exhaustive.
    # Ordinary chat stays concise and task-specific.
    if str(answer_style or "plain_language") == "missing_information":
        missing.extend(value for value in source_missing if value not in missing)
    elif intake_summary.task in {"general_question", "describe_situation"}:
        missing.extend(value for value in source_missing[:2] if value not in missing)
    missing = missing[:5]

    child_relevant = child_impact_enabled or intake_summary.child_relevant or any(
        term in intake_summary.normalized_text for term in CHILD_TERMS
    )
    child_impact: list[str] = []
    if child_relevant:
        child_impact = [
            "Protect routines, school, health or therapy logistics, exchanges, and important caregiver relationships where possible.",
            "Do not ask a child to choose, carry messages, investigate, or take sides in the adult dispute.",
            "Ask what would make the next step safer, more predictable, and less stressful for the child.",
        ]

    grounding = lane_grounding or {
        "legal_authority": bool(law_sources),
        "private_record": bool(record_sources),
    }
    meaning = _strip_legacy_noise(legacy_answer)
    if "immediate_safety" in intake_summary.urgency_flags:
        meaning = (
            "Safety comes before routine case planning. I cannot determine from chat exactly what is happening, "
            "contact anyone for you, or create legal protection. Use immediate local help when danger may be present, "
            "and avoid taking steps that could increase risk."
        )
    elif "urgent_child_safety" in intake_summary.urgency_flags or intake_summary.task == "child_safety":
        meaning = (
            "A possible child-safety concern needs careful human review. This chat cannot determine whether abuse, "
            "neglect, or another legal standard is established. Focus first on immediate safety and existing official "
            "orders or professional guidance."
        )
    elif not meaning:
        meaning = "The available sources did not establish a substantive answer."

    if response_kind in {"local_search_results", "source_card_followup", "ui_command"}:
        now, next_steps, gather, missing, child_impact, human_help = [], [], [], [], [], []

    suggested_questions = _clean_lines(follow_up_questions)
    for item in intake_summary.essential_follow_up_questions:
        if item not in suggested_questions:
            suggested_questions.append(item)

    return {
        "schema_version": "family_answer_v4_1",
        "response_kind": response_kind,
        "answer_style": str(answer_style or "plain_language"),
        "intake": intake_summary.to_dict(),
        "intake_label": concise_intake_label(intake_summary),
        "what_this_means": meaning,
        "what_to_do_right_now": now,
        "next_three_steps": next_steps,
        "what_to_gather": gather,
        "what_may_be_missing": missing,
        "suggested_questions": suggested_questions[:3],
        "critical_dates": list(intake_summary.critical_dates),
        "requested_actions": list(intake_summary.requested_actions),
        "routing_reasons": list(intake_summary.routing_reasons),
        "attention_level": intake_summary.attention_level,
        "routing_confidence": intake_summary.confidence,
        "child_impact_lens": child_impact,
        "maine_law_sources": law_sources,
        "private_record_sources": record_sources,
        "when_to_get_human_help": human_help,
        "safety_flags": {
            "immediate_safety_concern": "immediate_safety" in intake_summary.urgency_flags or bool(safety.get("requires_emergency_language")),
            "possible_deadline": "possible_deadline" in intake_summary.urgency_flags,
            "served_papers": "served_papers" in intake_summary.urgency_flags,
            "hearing_preparation": intake_summary.task == "hearing_preparation",
            "protection_from_abuse_routing": "protection_from_abuse" in intake_summary.issues,
            "urgent_child_safety_concern": "urgent_child_safety" in intake_summary.urgency_flags,
        },
        "lane_grounding": grounding,
        "grounding_integrity": dict(grounding_integrity or {}),
        "answer_support_integrity": dict(answer_support_integrity or {}),
        "research_brief": _research_brief(
            question=question,
            search_mode=search_mode,
            law_sources=law_sources,
            record_sources=record_sources,
            missing=missing,
            grounding=grounding,
        ) if str(answer_style or "plain_language") == "research_brief" else {},
        "limits": [
            "Private records may support a factual statement about a matter; they are not legal authority.",
            "Legal authority may support a statement of law; it does not prove disputed family facts.",
            "The intake summary routes the conversation; it is not a legal or factual finding.",
        ],
    }
