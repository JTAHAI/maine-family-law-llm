"""Deterministic local chat question/answer library.

This is a source-backed starter library for the local workbench. It is not an
LLM fine tune and it does not make answers filing-ready. It gives common parent,
lawyer, caregiver, counselor, and therapist prompts a stable first-pass answer
when matching official/safe bundled source snippets are retrieved.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

from .cite import render_citation_appendix
from .retrieve import SearchResult


DISCLAIMER = (
    "This is legal information for Maine family-law research and planning. It is not legal advice, "
    "does not create an attorney-client relationship, and is not filing-ready."
)


@dataclass(frozen=True)
class ChatLibraryItem:
    id: str
    audience: str
    topic: str
    title: str
    prompts: tuple[str, ...]
    keywords: tuple[str, ...]
    answer: str
    source_terms: tuple[str, ...]
    next_steps: tuple[str, ...]
    safety_note: str = ""

    def public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["prompts"] = list(self.prompts)
        payload["keywords"] = list(self.keywords)
        payload["source_terms"] = list(self.source_terms)
        payload["next_steps"] = list(self.next_steps)
        return payload


@dataclass(frozen=True)
class LibraryAnswer:
    item: ChatLibraryItem
    text: str
    citations: tuple[SearchResult, ...]


def _item(
    id: str,
    audience: str,
    topic: str,
    title: str,
    prompts: tuple[str, ...],
    keywords: tuple[str, ...],
    answer: str,
    source_terms: tuple[str, ...],
    next_steps: tuple[str, ...],
    safety_note: str = "",
) -> ChatLibraryItem:
    return ChatLibraryItem(
        id=id,
        audience=audience,
        topic=topic,
        title=title,
        prompts=prompts,
        keywords=keywords,
        answer=answer.strip(),
        source_terms=source_terms,
        next_steps=next_steps,
        safety_note=safety_note.strip(),
    )


CHAT_LIBRARY: tuple[ChatLibraryItem, ...] = (
    _item(
        "parent_best_interest_apply",
        "parent",
        "parental_rights",
        "How do I use the best-interest factors?",
        (
            "How do I use the best-interest factors in my parenting case?",
            "What should I organize for a best interest argument?",
        ),
        ("best interest", "factor", "parent", "residence", "contact", "custody"),
        "Maine parental-rights decisions are organized around the child's best interest. The most useful way to prepare is to connect each important fact to one or more 19-A M.R.S. § 1653(3) factors, especially safety, stability, the child's relationships, adjustment to home/school/community, parental cooperation, domestic abuse, child abuse, and whether the proposed allocation supports the child's safety and well-being.",
        ("1653", "parental rights", "best interest"),
        (
            "Make a factor-by-factor list of facts.",
            "Attach or identify evidence for each fact: orders, messages, school records, medical records, police/PFA records, or witness names.",
            "Separate safety issues from ordinary scheduling disputes.",
        ),
    ),
    _item(
        "parent_start_case",
        "parent",
        "court_process",
        "How do I start a Maine family matter?",
        (
            "How do I start a parental rights case in Maine?",
            "What is the first step in a Maine family matter?",
        ),
        ("start", "file", "commence", "complaint", "parental rights", "family matter"),
        "A Maine family matter usually begins with the correct Judicial Branch forms, filing, service, scheduling, and court review. The local workbench cannot tell you which filing is right for your facts, but it can point you to the official family-process and forms sources so you can verify the current packet and instructions.",
        ("family matter", "court forms", "rule 101", "commencement"),
        (
            "Identify whether this is divorce, parental rights, parentage, post-judgment, enforcement, contempt, or protection-from-abuse related.",
            "Use the current Maine Judicial Branch forms page, not a saved old PDF.",
            "Check service requirements and deadlines before filing.",
        ),
    ),
    _item(
        "parent_change_order",
        "parent",
        "post_judgment",
        "Can I change an existing order?",
        (
            "How do I change a custody order?",
            "Can I modify a Maine parental rights order?",
        ),
        ("modify", "change", "post judgment", "post-judgment", "existing order", "motion"),
        "Changing an existing Maine family order generally requires using the proper post-judgment motion process rather than informally ignoring the order. The key work is identifying what order exists, what part needs to change, what facts changed, and what source-backed evidence supports the requested change.",
        ("changing or enforcing", "family order", "motion process"),
        (
            "Locate the current order and docket information.",
            "List the exact requested change.",
            "Build a short timeline of changed facts and supporting evidence.",
        ),
    ),
    _item(
        "parent_enforce_order",
        "parent",
        "post_judgment",
        "What if the other parent is not following the order?",
        (
            "What can I do if the other parent is not following the order?",
            "How do I enforce a Maine family order?",
        ),
        ("enforce", "contempt", "not following", "violating", "order", "parent"),
        "If an existing family order is not being followed, the issue is usually enforcement, contempt, or a related post-judgment motion. The workbench should not tell you to withhold contact or support on your own. It should help you organize the order language, the alleged violation, dates, proof, and the proper Maine court process to review.",
        ("changing or enforcing", "family order", "motion process"),
        (
            "Quote the exact order language that was violated.",
            "Create a date-by-date log of what happened.",
            "Keep evidence separate from conclusions.",
        ),
    ),
    _item(
        "parent_child_support",
        "parent",
        "child_support",
        "What should I gather for child support?",
        (
            "What should I gather for child support?",
            "What should I review before a child support hearing?",
        ),
        ("child support", "support", "income", "affidavit", "guidelines"),
        "For a Maine child-support issue, start with the current court forms and official child-support information. The common preparation tasks are identifying income, support-affidavit requirements, health-insurance or childcare issues, the current order if one exists, and whether the issue is initial support, modification, or enforcement.",
        ("child support", "FM-050", "support enforcement", "guidelines"),
        (
            "Use the current Child Support Affidavit form if required.",
            "Collect recent pay records, benefit information, childcare costs, insurance costs, and the existing order.",
            "Do not rely on an estimated support number without checking the official worksheet/process.",
        ),
    ),
    _item(
        "safety_pfa_parent",
        "parent",
        "safety_pfa",
        "What if there is abuse or immediate danger?",
        (
            "What if I need protection from abuse?",
            "What if there is immediate danger in a parenting case?",
        ),
        ("danger", "abuse", "protection from abuse", "pfa", "unsafe", "violence", "threat"),
        "If someone is in immediate danger, call 911 or local emergency services. For non-immediate but serious safety concerns, use official protection-from-abuse and court resources. In a family case, keep safety facts separate from ordinary parenting disagreements and make sure any requested contact limits are tied to evidence.",
        ("protection from abuse", "immediate danger", "safety"),
        (
            "Use emergency resources first if safety is immediate.",
            "Write a clear timeline of safety events.",
            "Do not ask the workbench to make a safety plan; use qualified local resources.",
        ),
        safety_note="Emergency/safety routing required.",
    ),
    _item(
        "lawyer_rule_52_findings",
        "lawyer",
        "findings_review",
        "How should I check findings for a proposed order?",
        (
            "How do I check a proposed order for Rule 52 findings?",
            "What findings gaps should I review in a family order?",
        ),
        ("rule 52", "findings", "proposed order", "best interest", "factor gap"),
        "For a Maine family-law proposed order, review whether the order connects conclusions to findings and whether the best-interest factors that matter to the dispute are addressed with record-supported facts. The local workbench should flag missing findings, unsupported contact restrictions, PFA-family overlap issues, and best-interest factor gaps for human review.",
        ("rule", "family division", "best interest", "1653"),
        (
            "Map each requested ruling to a finding and supporting record fact.",
            "Check safety/contact restrictions for source-backed findings.",
            "Mark the draft review_required unless the filing-ready gate passes.",
        ),
    ),
    _item(
        "lawyer_source_stack",
        "lawyer",
        "authority_matrix",
        "What source stack should I check before drafting?",
        (
            "What sources should I check before drafting a Maine parental rights motion?",
            "Build an authority checklist for a Maine family-law motion.",
        ),
        ("source", "authority", "draft", "motion", "parental rights", "check"),
        "A safe drafting workflow should start with official Maine authority: Title 19-A statutes, Maine Judicial Branch forms and process pages, Maine Rules of Civil Procedure / Family Division rules, and relevant Law Court authority where available. Secondary summaries can help orientation, but they should not override official sources.",
        ("title 19-a", "family forms", "family division", "law court", "official"),
        (
            "Open the current official source before using language in a draft.",
            "Build an authority matrix: proposition, source, quote/span, freshness, and risk flag.",
            "Run citation/quote verification before export.",
        ),
    ),
    _item(
        "lawyer_pfa_family_overlap",
        "lawyer",
        "safety_pfa",
        "How should PFA orders interact with family orders?",
        (
            "Can a PFA order control the parental rights case?",
            "How should I analyze PFA-family overlap?",
        ),
        ("pfa", "protective order", "protection from abuse", "family overlap", "de novo"),
        "The workbench should flag PFA-family overlap for independent review. The Title 19-A fixture notes that although a court considers that a protective order was issued, parental rights and contact are determined de novo and the protective-order award should not be treated as precedent for the family case.",
        ("protective-order", "de novo", "1653", "protection from abuse"),
        (
            "Separate the PFA record from the family-case best-interest analysis.",
            "Identify which safety facts are independently supported.",
            "Check whether proposed contact limits have findings and evidence.",
        ),
    ),
    _item(
        "caregiver_guardian_start",
        "caregiver",
        "caregiver_role",
        "I am caring for a child. What should I ask?",
        (
            "I am a caregiver for a child. What should I ask the court about?",
            "Can a grandparent or caregiver use this tool?",
        ),
        ("caregiver", "grandparent", "guardian", "guardianship", "relative", "child"),
        "Caregivers should first identify what legal role is actually at issue: informal care, parental rights/contact, guardianship, protection-from-abuse overlap, or another court process. This local tool can help organize questions and source cards, but it should not tell a caregiver that they have rights without checking the proper Maine statute, form, and procedure.",
        ("family matter", "court forms", "parental rights", "child"),
        (
            "Write down the child's current living arrangement and who has an existing order.",
            "Identify whether any court order, DHHS involvement, or safety issue exists.",
            "Use current forms and get qualified review before filing.",
        ),
    ),
    _item(
        "counselor_records_boundaries",
        "counselor",
        "professional_boundaries",
        "What can a counselor safely use the tool for?",
        (
            "I am a counselor. How can I use this without giving legal advice?",
            "Can a counselor help a parent understand court language?",
        ),
        ("counselor", "therapist", "clinician", "legal advice", "records", "client"),
        "Counselors and therapists can use the workbench for general orientation to Maine family-law concepts, but should avoid giving legal advice, predicting case outcomes, or deciding parenting contact. The safe use is to help a client identify questions for counsel, understand that legal decisions require court/source review, and preserve clinical boundaries.",
        ("family matter", "parental rights", "best interest", "court forms"),
        (
            "Use plain-language explanations, not case-specific legal directives.",
            "Encourage the client to consult counsel or official court resources.",
            "Do not upload private clinical records into public repos or shared models.",
        ),
    ),
    _item(
        "therapist_non_delegation",
        "therapist",
        "professional_boundaries",
        "Can a therapist decide parenting time?",
        (
            "Can a therapist decide whether visits happen?",
            "Can a counselor control parent-child contact?",
        ),
        ("therapist", "counselor", "decide", "visits", "contact", "delegate"),
        "A therapist or counselor should be very careful about appearing to decide legal parenting time. The workbench should flag this as a non-delegation / contact-restriction issue: parenting contact decisions need court authority, source-backed findings, and review under the relevant Maine family-law standards, not an unsourced clinical veto.",
        ("contact", "parental rights", "best interest", "1653"),
        (
            "Clarify whether the therapist is providing treatment input, safety observations, or a court-ordered role.",
            "Do not convert clinical preference into a legal contact order.",
            "Ask for legal review if any order delegates contact decisions to a third party.",
        ),
    ),
    _item(
        "forms_current_version",
        "lawyer",
        "forms_rules",
        "How do I avoid stale forms?",
        (
            "How do I know which Maine family form to use?",
            "How do I avoid stale court forms?",
        ),
        ("form", "forms", "packet", "stale", "current", "fm-"),
        "Use the current Maine Judicial Branch forms page and verify the form number, version, and instructions before filing. A saved PDF, old packet, or copied sample may be stale. The workbench should surface form source cards and keep drafts review_required until forms and required fields are checked.",
        ("family forms", "court forms", "FM-050", "version"),
        (
            "Open the current official forms page.",
            "Record the form number and version/date in the draft packet.",
            "Run the filing-ready gate before export.",
        ),
    ),
    _item(
        "parent_served_papers",
        "parent",
        "court_process",
        "I was served with family-court papers. What should I do first?",
        (
            "I was served with family court papers. What should I do first?",
            "I got divorce or parental rights papers. What do I look at?",
        ),
        ("served", "papers", "summons", "complaint", "deadline", "respond", "divorce"),
        "Start by reading the papers carefully and identifying the court, docket number, case type, deadlines, scheduled events, and what the other party is asking for. The workbench can help organize the documents and point to official court-process and forms sources, but it cannot decide your legal response or deadline strategy.",
        ("family matter", "court forms", "service", "commencement", "divorce"),
        (
            "Write down every date on the papers and any scheduled court event.",
            "Identify whether the case is divorce, parental rights, parentage, protection from abuse, support, or post-judgment.",
            "Use current Maine Judicial Branch forms/instructions and seek legal review before filing a response.",
        ),
    ),
    _item(
        "parent_mediation_prep",
        "parent",
        "court_process",
        "How should I prepare for mediation or a court conference?",
        (
            "How should I prepare for mediation?",
            "What should I bring to a family court conference?",
        ),
        ("mediation", "conference", "hearing", "prepare", "bring", "schedule"),
        "For mediation or a court conference, organize the current order or pleadings, the issues in dispute, proposed schedules, support information, and any safety concerns. Keep the focus on the child's best interest and on facts that can be tied to documents, dates, witnesses, or official forms.",
        ("family matter", "mediation", "court review", "best interest", "1653"),
        (
            "Make a one-page issue list: residence, contact schedule, decision-making, support, safety, and forms.",
            "Bring or identify the current order, proposed schedule, income/support documents, and important records.",
            "Separate settlement ideas from safety concerns and non-negotiable legal issues.",
        ),
    ),
    _item(
        "parent_evidence_organize",
        "parent",
        "evidence_map",
        "How do I organize proof for court without dumping everything?",
        (
            "How do I organize evidence for family court?",
            "What proof should I organize for a parenting issue?",
        ),
        ("evidence", "proof", "records", "messages", "timeline", "organize"),
        "Organize proof by issue and date, not by emotion. For each claim, write the fact, date, source of proof, and which issue it supports. In a parental-rights dispute, connect facts to the best-interest factors and keep safety evidence separate from ordinary disagreement evidence.",
        ("best interest", "1653", "family matter", "court forms"),
        (
            "Build a timeline with date, event, document/witness, and issue tag.",
            "Use exact order language and exact dates for alleged violations.",
            "Do not upload private records into public repos or shared models; keep matter files local/private.",
        ),
    ),
    _item(
        "parent_contact_schedule",
        "parent",
        "parental_rights",
        "What is a parenting/contact schedule supposed to cover?",
        (
            "What should a parenting schedule cover?",
            "What is parent-child contact in Maine family court?",
        ),
        ("parenting schedule", "contact schedule", "visitation", "holiday", "vacation", "transportation"),
        "A useful parenting/contact schedule should be specific enough that both parents know regular time, exchanges, holidays, vacations, transportation, communication, and safety restrictions if any. The legal analysis still ties back to parental rights and responsibilities and the child's best interest.",
        ("parent-child contact", "parental rights", "best interest", "1653"),
        (
            "Draft a regular weekly schedule and a holiday/vacation schedule separately.",
            "Identify exchange locations, transportation, communication, and missed-time procedures.",
            "Tie any restriction to a source-backed safety fact or best-interest factor.",
        ),
    ),
    _item(
        "parent_gender_preference",
        "parent",
        "parental_rights",
        "Can the court prefer one parent because of gender?",
        (
            "Does Maine prefer mothers in custody cases?",
            "Can the court favor one parent because of gender?",
        ),
        ("mother", "father", "gender", "prefer", "preference", "custody"),
        "The Title 19-A fixture notes that the court may not apply a preference for one parent over the other because of the parent's gender or the child's age or gender. The analysis should stay focused on the child's best interest and source-backed facts.",
        ("gender", "preference", "1653", "best interest"),
        (
            "Frame facts around best-interest factors instead of gender stereotypes.",
            "List each parent's actual caregiving history, safety concerns, cooperation, and stability.",
            "Ask for legal review if a proposed order appears to rely on a gender preference.",
        ),
    ),
    _item(
        "parent_child_preference",
        "parent",
        "parental_rights",
        "Can my child choose where to live?",
        (
            "Can my child choose which parent to live with?",
            "Does the child's preference matter?",
        ),
        ("child choose", "preference", "child's preference", "old enough", "meaningful preference"),
        "The child's preference can be one factor if the child is old enough to express a meaningful preference, but it is not the only factor. Maine's best-interest analysis considers the full set of relevant factors, including safety, relationships, stability, adjustment, cooperation, and other welfare concerns.",
        ("preference", "meaningful preference", "1653", "best interest"),
        (
            "Do not pressure the child to choose sides.",
            "Organize facts about the child's adjustment, stability, safety, and relationships.",
            "Ask a lawyer or qualified professional how child preference evidence should be handled.",
        ),
    ),
    _item(
        "parent_safety_vs_conflict",
        "parent",
        "safety_pfa",
        "How do I separate safety concerns from ordinary conflict?",
        (
            "How do I explain safety concerns without sounding like conflict?",
            "How do domestic abuse concerns affect parenting issues?",
        ),
        ("safety", "domestic abuse", "abuse", "conflict", "fear", "unsafe"),
        "Safety concerns should be presented as specific facts tied to dates, conduct, evidence, and child impact. The best-interest factors include domestic abuse and child abuse considerations; ordinary co-parenting conflict should be separated from safety facts that affect contact or residence.",
        ("domestic abuse", "child abuse", "safety", "1653", "protection from abuse"),
        (
            "Create a safety timeline with date, event, evidence, and child impact.",
            "Use emergency/PFA resources for immediate danger.",
            "Tie requested contact restrictions to evidence and child-safety factors.",
        ),
        safety_note="Emergency/safety routing required if anyone is in immediate danger.",
    ),
    _item(
        "lawyer_motion_to_modify_vs_contempt",
        "lawyer",
        "post_judgment",
        "Modification, enforcement, or contempt?",
        (
            "Is this a motion to modify, enforce, or contempt issue?",
            "How do I triage a post-judgment family motion?",
        ),
        ("modify", "enforce", "contempt", "post-judgment", "triage", "motion"),
        "Triage post-judgment issues by separating requested future change, enforcement of existing language, and alleged noncompliance. The workbench should identify the existing order language, the requested remedy, the factual timeline, and whether the issue needs source-backed support, forms, or a findings review.",
        ("changing or enforcing", "existing family order", "motion process", "family matter"),
        (
            "Quote the exact existing order language.",
            "Classify each requested remedy as change, enforcement, contempt, or safety relief.",
            "Run citation/claim support review before drafting final language.",
        ),
    ),
    _item(
        "lawyer_best_interest_findings_matrix",
        "lawyer",
        "findings_review",
        "Build a best-interest findings matrix",
        (
            "Build a best-interest findings matrix.",
            "How do I structure proposed findings under 19-A M.R.S. § 1653?",
        ),
        ("matrix", "proposed findings", "1653", "best-interest", "findings"),
        "A best-interest findings matrix should list each contested factor, proposed finding, supporting record cite, contrary evidence, and requested ruling. It should not treat every factor as equally contested, but it should show that the relevant factors were considered and that safety/well-being were treated as primary where residence/contact are involved.",
        ("1653", "best interest", "safety and well-being", "findings"),
        (
            "Create columns: factor, fact, evidence, requested finding, risk/contrary proof.",
            "Flag domestic abuse, child abuse, sex-offense, and safety factors separately.",
            "Run the filing-ready gate; keep output review_required until verified.",
        ),
    ),
    _item(
        "lawyer_jurisdiction_scope_warning",
        "lawyer",
        "jurisdiction",
        "What jurisdiction issues should I flag?",
        (
            "What jurisdiction issues should I flag in a Maine custody matter?",
            "How should the tool handle out-of-state facts?",
        ),
        ("jurisdiction", "out of state", "uccjea", "another state", "home state"),
        "The workbench should not assume Maine authority covers every custody dispute with out-of-state facts. It should flag jurisdiction questions, out-of-state orders, existing proceedings, and federal/tribal issues for legal review before answering as if Maine can decide the issue.",
        ("Maine", "jurisdiction", "parental rights", "family matter"),
        (
            "Identify where the child has lived and whether another order/proceeding exists.",
            "Flag federal, tribal, or out-of-state authority questions instead of guessing.",
            "Do not use 'current Maine law' language unless source freshness and scope are known.",
        ),
    ),
    _item(
        "caregiver_existing_order",
        "caregiver",
        "caregiver_role",
        "What if I care for a child but there is an existing order?",
        (
            "I care for a child but there is an existing order. What should I ask?",
            "What should a relative caregiver check first?",
        ),
        ("caregiver", "relative", "existing order", "grandparent", "guardian", "care for a child"),
        "A relative or caregiver should first identify whether there is an existing court order, who has parental rights and responsibilities, whether DHHS or another court is involved, and whether the issue is safety, guardianship, contact, or support. The workbench can organize questions and source cards, but it cannot create rights without the correct legal process.",
        ("family matter", "parental rights", "court forms", "child"),
        (
            "Locate any existing court order or docket information.",
            "Write down the child's living arrangement and who is making decisions.",
            "Use official forms/resources and get qualified review before filing anything.",
        ),
    ),
    _item(
        "caregiver_safety_routing",
        "caregiver",
        "safety_pfa",
        "What if a child in my care may be unsafe?",
        (
            "What if a child in my care may be unsafe?",
            "I am a caregiver and there is a safety concern. What should I do?",
        ),
        ("caregiver", "unsafe", "safety", "abuse", "danger", "child in my care"),
        "If anyone is in immediate danger, use emergency services. For non-immediate safety concerns, document dates, conduct, child impact, existing orders, and official resources used. The workbench should route safety questions carefully and avoid pretending to make a safety plan.",
        ("protection from abuse", "immediate danger", "safety", "child"),
        (
            "Use emergency services for immediate danger.",
            "Create a factual timeline with dates and evidence.",
            "Ask qualified local/legal resources what reporting or court steps are required.",
        ),
        safety_note="Emergency/safety routing required.",
    ),
    _item(
        "counselor_client_explainer",
        "counselor",
        "plain_language",
        "How can I explain the court process without giving advice?",
        (
            "How can I explain family court language without giving legal advice?",
            "What can a counselor safely say about a parenting case?",
        ),
        ("counselor", "explain", "plain language", "without giving legal advice", "client"),
        "A counselor can explain that family-court decisions use legal standards, forms, source-backed facts, and court orders, while avoiding predictions, strategy, or instructions about what to file. The safest lane is helping the client identify questions for counsel and organize non-legal facts.",
        ("family matter", "court forms", "parental rights", "not legal advice"),
        (
            "Use neutral language: 'a court may need to review this,' not 'you should file this.'",
            "Encourage the client to use official court resources and counsel where possible.",
            "Do not upload confidential clinical records into shared systems.",
        ),
    ),
    _item(
        "counselor_court_letter",
        "counselor",
        "professional_boundaries",
        "Should I write a court letter?",
        (
            "Should I write a court letter for a parent?",
            "What should a counselor consider before writing to family court?",
        ),
        ("counselor", "letter", "court letter", "records", "confidential", "subpoena"),
        "Before writing a court letter, a counselor should consider role, consent, confidentiality, records rules, subpoena/order issues, clinical boundaries, and whether the letter risks becoming legal advocacy. The workbench can flag boundaries, but it cannot provide professional ethics advice or substitute for counsel/supervision.",
        ("court", "records", "family matter", "parental rights"),
        (
            "Clarify whether the request is treatment confirmation, observations, or legal opinion.",
            "Avoid recommending legal outcomes unless properly authorized and qualified.",
            "Consult supervision, counsel, or agency policy for record/confidentiality questions.",
        ),
    ),
    _item(
        "therapist_reunification_boundaries",
        "therapist",
        "professional_boundaries",
        "What if a court order mentions reunification therapy?",
        (
            "What if a court order mentions reunification therapy?",
            "How should a therapist handle court-ordered contact work?",
        ),
        ("reunification", "therapy", "therapist", "court ordered", "contact", "visits"),
        "When an order mentions therapy or reunification work, the therapist should distinguish clinical treatment from legal decision-making. The workbench should flag any language that appears to let a clinician decide whether parenting time happens, because contact restrictions and parenting decisions need court authority and source-backed findings.",
        ("therapist", "contact", "parental rights", "best interest", "1653"),
        (
            "Read the exact order language before acting.",
            "Clarify the clinical role, reporting requirements, and limits of authority.",
            "Refer legal-contact questions back to counsel/court rather than deciding them clinically.",
        ),
    ),
    _item(
        "therapist_records_caution",
        "therapist",
        "professional_boundaries",
        "Can therapy records be used in family court?",
        (
            "Can therapy records be used in family court?",
            "Should I upload clinical notes to the workbench?",
        ),
        ("therapy records", "clinical notes", "records", "confidentiality", "upload", "therapist"),
        "Do not upload private therapy notes or confidential clinical records into a public repo, shared model, or unapproved system. For family-court use, records issues require consent, orders/subpoenas, professional rules, and legal review. The workbench can help with general orientation only.",
        ("private", "records", "family matter", "not legal advice"),
        (
            "Keep records in approved clinical/legal systems only.",
            "Ask counsel/supervision before disclosing or summarizing clinical records for court.",
            "Use the tool for general questions, not confidential record processing unless the local matter workflow is approved.",
        ),
        safety_note="Privacy/confidentiality caution.",
    ),

)


def get_chat_library() -> tuple[ChatLibraryItem, ...]:
    return CHAT_LIBRARY


def public_library() -> list[dict[str, Any]]:
    return [item.public_dict() for item in CHAT_LIBRARY]


def expand_query_for_library(question: str) -> str:
    """Add safe retrieval hints for common human phrasing.

    The hints make the tiny offline fixture index behave more like a legal
    retriever without relying on model memory.
    """
    text = question.lower()
    hints: list[str] = []
    if any(term in text for term in ("therapist", "counselor", "clinician", "visits")):
        hints.append("parental rights responsibilities contact best interest 1653")
    if any(term in text for term in ("caregiver", "grandparent", "guardian", "relative")):
        hints.append("family matter court forms parental rights child")
    if any(term in text for term in ("modify", "change", "enforce", "contempt", "post judgment", "post-judgment")):
        hints.append("changing or enforcing order motion process family matter")
    if any(term in text for term in ("support", "affidavit", "income")):
        hints.append("child support FM-050 support enforcement guidelines")
    if any(term in text for term in ("pfa", "abuse", "danger", "unsafe", "violence")):
        hints.append("protection from abuse immediate danger safety 1653")
    if any(term in text for term in ("rule 52", "findings", "proposed order")):
        hints.append("family division rule best interest findings 1653")
    if any(term in text for term in ("form", "forms", "packet", "stale")):
        hints.append("court forms family forms version FM-050")
    if any(term in text for term in ("served", "papers", "summons", "deadline", "respond")):
        hints.append("family matter court forms commencement divorce service")
    if any(term in text for term in ("mediation", "conference", "hearing", "prepare", "bring")):
        hints.append("family matter mediation court review best interest 1653")
    if any(term in text for term in ("evidence", "proof", "records", "messages", "timeline")):
        hints.append("best interest 1653 family matter court forms records")
    if any(term in text for term in ("schedule", "visitation", "holiday", "transportation")):
        hints.append("parent-child contact parental rights best interest 1653")
    if any(term in text for term in ("mother", "father", "gender", "preference", "choose")):
        hints.append("gender preference meaningful preference best interest 1653")
    if any(term in text for term in ("jurisdiction", "out of state", "another state", "uccjea")):
        hints.append("Maine jurisdiction parental rights family matter court review")
    if any(term in text for term in ("letter", "court letter", "confidential", "subpoena", "clinical notes", "therapy records")):
        hints.append("family matter court records parental rights not legal advice")
    if any(term in text for term in ("reunification", "court ordered", "clinical role")):
        hints.append("therapist contact parental rights best interest 1653")
    if not hints:
        return question
    return question + "\n\nRetrieval hints: " + " ".join(hints)


def match_chat_library(question: str) -> ChatLibraryItem | None:
    text = _normalize(question)
    best: tuple[int, ChatLibraryItem] | None = None
    for item in CHAT_LIBRARY:
        score = _score_item(text, item)
        if score <= 0:
            continue
        if best is None or score > best[0]:
            best = (score, item)
    if best is None:
        return None
    # Keep the library from over-matching generic short questions.
    return best[1] if best[0] >= 4 else None


def compose_library_answer(
    question: str,
    retrieval_results: tuple[SearchResult, ...],
    *,
    answer_style: str = "plain_language",
    matter_context: str = "",
) -> LibraryAnswer | None:
    item = match_chat_library(question + " " + matter_context)
    if item is None:
        return None
    citations = _pick_citations(item, retrieval_results)
    if not citations:
        return None

    lines: list[str] = []
    heading = f"{item.title}"
    if answer_style == "checklist":
        lines.append(f"Checklist: {heading}")
        lines.append("")
        lines.append(item.answer)
        lines.append("")
        lines.append("Next steps:")
        for step in item.next_steps:
            lines.append(f"[ ] {step}")
    elif answer_style == "source_first":
        lines.append("Source-backed answer")
        lines.append("")
        lines.append(item.answer)
        lines.append("")
        lines.append("Why these sources matter:")
        for result in citations:
            lines.append(f"- {result.title}: {result.snippet}")
        lines.append("")
        lines.append("Next steps:")
        for step in item.next_steps:
            lines.append(f"- {step}")
    else:
        lines.append(item.answer)
        lines.append("")
        lines.append("Practical next steps:")
        for step in item.next_steps:
            lines.append(f"- {step}")
    if item.safety_note:
        lines.append("")
        lines.append(f"Safety note: {item.safety_note}")
    lines.append("")
    lines.append(DISCLAIMER)
    lines.append("")
    lines.append(render_citation_appendix(citations))
    return LibraryAnswer(item=item, text="\n".join(lines), citations=citations)


def _score_item(text: str, item: ChatLibraryItem) -> int:
    score = 0
    for keyword in item.keywords:
        normalized = _normalize(keyword)
        if " " in normalized:
            if normalized in text:
                score += 3
        elif re.search(rf"\b{re.escape(normalized)}\b", text):
            score += 1
    for prompt in item.prompts:
        for token in _tokens(prompt):
            if token in text:
                score += 1
    if item.audience in text:
        score += 2
    return score


def _pick_citations(item: ChatLibraryItem, results: tuple[SearchResult, ...]) -> tuple[SearchResult, ...]:
    chosen: list[SearchResult] = []
    for result in results:
        haystack = _normalize(
            " ".join(
                [
                    result.title,
                    result.citation,
                    result.snippet,
                    str(result.metadata.get("source_type", "")),
                    str(result.metadata.get("citation_hint", "")),
                    str(result.metadata.get("text", ""))[:2400],
                ]
            )
        )
        if any(_normalize(term) in haystack for term in item.source_terms):
            chosen.append(result)
    if not chosen:
        chosen = [result for result in results if result.metadata.get("official")]
    return tuple(chosen[:4])


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9']+", _normalize(value)) if len(token) > 2}


def _normalize(value: str) -> str:
    return " ".join(value.lower().replace("§", " ").split())
