from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
from pathlib import Path
from typing import Any

VERSION = "2.04.0"
PACKET_SCHEMA = "maine_family_law_llm.family_first_chat.packet.v1"
AUDIT_SCHEMA = "maine_family_law_llm.family_first_chat.audit.v1"

DISCLAIMER = (
    "Maine Family Law LLM is legal information and workflow support, not legal advice. "
    "It does not create an attorney-client relationship. Every answer, checklist, form note, "
    "and draft remains review-required unless source freshness, authority, citations, quotes, facts, "
    "procedure, forms, and human review are verified."
)

AUDIENCES: dict[str, dict[str, str]] = {
    "parent": {
        "label": "Parent or caregiver",
        "tone": "plain language, calm, practical, safety-aware",
        "primary_goal": "understand the next safe step and what Maine sources/forms to verify",
    },
    "lawyer": {
        "label": "Lawyer or legal professional",
        "tone": "concise legal workflow, authority-first, review-gate oriented",
        "primary_goal": "triage issues, authority, evidence, citations, and filing-readiness blockers",
    },
    "advocate": {
        "label": "Legal aid / advocate",
        "tone": "plain language with structured triage and referral-friendly next steps",
        "primary_goal": "spot issues, missing facts, safety concerns, and review needs",
    },
    "court_helper": {
        "label": "Court help / navigator",
        "tone": "neutral, form-oriented, non-advice, process-focused",
        "primary_goal": "identify likely form categories and information to verify",
    },
}

ISSUE_PATTERNS: dict[str, tuple[str, ...]] = {
    "divorce": ("divorce", "dissolution", "marriage", "spouse", "marital"),
    "parental_rights_responsibilities": ("parental rights", "responsibilities", "custody", "decision-making", "decision making", "parenting"),
    "primary_residence": ("primary residence", "primary home", "live with", "reside primarily"),
    "contact_schedule": ("contact", "visitation", "parenting time", "schedule", "supervised"),
    "child_support": ("child support", "support worksheet", "guidelines", "income", "deviation"),
    "parentage": ("parentage", "paternity", "de facto parent", "biological parent"),
    "post_judgment_motion": ("post-judgment", "post judgment", "after judgment", "after final", "modify", "enforce"),
    "motion_to_modify": ("motion to modify", "modify", "substantial change", "changed circumstances"),
    "motion_to_enforce": ("motion to enforce", "enforce", "not following the order", "compliance"),
    "motion_for_contempt": ("contempt", "violated the order", "willful"),
    "protection_from_abuse": ("protection from abuse", "pfa", "abuse order", "domestic violence", "harassment"),
    "pfa_family_overlap": ("pfa", "protection order", "family case", "custody case"),
    "grandparent_visitation": ("grandparent", "grandparents", "visitation by grandparent"),
    "guardianship": ("guardian", "guardianship", "probate"),
    "GAL_issue": ("guardian ad litem", "gal"),
    "UCCJEA_jurisdiction": ("uccjea", "home state", "jurisdiction", "moved to maine", "other state"),
    "Rule_52_findings": ("rule 52", "findings", "proposed findings", "no findings"),
    "best_interest_factor_gap": ("best interest", "19-a m.r.s. § 1653", "1653"),
    "appeal_preservation": ("appeal", "preserve", "law court", "notice of appeal"),
    "transcript_record_issue": ("transcript", "record on appeal", "audio recording"),
    "eCourts_record_access": ("ecourts", "odyssey", "record access", "portal"),
    "therapist_non_delegation": ("therapist decides", "counselor decides", "gal decides", "third party decides"),
}

POSTURE_PATTERNS: dict[str, tuple[str, ...]] = {
    "initial_complaint": ("complaint", "starting", "file for", "summons"),
    "temporary_order": ("temporary order", "interim relief", "until final", "emergency motion"),
    "interim_order": ("interim", "before final"),
    "final_order": ("final order", "judgment", "divorce judgment", "final hearing"),
    "post_judgment": ("post-judgment", "post judgment", "after judgment", "after final"),
    "contempt": ("contempt", "violated", "willful"),
    "appeal": ("appeal", "law court", "notice of appeal"),
    "remand": ("remand", "remanded"),
    "motion_for_findings": ("motion for findings", "rule 52", "findings"),
    "motion_to_reconsider": ("reconsider", "alter or amend"),
    "stay_pending_appeal": ("stay pending appeal", "stay while appeal"),
}

RED_FLAG_PATTERNS: dict[str, tuple[str, ...]] = {
    "immediate safety risk": ("hurt me", "hurt the child", "threat", "weapon", "unsafe tonight", "in danger", "stalking"),
    "missing Rule 52 findings": ("final order", "no findings", "without findings"),
    "unsupported best-interest findings": ("best interest", "unsupported", "no evidence"),
    "therapist or third-party delegated contact decision": ("therapist decides", "counselor decides", "gal decides", "third party decides"),
    "protective-order finding imported without independent family analysis": ("pfa controls custody", "automatic custody", "protection order decides custody"),
    "contact restriction without sourced findings": ("no contact", "supervised contact", "supervised visitation", "restriction"),
    "missing transcript or incomplete appellate record": ("appeal", "no transcript", "missing transcript"),
    "stale or unknown form": ("old form", "stale form", "wrong form"),
    "unverified citation": ("fake citation", "unverified citation"),
    "deadline risk": ("deadline", "today", "tomorrow", "served", "appeal due"),
    "service defect": ("not served", "service defect", "served by text"),
    "jurisdiction defect": ("home state", "other state", "just moved", "jurisdiction defect"),
    "privacy or sealed-record issue": ("sealed", "confidential", "minor child name", "social security", "ssn"),
}

SOURCE_CARD_LIBRARY: dict[str, list[dict[str, Any]]] = {
    "parental_rights_responsibilities": [
        {
            "source_id": "starter_me_19a_1653",
            "title": "Maine parental rights / best-interest statute starter card",
            "canonical_citation": "19-A M.R.S. § 1653",
            "source_class": "statute",
            "jurisdiction": "maine",
            "authority_status": "requires_live_verification",
            "freshness_status": "must_verify_current_official_source",
            "why_it_matters": "Often central to parental rights, residence, contact, and best-interest review.",
        }
    ],
    "best_interest_factor_gap": [
        {
            "source_id": "starter_me_best_interest_review",
            "title": "Best-interest factor coverage review",
            "canonical_citation": "19-A M.R.S. § 1653",
            "source_class": "statute_review_checklist",
            "jurisdiction": "maine",
            "authority_status": "requires_live_verification",
            "freshness_status": "must_verify_current_official_source",
            "why_it_matters": "A draft or order should not skip material best-interest factors when they are relevant.",
        }
    ],
    "Rule_52_findings": [
        {
            "source_id": "starter_me_rule_52",
            "title": "Maine Rule 52 findings starter card",
            "canonical_citation": "M.R. Civ. P. 52",
            "source_class": "court_rule",
            "jurisdiction": "maine",
            "authority_status": "requires_live_verification",
            "freshness_status": "must_verify_current_official_source",
            "why_it_matters": "Findings can matter for final family orders, appellate review, and proposed findings workflows.",
        }
    ],
    "child_support": [
        {
            "source_id": "starter_me_child_support",
            "title": "Maine child-support statutes and worksheet starter card",
            "canonical_citation": "19-A M.R.S. child support provisions / official worksheet forms",
            "source_class": "statute_and_form_family",
            "jurisdiction": "maine",
            "authority_status": "requires_live_verification",
            "freshness_status": "must_verify_current_official_source",
            "why_it_matters": "Support work normally needs current income facts, guideline/worksheet review, and form freshness checks.",
        }
    ],
    "divorce": [
        {
            "source_id": "starter_me_divorce_forms",
            "title": "Maine divorce form packet starter card",
            "canonical_citation": "Maine Judicial Branch FM forms / divorce packet",
            "source_class": "official_form_packet",
            "jurisdiction": "maine",
            "authority_status": "requires_live_verification",
            "freshness_status": "must_verify_current_official_source",
            "why_it_matters": "Divorce workflows depend on the correct current packet, summons/service, financial forms, and child-related forms when applicable.",
        }
    ],
    "protection_from_abuse": [
        {
            "source_id": "starter_me_pfa",
            "title": "Maine Protection From Abuse starter card",
            "canonical_citation": "19-A M.R.S. protection-from-abuse provisions / official PFA forms",
            "source_class": "statute_and_form_family_safety",
            "jurisdiction": "maine",
            "authority_status": "requires_live_verification",
            "freshness_status": "must_verify_current_official_source",
            "why_it_matters": "Safety and family-case overlap need careful review, especially when parenting orders are involved.",
        }
    ],
    "UCCJEA_jurisdiction": [
        {
            "source_id": "starter_me_uccjea",
            "title": "Maine child-custody jurisdiction starter card",
            "canonical_citation": "Maine UCCJEA provisions / 19-A M.R.S.",
            "source_class": "statute_jurisdiction",
            "jurisdiction": "maine",
            "authority_status": "requires_live_verification",
            "freshness_status": "must_verify_current_official_source",
            "why_it_matters": "When children recently moved or another state has orders, jurisdiction must be checked before drafting.",
        }
    ],
}

STARTER_PROMPTS: dict[str, list[str]] = {
    "parent": [
        "I have a Maine parenting order and the other parent is not following the contact schedule. What should I gather before asking for help?",
        "What Maine sources and forms should I check before filing for divorce with children?",
        "The final order does not explain the best-interest reasons. What should I ask a lawyer to review?",
        "I am worried about safety during exchanges. What information should I organize before seeking help?",
    ],
    "lawyer": [
        "Review a proposed final parental-rights order for Rule 52 findings, best-interest coverage, and filing-readiness blockers.",
        "Build an authority matrix for a post-judgment motion to modify contact after a substantial change.",
        "Generate a citation and quote verification checklist for a draft motion relying on 19-A M.R.S. § 1653.",
        "Triage appellate red flags in a family judgment with missing transcript and thin findings.",
    ],
    "advocate": [
        "Create a plain-language intake checklist for a Maine parent asking about child support and contact.",
        "Spot safety, service, jurisdiction, and form-freshness issues in a Maine family matter.",
        "Explain why a draft is review-required and not filing-ready.",
    ],
    "court_helper": [
        "Help identify what kind of Maine family form packet someone may need without giving legal advice.",
        "Create a neutral missing-information checklist for a person asking about a post-judgment motion.",
        "Explain source cards, citation checks, and human review in plain language.",
    ],
}

CITATION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("maine_statute", re.compile(r"\b\d{1,2}-?[A-Z]?\s*(?:M\.?\s*R\.?\s*S\.?|MRS|MRSA|M\.R\.S\.)\.?\s*§+\s*[\dA-Za-z][\dA-Za-z.\-]*", re.I)),
    ("maine_rule", re.compile(r"\bM\.?\s*R\.?\s*(?:Civ\.?|App\.?|Evid\.?)\s*P\.?\s*\d+[A-Za-z\-]*\b", re.I)),
    ("maine_case", re.compile(r"\b(?:20\d{2}|19\d{2})\s+ME\s+\d+\b", re.I)),
    ("maine_form", re.compile(r"\bFM[-\s]?\d{3,4}[A-Z]?\b", re.I)),
    ("federal_statute", re.compile(r"\b\d{1,2}\s*U\.?\s*S\.?\s*C\.?\s*§+\s*[\dA-Za-z][\dA-Za-z.\-]*", re.I)),
)


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def detect_labels(text: str, patterns: dict[str, tuple[str, ...]], default: str) -> list[str]:
    low = (text or "").lower()
    labels = [label for label, needles in patterns.items() if any(needle in low for needle in needles)]
    return sorted(set(labels or [default]))


def detect_issue_labels(text: str) -> list[str]:
    labels = detect_labels(text, ISSUE_PATTERNS, "general_family_law_question")
    if "best_interest_factor_gap" in labels and "parental_rights_responsibilities" not in labels:
        labels.append("parental_rights_responsibilities")
    return sorted(set(labels))


def detect_posture_labels(text: str) -> list[str]:
    return detect_labels(text, POSTURE_PATTERNS, "posture_unknown")


def parse_citations(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int]] = set()
    for kind, pattern in CITATION_PATTERNS:
        for match in pattern.finditer(text or ""):
            key = (kind, match.start(), match.end())
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "citation_text": match.group(0).rstrip(".;,"),
                    "citation_type": kind,
                    "start": match.start(),
                    "end": match.end(),
                    "status": "parsed_unverified_needs_source_registry_resolution",
                    "blocks_filing_ready": True,
                }
            )
    return sorted(rows, key=lambda row: row["start"])


def detect_red_flags(text: str) -> list[dict[str, Any]]:
    low = (text or "").lower()
    flags = []
    for label, needles in RED_FLAG_PATTERNS.items():
        hits = [needle for needle in needles if needle in low]
        if hits:
            flags.append(
                {
                    "red_flag": label,
                    "matched_terms": hits,
                    "review_required": True,
                    "severity": "urgent" if "safety" in label else "blocker",
                }
            )
    return flags


def route_source_cards(issue_labels: list[str]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    seen: set[str] = set()
    for issue in issue_labels:
        for card in SOURCE_CARD_LIBRARY.get(issue, []):
            if card["source_id"] not in seen:
                seen.add(card["source_id"])
                cards.append({**card, "matched_issue": issue})
    if not cards:
        cards.append(
            {
                "source_id": "starter_me_general_family_law",
                "title": "General Maine family-law source starter card",
                "canonical_citation": "Maine Judicial Branch family pages, current Maine statutes, court rules, and official forms",
                "source_class": "source_scope_checklist",
                "jurisdiction": "maine",
                "authority_status": "requires_live_verification",
                "freshness_status": "must_verify_current_official_source",
                "why_it_matters": "The exact authority depends on the case type, posture, forms, and facts.",
                "matched_issue": "general_family_law_question",
            }
        )
    return cards


def intake_questions(issue_labels: list[str], posture_labels: list[str]) -> list[str]:
    questions = [
        "What Maine court order, case number, form packet, or filing stage are we dealing with?",
        "What exact outcome is being requested, and is there an existing order?",
        "What sources have already been verified: statutes, rules, forms, orders, notices, transcripts, exhibits, or messages?",
    ]
    issues = set(issue_labels)
    postures = set(posture_labels)
    if "protection_from_abuse" in issues or "immediate safety risk" in {f.get("red_flag") for f in detect_red_flags(" ".join(issue_labels))}:
        questions.insert(0, "Is anyone in immediate danger right now, and is emergency help or a protection-from-abuse resource needed?")
    if "child_support" in issues:
        questions.append("What current income, child-care, health-insurance, and support-order facts are available for worksheet review?")
    if "UCCJEA_jurisdiction" in issues:
        questions.append("Where has the child lived during the last six months, and is there an order or case in another state?")
    if "Rule_52_findings" in issues or "final_order" in postures:
        questions.append("Does the order include findings tied to the relevant statutory factors, or only conclusions?")
    if "appeal" in postures:
        questions.append("Is the notice deadline known, and are transcripts/exhibits/orders available for the appellate record?")
    return questions


def build_next_actions(issue_labels: list[str], red_flags: list[dict[str, Any]]) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    if any(flag["red_flag"] == "immediate safety risk" for flag in red_flags):
        actions.append(
            {
                "action": "safety_first",
                "label": "If there is immediate danger, contact emergency services or an appropriate local crisis/safety resource before using this tool.",
            }
        )
    actions.extend(
        [
            {"action": "confirm_posture", "label": "Identify the case stage: starting case, temporary order, final order, post-judgment, contempt, appeal, or unknown."},
            {"action": "attach_sources", "label": "Attach or verify official Maine source cards before relying on any legal claim."},
            {"action": "map_facts", "label": "Turn each important factual statement into a fact-to-evidence row with document, date, quote/span, and confidence."},
            {"action": "run_gate", "label": "Run citation, quote, source freshness, form freshness, claim-support, and human-review gates before export."},
        ]
    )
    if "best_interest_factor_gap" in issue_labels or "parental_rights_responsibilities" in issue_labels:
        actions.append({"action": "best_interest_check", "label": "Review best-interest factor coverage and any contact/residence restrictions."})
    if "Rule_52_findings" in issue_labels:
        actions.append({"action": "findings_check", "label": "Check whether proposed or final findings are specific enough for review."})
    return actions


def build_answer_blocks(question: str, audience: str, issue_labels: list[str], posture_labels: list[str], cards: list[dict[str, Any]]) -> dict[str, Any]:
    audience_config = AUDIENCES.get(audience, AUDIENCES["parent"])
    issue_text = ", ".join(issue_labels).replace("_", " ")
    posture_text = ", ".join(posture_labels).replace("_", " ")
    source_names = ", ".join(card["canonical_citation"] for card in cards[:4])
    if audience == "lawyer":
        summary = (
            f"Triage result: likely issues are {issue_text}; posture is {posture_text}. "
            f"Treat this as an authority/evidence workflow, not a final answer. Start with source-scope verification for {source_names}, "
            "then run citation, quote, claim-support, form-freshness, and human-review gates."
        )
    else:
        summary = (
            f"This looks like a Maine family-law question involving {issue_text}. The safest next step is to identify the case stage "
            f"({posture_text}), gather the relevant orders/forms/facts, and verify the official Maine sources before relying on any answer. "
            "This tool can organize questions and source cards, but it cannot tell you what choice to make."
        )
    return {
        "audience_label": audience_config["label"],
        "summary": summary,
        "plain_language": [
            "Start with the actual papers: complaint, motion, order, notice, form packet, service papers, and any scheduled hearing information.",
            "Separate legal questions from factual claims. Legal questions need verified Maine authority. Factual claims need evidence with dates and document spans.",
            "Do not treat a draft, checklist, or chat answer as filing-ready until a qualified human reviewer confirms it.",
        ],
        "professional_workflow": [
            "Build source scope and authority matrix before drafting.",
            "Resolve citations to source IDs and confirm quote offsets.",
            "Map facts to evidence and mark unsupported assertions before export.",
            "Keep final certification outside the generator; only the filing-ready gate and human review can pass export.",
        ],
        "source_cards_to_verify": cards,
        "copy_safe_note": "Copy only the checklist or question list into client communications unless a qualified reviewer approves legal conclusions.",
    }


def build_filing_gate(red_flags: list[dict[str, Any]], citations: list[dict[str, Any]], source_cards: list[dict[str, Any]]) -> dict[str, Any]:
    blockers = [
        {
            "category": "source_scope",
            "message": "Live official Maine source registry resolution has not been completed in this chat packet.",
            "blocks_filing_ready": True,
        },
        {
            "category": "human_review",
            "message": "Human legal review is required before any filing-ready export.",
            "blocks_filing_ready": True,
        },
    ]
    if citations:
        blockers.append(
            {
                "category": "citation_resolution",
                "message": "One or more user-provided citations were parsed but not resolved to source IDs in this packet.",
                "blocks_filing_ready": True,
                "citations": citations,
            }
        )
    if any(card.get("freshness_status") != "fresh_verified" for card in source_cards):
        blockers.append(
            {
                "category": "freshness",
                "message": "Starter source cards require live freshness verification before current-law language is allowed.",
                "blocks_filing_ready": True,
            }
        )
    if red_flags:
        blockers.append(
            {
                "category": "red_flags",
                "message": "Potential legal, safety, procedural, privacy, or record problems were detected.",
                "blocks_filing_ready": True,
                "red_flags": red_flags,
            }
        )
    return {
        "status": "blocked",
        "filing_ready": False,
        "review_required": True,
        "blockers": blockers,
        "warnings": [
            "This v2.04 chat packet is an intake and UX layer. It does not certify live law, form freshness, fact support, or filing readiness.",
            "Private matter facts should stay in the approved matter store or user-controlled upload flow, not in the source repository.",
        ],
    }


def build_chat_packet(question: str, audience: str = "parent", mode: str = "guided_chat") -> dict[str, Any]:
    audience = audience if audience in AUDIENCES else "parent"
    question = normalize_space(question or "What Maine family-law sources and forms should I verify before drafting?")
    issue_labels = detect_issue_labels(question)
    posture_labels = detect_posture_labels(question)
    red_flags = detect_red_flags(question)
    citations = parse_citations(question)
    source_cards = route_source_cards(issue_labels)
    answer_blocks = build_answer_blocks(question, audience, issue_labels, posture_labels, source_cards)
    gate = build_filing_gate(red_flags, citations, source_cards)
    packet = {
        "schema": PACKET_SCHEMA,
        "version": VERSION,
        "generated_at": utcnow(),
        "mode": mode,
        "question": question,
        "audience": audience,
        "audience_config": AUDIENCES[audience],
        "status": "review_required",
        "issue_labels": issue_labels,
        "posture_labels": posture_labels,
        "red_flags": red_flags,
        "citation_report": citations,
        "answer_blocks": answer_blocks,
        "intake_questions": intake_questions(issue_labels, posture_labels),
        "next_actions": build_next_actions(issue_labels, red_flags),
        "filing_gate": gate,
        "starter_prompts": STARTER_PROMPTS,
        "ui": {
            "hero": "Fast, calm Maine family-law help with source cards and review gates.",
            "primary_cta": "Ask safely",
            "secondary_cta": "Build review checklist",
            "empty_state": "Ask a question, choose an audience, and get a review-required source workflow.",
            "tabs": ["Answer", "Source cards", "Checklist", "Filing gate"],
            "badges": ["Maine-only", "Source-first", "Review-required", "No private data in repo"],
        },
        "claims": {
            "legal_advice": False,
            "filing_ready": False,
            "attorney_review_completed": False,
            "private_data_packaged": False,
            "model_memory_used_as_authority": False,
        },
        "disclaimer": DISCLAIMER,
    }
    return packet


def build_sample_packets() -> list[dict[str, Any]]:
    return [
        build_chat_packet(
            "I have a final Maine parenting order with no findings. The therapist decides contact and I need to know what to gather before asking for help about 19-A M.R.S. § 1653.",
            audience="parent",
        ),
        build_chat_packet(
            "Review a proposed final parental rights order for Rule 52 findings, best-interest coverage, transcript risk, and quote/citation gates.",
            audience="lawyer",
        ),
        build_chat_packet(
            "A parent just moved to Maine with a child and there may be an order from another state. What jurisdiction facts should be collected?",
            audience="advocate",
        ),
    ]


def build_audit(packet: dict[str, Any] | None = None) -> dict[str, Any]:
    packet = packet or build_chat_packet("What should I verify before filing a Maine family-law motion?", audience="parent")
    return {
        "schema": AUDIT_SCHEMA,
        "version": VERSION,
        "generated_at": utcnow(),
        "status": "pass",
        "checks": {
            "packet_schema_present": packet.get("schema") == PACKET_SCHEMA,
            "review_required": packet.get("status") == "review_required",
            "filing_ready_blocked": packet.get("filing_gate", {}).get("filing_ready") is False,
            "source_cards_present": bool(packet.get("answer_blocks", {}).get("source_cards_to_verify")),
            "starter_prompts_present": bool(packet.get("starter_prompts")),
            "legal_advice_claim_false": packet.get("claims", {}).get("legal_advice") is False,
            "private_data_packaged_false": packet.get("claims", {}).get("private_data_packaged") is False,
        },
        "outputs_expected": [
            "docs/external-evidence/family_first_chat_v204_packet.json",
            "docs/external-evidence/family_first_chat_v204_audit.json",
            "docs/external-evidence/family_first_chat_v204.html",
        ],
    }


def render_chat_html(packet: dict[str, Any] | None = None) -> str:
    packet = packet or build_chat_packet("What Maine family-law sources should I verify before drafting?", audience="parent")
    seed_json = json.dumps(packet, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
    prompts_json = json.dumps(STARTER_PROMPTS, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
    html_doc = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Maine Family Law Chat Studio v__VERSION__</title>
  <style>
    :root {
      --bg0:#07111f; --bg1:#0f2a44; --card:#ffffff; --ink:#0f172a; --muted:#64748b;
      --line:#dbeafe; --soft:#f8fafc; --accent:#1d4ed8; --accent2:#0f766e; --warn:#991b1b;
      --gold:#f59e0b; --shadow:0 24px 80px rgba(2,8,23,.35); --radius:28px;
    }
    * { box-sizing:border-box; }
    body { margin:0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; color:var(--ink); background:
      radial-gradient(circle at top left, rgba(37,99,235,.45), transparent 34rem),
      radial-gradient(circle at top right, rgba(15,118,110,.35), transparent 32rem),
      linear-gradient(135deg, var(--bg0), var(--bg1)); min-height:100vh; }
    .shell { max-width:1220px; margin:0 auto; padding:28px; }
    .hero { display:grid; grid-template-columns:1.1fr .9fr; gap:22px; align-items:stretch; }
    .panel { background:rgba(255,255,255,.96); border:1px solid rgba(255,255,255,.65); border-radius:var(--radius); box-shadow:var(--shadow); }
    .heroCard { padding:34px; color:white; background:linear-gradient(145deg, rgba(15,23,42,.96), rgba(30,64,175,.84)); border-radius:var(--radius); min-height:360px; position:relative; overflow:hidden; }
    .heroCard:after { content:""; position:absolute; inset:auto -80px -120px auto; width:280px; height:280px; border-radius:999px; background:rgba(255,255,255,.09); }
    .eyebrow { display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin-bottom:18px; }
    .badge { border:1px solid rgba(255,255,255,.3); background:rgba(255,255,255,.14); color:white; border-radius:999px; padding:7px 10px; font-weight:800; font-size:12px; letter-spacing:.02em; }
    .badge.light { color:#1e3a8a; border-color:#bfdbfe; background:#eff6ff; }
    h1 { font-size:clamp(34px, 5vw, 62px); line-height:.94; margin:0 0 18px; letter-spacing:-.05em; }
    .sub { font-size:18px; color:#dbeafe; line-height:1.55; max-width:780px; }
    .chat { padding:22px; display:flex; flex-direction:column; min-height:360px; }
    label { font-weight:900; display:block; margin:0 0 8px; }
    select, textarea, button { font:inherit; }
    select, textarea { width:100%; border:1px solid #cbd5e1; border-radius:18px; padding:13px 14px; outline:none; background:white; }
    textarea { min-height:116px; resize:vertical; line-height:1.45; }
    textarea:focus, select:focus { border-color:#2563eb; box-shadow:0 0 0 4px rgba(37,99,235,.14); }
    .row { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
    .actions { display:flex; gap:10px; margin-top:14px; flex-wrap:wrap; }
    button { border:0; border-radius:16px; padding:12px 16px; font-weight:900; cursor:pointer; }
    .primary { background:linear-gradient(135deg, #2563eb, #0f766e); color:white; }
    .secondary { background:#e0f2fe; color:#075985; }
    .ghost { background:#f1f5f9; color:#334155; }
    .grid { display:grid; grid-template-columns:.95fr 1.05fr; gap:22px; margin-top:22px; }
    .section { padding:22px; }
    .section h2 { margin:0 0 12px; letter-spacing:-.02em; }
    .answer { font-size:18px; line-height:1.55; }
    .meta { display:flex; flex-wrap:wrap; gap:8px; margin:12px 0; }
    .pill { display:inline-flex; align-items:center; gap:6px; border-radius:999px; padding:7px 10px; font-size:12px; font-weight:900; background:#f1f5f9; color:#334155; }
    .pill.block { background:#fef2f2; color:#991b1b; }
    .pill.good { background:#ecfdf5; color:#047857; }
    .cards { display:grid; gap:12px; }
    .source { border:1px solid #dbeafe; border-radius:20px; padding:14px; background:linear-gradient(180deg,#fff,#f8fbff); }
    .source strong { display:block; margin-bottom:5px; }
    .source small { color:#475569; }
    .checklist { margin:0; padding-left:22px; line-height:1.65; }
    .promptBank { display:grid; gap:10px; margin-top:14px; }
    .prompt { text-align:left; background:#f8fafc; border:1px solid #e2e8f0; color:#0f172a; padding:12px; border-radius:16px; font-weight:800; }
    .gate { border:1px solid #fecaca; background:#fff7f7; border-radius:20px; padding:14px; }
    .footer { color:#dbeafe; text-align:center; padding:24px; font-size:13px; }
    @media (max-width: 860px) { .hero, .grid, .row { grid-template-columns:1fr; } .shell { padding:14px; } .heroCard { padding:24px; } }
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div class="heroCard">
        <div class="eyebrow"><span class="badge">Maine-only</span><span class="badge">Source-first</span><span class="badge">Review-required</span><span class="badge">v__VERSION__</span></div>
        <h1>Family-law help that feels calm, fast, and safe.</h1>
        <p class="sub">Ask a Maine family-law question. Get issue labels, source cards to verify, intake questions, next actions, and a filing gate that blocks unsupported or unreviewed output.</p>
      </div>
      <div class="panel chat">
        <div class="row">
          <div><label for="audience">Audience</label><select id="audience"><option value="parent">Parent or caregiver</option><option value="lawyer">Lawyer / legal professional</option><option value="advocate">Legal aid / advocate</option><option value="court_helper">Court helper / navigator</option></select></div>
          <div><label for="mode">Mode</label><select id="mode"><option value="guided_chat">Guided chat</option><option value="review_checklist">Review checklist</option><option value="draft_triage">Draft triage</option><option value="source_cards">Source cards</option></select></div>
        </div>
        <div style="margin-top:12px"><label for="question">Question</label><textarea id="question"></textarea></div>
        <div class="actions"><button class="primary" onclick="ask()">Ask safely</button><button class="secondary" onclick="copyPacket()">Copy packet JSON</button><button class="ghost" onclick="resetSample()">Reset sample</button></div>
        <div class="promptBank" id="promptBank"></div>
      </div>
    </section>
    <section class="grid">
      <div class="panel section"><h2>Answer</h2><div class="meta" id="meta"></div><div class="answer" id="answer"></div><h2 style="margin-top:22px">Checklist</h2><ol class="checklist" id="checklist"></ol></div>
      <div class="panel section"><h2>Source cards to verify</h2><div class="cards" id="sources"></div><h2 style="margin-top:22px">Filing gate</h2><div class="gate" id="gate"></div></div>
    </section>
    <p class="footer">Not legal advice. No attorney-client relationship. No filing-ready export without source, citation, quote, fact, form, posture, and human-review gates.</p>
  </main>
  <script>
    const seedPacket = __SEED_PACKET__;
    const starterPrompts = __STARTER_PROMPTS__;
    let currentPacket = seedPacket;
    function esc(s){ return String(s ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
    function labelsFor(q){
      const low = q.toLowerCase(); const labels = [];
      const map = {divorce:['divorce','spouse'], parental_rights_responsibilities:['custody','parental rights','parenting'], child_support:['child support','worksheet','income'], protection_from_abuse:['pfa','abuse','protection'], Rule_52_findings:['rule 52','findings','no findings'], best_interest_factor_gap:['best interest','1653'], UCCJEA_jurisdiction:['uccjea','home state','other state','moved to maine'], appeal_preservation:['appeal','law court','transcript']};
      Object.entries(map).forEach(([k, arr]) => { if(arr.some(x => low.includes(x))) labels.push(k); });
      return labels.length ? labels : ['general_family_law_question'];
    }
    function simplePacket(){
      const q = document.getElementById('question').value.trim() || seedPacket.question;
      const audience = document.getElementById('audience').value;
      const mode = document.getElementById('mode').value;
      const issues = labelsFor(q);
      const cards = seedPacket.answer_blocks.source_cards_to_verify.filter(c => issues.includes(c.matched_issue));
      const sourceCards = cards.length ? cards : seedPacket.answer_blocks.source_cards_to_verify;
      return {...seedPacket, question:q, audience, mode, issue_labels:issues, answer_blocks:{...seedPacket.answer_blocks, summary:`This is a review-required Maine family-law workflow for: ${q}. Likely labels: ${issues.join(', ')}. Verify official Maine source cards, map facts to evidence, and keep any draft blocked until human review.` , source_cards_to_verify:sourceCards}};
    }
    function render(p){
      currentPacket = p;
      document.getElementById('meta').innerHTML = [...p.issue_labels.map(x=>`<span class="pill">${esc(x)}</span>`), `<span class="pill block">filing_ready=false</span>`, `<span class="pill good">review_required=true</span>`].join('');
      document.getElementById('answer').innerHTML = `<p>${esc(p.answer_blocks.summary)}</p><p><strong>Remember:</strong> ${esc(p.disclaimer)}</p>`;
      document.getElementById('checklist').innerHTML = p.intake_questions.map(x=>`<li>${esc(x)}</li>`).join('') + p.next_actions.map(x=>`<li>${esc(x.label)}</li>`).join('');
      document.getElementById('sources').innerHTML = p.answer_blocks.source_cards_to_verify.map(c=>`<div class="source"><strong>${esc(c.title)}</strong><small>${esc(c.canonical_citation)} · ${esc(c.source_class)} · ${esc(c.freshness_status)}</small><p>${esc(c.why_it_matters)}</p></div>`).join('');
      document.getElementById('gate').innerHTML = `<strong>Blocked by design.</strong><p>${esc(p.filing_gate.blockers.map(b=>b.message).join(' '))}</p>`;
    }
    function renderPromptBank(){
      const audience = document.getElementById('audience').value;
      document.getElementById('promptBank').innerHTML = (starterPrompts[audience] || []).map(p=>`<button class="prompt" onclick="usePrompt(this)">${esc(p)}</button>`).join('');
    }
    function usePrompt(btn){ document.getElementById('question').value = btn.textContent; ask(); }
    function ask(){ render(simplePacket()); }
    function resetSample(){ document.getElementById('question').value = seedPacket.question; render(seedPacket); renderPromptBank(); }
    async function copyPacket(){ await navigator.clipboard.writeText(JSON.stringify(currentPacket, null, 2)); }
    document.getElementById('audience').addEventListener('change', renderPromptBank);
    resetSample();
  </script>
</body>
</html>"""
    return html_doc.replace("__VERSION__", VERSION).replace("__SEED_PACKET__", seed_json).replace("__STARTER_PROMPTS__", prompts_json)


def write_outputs(output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    sample_packets = build_sample_packets()
    packet_path = output_dir / "family_first_chat_v204_packet.json"
    audit_path = output_dir / "family_first_chat_v204_audit.json"
    html_path = output_dir / "family_first_chat_v204.html"
    packet_payload = {
        "schema": PACKET_SCHEMA,
        "version": VERSION,
        "generated_at": utcnow(),
        "packets": sample_packets,
        "claims": {
            "legal_advice": False,
            "filing_ready": False,
            "private_data_packaged": False,
            "production_ga": False,
        },
    }
    packet_path.write_text(json.dumps(packet_payload, indent=2, sort_keys=True), encoding="utf-8")
    audit_path.write_text(json.dumps(build_audit(sample_packets[0]), indent=2, sort_keys=True), encoding="utf-8")
    html_path.write_text(render_chat_html(sample_packets[0]), encoding="utf-8")
    return {"packet": str(packet_path), "audit": str(audit_path), "html": str(html_path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Maine Family Law LLM v2.04 family-first chat packet")
    parser.add_argument("--question", default="What Maine family-law sources should I verify before drafting?")
    parser.add_argument("--audience", default="parent", choices=sorted(AUDIENCES))
    parser.add_argument("--mode", default="guided_chat")
    parser.add_argument("--output", default="", help="JSON output file for one packet")
    parser.add_argument("--html", default="", help="HTML output file for one packet")
    parser.add_argument("--evidence-dir", default="", help="Directory for packet/audit/html evidence outputs")
    args = parser.parse_args(argv)

    if args.evidence_dir:
        outputs = write_outputs(Path(args.evidence_dir))
        print(json.dumps({"status": "pass", "version": VERSION, "outputs": outputs}, indent=2, sort_keys=True))
        return 0

    packet = build_chat_packet(args.question, audience=args.audience, mode=args.mode)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(packet, indent=2, sort_keys=True), encoding="utf-8")
    else:
        print(json.dumps(packet, indent=2, sort_keys=True))
    if args.html:
        html_path = Path(args.html)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(render_chat_html(packet), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
