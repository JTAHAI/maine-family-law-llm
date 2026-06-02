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

    _item(
        "parent_divorce_first_steps",
        "parent",
        "divorce",
        "What should I do first in a Maine divorce?",
        (
            "What should I do first in a Maine divorce?",
            "I am thinking about divorce in Maine. What should I organize?",
        ),
        ("divorce", "separation", "first steps", "marriage", "property", "children"),
        "For a Maine divorce, start by separating the legal process from personal decisions. Identify whether there are children, property, support, safety concerns, and any immediate court dates. Use the current Maine Judicial Branch divorce/family-process pages and forms; do not rely on a saved old packet or a generic internet checklist.",
        ("divorce", "family matter", "court forms", "Judicial Branch"),
        (
            "Write down case type, county/court, children, property/support issues, and safety concerns.",
            "Find the current official forms and instructions before drafting or filing anything.",
            "Treat all generated checklists as review_required until a qualified reviewer checks the facts and sources.",
        ),
    ),
    _item(
        "parent_unmarried_parent_prr",
        "parent",
        "parental_rights",
        "What if we were never married?",
        (
            "We were never married. How do parental rights work in Maine?",
            "Do unmarried parents use divorce forms?",
        ),
        ("unmarried", "never married", "parental rights", "parentage", "father", "mother"),
        "If parents were never married, the workbench should not treat the case as a divorce. The starting question is which Maine family process applies: parentage, parental rights and responsibilities, child support, or another family matter. The source-backed next step is to use official court process/forms and identify whether a court order already exists.",
        ("parental rights", "family matter", "court forms", "child support"),
        (
            "Identify whether parentage is established and whether any order already exists.",
            "Separate residence/contact, decision-making, and support questions.",
            "Use official current forms and get legal review before filing.",
        ),
    ),
    _item(
        "parent_temporary_order_prep",
        "parent",
        "court_process",
        "How should I prepare for a temporary order hearing?",
        (
            "How do I prepare for a temporary order hearing?",
            "What should I bring to an interim family court hearing?",
        ),
        ("temporary order", "interim", "hearing", "bring", "prepare", "urgent"),
        "For a temporary or interim family-court event, organize the immediate issues: child residence/contact, safety, support, service/deadlines, and any existing order. The answer should stay practical and source-backed: what facts, records, and forms need review, not what outcome the court should order.",
        ("family matter", "court review", "court forms", "best interest"),
        (
            "Make a one-page list of immediate disputed issues and requested temporary terms.",
            "Attach dates/documents to each fact, especially safety or support facts.",
            "Check the current official process/forms and ask for legal review before filing.",
        ),
    ),
    _item(
        "parent_supervised_contact_question",
        "parent",
        "parental_rights",
        "When does supervised contact come up?",
        (
            "Can I ask for supervised visits?",
            "When does supervised contact come up in Maine family court?",
        ),
        ("supervised", "supervision", "restricted contact", "visits", "safety", "contact"),
        "Supervised or restricted contact should be treated as a serious contact-restriction issue, not as a generic preference. The workbench should help organize the safety or best-interest facts, the evidence, and the requested terms, while flagging that any restriction needs source-backed findings and human legal review.",
        ("contact", "parental rights", "best interest", "safety", "1653"),
        (
            "List the specific safety facts and dates supporting the requested restriction.",
            "Separate supervision logistics from the legal basis for restriction.",
            "Flag the issue for findings/review before any proposed order is treated as ready.",
        ),
        safety_note="Contact restrictions should be tied to evidence and reviewed by a qualified legal professional.",
    ),
    _item(
        "parent_decision_making_school_medical",
        "parent",
        "parental_rights",
        "What about school, medical, and major decisions?",
        (
            "How do school and medical decisions work in a parenting order?",
            "What should decision-making terms cover?",
        ),
        ("school", "medical", "education", "decision-making", "decisions", "parental rights"),
        "Parenting orders often need clear terms for residence/contact and for decision-making about school, medical care, activities, and communication. The workbench can help list the decision areas and connect disputed issues to best-interest factors, but it should not choose the legal allocation without source-backed facts and review.",
        ("parental rights", "best interest", "1653", "family matter"),
        (
            "List each decision category: school, medical/dental, counseling, activities, travel, and communication.",
            "Identify which facts support shared or allocated decision-making.",
            "Check proposed language against the official source cards and human review gate.",
        ),
    ),
    _item(
        "parent_move_or_relocation_flag",
        "parent",
        "jurisdiction",
        "What if one parent wants to move?",
        (
            "What if one parent wants to move away with the child?",
            "How should I organize a relocation or move issue?",
        ),
        ("move", "relocate", "moving away", "out of state", "school district", "distance"),
        "A proposed move can affect residence, contact schedule, school stability, transportation, and sometimes jurisdiction. The workbench should not guess the outcome. It should organize the facts under best-interest themes and flag any out-of-state or existing-order issue for legal review.",
        ("best interest", "parental rights", "contact", "jurisdiction", "1653"),
        (
            "List current and proposed addresses/schools, travel distance, transportation, and contact impact.",
            "Identify any existing order and whether another state or court is involved.",
            "Tie the proposed schedule to stability, safety, relationships, and child adjustment facts.",
        ),
    ),
    _item(
        "parent_communication_messages",
        "parent",
        "evidence_map",
        "How should I use texts, emails, and app messages?",
        (
            "How should I organize texts and app messages for court?",
            "Can I use messages as evidence in a parenting case?",
        ),
        ("texts", "messages", "email", "app", "communication", "evidence"),
        "Messages are easiest to review when they are organized by date, issue, and exact claim they support. Do not dump a whole message history. For family-court review, connect selected messages to best-interest, safety, support, service, or order-compliance issues and preserve the original records privately.",
        ("evidence", "records", "best interest", "family matter", "1653"),
        (
            "Create a message log: date, sender, short description, issue tag, and why it matters.",
            "Keep screenshots/exports intact and private; do not upload confidential records to shared systems.",
            "Separate admissibility/legal-use questions for attorney review.",
        ),
    ),
    _item(
        "parent_missed_exchange_log",
        "parent",
        "post_judgment",
        "How do I document missed exchanges or denied contact?",
        (
            "How do I document missed exchanges?",
            "What proof do I need if parenting time is denied?",
        ),
        ("missed exchange", "denied contact", "no show", "late", "exchange", "violating order"),
        "For missed exchanges or denied contact, start with the exact current order language, then create a date-by-date log of what happened and what proof exists. The workbench should keep this in enforcement/post-judgment review mode and avoid telling a parent to self-help or violate another part of the order.",
        ("changing or enforcing", "family order", "motion process", "contact"),
        (
            "Quote the exact exchange/contact language from the current order.",
            "Log each incident with date, time, location, who was present, and proof.",
            "Ask for legal review before deciding whether the issue is enforcement, contempt, modification, or safety relief.",
        ),
    ),
    _item(
        "parent_support_change_income",
        "parent",
        "child_support",
        "What if income changed after a support order?",
        (
            "My income changed. What should I gather for child support?",
            "What documents matter for changing child support?",
        ),
        ("income changed", "lost job", "new job", "support modification", "child support", "pay"),
        "For a child-support change question, organize current income, past income, the existing order, childcare/insurance costs, and the reason for the change. The workbench can help prepare a source-backed document checklist, but it should not calculate or promise a support result without the official worksheet/process and legal review.",
        ("child support", "FM-050", "support enforcement", "guidelines", "court forms"),
        (
            "Collect pay records, benefit records, childcare/insurance costs, and the current order.",
            "Identify whether the issue is initial support, modification, enforcement, or arrears.",
            "Use current official forms and review any calculation before relying on it.",
        ),
    ),
    _item(
        "lawyer_intake_triage_parental_rights",
        "lawyer",
        "intake_triage",
        "How should I triage a new parental-rights intake?",
        (
            "Give me an intake checklist for a Maine parental rights case.",
            "What should I ask a new parenting client first?",
        ),
        ("intake", "triage", "new client", "parental rights", "checklist", "client"),
        "A safe intake triage should identify case type, posture, existing orders, child residence history, safety/PFA issues, support, service/deadlines, jurisdiction flags, and needed forms. The workbench should produce an issue map and source list, not legal conclusions unsupported by a file review.",
        ("family matter", "parental rights", "court forms", "best interest", "protection from abuse"),
        (
            "Classify posture: initial, temporary, final, post-judgment, contempt, appeal, or PFA overlap.",
            "Collect existing orders, pleadings, service papers, support documents, and safety records.",
            "Run issue labels, authority matrix, evidence map, and findings-gap review.",
        ),
    ),
    _item(
        "lawyer_draft_client_letter_plain_language",
        "lawyer",
        "plain_language",
        "How do I explain next steps to a client?",
        (
            "Draft a plain-language client explanation for a parenting case.",
            "How should I explain Maine family court next steps without legalese?",
        ),
        ("client letter", "plain language", "explain", "next steps", "parenting case"),
        "A client-facing explanation should separate what the official sources say from what counsel recommends after reviewing the facts. The workbench can produce a plain-language outline with review_required status, source cards, and a checklist of documents the client should gather.",
        ("family matter", "court forms", "best interest", "Judicial Branch"),
        (
            "Use plain language and define court terms like order, motion, service, mediation, and hearing.",
            "Attach source cards or links for official forms/process pages.",
            "Mark any strategy or recommendation as attorney-reviewed, not AI-generated.",
        ),
    ),
    _item(
        "parent_appeals_court_routing",
        "parent",
        "appeal_preservation",
        "What court handles Maine family-law appeals?",
        (
            "What court handles appeals?",
            "Which court hears an appeal from a Maine family order?",
            "Where does a Maine family court appeal go?",
        ),
        (
            "court handles appeals",
            "what court handles appeals",
            "appeals court",
            "appeal court",
            "appeals",
            "appeal",
            "law court",
            "supreme judicial court",
            "district court appeal",
        ),
        "For a Maine family-law order, do not use a parenting-schedule answer. Appeals are a separate court/posture issue. The Maine Judicial Branch appeals source says most District Court appeals are filed directly to the Supreme Judicial Court; small-claims and eviction appeals are different and go to Superior Court. The Supreme Judicial Court is Maine's highest court and court of final appeal, often called the Law Court when deciding appeals. A family-law appeal also requires checking the current Maine Rules of Appellate Procedure, the order's finality, deadlines, record/transcript issues, preservation, and whether a motion for findings or other post-order step is needed.",
        ("appeals", "Supreme Judicial Court", "Law Court", "M.R. App. P.", "appellate"),
        (
            "Identify the court that issued the order: District Court, Superior Court, or another tribunal.",
            "Confirm whether the order is final or otherwise appealable before assuming an appeal route.",
            "Check the current Maine Rules of Appellate Procedure and any notice-of-appeal deadline with a qualified reviewer.",
            "Gather the order, docket entries, requested findings, transcript/record status, and preserved objections.",
        ),
        safety_note="Appeal deadlines and preservation issues are time-sensitive; use qualified legal review.",
    ),
    _item(
        "lawyer_appeal_record_findings",
        "lawyer",
        "appeal_preservation",
        "What should I check before appeal or reconsideration?",
        (
            "What appellate record issues should I check in a family case?",
            "What should I review if findings are missing?",
        ),
        ("appeal", "record", "transcript", "findings", "reconsideration", "preservation"),
        "For appeal or post-order review, the workbench should flag missing findings, unclear best-interest analysis, unsupported restrictions, transcript/record needs, deadlines, and whether the issue belongs in a motion for findings, reconsideration-style review, appeal, or another procedure. It cannot supply appellate strategy without attorney review.",
        ("rule", "findings", "best interest", "family division", "1653"),
        (
            "Identify final/interim posture, order date, deadlines, and requested relief.",
            "Map each claimed error to the order text, record fact, and authority source.",
            "Flag missing transcript/record and source-freshness issues before drafting.",
        ),
    ),
    _item(
        "lawyer_source_card_audit",
        "lawyer",
        "authority_matrix",
        "How do I audit the source cards before using an answer?",
        (
            "How do I audit source cards before using an answer?",
            "What should I check in the citation appendix?",
        ),
        ("source card", "citation appendix", "audit", "verify", "quote", "authority"),
        "Before using any answer, audit each source card for source class, official status, freshness/version, citation hint, URL, and whether the cited snippet actually supports the claim. The workbench's deterministic answer is only a starting point; unresolved, stale, or unsupported cards should block final use.",
        ("official", "citation", "source", "forms", "family division"),
        (
            "Check every source card against the official page.",
            "Confirm the answer's claim is actually supported by the snippet or full source.",
            "Run citation, quote, claim-support, and filing-ready gates before export.",
        ),
    ),
    _item(
        "lawyer_adverse_source_check",
        "lawyer",
        "authority_matrix",
        "What could weaken this argument?",
        (
            "What sources could weaken my parenting argument?",
            "How should I build a contrary-authority checklist?",
        ),
        ("weaken", "contrary", "adverse", "argument", "risk", "opposing"),
        "For any requested parenting outcome, build a contrary-authority and contrary-fact checklist. The workbench should list missing facts, best-interest factors that cut the other way, safety concerns, jurisdiction questions, and stale/unsupported source risks instead of presenting only the favorable framing.",
        ("best interest", "1653", "source", "official", "family matter"),
        (
            "List the requested ruling and each fact that supports it.",
            "Add a column for contrary facts, missing evidence, stale sources, and unsupported assumptions.",
            "Use the challenger/reviewer lane before drafting final proposed findings.",
        ),
    ),
    _item(
        "advocate_self_represented_help_boundaries",
        "lawyer",
        "court_process",
        "How can an advocate help without crossing the line?",
        (
            "How can an advocate help a self-represented parent use this tool?",
            "What boundaries should a legal helper keep?",
        ),
        ("advocate", "self represented", "pro se", "helper", "boundaries", "legal advice"),
        "A helper can use the workbench to organize documents, identify official sources, generate questions for counsel/court help, and explain that outputs are review_required. The helper should not choose strategy, promise outcomes, or turn source-backed information into case-specific legal advice without proper authority.",
        ("court forms", "family matter", "not legal advice", "Judicial Branch"),
        (
            "Keep a written distinction between information, organization, and legal advice.",
            "Use official sources and source cards for every legal/procedure statement.",
            "Refer strategy, deadlines, filings, and safety issues to qualified review.",
        ),
    ),
    _item(
        "caregiver_school_medical_documents",
        "caregiver",
        "caregiver_role",
        "What documents should a caregiver gather?",
        (
            "What documents should a caregiver gather for school or medical issues?",
            "I am caring for a child and need to organize records. What matters?",
        ),
        ("caregiver", "school", "medical", "records", "documents", "child"),
        "A caregiver should gather documents that show the child's current living arrangement, school/medical needs, existing court orders, who has legal decision-making authority, and any safety issue. The workbench can organize records and questions, but it cannot decide the caregiver's legal authority without the correct Maine process and review.",
        ("family matter", "court forms", "parental rights", "child"),
        (
            "Collect existing orders, school communications, medical appointment summaries, and caregiver timeline facts.",
            "Identify who currently has parental rights/responsibilities or guardianship authority.",
            "Keep private records local/approved and ask for qualified review before disclosure.",
        ),
    ),
    _item(
        "caregiver_grandparent_contact_question",
        "caregiver",
        "caregiver_role",
        "Can a grandparent or relative ask for contact?",
        (
            "Can a grandparent ask for visitation in Maine?",
            "Can a relative caregiver ask for contact with a child?",
        ),
        ("grandparent", "relative", "visitation", "contact", "caregiver", "third party"),
        "A grandparent or relative-contact question needs careful source review. The workbench should not assume a non-parent has rights. It should identify the existing orders, the caregiver's role, the child's circumstances, and which Maine statute/form/procedure must be checked before any filing or expectation is formed.",
        ("family matter", "court forms", "parental rights", "contact"),
        (
            "Find out whether a parent, guardian, DHHS, or another court already has authority.",
            "List the caregiver's relationship, time caring for the child, and safety/stability facts.",
            "Use official forms/sources and get legal review before filing.",
        ),
    ),
    _item(
        "caregiver_dhhs_overlap_flag",
        "caregiver",
        "safety_pfa",
        "What if DHHS or child-safety issues overlap?",
        (
            "What if DHHS is involved with the family?",
            "How should a caregiver handle child-safety overlap?",
        ),
        ("dhhs", "child safety", "unsafe", "neglect", "abuse", "caregiver"),
        "When DHHS, child-safety, or abuse/neglect concerns overlap with family court, the workbench should route immediate danger to emergency resources, keep confidential facts protected, and flag that different courts/agencies may have different procedures. It should organize questions and source cards, not replace professional or legal guidance.",
        ("safety", "protection from abuse", "family matter", "child"),
        (
            "Use emergency resources first if anyone is in immediate danger.",
            "Separate family-court orders, DHHS communications, and safety facts in the timeline.",
            "Ask for qualified legal/professional review before disclosing private records or filing.",
        ),
        safety_note="Emergency/safety routing required if anyone may be in immediate danger.",
    ),
    _item(
        "counselor_subpoena_or_order",
        "counselor",
        "professional_boundaries",
        "What if I receive a subpoena or court order?",
        (
            "What should a counselor do if subpoenaed in a family case?",
            "I received a court order for records. Can this tool help?",
        ),
        ("subpoena", "court order", "records", "counselor", "testify", "disclosure"),
        "A subpoena or court order involving counseling records is not a simple chat question. The workbench can help organize what was received, deadlines, record categories, and questions for counsel/supervision, but it should not decide disclosure, privilege, confidentiality, or testimony obligations.",
        ("court", "records", "family matter", "not legal advice"),
        (
            "Record what was served, by whom, date/time, deadline, and requested records/testimony.",
            "Do not upload confidential records into the repo or a shared model.",
            "Contact agency counsel, supervision, malpractice/ethics resources, or qualified legal counsel.",
        ),
        safety_note="Confidentiality/records review required.",
    ),
    _item(
        "counselor_parent_needs_court_help",
        "counselor",
        "plain_language",
        "How can I help a client prepare questions for court or counsel?",
        (
            "How can I help a parent prepare questions for a lawyer?",
            "How can a counselor help a client understand family court paperwork?",
        ),
        ("prepare questions", "lawyer", "paperwork", "counselor", "client", "understand"),
        "A counselor can help a client organize questions, dates, documents, and emotional support needs without giving legal advice. The workbench can translate court-process concepts into plain language and produce a questions-for-counsel list, while keeping case-specific legal decisions for qualified legal review.",
        ("family matter", "court forms", "Judicial Branch", "not legal advice"),
        (
            "Help the client list deadlines, court dates, papers received, and questions.",
            "Avoid telling the client what to file or what outcome to seek.",
            "Refer legal decisions, deadlines, and filings to counsel or official court resources.",
        ),
    ),
    _item(
        "counselor_safety_disclosure_boundary",
        "counselor",
        "safety_pfa",
        "What if a client reports domestic abuse or child-safety concerns?",
        (
            "What if a counseling client reports domestic abuse in a family case?",
            "How should a counselor handle safety disclosures related to court?",
        ),
        ("domestic abuse", "safety disclosure", "child safety", "mandatory", "danger", "counselor"),
        "Safety disclosures should be handled through the counselor's professional, mandated-reporting, agency, emergency, and legal obligations. The workbench can help separate immediate danger, protection-from-abuse orientation, and family-court evidence organization, but it cannot make a clinical/legal disclosure decision.",
        ("protection from abuse", "immediate danger", "safety", "family matter"),
        (
            "Use emergency resources first if danger is immediate.",
            "Follow agency/professional reporting and confidentiality rules; seek supervision/counsel.",
            "If court-related, organize dates and facts without exposing private records to unapproved systems.",
        ),
        safety_note="Emergency and professional reporting review may be required.",
    ),
    _item(
        "therapist_parenting_evaluator_boundary",
        "therapist",
        "professional_boundaries",
        "Am I treating, evaluating, or making a legal recommendation?",
        (
            "What is the boundary between therapy and a parenting recommendation?",
            "Can a therapist make custody recommendations?",
        ),
        ("custody recommendation", "parenting recommendation", "evaluation", "therapy", "role", "boundary"),
        "A therapist should distinguish treatment, collateral observation, court-ordered evaluation, and legal advocacy. The workbench should flag any request to decide parental rights, residence, or contact as requiring court authority, source-backed findings, role clarity, and legal/professional review.",
        ("parental rights", "contact", "best interest", "1653", "court"),
        (
            "Clarify the role in writing: treater, evaluator, reunification provider, or other court-ordered role.",
            "Avoid legal conclusions unless the role and order authorize the specific opinion.",
            "Refer allocation/contact decisions back to court/counsel when role authority is unclear.",
        ),
    ),
    _item(
        "therapist_no_private_uploads",
        "therapist",
        "professional_boundaries",
        "Can I paste session notes into the workbench?",
        (
            "Can I paste session notes into this workbench?",
            "Can a therapist upload private records for analysis?",
        ),
        ("session notes", "paste", "upload", "private records", "clinical", "therapist"),
        "Do not paste session notes, private clinical records, protected health information, child identifiers, or sealed/confidential matter records into an unapproved tool or public repo. This local workbench is for general orientation unless an approved private matter workflow, storage policy, and human review process are configured.",
        ("private", "records", "not legal advice", "family matter"),
        (
            "Use de-identified hypotheticals for general orientation only.",
            "Keep clinical records in approved systems with agency/legal controls.",
            "Ask supervision/counsel before summarizing or disclosing records for court.",
        ),
        safety_note="Privacy/confidentiality caution.",
    ),
    _item(
        "therapist_child_voice_boundary",
        "therapist",
        "parental_rights",
        "How should a child's stated preference be handled clinically?",
        (
            "A child told me where they want to live. What should a therapist do?",
            "How should a therapist handle a child's preference in a custody dispute?",
        ),
        ("child preference", "child told me", "where to live", "therapist", "custody dispute"),
        "A child's preference may be relevant to Maine's best-interest analysis if the child is old enough to express a meaningful preference, but a therapist should not turn that statement into a legal decision. The safe role is to preserve clinical boundaries, avoid coaching or pressure, and refer legal-use questions to counsel/court.",
        ("preference", "meaningful preference", "best interest", "1653"),
        (
            "Avoid pressuring the child or translating clinical statements into legal conclusions.",
            "Clarify consent, confidentiality, and court-order/reporting obligations.",
            "Refer evidentiary/legal questions to qualified legal review.",
        ),
    ),
    _item(
        "therapist_safety_contact_boundary",
        "therapist",
        "safety_pfa",
        "What if safety concerns arise during contact work?",
        (
            "What if safety concerns arise during reunification or contact work?",
            "Can a therapist stop visits because of safety concerns?",
        ),
        ("safety concerns", "stop visits", "reunification", "contact work", "therapist", "unsafe"),
        "If immediate safety concerns arise, use emergency/professional protocols. For non-immediate contact concerns, a therapist should document observations within the authorized role and avoid unilaterally converting clinical concern into a legal contact order unless the court order and applicable professional/legal rules clearly authorize the action.",
        ("safety", "contact", "parental rights", "best interest", "1653"),
        (
            "Follow emergency, mandated-reporting, agency, and court-order protocols.",
            "Document observed facts separately from legal conclusions.",
            "Ask counsel/court for clarification if the order appears to delegate contact decisions.",
        ),
        safety_note="Emergency/professional protocol review required if safety is immediate.",
    ),

    _item(
        "parent_ask_lawyer_before_filing",
        "parent",
        "questions_to_ask",
        "What should I ask a lawyer before filing?",
        (
            "What should I ask a lawyer before filing a family case?",
            "What questions should I bring to a Maine family lawyer?",
        ),
        ("ask lawyer", "before filing", "lawyer questions", "consult", "attorney", "prepare"),
        "Before filing or responding, use the workbench to organize questions rather than to choose a legal strategy. A useful lawyer-prep list identifies case type, existing orders, deadlines, safety concerns, children, support, property, service, and what documents are missing.",
        ("family matter", "court forms", "divorce", "parental rights", "child support"),
        (
            "Ask what case type and procedure fit your facts.",
            "Ask what deadlines, service requirements, and court events matter first.",
            "Ask what documents, records, and source-backed facts the lawyer needs before drafting.",
        ),
    ),
    _item(
        "parent_court_clerk_questions",
        "parent",
        "questions_to_ask",
        "What can I ask a court clerk?",
        (
            "What can I ask the court clerk about my family case?",
            "Can the clerk tell me what forms I need?",
        ),
        ("court clerk", "clerk", "forms", "what forms", "filing window", "ask the court"),
        "Court clerks can often point people to public forms, filing logistics, and court-process information, but they cannot act as your lawyer, choose your claims, predict outcomes, or tell you what to say in court. The workbench should frame clerk questions around official forms and logistics, not legal advice.",
        ("court forms", "family matter", "court process", "Judicial Branch"),
        (
            "Ask where the current official form packet and instructions are located.",
            "Ask about filing logistics, copies, service instructions, fees, and scheduling information.",
            "Save legal-strategy and what-should-I-file questions for legal review.",
        ),
        safety_note="Clerks cannot provide legal advice or strategy.",
    ),
    _item(
        "parent_fee_waiver_filing_costs",
        "parent",
        "court_process",
        "What if I cannot afford filing fees?",
        (
            "What if I cannot afford family court filing fees?",
            "Is there a fee waiver for Maine family court?",
        ),
        ("fee waiver", "cannot afford", "filing fee", "cost", "indigent", "waive"),
        "If filing costs are a barrier, use the official court forms/instructions to identify any fee-waiver or payment-related process that applies. The workbench should not promise eligibility; it should help you find the current official form and organize income/expense information for review.",
        ("court forms", "family forms", "family matter", "Judicial Branch"),
        (
            "Check the current Maine Judicial Branch forms page for fee-related forms/instructions.",
            "Gather income, benefit, expense, and household information before asking for review.",
            "Ask the clerk about filing logistics, not whether you legally qualify.",
        ),
    ),
    _item(
        "parent_service_of_process_basics",
        "parent",
        "court_process",
        "How do I think about service of papers?",
        (
            "How do I serve family court papers in Maine?",
            "What should I check about service of process?",
        ),
        ("serve", "service", "served papers", "summons", "proof of service", "sheriff"),
        "Service is a procedure issue, not just a mailing task. Use official forms/rules and court instructions to verify who must be served, what must be served, how proof is shown, and whether deadlines or safety concerns affect service. The workbench should flag service questions for source-card and human review.",
        ("service", "commencement", "court forms", "rule 101", "family matter"),
        (
            "Identify the exact documents that must be served and the current court instructions.",
            "Write down dates: filing, service attempt, completed service, hearing or response deadline.",
            "Ask for legal review if service is disputed, unsafe, or out of state.",
        ),
    ),
    _item(
        "parent_agreement_parenting_plan",
        "parent",
        "parental_rights",
        "What if both parents agree?",
        (
            "What if we agree on a parenting plan?",
            "Can we write up our agreement for the court?",
        ),
        ("agree", "agreement", "parenting plan", "stipulation", "we both agree", "settlement"),
        "Even when parents agree, the proposed terms still need to be clear, source-backed, and acceptable under the court process. The workbench can help turn an agreement into a checklist of residence, contact, decision-making, support, safety, transportation, holidays, and forms to review, but it should not mark it filing-ready.",
        ("parental rights", "best interest", "court forms", "family matter", "1653"),
        (
            "Write the agreement in concrete terms: who, what days, exchanges, decisions, support, and holidays.",
            "Check whether child support forms/worksheets or other official forms are required.",
            "Have a qualified reviewer check the agreement before filing or relying on it.",
        ),
    ),
    _item(
        "parent_substance_or_mental_health_concern",
        "parent",
        "safety_pfa",
        "What if I am worried about substance use or mental health?",
        (
            "What if the other parent has substance use issues?",
            "How do I raise mental health concerns in a parenting case?",
        ),
        ("substance", "drinking", "drugs", "mental health", "treatment", "unsafe", "sobriety"),
        "Substance-use or mental-health concerns should be framed as source-backed facts about safety, parenting capacity, child impact, and requested protections—not as labels or diagnoses. Immediate danger requires emergency routing. Non-immediate concerns should be organized by dates, observations, records, and best-interest/safety factors for legal review.",
        ("best interest", "safety", "parental rights", "1653", "protection from abuse"),
        (
            "List specific events, dates, child impact, and available proof.",
            "Separate emergency danger from general concern or disagreement.",
            "Avoid unsupported diagnoses; ask what evidence and findings would support any requested restriction.",
        ),
        safety_note="Use emergency resources if anyone is in immediate danger.",
    ),
    _item(
        "parent_gal_involved_questions",
        "parent",
        "GAL_issue",
        "What if a Guardian ad Litem is involved?",
        (
            "What should I know if a GAL is involved?",
            "How should I prepare for a guardian ad litem in a parenting case?",
        ),
        ("gal", "guardian ad litem", "guardian", "investigation", "report"),
        "If a GAL is involved, keep your preparation factual, organized, and child-focused. The workbench can help organize documents, timelines, safety concerns, and best-interest factor notes, but it should not tell you how to influence a GAL or predict the GAL's recommendation.",
        ("best interest", "parental rights", "family matter", "1653", "court forms"),
        (
            "Prepare a concise timeline and key documents rather than a document dump.",
            "Tie concerns to best-interest factors, safety, stability, school, health, and relationships.",
            "Ask counsel or the court order what the GAL role, deadlines, and communication rules are.",
        ),
    ),
    _item(
        "parent_records_school_medical_sharing",
        "parent",
        "evidence_map",
        "How should I organize school and medical records?",
        (
            "How should I organize school and medical records for family court?",
            "What if a parent will not share school or medical information?",
        ),
        ("school records", "medical records", "information sharing", "doctor", "teacher", "records"),
        "School and medical records can matter when they connect to the child's adjustment, safety, health, schedule, or decision-making. Organize them by date and issue, keep private records secure, and distinguish record organization from legal questions about admissibility, privacy, subpoenas, or release.",
        ("best interest", "records", "parental rights", "1653", "family matter"),
        (
            "Create a log: date, source, issue, what it proves, and whether the record is private/confidential.",
            "Connect records to a specific disputed issue or best-interest factor.",
            "Ask for legal review before filing, disclosing, or quoting private records.",
        ),
        safety_note="Privacy/confidentiality review required before filing private records.",
    ),
    _item(
        "parent_pfa_served_response",
        "parent",
        "safety_pfa",
        "What if I was served with PFA papers?",
        (
            "I was served with protection from abuse papers. What should I do first?",
            "What should I look at if there is a PFA hearing?",
        ),
        ("served", "pfa", "protection from abuse", "hearing", "temporary order", "abuse papers"),
        "If you were served with PFA papers, read the order and hearing notice immediately and follow the order while seeking legal review. The workbench can help organize dates, alleged conduct, requested restrictions, related family orders, and source cards, but it cannot tell you how to defend the case.",
        ("protection from abuse", "safety", "family matter", "court forms"),
        (
            "Record the hearing date, court, order terms, and any no-contact or parenting restrictions.",
            "Gather relevant orders, messages, witness names, and timeline facts.",
            "Use qualified legal/safety resources before taking action that could violate the order.",
        ),
        safety_note="Follow any existing court order; use emergency resources for immediate danger.",
    ),
    _item(
        "lawyer_opposition_review_checklist",
        "lawyer",
        "draft_review",
        "How should I review an opposition or objection?",
        (
            "Give me a checklist for opposing a Maine family motion.",
            "How should I review an objection in a parental rights case?",
        ),
        ("opposition", "objection", "oppose", "opposing", "checklist for opposing", "Maine family motion", "response", "motion", "review"),
        "An opposition-review checklist should separate procedure, facts, authority, evidence, requested relief, and red flags. The workbench can identify possible issue labels and source cards, but counsel still needs to verify deadlines, service, record support, and whether contrary authority changes the argument.",
        ("family matter", "court forms", "rule", "parental rights", "best interest"),
        (
            "Check deadline, service, posture, requested relief, and any existing order.",
            "Map each factual response to evidence and each legal response to a source card.",
            "Run citation, quote, and unsupported-claim review before filing.",
        ),
    ),
    _item(
        "lawyer_settlement_source_audit",
        "lawyer",
        "authority_matrix",
        "How should I audit a settlement or agreed order?",
        (
            "How should I review a parenting settlement before filing?",
            "What should I check in an agreed family order?",
        ),
        ("settlement", "agreed order", "stipulated", "agreement", "consent", "before filing"),
        "An agreed order still needs source-card and gate review. Check that the terms are clear, within the court's authority, consistent with required forms/process, and supported by necessary findings where safety, child support, or contact restrictions are involved.",
        ("court forms", "parental rights", "best interest", "child support", "family matter"),
        (
            "Check required forms, child-support materials, and any findings needed for contact restrictions.",
            "Confirm the order says exactly who does what, when, where, and under what conditions.",
            "Keep the draft review_required until source, claim, quote, and human review gates pass.",
        ),
    ),
    _item(
        "lawyer_client_plain_language_letter",
        "lawyer",
        "plain_language",
        "How do I turn a legal answer into a client explainer?",
        (
            "Write a plain-language client explainer for a Maine parenting issue.",
            "How should I explain best-interest factors to a client?",
        ),
        ("client explainer", "plain language", "explain to client", "client letter", "best interest"),
        "A client explainer should summarize the court-process issue, identify the source-backed legal standard, list the facts still needed, and avoid promising outcomes. For parental-rights questions, connect the explanation to best-interest factors and evidence organization.",
        ("best interest", "1653", "parental rights", "family matter", "court forms"),
        (
            "State the issue in plain language and name the source cards used.",
            "List what facts/evidence are still missing.",
            "Mark the output as informational and review_required, not legal advice to the public.",
        ),
    ),
    _item(
        "lawyer_appeal_preservation_triage",
        "lawyer",
        "appeal_preservation",
        "What should I check for appeal preservation?",
        (
            "What should I check for appeal preservation in a family case?",
            "How do I triage a possible appeal from a family order?",
        ),
        ("appeal", "preservation", "transcript", "record", "findings", "remand"),
        "Appeal triage should start with the final order, deadlines, requested findings, transcript/record status, preserved objections, and whether the claimed error is factual, legal, discretionary, or findings-related. The workbench should flag missing findings and missing record materials rather than guessing appellate viability.",
        ("rule", "findings", "best interest", "family matter", "record"),
        (
            "Identify judgment date, notice/deadline issues, and post-judgment motions.",
            "Check whether Rule 52/findings issues or transcript/record gaps exist.",
            "Separate legal-error, clear-error, abuse-of-discretion, and preservation questions for review.",
        ),
    ),
    _item(
        "lawyer_form_packet_selection_audit",
        "lawyer",
        "forms_rules",
        "How do I audit form-packet selection?",
        (
            "How do I audit which family form packet applies?",
            "What should I check before giving a client Maine court forms?",
        ),
        ("form packet", "packet selection", "forms audit", "current forms", "FM", "client forms"),
        "Form-packet review should check case type, posture, county/court process, children/support issues, service, fee forms, and whether any saved PDF is stale. The workbench should surface official form source cards and avoid telling users that a packet is correct unless version/freshness is verified.",
        ("court forms", "family forms", "version", "family matter", "FM-050"),
        (
            "Start from the current official forms page, not a local copy.",
            "Record form ID/version, filing context, required attachments, and service instructions.",
            "Flag stale, missing, or mismatched forms before drafting.",
        ),
    ),
    _item(
        "advocate_self_represented_boundary",
        "lawyer",
        "professional_boundaries",
        "How can an advocate help a self-represented person safely?",
        (
            "How can an advocate help a self-represented parent without giving legal advice?",
            "What is safe legal-information help for a pro se family litigant?",
        ),
        ("advocate", "self represented", "self-represented", "pro se", "without giving legal advice", "helper"),
        "A non-lawyer advocate should stay in the legal-information lane: help the person find official sources, organize facts, prepare questions, and understand court-process language. Avoid selecting claims, predicting outcomes, drafting legal strategy, or telling the person what to file.",
        ("court forms", "family matter", "not legal advice", "Judicial Branch"),
        (
            "Use official forms and public court-process information as the anchor.",
            "Help organize facts and questions, not legal conclusions or strategy.",
            "Refer case-specific legal choices to a qualified attorney or court-approved resource.",
        ),
        safety_note="Non-lawyers should not provide legal advice.",
    ),
    _item(
        "caregiver_guardianship_vs_parental_rights",
        "caregiver",
        "caregiver_role",
        "Is this guardianship, parental rights, or something else?",
        (
            "Is this guardianship or a parental rights case?",
            "I am caring for a child. What legal path should I ask about?",
        ),
        ("guardianship", "parental rights", "caregiver", "relative", "legal path", "child living with me"),
        "A caregiver should not assume that caring for a child automatically creates parental rights. The first task is to identify the existing order, who has legal decision-making authority, whether probate/DHHS/family court is involved, and which official process might apply.",
        ("family matter", "court forms", "parental rights", "child"),
        (
            "Locate any existing family, probate, juvenile, or DHHS order.",
            "Write down who the child lives with, who makes decisions, and whether parents agree.",
            "Ask a lawyer or court resource which process applies before filing forms.",
        ),
    ),
    _item(
        "caregiver_parent_incarcerated_or_absent",
        "caregiver",
        "caregiver_role",
        "What if a parent is absent or unavailable?",
        (
            "I care for a child because a parent is absent. What should I organize?",
            "What if a parent is incarcerated or unavailable in a child care arrangement?",
        ),
        ("parent absent", "incarcerated", "unavailable", "caregiver", "temporary care", "relative"),
        "When a parent is absent, incarcerated, or unavailable, organize facts about the child's placement, decision-making needs, safety, school/medical issues, parent contact, and any existing orders. The workbench should help prepare questions and records, not decide which legal process applies.",
        ("family matter", "court forms", "parental rights", "child"),
        (
            "List the child's current living arrangement and urgent decision needs.",
            "Identify existing orders, parent consent, and whether any agency/court is involved.",
            "Ask qualified legal help what forms or procedures fit the facts.",
        ),
    ),
    _item(
        "counselor_client_asks_what_to_file",
        "counselor",
        "professional_boundaries",
        "What if a client asks me what to file?",
        (
            "A client asked me what to file in family court. What can I say?",
            "Can I tell a therapy client which family court motion to use?",
        ),
        ("what to file", "which motion", "client asked", "therapy client", "counselor", "legal advice"),
        "A counselor should not choose a client's legal filing or motion. A safe response is to distinguish legal information from legal advice, encourage official court resources and legal counsel, and help the client organize facts/questions without directing a filing strategy.",
        ("court forms", "family matter", "not legal advice", "parental rights"),
        (
            "Say that selecting a filing is a legal question for counsel/court-approved resources.",
            "Help the client list facts, documents, court dates, and questions to ask.",
            "Avoid drafting claims, choosing remedies, or predicting the court result.",
        ),
        safety_note="Professional-boundary/legal-advice caution.",
    ),
    _item(
        "counselor_mandated_reporting_boundary",
        "counselor",
        "safety_pfa",
        "What about mandated reporting and court cases?",
        (
            "How should a counselor think about mandated reporting in a family case?",
            "What if a client discloses child safety concerns during therapy?",
        ),
        ("mandated reporting", "report abuse", "child safety", "client discloses", "counselor", "therapist"),
        "The workbench should not give professional reporting advice. If safety or abuse concerns arise, follow emergency, mandated-reporting, agency, supervision, and legal protocols. For family-court orientation, keep factual observations, clinical role, court orders, and legal conclusions separate.",
        ("safety", "protection from abuse", "family matter", "child"),
        (
            "Use emergency/professional protocols for immediate risk or reportable concerns.",
            "Document factual observations according to approved professional policy.",
            "Refer legal-effect questions to counsel/supervision rather than deciding them in the workbench.",
        ),
        safety_note="Emergency/mandated-reporting protocols may apply.",
    ),
    _item(
        "counselor_testimony_request_boundary",
        "counselor",
        "professional_boundaries",
        "What if a parent wants me to testify?",
        (
            "A parent wants me to testify in family court. What should I consider?",
            "Can a counselor testify for a parent in a custody case?",
        ),
        ("testify", "testimony", "witness", "court", "parent wants me", "custody case"),
        "Before testimony or a witness request, a counselor should evaluate role, subpoena/order status, consent, privilege/confidentiality, clinical boundaries, scope of opinions, and agency/professional rules. The workbench can help list issues to ask counsel/supervision about, but cannot give legal or professional ethics advice.",
        ("court", "records", "family matter", "parental rights"),
        (
            "Clarify whether there is a subpoena, court order, consent, or informal request.",
            "Separate treatment facts from legal conclusions or custody recommendations.",
            "Consult supervision, counsel, or agency policy before responding.",
        ),
        safety_note="Confidentiality/privilege/professional-rule review required.",
    ),
    _item(
        "therapist_parent_pressure_boundary",
        "therapist",
        "professional_boundaries",
        "What if a parent pressures me for a legal opinion?",
        (
            "A parent wants me to say they should get custody. What should I do?",
            "What if a parent pressures a therapist for a court opinion?",
        ),
        ("custody opinion", "pressures", "parent wants me", "legal opinion", "recommend custody", "therapist"),
        "A therapist should avoid turning clinical treatment into a legal custody recommendation unless properly authorized, qualified, and ordered. The safe lane is to document treatment facts within role, preserve confidentiality, and refer legal-outcome questions to counsel or the court.",
        ("parental rights", "best interest", "family matter", "court"),
        (
            "Name the clinical role and what it does not authorize.",
            "Avoid predicting outcomes or recommending legal custody/residence unless the role specifically permits it.",
            "Ask counsel/supervision how to respond to pressure, records requests, or subpoenas.",
        ),
        safety_note="Professional-boundary caution.",
    ),
    _item(
        "therapist_collateral_contacts_records",
        "therapist",
        "professional_boundaries",
        "How should collateral contacts be handled?",
        (
            "How should a therapist handle collateral contacts in a family court dispute?",
            "Can I talk with teachers or relatives for a court-involved child?",
        ),
        ("collateral", "teacher", "relative", "records", "release", "court involved child", "therapist"),
        "Collateral contacts can raise consent, confidentiality, scope-of-treatment, recordkeeping, and court-order issues. The workbench can provide a boundary checklist, but the therapist should follow professional policy, releases, court orders, and legal/supervisory guidance.",
        ("records", "family matter", "parental rights", "court"),
        (
            "Confirm releases/consent, court-order language, and clinical purpose before contact.",
            "Keep treatment notes and legal opinions separate.",
            "Ask supervision/counsel before using collateral information in court-facing statements.",
        ),
        safety_note="Confidentiality and consent review required.",
    ),
    _item(
        "therapist_child_resists_contact",
        "therapist",
        "professional_boundaries",
        "What if a child resists contact with a parent?",
        (
            "A child resists contact with a parent. What should a therapist do?",
            "Can a therapist decide visits should stop if a child refuses?",
        ),
        ("child resists", "refuses visits", "stop visits", "child refuses", "contact", "therapist"),
        "A child's resistance to contact may be clinically important, but it should not automatically become a legal contact decision by the therapist. The workbench should help distinguish clinical observations, safety concerns, court-order duties, and legal contact restrictions that require court authority and source-backed findings.",
        ("contact", "parental rights", "best interest", "1653", "safety"),
        (
            "Assess immediate safety using professional/emergency protocols.",
            "Document observed facts without converting them into a legal order.",
            "Ask counsel/court for clarification if the order appears to delegate contact decisions.",
        ),
        safety_note="Immediate safety concerns require emergency/professional protocols.",
    ),
    _item(
        "public_download_share_test",
        "parent",
        "local_workbench_use",
        "How do I share a transcript for review?",
        (
            "How do I share this answer with a lawyer for review?",
            "Can I download the chat transcript and source cards?",
        ),
        ("download", "transcript", "share", "source cards", "lawyer review", "export"),
        "Use transcript export to share the question, answer, source cards, metadata, and review-required status with a lawyer or reviewer. Do not treat the transcript as legal advice or a filing; it is a planning record that helps a human reviewer see what sources the local workbench used.",
        ("source", "court forms", "family matter", "not legal advice"),
        (
            "Download both text and JSON transcript if available.",
            "Share the source cards and exact question/context with the reviewer.",
            "Ask the reviewer which claims, facts, forms, and deadlines still need verification.",
        ),
    ),

    _item(
        "parent_case_management_conference_prep",
        "parent",
        "court_process",
        "How do I prepare for a case management or first court event?",
        (
            "How do I prepare for a case management conference in family court?",
            "What should I bring to my first Maine family court event?",
        ),
        ("case management", "first court", "conference", "hearing", "prepare", "bring", "family court"),
        "For an early Maine family-court event, prepare by identifying the case type, current papers, service status, deadlines, existing orders, safety concerns, support issues, and what decisions the court may be asked to make. The workbench can help organize a checklist and official source cards, but it cannot predict what a judge will do.",
        ("family matter", "court forms", "service", "scheduling", "mediation"),
        (
            "Bring or organize the papers filed/served, existing orders, proof of service, and any hearing notice.",
            "Make a one-page list of requested next steps, disputed issues, safety concerns, and missing documents.",
            "Use court-clerk questions for logistics only; use counsel/reviewer questions for strategy and deadlines.",
        ),
    ),
    _item(
        "parent_mediation_prep",
        "parent",
        "court_process",
        "How should I prepare for mediation or settlement talks?",
        (
            "How should I prepare for mediation in a Maine parenting case?",
            "What should I organize before settlement talks?",
        ),
        ("mediation", "settlement talks", "negotiate", "agreement", "resolve", "parenting plan"),
        "For mediation or settlement talks, organize the issues before trying to resolve them: residence, contact schedule, exchanges, holidays, decision-making, support, safety limits, and how future disputes will be handled. Any agreement should still be checked against current official forms, child-support requirements, and best-interest/source review.",
        ("family matter", "mediation", "court forms", "best interest", "1653"),
        (
            "List what is agreed, what is disputed, and what information is missing.",
            "Translate each proposed term into clear order language for human review.",
            "Do not sign or file an agreement until a qualified reviewer checks source, support, and safety issues.",
        ),
    ),
    _item(
        "parent_missing_documents_before_asking",
        "parent",
        "missing_information",
        "What information should I gather before asking for help?",
        (
            "What information do I need before asking a family law question?",
            "What documents are missing before I ask a lawyer?",
        ),
        ("missing information", "documents missing", "before asking", "what do i need", "lawyer"),
        "A useful Maine family-law question usually needs the case type, court, posture, existing orders, upcoming dates, service status, children involved, safety issues, requested outcome, and documents that support the facts. The workbench should help make that missing-information list instead of guessing from an incomplete question.",
        ("family matter", "court forms", "parental rights", "child support", "protection from abuse"),
        (
            "Find the latest order, complaint/motion, summons/notice, and any hearing or mediation date.",
            "Write the requested outcome in one sentence and separate facts from opinions.",
            "Flag safety, service, deadline, jurisdiction, support, and form-version questions for review.",
        ),
    ),
    _item(
        "parent_order_language_confusing",
        "parent",
        "order_review",
        "What if I do not understand the order language?",
        (
            "I don't understand my parenting order. What should I check?",
            "What if the order language about visits is confusing?",
        ),
        ("don't understand", "confusing", "order language", "visits", "parenting order", "unclear"),
        "If order language is confusing, do not guess or self-help your way around it. Organize the exact order text, the disputed sentence, what each person thinks it means, and any immediate deadline or safety issue. The workbench can make a reviewer handoff checklist, but only the court or qualified legal review can resolve legal meaning.",
        ("family order", "changing or enforcing", "parental rights", "contact"),
        (
            "Quote the exact confusing language and identify the page/paragraph.",
            "List the practical problem: exchange time, location, decision-making, support, or restriction.",
            "Ask counsel/reviewer whether clarification, enforcement, modification, or another procedure is appropriate.",
        ),
    ),
    _item(
        "parent_cannot_follow_order_this_weekend",
        "parent",
        "post_judgment",
        "What if the current order cannot be followed this weekend?",
        (
            "What if I cannot follow the parenting order this weekend?",
            "What if the exchange cannot happen as ordered?",
        ),
        ("cannot follow", "can't follow", "this weekend", "exchange cannot", "as ordered", "parenting order"),
        "A short-term problem with an existing order should be documented carefully and handled through appropriate communication, safety resources, or court/legal review. The workbench should not advise unilateral denial of contact. It should help identify the order language, reason the exchange cannot happen, safety facts, attempted communication, and what review is needed.",
        ("family order", "changing or enforcing", "contact", "safety"),
        (
            "Save the exact order language and any messages about the exchange.",
            "Separate emergency/safety facts from logistics or inconvenience.",
            "Ask counsel/reviewer whether emergency relief, clarification, enforcement, or modification is needed.",
        ),
        safety_note="Immediate danger requires emergency resources first.",
    ),
    _item(
        "parent_child_support_arrears_or_missed_payment",
        "parent",
        "child_support",
        "What if support was missed or arrears are claimed?",
        (
            "What should I do if child support payments were missed?",
            "How should I organize child support arrears information?",
        ),
        ("arrears", "missed payment", "missed support", "past due", "support payment", "child support"),
        "For missed support or arrears questions, organize the current order, payment history, employer/DHHS information, dates, amounts claimed, and any enforcement papers. The workbench can help prepare a source-backed checklist, but it should not calculate arrears or tell a parent to ignore support obligations.",
        ("child support", "support enforcement", "FM-050", "family order"),
        (
            "Collect the current support order and a payment-by-payment history.",
            "Identify whether DHHS support enforcement is involved.",
            "Ask a qualified reviewer what process applies before filing or responding.",
        ),
    ),
    _item(
        "parent_address_school_change_notice",
        "parent",
        "parental_rights",
        "What if address, school, or medical information changed?",
        (
            "What if my address or the child's school changed?",
            "How should I handle school or medical information changes in a parenting case?",
        ),
        ("address changed", "school changed", "medical information", "doctor", "teacher", "records", "parenting case"),
        "School, medical, and address changes can affect contact, decision-making, service, notices, and best-interest facts. The workbench should help organize what changed, who was notified, what the order says, and what records support the change; it should not decide whether a change is legally permitted.",
        ("best interest", "school", "medical", "records", "1653", "family matter"),
        (
            "Check the existing order for notice, decision-making, school, medical, and contact terms.",
            "Save school/medical records and communications in date order.",
            "Ask counsel/reviewer whether notice, agreement, or court review is required.",
        ),
    ),
    _item(
        "lawyer_missing_info_intake_builder",
        "lawyer",
        "missing_information",
        "How do I build a missing-information list from a messy intake?",
        (
            "Build a missing information list for a new family case intake.",
            "What facts are missing from this Maine family law intake?",
        ),
        ("missing information", "missing facts", "intake", "messy intake", "new family case"),
        "A missing-information intake should identify unknowns that block reliable advice: case type, posture, orders, dates, service, jurisdiction/residence history, safety/PFA overlap, support/income, requested relief, child-specific facts, and source/form status. The output should be an interview checklist, not a conclusion.",
        ("family matter", "court forms", "best interest", "child support", "protection from abuse"),
        (
            "Create columns for known fact, missing fact, source/document needed, urgency, and reviewer owner.",
            "Flag safety, deadlines, service, jurisdiction, and stale forms as priority unknowns.",
            "Keep generated rows review_required until the file and sources are checked.",
        ),
    ),
    _item(
        "lawyer_reviewer_handoff_from_chat",
        "lawyer",
        "local_workbench_use",
        "How should I hand off a chat answer for legal review?",
        (
            "How should I review a transcript from the local workbench?",
            "What should a lawyer check in a chat handoff?",
        ),
        ("transcript", "handoff", "review", "source cards", "lawyer check", "chat answer"),
        "A chat handoff should include the user question, any context supplied, matched library item, answer style, source cards, source freshness notes, unresolved questions, and review-required status. The reviewer should treat it as an orientation record, not legal advice or a draft ready to file.",
        ("source", "official", "family matter", "not legal advice"),
        (
            "Check whether the cited source cards actually support each legal/procedure statement.",
            "List missing facts, documents, deadlines, and adverse facts before advising.",
            "Run citation, quote, claim-support, and filing-ready gates before using text in a filing.",
        ),
    ),
    _item(
        "lawyer_proposed_findings_source_map",
        "lawyer",
        "findings_review",
        "How do I source-map proposed findings?",
        (
            "How should I map proposed findings to sources and evidence?",
            "Give me a source map checklist for proposed family findings.",
        ),
        ("proposed findings", "source map", "findings", "evidence", "best interest", "order"),
        "A proposed-findings source map should connect each requested ruling to a factual finding, record evidence, and legal authority. In parenting matters, the map should show which best-interest factors are addressed, which factors are not relevant or disputed, and what evidence supports any contact restriction or safety finding.",
        ("rule", "family division", "best interest", "1653", "findings"),
        (
            "Create a table: requested ruling, finding, evidence span, authority/source card, and risk flag.",
            "Check all contact restrictions and safety findings for specific support.",
            "Mark gaps for human review before drafting proposed order language.",
        ),
    ),
    _item(
        "lawyer_deadline_service_audit",
        "lawyer",
        "court_process",
        "How do I audit deadline and service issues?",
        (
            "Give me a deadline and service audit checklist for a Maine family case.",
            "What service issues should I check before responding?",
        ),
        ("deadline", "service audit", "served", "responding", "summons", "notice", "filing"),
        "A deadline/service audit should start with the papers served, date/method of service, hearing notices, court, docket, requested relief, and applicable family-process/rule sources. The workbench can organize the audit, but it should not calculate or guarantee deadlines without official rules and human review.",
        ("service", "commencement", "family matter", "court forms", "rule 101"),
        (
            "Record date, method, server, documents served, and any hearing date.",
            "Compare the papers against current official forms and rules.",
            "Escalate any deadline, defective service, or emergency/safety issue to qualified review.",
        ),
    ),
    _item(
        "lawyer_client_document_request_pack",
        "lawyer",
        "intake_triage",
        "What documents should I request from a client?",
        (
            "What documents should I ask a family-law client to send first?",
            "Build a client document request checklist for parenting and support issues.",
        ),
        ("documents", "client send", "request checklist", "parenting", "support", "intake"),
        "A first document request should gather existing orders, pleadings, service papers, hearing notices, parenting schedules, support records, income information, school/medical records, safety/PFA records, and communications that support or contradict the requested outcome. Private records should stay in approved matter storage, not the repo.",
        ("court forms", "family matter", "best interest", "child support", "protection from abuse"),
        (
            "Separate court documents, financial/support records, child records, safety records, and communications.",
            "Ask for dates and source documents, not only narrative summaries.",
            "Do not add private client files to shared training, fixtures, or release ZIPs.",
        ),
    ),
    _item(
        "caregiver_parent_returns_or_objects",
        "caregiver",
        "caregiver_role",
        "What if a parent returns or objects to the caregiver's role?",
        (
            "What if a parent objects to me caring for the child?",
            "A parent came back and wants the child. What should a caregiver organize?",
        ),
        ("parent objects", "parent came back", "wants the child", "caregiver", "relative", "objects"),
        "When a parent objects to a caregiver's role, the workbench should not assume the caregiver has legal authority. It should help organize existing orders, who has parental rights or guardianship, the child's current care arrangement, safety concerns, school/medical records, and urgent questions for legal review.",
        ("parental rights", "family matter", "court forms", "child", "safety"),
        (
            "Find any existing order, guardianship paper, DHHS communication, or school/medical authorization.",
            "Build a timeline of where the child has lived and who has provided care.",
            "Use emergency resources if there is immediate danger; otherwise seek qualified legal review.",
        ),
        safety_note="Immediate safety concerns require emergency resources first.",
    ),
    _item(
        "caregiver_school_enrollment_authority",
        "caregiver",
        "caregiver_role",
        "Can a caregiver enroll a child in school or handle records?",
        (
            "Can I enroll a child in school as a caregiver?",
            "Can a caregiver talk to the school or doctor?",
        ),
        ("enroll", "school", "doctor", "medical", "records", "caregiver", "authority"),
        "A caregiver's ability to handle school or medical matters depends on existing parental-rights, guardianship, agency, consent, or court-order authority. The workbench can organize the documents and questions, but it should not decide authority from a chat prompt.",
        ("parental rights", "family matter", "court forms", "school", "medical"),
        (
            "Collect any order, guardianship document, written consent, or agency paperwork.",
            "List what the school/doctor is asking for and any deadline.",
            "Ask a qualified reviewer what authority or process applies before acting.",
        ),
    ),
    _item(
        "caregiver_private_records_boundary",
        "caregiver",
        "local_workbench_use",
        "Can a caregiver upload private child records?",
        (
            "Can I upload a child's school or medical records to this tool?",
            "Can I paste private child records into the workbench?",
        ),
        ("upload", "paste", "private child records", "school records", "medical records", "caregiver"),
        "Do not upload or paste private child records into an unapproved tool, public repo, or shared model. The local workbench can use de-identified descriptions for general organization, while real records should stay in approved private matter storage with role, consent, and disclosure review.",
        ("private", "records", "family matter", "not legal advice"),
        (
            "Use a de-identified summary for general planning if needed.",
            "Store actual records only in approved private systems.",
            "Ask counsel/reviewer before sharing child records with court, school, medical providers, or others.",
        ),
        safety_note="Privacy/confidentiality caution.",
    ),
    _item(
        "caregiver_lawyer_questions_pack",
        "caregiver",
        "questions_to_ask",
        "What should a caregiver ask a lawyer?",
        (
            "What should a caregiver ask a lawyer before filing anything?",
            "What questions should a relative caregiver ask for legal review?",
        ),
        ("ask a lawyer", "caregiver", "relative", "before filing", "questions", "legal review"),
        "A caregiver should ask about legal authority, existing orders, whether a family, probate, DHHS, or protection process is involved, what documents are needed, and what immediate safety or disclosure limits apply. The workbench should create questions, not decide the caregiver's rights.",
        ("family matter", "court forms", "parental rights", "protection from abuse"),
        (
            "What order, guardianship, consent, or agency paperwork currently gives authority, if any?",
            "Which court/process applies and what deadlines or service rules matter?",
            "What records can be used or disclosed without violating privacy/confidentiality?",
        ),
    ),
    _item(
        "counselor_parent_wants_strategy",
        "counselor",
        "professional_boundaries",
        "What if a client asks for legal strategy?",
        (
            "A client wants legal strategy for family court. What can a counselor do?",
            "What if a parent asks me how to win custody?",
        ),
        ("legal strategy", "win custody", "what should i file", "counselor", "parent asks"),
        "A counselor can support organization, coping, safety routing, and questions for counsel, but should not give legal strategy or predict outcomes. The workbench can convert the concern into a source-backed questions list and a documents-to-gather checklist.",
        ("not legal advice", "family matter", "court forms", "best interest"),
        (
            "Reflect the legal question back as something to ask counsel or official court resources.",
            "Help the client gather dates, documents, orders, and questions.",
            "Do not recommend what to file, what relief to seek, or how the court will rule.",
        ),
    ),
    _item(
        "counselor_records_release_to_lawyer",
        "counselor",
        "professional_boundaries",
        "What if a client asks me to send records to a lawyer?",
        (
            "A client asked me to send records to a lawyer. What should I consider?",
            "Can a counselor send therapy records to a family lawyer?",
        ),
        ("send records", "lawyer", "release", "therapy records", "counselor", "client asked"),
        "Requests to send counseling records require consent, scope, confidentiality, privilege, agency policy, and possible court-order review. The workbench can help list what was requested and which questions to ask supervision/counsel, but it should not decide disclosure.",
        ("records", "court", "family matter", "not legal advice"),
        (
            "Confirm written authorization, requested record range, recipient, purpose, and deadline.",
            "Use agency/supervisory/legal review before disclosure.",
            "Do not upload records into the repo or shared model during review.",
        ),
        safety_note="Confidentiality/records review required.",
    ),
    _item(
        "counselor_treatment_summary_request",
        "counselor",
        "professional_boundaries",
        "What if someone asks for a treatment summary for court?",
        (
            "Can I write a treatment summary for family court?",
            "What should a counselor consider before writing a court summary?",
        ),
        ("treatment summary", "court summary", "write a summary", "family court", "counselor"),
        "A court-facing treatment summary should be handled through professional, agency, consent, and legal review. The workbench can help identify requested scope, source of authority, deadlines, and boundary language, but it should not draft clinical/legal opinions that exceed the provider's role.",
        ("court", "family matter", "records", "not legal advice"),
        (
            "Clarify who requested it, under what authority, and what exact questions it should answer.",
            "Separate observed treatment facts from custody/contact opinions.",
            "Get supervision/counsel review before releasing or filing anything.",
        ),
        safety_note="Professional and confidentiality review required.",
    ),
    _item(
        "therapist_unclear_court_order",
        "therapist",
        "professional_boundaries",
        "What if a court order gives an unclear therapy role?",
        (
            "What if a court order about therapy is unclear?",
            "A court order says I decide contact but I am the therapist. What should I do?",
        ),
        ("unclear court order", "decide contact", "court order", "therapy role", "therapist"),
        "If a court order appears to give a therapist an unclear or legal decision-making role, the workbench should flag the issue for counsel/court clarification. Clinical observations are different from court authority to allocate contact or parental rights, and any ambiguity should be resolved before the therapist acts outside role.",
        ("contact", "parental rights", "best interest", "court", "1653"),
        (
            "Quote the exact order language and identify what is unclear.",
            "Separate clinical tasks from legal decisions about residence/contact.",
            "Seek supervision, counsel, or court clarification before acting beyond the treatment role.",
        ),
        safety_note="Immediate safety concerns still require emergency/professional protocols.",
    ),
    _item(
        "therapist_parent_requests_opinion_letter",
        "therapist",
        "professional_boundaries",
        "What if a parent asks for an opinion letter?",
        (
            "A parent asked me for a custody opinion letter. What should I do?",
            "Can a therapist write a letter saying a parent should get custody?",
        ),
        ("opinion letter", "custody opinion", "write a letter", "parent asked", "therapist"),
        "A therapist should distinguish treatment facts from custody/contact opinions. Unless the therapist has a proper authorized evaluation role, the workbench should flag custody-opinion letters for professional/legal review rather than generate them as advocacy.",
        ("parental rights", "best interest", "court", "records", "1653"),
        (
            "Clarify role, consent, court-order authority, and requested audience.",
            "Avoid legal conclusions about custody/contact unless clearly authorized and reviewed.",
            "Use supervision/counsel before releasing any court-facing letter.",
        ),
        safety_note="Professional-boundary review required.",
    ),
    _item(
        "therapist_records_subpoena_handoff",
        "therapist",
        "professional_boundaries",
        "What should a therapist collect for subpoena review?",
        (
            "What should I collect if therapy records are subpoenaed?",
            "How should a therapist prepare a subpoena handoff?",
        ),
        ("subpoena", "therapy records", "records subpoenaed", "handoff", "therapist"),
        "For subpoena review, collect the subpoena/order, service details, deadline, case caption, requested records, client identity, applicable releases, and any agency/legal contacts. The workbench should create a handoff list, not decide privilege, confidentiality, or production.",
        ("records", "court", "family matter", "not legal advice"),
        (
            "Record who served it, when, how, and what exact records/testimony are requested.",
            "Notify supervision/agency counsel or qualified legal counsel promptly.",
            "Do not upload confidential records into the workbench or repo.",
        ),
        safety_note="Confidentiality/records review required.",
    ),
    _item(
        "public_reviewer_handoff_export",
        "parent",
        "local_workbench_use",
        "How do I export a reviewer handoff?",
        (
            "How do I export a reviewer handoff from this chat?",
            "Can I give my lawyer the JSON export and source cards?",
        ),
        ("reviewer handoff", "json export", "lawyer", "source cards", "download", "transcript"),
        "A reviewer handoff should preserve the exact question, answer style, context used, source cards, matched library metadata, and review-required status. The export helps a lawyer or reviewer audit what the workbench used; it is not legal advice and is not a filing-ready document.",
        ("source", "family matter", "court forms", "not legal advice"),
        (
            "Download the JSON transcript and include the source-card list.",
            "Tell the reviewer which facts/documents were not included in the chat.",
            "Ask which claims, deadlines, forms, and evidence still need verification.",
        ),
    ),


    _item(
        "parent_lawyer_call_prep",
        "parent",
        "questions_to_ask",
        "How do I prepare for a short lawyer call?",
        (
            "How do I prepare for a short lawyer call about family court?",
            "What should I have ready before a consultation?",
        ),
        ("lawyer call", "consultation", "short call", "prepare", "questions", "family court"),
        "For a short lawyer call, organize the case type, court papers, existing orders, upcoming dates, safety issues, support questions, and the one or two outcomes you need reviewed first. The workbench can make a questions list, but the lawyer needs the actual documents to advise.",
        ("family matter", "court forms", "parental rights", "child support", "protection from abuse"),
        (
            "Send or bring the latest order, papers served, hearing notices, and any urgent messages.",
            "Ask what deadline or safety issue must be handled first.",
            "Ask what not to file, sign, or say until counsel reviews the record.",
        ),
    ),
    _item(
        "lawyer_source_gap_table",
        "lawyer",
        "authority_matrix",
        "How do I turn an answer into a source-gap table?",
        (
            "Build a source gap table from a chat answer.",
            "How should I list unsupported claims from the workbench?",
        ),
        ("source gap", "unsupported claims", "source table", "chat answer", "authority matrix"),
        "A source-gap table should list each legal/procedure claim, cited source card, quote/span if available, freshness status, and whether the source actually supports the claim. Any unsupported, stale, jurisdiction-mismatched, or missing-source claim stays review_required.",
        ("source", "official", "citation", "family matter", "best interest"),
        (
            "Make columns for claim, source card, quote/span, support status, and reviewer note.",
            "Treat official Maine sources as higher authority than summaries or placeholder fixtures.",
            "Block final use until citation, quote, and claim-support checks pass.",
        ),
    ),
    _item(
        "therapist_reunification_session_planning_boundary",
        "therapist",
        "professional_boundaries",
        "How should reunification-session planning stay within role?",
        (
            "How should a therapist plan reunification sessions without deciding custody?",
            "What boundaries apply to reunification therapy in a family case?",
        ),
        ("reunification", "session planning", "custody", "contact", "therapist", "family case"),
        "Reunification-session planning should stay within the authorized clinical role and should not become a therapist-made custody/contact order. The workbench should help identify the court-order language, treatment goals, safety concerns, reporting boundaries, and questions for supervision/counsel.",
        ("contact", "parental rights", "best interest", "court", "1653"),
        (
            "Quote the order or referral language that defines the therapist's role.",
            "Separate treatment observations from legal recommendations about contact or residence.",
            "Use supervision/counsel or court clarification when the role is unclear.",
        ),
        safety_note="Immediate safety concerns require emergency/professional protocols.",
    ),



)


def get_chat_library() -> tuple[ChatLibraryItem, ...]:
    return CHAT_LIBRARY


def public_library() -> list[dict[str, Any]]:
    return [item.public_dict() for item in CHAT_LIBRARY]


def public_topics() -> list[dict[str, Any]]:
    topics: dict[str, set[str]] = {}
    for item in CHAT_LIBRARY:
        topics.setdefault(item.topic, set()).add(item.audience)
    return [
        {
            "topic": topic,
            "audiences": sorted(audiences),
            "count": sum(1 for item in CHAT_LIBRARY if item.topic == topic),
        }
        for topic, audiences in sorted(topics.items())
    ]


def missing_information_for_item(item: ChatLibraryItem) -> list[str]:
    base = [
        "case type and procedural posture",
        "existing orders, papers served, and upcoming court dates",
        "requested outcome stated in one sentence",
        "facts separated from conclusions",
        "documents or witnesses that support each important fact",
        "safety, service, deadline, jurisdiction, and form-version flags",
    ]
    if item.topic == "child_support":
        base.extend(["current order and payment history", "income, childcare, health-insurance, and DHHS/support-enforcement records"])
    if item.topic in {"professional_boundaries", "local_workbench_use"}:
        base.extend(["role/authority for the person using the tool", "privacy, consent, release, subpoena, or court-order limits"])
    if item.topic in {"parental_rights", "findings_review", "order_review"}:
        base.extend(["specific order language or proposed finding", "best-interest factors and contact/safety facts at issue"])
    if item.topic == "safety_pfa":
        base.extend(["immediate danger status", "safety-resource or protection-from-abuse papers, if any"])
    return list(dict.fromkeys(base))


def follow_up_questions_for_item(item: ChatLibraryItem) -> list[str]:
    questions = [f"Which official source card supports the main point in {item.title}?", "What facts or documents are still missing before a qualified reviewer can rely on this?", "What deadline, service, safety, or jurisdiction issue could change the next step?"]
    if item.audience == "parent":
        questions.append("What should I ask a lawyer, and what can I ask a court clerk only about logistics?")
    elif item.audience == "lawyer":
        questions.append("What adverse facts, contrary authority, or unsupported claims should be added to the reviewer checklist?")
    elif item.audience == "caregiver":
        questions.append("What document, order, consent, or agency record shows the caregiver's current authority?")
    elif item.audience in {"counselor", "therapist"}:
        questions.append("What role, consent, confidentiality, subpoena, release, or court-order boundary must be reviewed first?")
    return questions


def public_missing_information_prompts() -> list[dict[str, Any]]:
    return [
        {
            "item_id": item.id,
            "audience": item.audience,
            "topic": item.topic,
            "title": item.title,
            "missing_information": missing_information_for_item(item),
            "follow_up_questions": follow_up_questions_for_item(item),
        }
        for item in CHAT_LIBRARY
    ]


PROMPT_PACK_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "parent_first_30_minutes",
        "audience": "parent",
        "title": "Parent: first 30 minutes of case triage",
        "description": "Good first questions for a parent trying to understand papers, deadlines, safety, support, and evidence without getting legal advice from the tool.",
        "item_ids": (
            "parent_served_papers",
            "parent_missing_documents_before_asking",
            "parent_case_management_conference_prep",
            "parent_ask_lawyer_before_filing",
            "parent_court_clerk_questions",
            "parent_evidence_organize",
            "parent_child_support",
            "safety_pfa_parent",
        ),
    },
    {
        "id": "parent_parenting_order_review",
        "audience": "parent",
        "title": "Parent: parenting order and contact review",
        "description": "Questions for residence, contact, decision-making, exchanges, supervised contact, and child preference issues.",
        "item_ids": (
            "parent_best_interest_apply",
            "parent_contact_schedule",
            "parent_decision_making_school_medical",
            "parent_missed_exchange_log",
            "parent_supervised_contact_question",
            "parent_child_preference",
        ),
    },
    {
        "id": "lawyer_advocate_intake_review",
        "audience": "lawyer",
        "title": "Lawyer/advocate: intake and draft review",
        "description": "Source-backed intake, authority, form, findings, and review questions for lawyers and advocates.",
        "item_ids": (
            "lawyer_intake_triage_parental_rights",
            "lawyer_missing_info_intake_builder",
            "lawyer_reviewer_handoff_from_chat",
            "lawyer_source_stack",
            "lawyer_rule_52_findings",
            "lawyer_opposition_review_checklist",
            "lawyer_form_packet_selection_audit",
            "advocate_self_represented_boundary",
        ),
    },
    {
        "id": "caregiver_relative_triage",
        "audience": "caregiver",
        "title": "Caregiver/relative: what to ask before filing",
        "description": "Questions for relatives or caregivers who need to understand existing orders, child safety, and which process may apply.",
        "item_ids": (
            "caregiver_existing_order",
            "caregiver_lawyer_questions_pack",
            "caregiver_school_enrollment_authority",
            "caregiver_existing_order",
            "caregiver_guardianship_vs_parental_rights",
            "caregiver_parent_incarcerated_or_absent",
            "caregiver_safety_routing",
            "caregiver_grandparent_contact_question",
        ),
    },
    {
        "id": "counselor_boundary_pack",
        "audience": "counselor",
        "title": "Counselor: court-boundary questions",
        "description": "Questions for counselors asked to explain family court, write letters, respond to subpoenas, testify, or handle safety disclosures.",
        "item_ids": (
            "counselor_client_explainer",
            "counselor_parent_wants_strategy",
            "counselor_client_asks_what_to_file",
            "counselor_court_letter",
            "counselor_subpoena_or_order",
            "counselor_testimony_request_boundary",
            "counselor_mandated_reporting_boundary",
        ),
    },
    {
        "id": "therapist_contact_records_pack",
        "audience": "therapist",
        "title": "Therapist: contact, records, and court-role boundaries",
        "description": "Questions for therapists dealing with court-involved treatment, records, contact resistance, reunification, and pressure for legal opinions.",
        "item_ids": (
            "therapist_records_caution",
            "therapist_unclear_court_order",
            "therapist_no_private_uploads",
            "therapist_reunification_boundaries",
            "therapist_child_resists_contact",
            "therapist_parent_pressure_boundary",
            "therapist_collateral_contacts_records",
        ),
    },
    {
        "id": "reviewer_handoff_missing_info",
        "audience": "lawyer",
        "title": "Reviewer: handoff and missing-information audit",
        "description": "Questions that turn chat output into a reviewer checklist with missing facts, source gaps, and export metadata.",
        "item_ids": (
            "public_reviewer_handoff_export",
            "lawyer_reviewer_handoff_from_chat",
            "lawyer_missing_info_intake_builder",
            "lawyer_deadline_service_audit",
            "lawyer_proposed_findings_source_map",
            "lawyer_client_document_request_pack",
        ),
    },
)


def public_prompt_packs() -> list[dict[str, Any]]:
    by_id = {item.id: item for item in CHAT_LIBRARY}
    packs: list[dict[str, Any]] = []
    for pack in PROMPT_PACK_DEFINITIONS:
        prompts = []
        for item_id in pack["item_ids"]:
            item = by_id.get(str(item_id))
            if item is None:
                continue
            prompts.append(
                {
                    "item_id": item.id,
                    "audience": item.audience,
                    "topic": item.topic,
                    "title": item.title,
                    "prompt": item.prompts[0] if item.prompts else item.title,
                    "recommended_style": _recommended_style_for_item(item),
                }
            )
        packs.append(
            {
                "id": pack["id"],
                "audience": pack["audience"],
                "title": pack["title"],
                "description": pack["description"],
                "prompt_count": len(prompts),
                "prompts": prompts,
            }
        )
    return packs


def _recommended_style_for_item(item: ChatLibraryItem) -> str:
    if item.topic in {"professional_boundaries", "safety_pfa"} and item.audience in {"counselor", "therapist"}:
        return "professional_boundary"
    if item.topic in {"missing_information", "order_review"}:
        return "missing_information"
    if item.topic in {"intake_triage", "questions_to_ask"}:
        return "questions_to_ask"
    if item.topic in {"authority_matrix", "forms_rules", "findings_review", "draft_review"}:
        return "source_card_table"
    return "checklist"


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
    if any(term in text for term in ("support", "affidavit", "income", "pay", "lost job", "new job")):
        hints.append("child support FM-050 support enforcement guidelines court forms")
    if any(term in text for term in ("pfa", "abuse", "danger", "unsafe", "violence")):
        hints.append("protection from abuse immediate danger safety 1653")
    if any(term in text for term in ("rule 52", "findings", "proposed order")):
        hints.append("family division rule best interest findings 1653")
    if any(term in text for term in ("form", "forms", "packet", "stale")):
        hints.append("court forms family forms version FM-050")
    if any(term in text for term in ("served", "papers", "summons", "deadline", "respond")):
        hints.append("family matter court forms commencement divorce service")
    if any(term in text for term in ("mediation", "conference", "hearing", "prepare", "bring", "temporary order", "interim")):
        hints.append("family matter mediation court review best interest 1653 court forms")
    if any(term in text for term in ("evidence", "proof", "records", "messages", "timeline", "texts", "email", "app")):
        hints.append("best interest 1653 family matter court forms records")
    if any(term in text for term in ("schedule", "visitation", "holiday", "transportation", "supervised", "restricted contact", "exchange", "denied contact")):
        hints.append("parent-child contact parental rights best interest 1653 changing or enforcing order motion process")
    if any(term in text for term in ("mother", "father", "gender", "preference", "choose")):
        hints.append("gender preference meaningful preference best interest 1653")
    if any(term in text for term in ("jurisdiction", "out of state", "another state", "uccjea", "move", "relocate", "moving away")):
        hints.append("Maine jurisdiction parental rights family matter court review best interest 1653")
    if any(term in text for term in ("letter", "court letter", "confidential", "subpoena", "clinical notes", "therapy records", "session notes", "court order", "testify")):
        hints.append("family matter court records parental rights not legal advice court forms")
    if any(term in text for term in ("reunification", "court ordered", "clinical role")):
        hints.append("therapist contact parental rights best interest 1653")
    if any(term in text for term in ("divorce", "separation", "marriage")):
        hints.append("divorce family separation family matter court forms Judicial Branch")
    if any(term in text for term in ("unmarried", "never married", "parentage")):
        hints.append("parental rights family matter court forms child support")
    if any(term in text for term in ("intake", "new client", "triage", "client letter", "plain language")):
        hints.append("family matter court forms parental rights best interest Judicial Branch")
    if any(term in text for term in ("source card", "citation appendix", "audit", "weaken", "contrary", "adverse")):
        hints.append("official source citation best interest 1653 family matter")
    if any(term in text for term in ("advocate", "self represented", "self-represented", "pro se", "helper")):
        hints.append("court forms family matter not legal advice Judicial Branch")
    if any(term in text for term in ("court clerk", "clerk", "fee waiver", "filing fee", "cannot afford", "serve", "service", "proof of service")):
        hints.append("court forms family matter service commencement Judicial Branch")
    if any(term in text for term in ("agree", "agreement", "settlement", "stipulation", "agreed order", "parenting plan")):
        hints.append("parental rights best interest court forms family matter child support 1653")
    if any(term in text for term in ("substance", "drinking", "drugs", "mental health", "sobriety", "treatment")):
        hints.append("best interest safety parental rights protection from abuse 1653")
    if any(term in text for term in ("gal", "guardian ad litem", "guardian", "investigation", "report")):
        hints.append("best interest parental rights family matter 1653 court forms")
    if any(term in text for term in ("school records", "medical records", "information sharing", "doctor", "teacher")):
        hints.append("best interest records parental rights family matter 1653")
    if any(term in text for term in ("opposition", "objection", "oppose", "appeal", "appeals", "appeals court", "law court", "supreme judicial court", "preservation", "transcript", "record")):
        hints.append("Maine appeals Supreme Judicial Court Law Court appellate procedure record notice of appeal family matter")
    if any(term in text for term in ("mandated reporting", "testify", "testimony", "witness", "what to file", "which motion", "legal opinion", "custody opinion", "collateral")):
        hints.append("family matter court records parental rights not legal advice court forms")
    if any(term in text for term in ("download", "transcript", "share", "export", "reviewer handoff", "json export")):
        hints.append("source court forms family matter not legal advice official")
    if any(term in text for term in ("missing information", "missing documents", "missing facts", "what information", "before asking", "case management", "first court", "mediation")):
        hints.append("family matter court forms service scheduling mediation best interest 1653")
    if any(term in text for term in ("confusing", "unclear", "cannot follow", "can't follow", "order language", "this weekend", "exchange cannot")):
        hints.append("family order changing or enforcing parental rights contact safety")
    if any(term in text for term in ("arrears", "missed payment", "missed support", "past due")):
        hints.append("child support support enforcement FM-050 family order")
    if any(term in text for term in ("source map", "proposed findings", "document request", "service audit", "deadline audit")):
        hints.append("family division rule best interest findings court forms service 1653")
    if any(term in text for term in ("parent objects", "parent came back", "enroll", "school", "doctor", "caregiver authority")):
        hints.append("family matter parental rights child court forms records")
    if any(term in text for term in ("legal strategy", "win custody", "send records", "treatment summary", "opinion letter", "unclear court order")):
        hints.append("family matter court records parental rights not legal advice best interest")
    if any(term in text for term in ("lawyer call", "consultation", "source gap", "unsupported claims", "reunification sessions", "session planning")):
        hints.append("family matter court forms source official parental rights best interest contact 1653")
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
    elif answer_style == "intake":
        lines.append(f"Intake triage: {heading}")
        lines.append("")
        lines.append(item.answer)
        lines.append("")
        lines.append("Intake questions to ask next:")
        for step in item.next_steps:
            lines.append(f"- {step}")
        lines.append("- What documents, deadlines, hearings, and safety issues are missing from the file?")
        lines.append("- Which legal/procedure claims still need source-card verification?")
    elif answer_style == "professional_boundary":
        lines.append(f"Professional-boundary note: {heading}")
        lines.append("")
        lines.append(item.answer)
        lines.append("")
        lines.append("Boundary guardrails:")
        for step in item.next_steps:
            lines.append(f"- {step}")
        lines.append("- Keep role, consent, confidentiality, and court authority separate.")
        lines.append("- Do not upload private clinical or matter records unless an approved local workflow is configured.")
    elif answer_style == "questions_to_ask":
        lines.append(f"Questions to ask next: {heading}")
        lines.append("")
        lines.append(item.answer)
        lines.append("")
        lines.append("Ask a lawyer / qualified reviewer:")
        for step in item.next_steps:
            lines.append(f"- {step}")
        lines.append("- What deadlines, service issues, safety issues, or source gaps should be handled first?")
        lines.append("- What should not be filed or relied on until reviewed?")
        lines.append("")
        lines.append("Ask a court clerk only about logistics:")
        lines.append("- Where are the current official forms and instructions?")
        lines.append("- What copies, fees, filing method, service instructions, or hearing logistics apply?")
        lines.append("- Clerks cannot choose claims, predict outcomes, or give legal strategy.")
    elif answer_style == "missing_information":
        lines.append(f"Missing-information checklist: {heading}")
        lines.append("")
        lines.append(item.answer)
        lines.append("")
        lines.append("Information still needed before anyone should rely on this:")
        for value in missing_information_for_item(item):
            lines.append(f"[ ] {value}")
        lines.append("")
        lines.append("Role-specific follow-up questions:")
        for question_text in follow_up_questions_for_item(item):
            lines.append(f"- {question_text}")
        lines.append("")
        lines.append("Source-card handoff:")
        for result in citations:
            lines.append(f"- {result.title} — {result.citation or result.metadata.get('citation_hint', 'source card')}")
    elif answer_style == "source_card_table":
        lines.append(f"Source-card review: {heading}")
        lines.append("")
        lines.append(item.answer)
        lines.append("")
        lines.append("Source-card audit table:")
        lines.append("| Source | Type | Citation hint | Why it matters |")
        lines.append("| --- | --- | --- | --- |")
        for result in citations:
            meta = result.metadata
            lines.append(
                "| "
                + result.title.replace("|", "/")
                + " | "
                + str(meta.get("source_type", "source")).replace("|", "/")
                + " | "
                + str(meta.get("citation_hint", result.citation)).replace("|", "/")
                + " | "
                + result.snippet.replace("|", "/")[:140]
                + " |"
            )
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
    if any(result.metadata.get("effective_date") or result.metadata.get("version_label") for result in citations):
        lines.append("")
        lines.append("Source freshness note: Check the effective date and version label on each source card before relying on this information.")
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
