from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

VERSION = "2.05.0"
PACKET_SCHEMA = "maine_family_law_llm.family_justice_workbench.packet.v1"
AUDIT_SCHEMA = "maine_family_law_llm.family_justice_workbench.audit.v1"
TEST_SUMMARY_SCHEMA = "maine_family_law_llm.family_justice_workbench.test_summary.v1"
DETERMINISTIC_GENERATED_AT = "2026-06-05T00:00:00Z"

DISCLAIMER = (
    "Maine Family Law LLM provides legal information and review workflow support, "
    "not legal advice. It does not create an attorney-client relationship. Outputs "
    "remain review_required and not filing_ready unless official-source, citation, "
    "quote-span, fact-support, form-freshness, posture, jurisdiction, and human-review "
    "gates all pass."
)

AUDIENCES: dict[str, dict[str, str]] = {
    "parent": {
        "label": "Parent",
        "pathway": "plain-language intake, safety routing, source cards, next steps",
    },
    "caregiver": {
        "label": "Caregiver",
        "pathway": "caregiver authority questions, records boundaries, lawyer handoff",
    },
    "lawyer": {
        "label": "Lawyer",
        "pathway": "authority matrix, claim checklist, blocker review, export packet",
    },
    "counselor": {
        "label": "Counselor",
        "pathway": "professional boundary, subpoena/records caution, referral handoff",
    },
    "therapist": {
        "label": "Therapist",
        "pathway": "professional boundary, treatment-record privacy, no legal strategy",
    },
    "reviewer": {
        "label": "Reviewer",
        "pathway": "source freshness, citation, quote, fact, and filing-gate audit",
    },
}

POSTURES = {
    "unknown": "Posture unknown",
    "initial_complaint": "Initial complaint or first filing",
    "temporary_order": "Temporary order or interim relief",
    "final_order": "Final order or judgment",
    "post_judgment": "Post-judgment modification, enforcement, or contempt",
    "appeal": "Appeal or preservation review",
    "remand": "Remand after appeal",
}

OUTPUT_STYLES = {
    "plain_language",
    "checklist",
    "source_card_table",
    "reviewer_handoff",
    "missing_information",
    "professional_boundary",
}

SOURCE_LIBRARY: dict[str, dict[str, Any]] = {
    "family_division_process": {
        "source_id": "starter_me_family_division_process",
        "title": "Maine Judicial Branch family case process starter card",
        "canonical_citation": "Maine Judicial Branch family division and family matters pages",
        "authority_type": "official_court_process",
        "jurisdiction": "Maine",
        "source_status": "starter_card_requires_official_verification",
        "freshness_status": "must_verify_current_official_source",
        "can_support_current_law_claim": False,
        "registry_note": "Resolve against the official Maine Judicial Branch source registry before use.",
    },
    "official_forms": {
        "source_id": "starter_me_family_forms",
        "title": "Official Maine family forms starter card",
        "canonical_citation": "Maine Judicial Branch official family forms",
        "authority_type": "official_form_registry",
        "jurisdiction": "Maine",
        "source_status": "starter_card_requires_official_verification",
        "freshness_status": "must_verify_current_official_source",
        "can_support_current_law_claim": False,
        "registry_note": "Check form revision, packet membership, and required fields before drafting.",
    },
    "best_interest": {
        "source_id": "starter_me_19a_1653_best_interest",
        "title": "Parental rights and best-interest review starter card",
        "canonical_citation": "19-A M.R.S. section 1653",
        "authority_type": "statute",
        "jurisdiction": "Maine",
        "source_status": "starter_card_requires_official_verification",
        "freshness_status": "must_verify_current_official_source",
        "can_support_current_law_claim": False,
        "registry_note": "Verify the official statute text and effective version before relying on it.",
    },
    "child_support": {
        "source_id": "starter_me_child_support_guidelines",
        "title": "Child support guideline and worksheet starter card",
        "canonical_citation": "19-A M.R.S. child support provisions and official worksheet forms",
        "authority_type": "statute_and_form_registry",
        "jurisdiction": "Maine",
        "source_status": "starter_card_requires_official_verification",
        "freshness_status": "must_verify_current_official_source",
        "can_support_current_law_claim": False,
        "registry_note": "Verify income inputs, guideline version, worksheet forms, and deviations.",
    },
    "pfa": {
        "source_id": "starter_me_pfa_safety",
        "title": "Protection from abuse and safety routing starter card",
        "canonical_citation": "19-A M.R.S. protection-from-abuse provisions and official PFA forms",
        "authority_type": "statute_and_form_registry_safety",
        "jurisdiction": "Maine",
        "source_status": "starter_card_requires_official_verification",
        "freshness_status": "must_verify_current_official_source",
        "can_support_current_law_claim": False,
        "registry_note": "Use official court and safety resources; do not rely on model memory.",
    },
    "post_judgment": {
        "source_id": "starter_me_post_judgment_motions",
        "title": "Post-judgment modification, enforcement, and contempt starter card",
        "canonical_citation": "Maine family post-judgment motion rules, statutes, and official forms",
        "authority_type": "rule_statute_form_workflow",
        "jurisdiction": "Maine",
        "source_status": "starter_card_requires_official_verification",
        "freshness_status": "must_verify_current_official_source",
        "can_support_current_law_claim": False,
        "registry_note": "Confirm the requested relief, burden, service, and correct form packet.",
    },
    "appeal_rules": {
        "source_id": "starter_me_appellate_rules",
        "title": "Appeal, deadline, record, and transcript starter card",
        "canonical_citation": "Maine Rules of Appellate Procedure and Law Court resources",
        "authority_type": "court_rule_and_court_resource",
        "jurisdiction": "Maine",
        "source_status": "starter_card_requires_official_verification",
        "freshness_status": "must_verify_current_official_source",
        "can_support_current_law_claim": False,
        "registry_note": "Deadlines and record requirements must be checked against official rules.",
    },
    "rule_52": {
        "source_id": "starter_me_rule_52_findings",
        "title": "Rule 52 findings review starter card",
        "canonical_citation": "M.R. Civ. P. 52",
        "authority_type": "court_rule",
        "jurisdiction": "Maine",
        "source_status": "starter_card_requires_official_verification",
        "freshness_status": "must_verify_current_official_source",
        "can_support_current_law_claim": False,
        "registry_note": "Verify rule text, preservation requirements, and order-specific findings.",
    },
    "third_party_contact": {
        "source_id": "starter_me_non_delegation_contact",
        "title": "Third-party contact restriction and non-delegation starter card",
        "canonical_citation": "Maine parental-rights orders, contact restrictions, and findings review",
        "authority_type": "issue_review_checklist",
        "jurisdiction": "Maine",
        "source_status": "starter_card_requires_official_verification",
        "freshness_status": "must_verify_current_official_source",
        "can_support_current_law_claim": False,
        "registry_note": "Verify any order language that lets a therapist, GAL, or third party control contact.",
    },
    "caregiver_guardianship": {
        "source_id": "starter_me_caregiver_guardianship",
        "title": "Caregiver, guardianship, and grandparent question starter card",
        "canonical_citation": "Maine Probate Court guardianship resources and 19-A M.R.S. family provisions",
        "authority_type": "court_process_and_statute",
        "jurisdiction": "Maine",
        "source_status": "starter_card_requires_official_verification",
        "freshness_status": "must_verify_current_official_source",
        "can_support_current_law_claim": False,
        "registry_note": "Distinguish parental rights, probate guardianship, and grandparent visitation before advice.",
    },
    "records_privacy": {
        "source_id": "starter_me_records_privacy",
        "title": "School, medical, therapy, and confidential records starter card",
        "canonical_citation": "Maine court confidentiality rules, evidence rules, and applicable privacy law",
        "authority_type": "privacy_and_evidence_boundary",
        "jurisdiction": "Maine",
        "source_status": "starter_card_requires_official_verification",
        "freshness_status": "must_verify_current_official_source",
        "can_support_current_law_claim": False,
        "registry_note": "Do not upload private records into the repo; verify confidentiality before sharing.",
    },
    "court_clerk_boundary": {
        "source_id": "starter_me_clerk_and_legal_advice_boundary",
        "title": "Court clerk, lawyer, and legal-advice boundary starter card",
        "canonical_citation": "Maine court self-help and court-clerk role resources",
        "authority_type": "official_court_public_guidance",
        "jurisdiction": "Maine",
        "source_status": "starter_card_requires_official_verification",
        "freshness_status": "must_verify_current_official_source",
        "can_support_current_law_claim": False,
        "registry_note": "Clerks can provide process information, not legal advice or strategy.",
    },
}

ISSUE_ROUTES: list[dict[str, Any]] = [
    {
        "label": "served_with_family_court_papers",
        "title": "Served with family court papers",
        "patterns": ("served", "summons", "complaint was served", "got papers", "family court papers"),
        "source_keys": ("family_division_process", "official_forms"),
        "summary": "Start by identifying what was served, the response deadline, the court, and any temporary-order or hearing date.",
        "missing": (
            "Exact documents served, including summons, complaint, motions, notices, and attachments.",
            "Date, time, and method of service.",
            "Any hearing date, response deadline, or temporary order already entered.",
        ),
        "actions": (
            "Make a dated inventory of every document received.",
            "Confirm response and hearing dates from official court paperwork.",
            "Ask a lawyer or court help resource to review deadline risk before filing anything.",
        ),
        "red_flags": ("deadline_risk", "service_or_notice_issue"),
    },
    {
        "label": "protection_from_abuse_safety",
        "title": "Protection from abuse or safety concern",
        "patterns": (
            "protection from abuse",
            "pfa",
            "abuse",
            "domestic violence",
            "unsafe",
            "threat",
            "stalking",
            "weapon",
            "hurt me",
            "hurt the child",
        ),
        "source_keys": ("pfa", "family_division_process", "official_forms"),
        "summary": "Safety questions should be routed first, with family-case overlap reviewed against official PFA and family-court sources.",
        "missing": (
            "Whether anyone is in immediate danger or needs emergency help.",
            "Whether a PFA case, family case, or criminal/bail condition already exists.",
            "Any existing orders affecting contact, exchange locations, residence, or communication.",
        ),
        "actions": (
            "If there is immediate danger, contact 911 or local emergency services.",
            "Use official court and safety resources before relying on any drafted language.",
            "Separate emergency safety facts from longer-term parenting or divorce questions.",
        ),
        "red_flags": ("immediate_safety_risk", "pfa_family_overlap"),
    },
    {
        "label": "divorce_first_steps",
        "title": "Divorce first steps",
        "patterns": ("divorce", "dissolution", "spouse", "marriage", "marital"),
        "source_keys": ("family_division_process", "official_forms", "child_support", "best_interest"),
        "summary": "Divorce intake should separate relationship status, children, property/debt, support, service, and form freshness.",
        "missing": (
            "Whether there are minor children, a pregnancy, prior orders, or a PFA case.",
            "Income, health insurance, property, debt, and address/service information.",
            "Which official divorce packet and financial forms apply.",
        ),
        "actions": (
            "Collect marriage, children, residence, income, property, debt, and service facts.",
            "Check the official divorce packet before preparing forms.",
            "Keep drafts review_required until forms and authority are verified.",
        ),
        "red_flags": ("form_freshness_unknown", "private_records_risk"),
    },
    {
        "label": "parental_rights_responsibilities",
        "title": "Parental rights and responsibilities",
        "patterns": (
            "parental rights",
            "responsibilities",
            "custody",
            "primary residence",
            "contact schedule",
            "parenting time",
            "decision-making",
            "decision making",
        ),
        "source_keys": ("best_interest", "family_division_process", "official_forms"),
        "summary": "Parenting questions should be organized around best-interest factors, residence, decision-making, contact, safety, and evidence.",
        "missing": (
            "Current order status and whether any temporary or final order exists.",
            "Child age, schedule, school, medical needs, safety facts, and each parent's role.",
            "Evidence for each material best-interest factor.",
        ),
        "actions": (
            "Map each requested parenting term to facts and evidence.",
            "Build a best-interest factor checklist before drafting.",
            "Flag contact restrictions or third-party control language for reviewer attention.",
        ),
        "red_flags": ("best_interest_gap",),
    },
    {
        "label": "child_support_documents",
        "title": "Child support documents",
        "patterns": ("child support", "support worksheet", "guidelines", "income", "deviation", "health insurance"),
        "source_keys": ("child_support", "official_forms"),
        "summary": "Support questions need current income documents, worksheet inputs, health insurance, childcare, and deviation facts.",
        "missing": (
            "Recent income documents for each parent.",
            "Childcare, health insurance, public benefits, and extraordinary expense facts.",
            "Whether support is initial, temporary, final, or post-judgment.",
        ),
        "actions": (
            "Gather income and expense documents before calculating or drafting.",
            "Verify official worksheet forms and guideline sources.",
            "Separate calculation inputs from legal arguments for review.",
        ),
        "red_flags": ("unsupported_financial_input",),
    },
    {
        "label": "modification_enforcement_contempt",
        "title": "Modification, enforcement, or contempt",
        "patterns": (
            "modify",
            "modification",
            "enforce",
            "enforcement",
            "contempt",
            "not following the order",
            "violated",
            "missed support",
            "post-judgment",
            "post judgment",
        ),
        "source_keys": ("post_judgment", "official_forms", "best_interest"),
        "summary": "Post-judgment routing must distinguish changed circumstances, enforcement, and contempt before choosing forms or relief.",
        "missing": (
            "The exact order language allegedly changed or violated.",
            "Dates, proof, and whether the violation was willful or the circumstances changed.",
            "What relief is requested and whether safety or emergency issues exist.",
        ),
        "actions": (
            "Quote the existing order language in the review packet.",
            "Sort facts into modification, enforcement, contempt, or safety categories.",
            "Verify service and official post-judgment forms before filing.",
        ),
        "red_flags": ("order_language_missing", "deadline_risk"),
    },
    {
        "label": "appeal_deadline_preservation_transcript",
        "title": "Appeal deadline, preservation, and transcript",
        "patterns": ("appeal", "law court", "notice of appeal", "transcript", "record on appeal", "preserve"),
        "source_keys": ("appeal_rules", "rule_52"),
        "summary": "Appeal questions are deadline-sensitive and should be routed to appellate rules, preservation, findings, and record/transcript checks.",
        "missing": (
            "Date the judgment or order was entered on the docket.",
            "Whether any post-judgment motion, findings motion, or reconsideration motion was filed.",
            "Whether a transcript or record materials are needed and available.",
        ),
        "actions": (
            "Verify appeal deadlines against the official appellate rules immediately.",
            "Create a preservation checklist with findings, objections, exhibits, and transcript status.",
            "Ask an appellate reviewer to inspect the record before relying on a strategy.",
        ),
        "red_flags": ("appeal_deadline_risk", "missing_transcript_or_record"),
    },
    {
        "label": "rule_52_findings_gap",
        "title": "Rule 52 findings gap",
        "patterns": ("rule 52", "findings", "no findings", "missing findings", "proposed findings"),
        "source_keys": ("rule_52", "best_interest"),
        "summary": "Findings gaps require review of the rule, the final order, preservation posture, and the evidence tied to each disputed issue.",
        "missing": (
            "The exact order text and whether findings were requested.",
            "Which disputed issues lack findings.",
            "Relevant transcript, exhibits, proposed findings, and docket entries.",
        ),
        "actions": (
            "Build a findings matrix by disputed issue.",
            "Verify preservation and timing with official rules and human review.",
            "Do not label a findings argument filing-ready without record review.",
        ),
        "red_flags": ("missing_rule_52_findings",),
    },
    {
        "label": "best_interest_factor_gap",
        "title": "Best-interest factor gap",
        "patterns": ("best interest", "best-interest", "1653", "factor", "factors"),
        "source_keys": ("best_interest", "rule_52"),
        "summary": "Best-interest review should check which material factors are addressed, omitted, unsupported, or contradicted by the record.",
        "missing": (
            "Which best-interest factors are disputed or material.",
            "Evidence supporting each factor and any contrary evidence.",
            "Whether the order explains the reasoning for residence, contact, and decision-making.",
        ),
        "actions": (
            "Create a factor-by-factor evidence table.",
            "Separate facts from argument and source each claim.",
            "Ask a reviewer to check whether omitted factors are material.",
        ),
        "red_flags": ("best_interest_gap",),
    },
    {
        "label": "therapist_gal_non_delegation_contact",
        "title": "Therapist, GAL, non-delegation, or contact restriction",
        "patterns": (
            "therapist decides",
            "counselor decides",
            "gal decides",
            "third party decides",
            "reunification therapist",
            "no contact",
            "supervised contact",
            "contact restriction",
            "visits happen",
        ),
        "source_keys": ("third_party_contact", "best_interest", "records_privacy"),
        "summary": "Any contact restriction or third-party control term should be reviewed for findings, scope, delegation, privacy, and professional-role boundaries.",
        "missing": (
            "Exact order language about therapy, GAL role, exchanges, supervision, and contact.",
            "Who controls the decision and what standards or findings support that control.",
            "Treatment-record privacy and consent/subpoena status.",
        ),
        "actions": (
            "Quote the contact restriction language exactly in the reviewer handoff.",
            "Flag any therapist, counselor, GAL, or third-party veto over contact.",
            "Keep therapists and counselors out of legal-strategy recommendations.",
        ),
        "red_flags": ("third_party_contact_delegation", "contact_restriction_without_findings"),
    },
    {
        "label": "caregiver_guardianship_grandparent",
        "title": "Caregiver, guardianship, or grandparent question",
        "patterns": ("caregiver", "grandparent", "guardianship", "guardian", "relative", "enroll a child"),
        "source_keys": ("caregiver_guardianship", "records_privacy", "family_division_process"),
        "summary": "Caregiver questions need careful routing between family court, probate guardianship, records authority, and grandparent visitation.",
        "missing": (
            "Relationship to the child and whether parents consent or object.",
            "Existing family, probate, PFA, or child-protection orders.",
            "School, medical, and day-to-day authority documents.",
        ),
        "actions": (
            "Identify whether the question belongs in family court, probate, or another process.",
            "Collect existing orders and consent documents before drafting.",
            "Ask a lawyer to check caregiver authority and records access.",
        ),
        "red_flags": ("wrong_forum_risk", "records_privacy_risk"),
    },
    {
        "label": "school_medical_records_privacy",
        "title": "School, medical, or records privacy",
        "patterns": ("school records", "medical records", "therapy records", "session notes", "hipaa", "ferpa", "confidential", "sealed"),
        "source_keys": ("records_privacy", "court_clerk_boundary"),
        "summary": "Records questions should route to privacy, confidentiality, consent, subpoena, and court-order review before sharing materials.",
        "missing": (
            "What record type is involved and who created it.",
            "Whether there is consent, subpoena, court order, or privilege claim.",
            "Whether the record includes minors, health information, sealed material, or social security numbers.",
        ),
        "actions": (
            "Do not paste private records into the repo or public tools.",
            "Verify confidentiality, privilege, and disclosure rules before sharing.",
            "Prepare a records log for reviewer inspection instead of raw private content.",
        ),
        "red_flags": ("records_privacy_risk", "private_records_risk"),
    },
    {
        "label": "court_clerk_lawyer_boundary",
        "title": "Court clerk, lawyer, and professional boundary",
        "patterns": (
            "court clerk",
            "clerk",
            "lawyer",
            "legal advice",
            "what can i say",
            "what should i tell",
            "what to file",
            "what should i file",
        ),
        "source_keys": ("court_clerk_boundary", "family_division_process"),
        "summary": "Role-boundary questions should separate neutral process information, legal advice, and lawyer review needs.",
        "missing": (
            "The user's role and whether they are asking for process information or legal strategy.",
            "The exact procedural step or form question.",
            "Whether a lawyer already represents any party.",
        ),
        "actions": (
            "Provide neutral process and source-check information only.",
            "Refer legal strategy, filing choices, and rights analysis to a lawyer.",
            "Document what information was given and what was deferred.",
        ),
        "red_flags": ("unauthorized_practice_boundary",),
    },
    {
        "label": "missing_information_before_answering",
        "title": "Missing information before answering",
        "patterns": ("missing information", "what information", "before asking", "what do you need", "intake checklist"),
        "source_keys": ("family_division_process", "official_forms", "best_interest"),
        "summary": "When facts are thin, the safest answer is an intake checklist before legal analysis.",
        "missing": (
            "Case type, county/court, posture, and existing orders.",
            "Dates for service, hearings, orders, and deadlines.",
            "Requested outcome, safety concerns, and documents already available.",
        ),
        "actions": (
            "Answer with a missing-information checklist first.",
            "Defer merits analysis until posture, dates, sources, and facts are known.",
            "Keep the export packet review_required.",
        ),
        "red_flags": ("posture_unknown",),
    },
]

RED_FLAG_LIBRARY: dict[str, dict[str, str]] = {
    "immediate_safety_risk": {
        "label": "Immediate safety risk",
        "severity": "high",
        "explanation": "Safety routing comes before ordinary family-law workflow.",
    },
    "pfa_family_overlap": {
        "label": "PFA and family-case overlap",
        "severity": "high",
        "explanation": "Protective orders and parenting orders must be reviewed together against official sources.",
    },
    "deadline_risk": {
        "label": "Deadline risk",
        "severity": "high",
        "explanation": "Service, response, hearing, and appeal deadlines require official-rule verification.",
    },
    "service_or_notice_issue": {
        "label": "Service or notice issue",
        "severity": "medium",
        "explanation": "The method and date of service can affect next steps and deadlines.",
    },
    "appeal_deadline_risk": {
        "label": "Appeal deadline risk",
        "severity": "high",
        "explanation": "Appeal timing must be checked against the official appellate rules and docket entry date.",
    },
    "missing_transcript_or_record": {
        "label": "Missing transcript or incomplete record",
        "severity": "high",
        "explanation": "A review packet cannot assess an appeal without record and transcript status.",
    },
    "missing_rule_52_findings": {
        "label": "Missing Rule 52 findings",
        "severity": "high",
        "explanation": "Thin or absent findings can affect review, preservation, and proposed-order workflows.",
    },
    "best_interest_gap": {
        "label": "Best-interest factor gap",
        "severity": "high",
        "explanation": "Material best-interest factors need evidence and source-backed analysis.",
    },
    "third_party_contact_delegation": {
        "label": "Therapist/GAL/non-delegation contact red flag",
        "severity": "high",
        "explanation": "A third party controlling contact may require findings, scope, and legal review.",
    },
    "contact_restriction_without_findings": {
        "label": "Contact restriction without sourced findings",
        "severity": "high",
        "explanation": "Restrictions on parent-child contact need careful findings and authority review.",
    },
    "form_freshness_unknown": {
        "label": "Form freshness unknown",
        "severity": "medium",
        "explanation": "Official form version and packet membership must be verified.",
    },
    "unsupported_financial_input": {
        "label": "Unsupported financial input",
        "severity": "medium",
        "explanation": "Support calculations need evidence-backed income and expense inputs.",
    },
    "order_language_missing": {
        "label": "Exact order language missing",
        "severity": "medium",
        "explanation": "Modification, enforcement, and contempt review depends on the precise order text.",
    },
    "wrong_forum_risk": {
        "label": "Wrong forum risk",
        "severity": "medium",
        "explanation": "Caregiver questions may belong in family court, probate, or another process.",
    },
    "records_privacy_risk": {
        "label": "Records privacy risk",
        "severity": "high",
        "explanation": "School, medical, therapy, sealed, and minor-child records need privacy review.",
    },
    "private_records_risk": {
        "label": "Private records handling risk",
        "severity": "high",
        "explanation": "Private matter documents must not enter the source repo or public evidence outputs.",
    },
    "unauthorized_practice_boundary": {
        "label": "Professional role boundary",
        "severity": "medium",
        "explanation": "Non-lawyer roles should avoid legal strategy, filing choices, and rights advice.",
    },
    "posture_unknown": {
        "label": "Procedural posture unknown",
        "severity": "medium",
        "explanation": "The safest next step is an intake checklist until posture and dates are known.",
    },
}

PATTERN_RED_FLAGS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("immediate_safety_risk", ("unsafe tonight", "in danger", "weapon", "hurt me", "hurt the child", "threat")),
    ("appeal_deadline_risk", ("appeal", "notice of appeal", "deadline", "transcript")),
    ("missing_rule_52_findings", ("no findings", "missing findings", "rule 52")),
    ("best_interest_gap", ("best interest", "best-interest", "1653")),
    ("third_party_contact_delegation", ("therapist decides", "counselor decides", "gal decides", "visits happen")),
    ("contact_restriction_without_findings", ("no contact", "supervised contact", "contact restriction")),
    ("records_privacy_risk", ("school records", "medical records", "therapy records", "session notes", "sealed")),
)

BASE_MISSING_INFORMATION = (
    "County/court, docket number if any, and whether the matter is new, temporary, final, post-judgment, appeal, or remand.",
    "All known dates: service, orders, hearings, deadlines, moves, payments, incidents, and notices.",
    "Existing orders, official forms, source cards, and documents already available for human review.",
)

BASE_NEXT_ACTIONS = (
    "Keep private matter files outside the repo and summarize sensitive facts instead of copying raw records.",
    "Verify every source card against the official Maine registry before relying on a legal claim.",
    "Prepare a reviewer packet with facts, documents, citations, quote spans, and unresolved blockers.",
)


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _normalize_choice(value: str, allowed: set[str] | dict[str, Any], default: str) -> str:
    normalized = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return normalized if normalized in allowed else default


def _has_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in text for pattern in patterns)


def _dedupe_dicts(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for row in rows:
        value = str(row.get(key, ""))
        if value and value not in seen:
            deduped.append(row)
            seen.add(value)
    return deduped


def _route_by_label(label: str) -> dict[str, Any]:
    for route in ISSUE_ROUTES:
        if route["label"] == label:
            return route
    return {
        "label": label,
        "title": "General Maine family-law question",
        "source_keys": ("family_division_process", "official_forms"),
        "summary": "Use source cards and missing-information review before legal analysis.",
        "missing": (),
        "actions": (),
        "red_flags": ("posture_unknown",),
    }


def infer_posture(question: str, facts_context: str = "", requested_posture: str = "unknown") -> str:
    posture = _normalize_choice(requested_posture, POSTURES, "unknown")
    if posture != "unknown":
        return posture
    text = f"{question} {facts_context}".lower()
    if _has_any(text, ("appeal", "law court", "notice of appeal", "transcript")):
        return "appeal"
    if _has_any(text, ("remand", "remanded")):
        return "remand"
    if _has_any(text, ("post-judgment", "post judgment", "after final", "modify", "enforce", "contempt")):
        return "post_judgment"
    if _has_any(text, ("final order", "judgment", "divorce judgment", "final hearing")):
        return "final_order"
    if _has_any(text, ("temporary order", "interim", "emergency motion")):
        return "temporary_order"
    if _has_any(text, ("served", "summons", "complaint", "first file", "start divorce")):
        return "initial_complaint"
    return "unknown"


def route_issue_labels(question: str, facts_context: str = "") -> list[str]:
    text = f"{question} {facts_context}".lower()
    labels = [route["label"] for route in ISSUE_ROUTES if _has_any(text, route["patterns"])]
    if not labels:
        labels = ["missing_information_before_answering"]

    if "appeal_deadline_preservation_transcript" in labels:
        labels = [
            label
            for label in labels
            if label not in {"parental_rights_responsibilities", "divorce_first_steps"}
        ]
        labels.insert(0, labels.pop(labels.index("appeal_deadline_preservation_transcript")))

    return list(dict.fromkeys(labels))[:7]


def build_source_cards(issue_labels: list[str]) -> list[dict[str, Any]]:
    keys: list[str] = []
    for label in issue_labels:
        keys.extend(_route_by_label(label).get("source_keys", ()))
    if not keys:
        keys.extend(("family_division_process", "official_forms"))
    rows = [dict(SOURCE_LIBRARY[key], matched_issue=label) for label in issue_labels for key in _route_by_label(label).get("source_keys", ()) if key in SOURCE_LIBRARY]
    if not rows:
        rows = [dict(SOURCE_LIBRARY["family_division_process"], matched_issue="general"), dict(SOURCE_LIBRARY["official_forms"], matched_issue="general")]
    return _dedupe_dicts(rows, "source_id")


def build_red_flags(issue_labels: list[str], question: str, facts_context: str = "") -> list[dict[str, Any]]:
    red_flag_ids: list[str] = []
    for label in issue_labels:
        red_flag_ids.extend(_route_by_label(label).get("red_flags", ()))
    text = f"{question} {facts_context}".lower()
    for flag_id, patterns in PATTERN_RED_FLAGS:
        if _has_any(text, patterns):
            red_flag_ids.append(flag_id)
    rows: list[dict[str, Any]] = []
    for flag_id in dict.fromkeys(red_flag_ids):
        base = RED_FLAG_LIBRARY.get(flag_id)
        if not base:
            continue
        rows.append(
            {
                "flag_id": flag_id,
                **base,
                "blocks_filing_ready": True,
                "reviewer_note": "Explain this blocker in the reviewer handoff before any filing decision.",
            }
        )
    return rows


def build_missing_information(issue_labels: list[str], posture: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = [
        {"category": "baseline", "question": item} for item in BASE_MISSING_INFORMATION
    ]
    if posture == "unknown":
        rows.append(
            {
                "category": "posture",
                "question": "What is the procedural posture: new case, temporary order, final order, post-judgment, appeal, or remand?",
            }
        )
    for label in issue_labels:
        route = _route_by_label(label)
        rows.extend({"category": label, "question": item} for item in route.get("missing", ()))
    return _dedupe_dicts(rows, "question")


def build_next_best_actions(issue_labels: list[str], audience: str, red_flags: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = [
        {"priority": "1", "label": item, "reason": "Baseline source-first safety and review workflow."}
        for item in BASE_NEXT_ACTIONS
    ]
    if any(flag["flag_id"] == "immediate_safety_risk" for flag in red_flags):
        rows.insert(
            0,
            {
                "priority": "0",
                "label": "If there is immediate danger, contact 911 or local emergency services.",
                "reason": "Safety routing outranks ordinary family-law workflow.",
            },
        )
    for label in issue_labels:
        route = _route_by_label(label)
        rows.extend(
            {
                "priority": str(len(rows) + 1),
                "label": item,
                "reason": route["title"],
            }
            for item in route.get("actions", ())
        )
    if audience in {"counselor", "therapist"}:
        rows.insert(
            0,
            {
                "priority": "0",
                "label": "Stay within professional role boundaries and do not choose filings or legal strategy.",
                "reason": "Counselor and therapist outputs must be professional-boundary guidance, not legal advice.",
            },
        )
    return _dedupe_dicts(rows, "label")


def build_urgency_and_safety(issue_labels: list[str], red_flags: list[dict[str, Any]]) -> dict[str, Any]:
    high_flags = [flag for flag in red_flags if flag.get("severity") == "high"]
    safety = "protection_from_abuse_safety" in issue_labels or any(
        flag["flag_id"] == "immediate_safety_risk" for flag in red_flags
    )
    if safety:
        level = "safety_priority"
    elif high_flags:
        level = "urgent_review"
    else:
        level = "ordinary_review"
    return {
        "urgency": level,
        "safety_routing": safety,
        "emergency_caveat": (
            "If anyone is in immediate danger, contact 911 or local emergency services. "
            "The workbench is not an emergency service."
            if safety
            else ""
        ),
        "high_severity_flags": [flag["flag_id"] for flag in high_flags],
    }


def build_authority_matrix(issue_labels: list[str], source_cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for card in source_cards:
        rows.append(
            {
                "issue": card.get("matched_issue", "general"),
                "source_id": card["source_id"],
                "authority": card["canonical_citation"],
                "source_status": card["source_status"],
                "freshness_status": card["freshness_status"],
                "verification_task": "Resolve source, confirm effective text/form version, and attach citation/quote support.",
            }
        )
    if not rows:
        rows.append(
            {
                "issue": issue_labels[0] if issue_labels else "general",
                "source_id": "missing_source_card",
                "authority": "No source card selected",
                "source_status": "blocked",
                "freshness_status": "unknown",
                "verification_task": "Add official Maine source cards before answering.",
            }
        )
    return rows


def build_filing_readiness(
    source_cards: list[dict[str, Any]],
    red_flags: list[dict[str, Any]],
    posture: str,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    blockers: list[dict[str, str]] = [
        {
            "category": "human_review",
            "message": "Human legal review has not certified this output.",
        },
        {
            "category": "source_freshness",
            "message": "Source cards are starter cards and must be resolved against official Maine sources.",
        },
        {
            "category": "citation_quote_fact_support",
            "message": "Citation existence, quote-span, and claim-support verification have not passed.",
        },
        {
            "category": "forms_and_procedure",
            "message": "Official forms, required fields, service, deadline, and posture checks have not passed.",
        },
    ]
    if posture == "unknown":
        blockers.append(
            {
                "category": "posture",
                "message": "Procedural posture is unknown.",
            }
        )
    if not source_cards:
        blockers.append(
            {
                "category": "source_cards",
                "message": "No source cards are attached.",
            }
        )
    blockers.extend(
        {
            "category": "red_flag",
            "message": f"{flag['label']}: {flag['explanation']}",
        }
        for flag in red_flags
        if flag.get("blocks_filing_ready")
    )
    blockers = _dedupe_dicts(blockers, "message")
    return (
        {
            "status": "review_required_not_filing_ready",
            "review_required": True,
            "filing_ready": False,
            "can_export_for_filing": False,
            "hard_gates_passed": False,
            "blocked_by_default": True,
            "blocker_count": len(blockers),
        },
        blockers,
    )


def build_legal_caveats(audience: str) -> list[str]:
    caveats = [
        DISCLAIMER,
        "Official Maine authority and verified source-registry data outrank model memory, summaries, mirrors, and snippets.",
        "No current-law certainty is claimed because starter source cards still require official freshness verification.",
        "Private uploaded matter data must stay outside the source repo and should not train shared models by default.",
    ]
    if audience in {"counselor", "therapist"}:
        caveats.append(
            "Professional-boundary mode does not give legal strategy, choose filings, or advise a party what to ask the court to do."
        )
    return caveats


def build_plain_language_answer(
    question: str,
    audience: str,
    output_style: str,
    issue_labels: list[str],
    posture: str,
    urgency: dict[str, Any],
    source_cards: list[dict[str, Any]],
    missing_information: list[dict[str, str]],
    next_actions: list[dict[str, str]],
    red_flags: list[dict[str, Any]],
) -> str:
    issue_titles = [_route_by_label(label)["title"] for label in issue_labels]
    source_intro = (
        f"Start with {len(source_cards)} source card(s), then answer only what those cards and verified facts can support."
    )
    if audience in {"counselor", "therapist"} or output_style == "professional_boundary":
        return (
            "This is a professional-boundary answer, not legal strategy. "
            "Stay in your treatment or support role, avoid telling anyone what to file or what relief to request, "
            "protect private records, and refer legal-rights and filing-choice questions to a lawyer. "
            f"{source_intro} Key issue(s): {', '.join(issue_titles)}."
        )
    if output_style == "missing_information":
        return (
            "The safest next answer is a missing-information checklist before legal analysis. "
            f"Posture is {POSTURES[posture]}. Collect the first {min(5, len(missing_information))} missing items, "
            f"then verify the source cards. Key issue(s): {', '.join(issue_titles)}."
        )
    if output_style == "reviewer_handoff":
        return (
            "Reviewer handoff: verify posture, source freshness, authority, citations, quote spans, facts, forms, "
            f"and red flags before any legal conclusion. Key issue(s): {', '.join(issue_titles)}. "
            f"Filing is blocked by {len(red_flags)} red flag(s) and default hard gates."
        )
    if urgency.get("safety_routing"):
        return (
            f"{urgency['emergency_caveat']} After immediate safety is handled, {source_intro} "
            f"Separate PFA/safety facts from parenting, divorce, support, or post-judgment workflow. "
            "Do not treat this packet as filing-ready."
        )
    if output_style == "checklist":
        return (
            f"Use this as a review-required checklist for: {_normalize_space(question)}. "
            f"{source_intro} Confirm posture, missing facts, and blocker explanations before drafting."
        )
    if output_style == "source_card_table":
        return (
            f"Source-card-first answer for: {_normalize_space(question)}. "
            "Each legal point must tie to an official-source card, freshness status, citation, quote span, and fact support."
        )
    return (
        f"This looks like a Maine family-law workflow about {', '.join(issue_titles)}. "
        f"{source_intro} The next useful move is to collect missing information, flag red flags, "
        "and prepare a reviewer packet. It is legal information only and remains review_required."
    )


def build_reviewer_handoff(
    question: str,
    audience: str,
    posture: str,
    issue_labels: list[str],
    source_cards: list[dict[str, Any]],
    missing_information: list[dict[str, str]],
    red_flags: list[dict[str, Any]],
    blockers: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "handoff_type": "family_justice_workbench_review_packet",
        "question": _normalize_space(question),
        "audience": audience,
        "posture": posture,
        "issue_labels": issue_labels,
        "authority_checklist": [
            {
                "source_id": card["source_id"],
                "task": "Verify official source, effective text/form version, citation, and quote support.",
            }
            for card in source_cards
        ],
        "claim_checklist": [
            "Separate legal claims from factual claims.",
            "Attach evidence or mark unsupported for every material fact.",
            "Verify quote spans against source text before quoting.",
            "Check jurisdiction, service, deadlines, and procedural posture.",
        ],
        "missing_documents": [row["question"] for row in missing_information[:10]],
        "red_flags": [flag["label"] for flag in red_flags],
        "filing_gate_blockers": [blocker["message"] for blocker in blockers],
        "human_review_required": True,
        "reviewer_mode": "authority_first_fail_closed",
    }


def build_workbench_packet(
    question: str,
    audience: str = "parent",
    posture: str = "unknown",
    facts_context: str = "",
    requested_output_style: str = "plain_language",
    *,
    generated_at: str = DETERMINISTIC_GENERATED_AT,
) -> dict[str, Any]:
    normalized_question = _normalize_space(question)
    normalized_context = _normalize_space(facts_context)
    audience = _normalize_choice(audience, AUDIENCES, "parent")
    output_style = _normalize_choice(requested_output_style, OUTPUT_STYLES, "plain_language")
    posture = infer_posture(normalized_question, normalized_context, posture)
    issue_labels = route_issue_labels(normalized_question, normalized_context)
    source_cards = build_source_cards(issue_labels)
    red_flags = build_red_flags(issue_labels, normalized_question, normalized_context)
    missing_information = build_missing_information(issue_labels, posture)
    next_actions = build_next_best_actions(issue_labels, audience, red_flags)
    urgency = build_urgency_and_safety(issue_labels, red_flags)
    filing_status, blockers = build_filing_readiness(source_cards, red_flags, posture)
    plain_answer = build_plain_language_answer(
        normalized_question,
        audience,
        output_style,
        issue_labels,
        posture,
        urgency,
        source_cards,
        missing_information,
        next_actions,
        red_flags,
    )
    reviewer_handoff = build_reviewer_handoff(
        normalized_question,
        audience,
        posture,
        issue_labels,
        source_cards,
        missing_information,
        red_flags,
        blockers,
    )
    packet = {
        "schema": PACKET_SCHEMA,
        "version": VERSION,
        "generated_at": generated_at,
        "question": normalized_question,
        "audience": audience,
        "audience_label": AUDIENCES[audience]["label"],
        "role_specific_pathway": AUDIENCES[audience]["pathway"],
        "posture": posture,
        "posture_label": POSTURES[posture],
        "requested_output_style": output_style,
        "facts_context_used": bool(normalized_context),
        "answer_preview": plain_answer[:240],
        "plain_language_answer": plain_answer,
        "issue_labels": issue_labels,
        "urgency_safety_routing": urgency,
        "source_cards": source_cards,
        "authority_matrix_preview": build_authority_matrix(issue_labels, source_cards),
        "legal_caveats": build_legal_caveats(audience),
        "missing_information": missing_information,
        "next_best_actions": next_actions,
        "red_flags": red_flags,
        "filing_readiness_status": filing_status,
        "why_not_filing_ready": blockers,
        "reviewer_handoff": reviewer_handoff,
        "export_metadata": {
            "export_schema": PACKET_SCHEMA,
            "export_version": VERSION,
            "default_export": "review_packet",
            "review_required": True,
            "filing_ready": False,
            "private_matter_data_included": False,
            "deterministic_offline": True,
            "source_freshness_claim": "none_without_official_registry_verification",
            "evidence_outputs": [
                "docs/external-evidence/family_justice_workbench_v205_packet.json",
                "docs/external-evidence/family_justice_workbench_v205_audit.json",
                "docs/external-evidence/family_justice_workbench_v205.html",
                "docs/external-evidence/family_justice_workbench_v205_test_summary.json",
            ],
        },
        "claims": {
            "legal_advice": False,
            "filing_ready": False,
            "current_law_certified": False,
            "attorney_review_completed": False,
            "private_data_packaged": False,
            "model_memory_used_as_authority": False,
        },
    }
    return packet


def build_sample_packets() -> list[dict[str, Any]]:
    samples = [
        {
            "question": "I was served with Maine family court papers and there is a hearing date. What should I do first?",
            "audience": "parent",
            "posture": "initial_complaint",
            "requested_output_style": "checklist",
        },
        {
            "question": "I need protection from abuse and I am worried about safety during exchanges.",
            "audience": "parent",
            "posture": "temporary_order",
            "requested_output_style": "plain_language",
        },
        {
            "question": "Review this final parenting order: no Rule 52 findings, best-interest factors are thin, and the therapist decides when visits happen.",
            "audience": "reviewer",
            "posture": "final_order",
            "requested_output_style": "reviewer_handoff",
        },
        {
            "question": "How long do I have to appeal a Maine family order and what transcript or record facts matter?",
            "audience": "lawyer",
            "posture": "appeal",
            "requested_output_style": "source_card_table",
        },
        {
            "question": "A parent asked me as a therapist what to file and whether I can share session notes in family court.",
            "audience": "therapist",
            "posture": "unknown",
            "requested_output_style": "professional_boundary",
        },
        {
            "question": "I am a caregiver and need school and medical record access. Is this guardianship, grandparent visitation, or parental rights?",
            "audience": "caregiver",
            "posture": "unknown",
            "requested_output_style": "missing_information",
        },
    ]
    return [build_workbench_packet(**sample) for sample in samples]


def build_audit(packets: list[dict[str, Any]] | None = None, html_text: str = "") -> dict[str, Any]:
    packets = packets or build_sample_packets()
    html_text = html_text or render_workbench_html(packets)
    checks = {
        "packet_schema_present": all(packet.get("schema") == PACKET_SCHEMA for packet in packets),
        "review_required_default": all(packet["filing_readiness_status"]["review_required"] is True for packet in packets),
        "filing_ready_blocked": all(packet["filing_readiness_status"]["filing_ready"] is False for packet in packets),
        "source_cards_present": all(bool(packet.get("source_cards")) for packet in packets),
        "no_current_law_certainty": all(packet["claims"]["current_law_certified"] is False for packet in packets),
        "professional_boundary_present": any(
            packet["audience"] in {"counselor", "therapist"}
            and "not legal strategy" in packet["plain_language_answer"].lower()
            for packet in packets
        ),
        "safety_routes_present": any(packet["urgency_safety_routing"]["safety_routing"] for packet in packets),
        "appeal_route_present": any("appeal_deadline_preservation_transcript" in packet["issue_labels"] for packet in packets),
        "html_markers_present": all(
            marker in html_text
            for marker in (
                "Family Justice Workbench",
                "ask-section",
                "review-section",
                "next-steps-section",
                "source-card",
                "blocker-card",
                "red-flag-chip",
                "role-pathway",
                "authority-matrix-preview",
                "review_required=true",
                "filing_ready=false",
            )
        ),
    }
    return {
        "schema": AUDIT_SCHEMA,
        "version": VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "claims": {
            "legal_advice": False,
            "filing_ready": False,
            "current_law_certified": False,
            "private_data_packaged": False,
        },
    }


def build_test_summary(packets: list[dict[str, Any]] | None = None, html_text: str = "") -> dict[str, Any]:
    packets = packets or build_sample_packets()
    html_text = html_text or render_workbench_html(packets)
    by_question = {packet["question"]: packet for packet in packets}
    appeal_packet = next(
        packet for packet in packets if "appeal_deadline_preservation_transcript" in packet["issue_labels"]
    )
    professional_packet = next(packet for packet in packets if packet["audience"] == "therapist")
    findings_packet = next(packet for packet in packets if packet["audience"] == "reviewer")
    checks = {
        "source_cards_exist_for_legal_answers": all(packet["source_cards"] for packet in packets),
        "review_required_by_default": all(packet["filing_readiness_status"]["review_required"] for packet in packets),
        "filing_ready_false_without_hard_gates": all(not packet["filing_readiness_status"]["filing_ready"] for packet in packets),
        "no_current_law_certainty_without_freshness": all(not packet["claims"]["current_law_certified"] for packet in packets),
        "professional_boundary_no_legal_strategy": "not legal strategy" in professional_packet["plain_language_answer"].lower(),
        "pfa_safety_routes_to_emergency_caveat": any(
            packet["urgency_safety_routing"]["safety_routing"]
            and "911" in packet["urgency_safety_routing"]["emergency_caveat"]
            for packet in packets
        ),
        "appeal_not_generic_parenting": appeal_packet["issue_labels"][0] == "appeal_deadline_preservation_transcript"
        and "parental_rights_responsibilities" not in appeal_packet["issue_labels"],
        "therapist_non_delegation_red_flag": "Therapist/GAL/non-delegation contact red flag"
        in findings_packet["reviewer_handoff"]["red_flags"],
        "rule_52_best_interest_flags": {"Missing Rule 52 findings", "Best-interest factor gap"}.issubset(
            set(findings_packet["reviewer_handoff"]["red_flags"])
        ),
        "html_expected_ui_markers": all(
            marker in html_text
            for marker in ("Ask", "Review", "Next Steps", "source-card", "blocker-card", "red-flag-chip")
        ),
        "json_schema_stable": all(
            key in next(iter(by_question.values()))
            for key in (
                "answer_preview",
                "plain_language_answer",
                "issue_labels",
                "source_cards",
                "filing_readiness_status",
                "reviewer_handoff",
                "export_metadata",
            )
        ),
        "no_private_runtime_artifacts": all(
            not packet["export_metadata"]["private_matter_data_included"] for packet in packets
        ),
    }
    return {
        "schema": TEST_SUMMARY_SCHEMA,
        "version": VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "status": "pass" if all(checks.values()) else "fail",
        "packet_count": len(packets),
        "checks": checks,
    }


def _json_for_script(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True).replace("</", "<\\/")


def render_workbench_html(packets: list[dict[str, Any]] | None = None) -> str:
    packets = packets or build_sample_packets()
    seed = packets[0]
    packets_json = _json_for_script(packets)
    seed_json = _json_for_script(seed)
    html_doc = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Family Justice Workbench v__VERSION__</title>
  <style>
    :root {
      --ink: #15202b;
      --muted: #576575;
      --paper: #fffdf8;
      --wash: #f4f7fb;
      --line: #d7dee8;
      --navy: #16324f;
      --river: #0b766d;
      --gold: #b7791f;
      --rose: #b42318;
      --green: #16794c;
      --shadow: 0 18px 42px rgba(18, 32, 46, .14);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif;
      background: linear-gradient(180deg, #f7fbff 0%, #fffdf8 44%, #eef6f4 100%);
    }
    .hero {
      min-height: 66vh;
      display: grid;
      grid-template-columns: minmax(280px, 1fr) minmax(300px, 520px);
      gap: 28px;
      align-items: center;
      padding: 34px clamp(18px, 5vw, 64px) 28px;
      background:
        linear-gradient(90deg, rgba(255, 253, 248, .90), rgba(255, 253, 248, .62)),
        url("../../assets/brand/focaf_family_law_llm_brand_kit/assets/social/focaf-family-law-llm-social-card.png") center right / cover no-repeat;
      border-bottom: 1px solid var(--line);
    }
    .brand-lockup { max-width: 320px; height: auto; margin-bottom: 26px; }
    h1 { margin: 0 0 14px; font-size: clamp(36px, 5vw, 58px); line-height: 1.02; font-weight: 900; }
    .lede { max-width: 740px; margin: 0; font-size: 18px; line-height: 1.55; color: #2d3d4f; }
    .status-strip { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 22px; }
    .chip { display: inline-flex; align-items: center; min-height: 32px; padding: 7px 10px; border: 1px solid var(--line); border-radius: 8px; background: rgba(255, 255, 255, .86); font-size: 12px; font-weight: 800; }
    .chip.good { border-color: #b7e2cb; color: var(--green); }
    .chip.block { border-color: #f6c7c1; color: var(--rose); }
    .ask-card { background: rgba(255,255,255,.94); border: 1px solid var(--line); border-radius: 8px; box-shadow: var(--shadow); padding: 18px; }
    label { display: block; margin: 0 0 6px; font-size: 13px; font-weight: 900; }
    select, textarea, button { font: inherit; }
    select, textarea { width: 100%; border: 1px solid #b8c4d2; border-radius: 8px; background: white; padding: 10px 11px; color: var(--ink); }
    textarea { min-height: 116px; resize: vertical; line-height: 1.45; }
    select:focus, textarea:focus { outline: 3px solid rgba(11, 118, 109, .18); border-color: var(--river); }
    .field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .button-row { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }
    button { border: 0; border-radius: 8px; padding: 10px 13px; cursor: pointer; font-weight: 900; }
    .primary { background: var(--navy); color: white; }
    .secondary { background: #e7f2ef; color: #075f58; }
    .page-band { padding: 28px clamp(18px, 5vw, 64px); }
    .section-heading { margin: 0 0 14px; font-size: 26px; }
    .workspace { display: grid; grid-template-columns: minmax(280px, .86fr) minmax(320px, 1.14fr); gap: 18px; align-items: start; }
    .panel { background: rgba(255,255,255,.92); border: 1px solid var(--line); border-radius: 8px; padding: 18px; box-shadow: var(--shadow); }
    .role-pathway { border-left: 4px solid var(--river); padding: 10px 12px; background: #eef8f6; border-radius: 8px; font-weight: 800; }
    .answer { font-size: 17px; line-height: 1.62; color: #203044; }
    .source-grid, .blocker-grid, .action-grid { display: grid; gap: 10px; }
    .source-card, .blocker-card, .action-card { border: 1px solid var(--line); border-radius: 8px; background: white; padding: 12px; }
    .source-card strong, .blocker-card strong, .action-card strong { display: block; margin-bottom: 5px; }
    .source-card small { color: var(--muted); display: block; line-height: 1.4; }
    .red-flags { display: flex; flex-wrap: wrap; gap: 8px; }
    .red-flag-chip { display: inline-flex; border-radius: 8px; padding: 7px 9px; background: #fff1ef; border: 1px solid #f6c7c1; color: var(--rose); font-size: 12px; font-weight: 900; }
    table { width: 100%; border-collapse: collapse; background: white; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
    th, td { text-align: left; padding: 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
    th { background: #eef3f8; font-size: 12px; text-transform: uppercase; color: #334155; }
    tr:last-child td { border-bottom: 0; }
    .footer-note { color: var(--muted); font-size: 13px; line-height: 1.5; }
    @media (max-width: 920px) {
      .hero, .workspace, .field-grid { grid-template-columns: 1fr; }
      .hero { min-height: auto; background-position: center top; }
    }
  </style>
</head>
<body data-workbench-version="__VERSION__">
  <header class="hero">
    <div>
      <img class="brand-lockup" src="../../assets/brand/focaf_family_law_llm_brand_kit/assets/logo/focaf-family-law-llm-horizontal.svg" alt="FOCAF Maine Family Law LLM">
      <h1>Family Justice Workbench</h1>
      <p class="lede">A local, source-card-first Maine family-law packet for safer intake, reviewer handoff, and filing-gate explanations.</p>
      <div class="status-strip" aria-label="Workbench status">
        <span class="chip good">review_required=true</span>
        <span class="chip block">filing_ready=false</span>
        <span class="chip">version=__VERSION__</span>
        <span class="chip">offline deterministic evidence</span>
      </div>
    </div>
    <section class="ask-card" id="ask-section" aria-labelledby="ask-title">
      <h2 id="ask-title" class="section-heading">Ask</h2>
      <div class="field-grid">
        <div>
          <label for="sample">Pathway</label>
          <select id="sample"></select>
        </div>
        <div>
          <label for="style">Output</label>
          <select id="style">
            <option>plain_language</option>
            <option>checklist</option>
            <option>source_card_table</option>
            <option>reviewer_handoff</option>
            <option>missing_information</option>
            <option>professional_boundary</option>
          </select>
        </div>
      </div>
      <div style="margin-top: 12px">
        <label for="question">Question</label>
        <textarea id="question"></textarea>
      </div>
      <div class="button-row">
        <button class="primary" type="button" id="ask-button">Ask</button>
        <button class="secondary" type="button" id="review-button">Review</button>
        <button class="secondary" type="button" id="packet-button">Packet</button>
      </div>
    </section>
  </header>
  <main>
    <section class="page-band" id="review-section" aria-labelledby="review-title">
      <h2 id="review-title" class="section-heading">Review</h2>
      <div class="workspace">
        <article class="panel">
          <div class="role-pathway" id="role-pathway"></div>
          <div class="answer" id="answer"></div>
          <div class="red-flags" id="red-flags" aria-label="Red flags"></div>
        </article>
        <article class="panel">
          <h3>Source Cards</h3>
          <div class="source-grid" id="source-cards"></div>
        </article>
      </div>
    </section>
    <section class="page-band" aria-labelledby="matrix-title">
      <h2 id="matrix-title" class="section-heading">Authority Matrix</h2>
      <div class="authority-matrix-preview" id="authority-matrix-preview"></div>
    </section>
    <section class="page-band" id="next-steps-section" aria-labelledby="next-title">
      <h2 id="next-title" class="section-heading">Next Steps</h2>
      <div class="workspace">
        <article class="panel">
          <h3>Blockers</h3>
          <div class="blocker-grid" id="blockers"></div>
        </article>
        <article class="panel">
          <h3>Actions</h3>
          <div class="action-grid" id="actions"></div>
        </article>
      </div>
      <p class="footer-note">Not legal advice. No attorney-client relationship. Official Maine authority and verified source registry data outrank model memory.</p>
    </section>
  </main>
  <script>
    const packets = __PACKETS_JSON__;
    const seedPacket = __SEED_JSON__;
    function esc(value) {
      return String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
    }
    function activePacket() {
      return packets[Number(document.getElementById('sample').value || 0)] || seedPacket;
    }
    function renderTable(rows) {
      const body = rows.map(row => `<tr><td>${esc(row.issue)}</td><td>${esc(row.authority)}</td><td>${esc(row.freshness_status)}</td><td>${esc(row.verification_task)}</td></tr>`).join('');
      return `<table><thead><tr><th>Issue</th><th>Authority</th><th>Freshness</th><th>Task</th></tr></thead><tbody>${body}</tbody></table>`;
    }
    function render(packet) {
      document.getElementById('question').value = packet.question;
      document.getElementById('style').value = packet.requested_output_style;
      document.getElementById('role-pathway').textContent = packet.audience_label + ': ' + packet.role_specific_pathway;
      document.getElementById('answer').innerHTML = `<p>${esc(packet.plain_language_answer)}</p>`;
      document.getElementById('red-flags').innerHTML = packet.red_flags.map(flag => `<span class="red-flag-chip">${esc(flag.label)}</span>`).join('');
      document.getElementById('source-cards').innerHTML = packet.source_cards.map(card => `<div class="source-card"><strong>${esc(card.title)}</strong><small>${esc(card.canonical_citation)} | ${esc(card.freshness_status)}</small><p>${esc(card.registry_note)}</p></div>`).join('');
      document.getElementById('authority-matrix-preview').innerHTML = renderTable(packet.authority_matrix_preview);
      document.getElementById('blockers').innerHTML = packet.why_not_filing_ready.map(blocker => `<div class="blocker-card"><strong>${esc(blocker.category)}</strong><p>${esc(blocker.message)}</p></div>`).join('');
      document.getElementById('actions').innerHTML = packet.next_best_actions.slice(0, 8).map(action => `<div class="action-card"><strong>${esc(action.label)}</strong><p>${esc(action.reason)}</p></div>`).join('');
    }
    function populateSamples() {
      const select = document.getElementById('sample');
      select.innerHTML = packets.map((packet, index) => `<option value="${index}">${esc(packet.audience_label)} | ${esc(packet.issue_labels[0])}</option>`).join('');
    }
    document.getElementById('sample').addEventListener('change', () => render(activePacket()));
    document.getElementById('ask-button').addEventListener('click', () => render(activePacket()));
    document.getElementById('review-button').addEventListener('click', () => document.getElementById('review-section').scrollIntoView());
    document.getElementById('packet-button').addEventListener('click', async () => navigator.clipboard.writeText(JSON.stringify(activePacket(), null, 2)));
    populateSamples();
    render(seedPacket);
  </script>
</body>
</html>"""
    return (
        html_doc.replace("__VERSION__", VERSION)
        .replace("__PACKETS_JSON__", packets_json)
        .replace("__SEED_JSON__", seed_json)
    )


def write_evidence_outputs(output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    packets = build_sample_packets()
    html_text = render_workbench_html(packets)
    packet_path = output_dir / "family_justice_workbench_v205_packet.json"
    audit_path = output_dir / "family_justice_workbench_v205_audit.json"
    html_path = output_dir / "family_justice_workbench_v205.html"
    summary_path = output_dir / "family_justice_workbench_v205_test_summary.json"
    packet_payload = {
        "schema": PACKET_SCHEMA,
        "version": VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "packets": packets,
        "claims": {
            "legal_advice": False,
            "filing_ready": False,
            "current_law_certified": False,
            "private_data_packaged": False,
            "production_ga": False,
        },
    }
    audit = build_audit(packets, html_text)
    summary = build_test_summary(packets, html_text)
    packet_path.write_text(json.dumps(packet_payload, indent=2, sort_keys=True), encoding="utf-8")
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "packet": str(packet_path),
        "audit": str(audit_path),
        "html": str(html_path),
        "test_summary": str(summary_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build v2.05 Family Justice Workbench packets and evidence")
    parser.add_argument("--question", default="What information should I gather before asking a Maine family-law question?")
    parser.add_argument("--audience", default="parent", choices=sorted(AUDIENCES))
    parser.add_argument("--posture", default="unknown", choices=sorted(POSTURES))
    parser.add_argument("--facts-context", default="")
    parser.add_argument("--output-style", default="plain_language", choices=sorted(OUTPUT_STYLES))
    parser.add_argument("--output", default="")
    parser.add_argument("--html", default="")
    parser.add_argument("--evidence-dir", default="")
    args = parser.parse_args(argv)

    if args.evidence_dir:
        outputs = write_evidence_outputs(Path(args.evidence_dir))
        print(json.dumps({"status": "pass", "version": VERSION, "outputs": outputs}, indent=2, sort_keys=True))
        return 0

    packet = build_workbench_packet(
        args.question,
        audience=args.audience,
        posture=args.posture,
        facts_context=args.facts_context,
        requested_output_style=args.output_style,
    )
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(packet, indent=2, sort_keys=True), encoding="utf-8")
    else:
        print(json.dumps(packet, indent=2, sort_keys=True))
    if args.html:
        html_path = Path(args.html)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(render_workbench_html([packet]), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
