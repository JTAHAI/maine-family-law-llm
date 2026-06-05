from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

VERSION = "2.03.0"
PACKET_SCHEMA = "maine_family_law_llm.filing_gate_studio.packet.v1"
GATE_SCHEMA = "maine_family_law_llm.filing_gate_studio.gate_report.v1"

DISCLAIMER = (
    "Maine Family Law LLM provides legal information and workflow support, not legal advice. "
    "Drafts are review-required and not filing-ready unless authority, citations, quote spans, "
    "facts, source scope, forms, docket posture, and human review gates pass."
)

SAFE_SOURCE_STATUSES = {
    "verified_official_maine",
    "verified_maine_law_court",
    "verified_federal",
    "verified_public_api",
}

FRESH_ENOUGH = {"fresh", "current", "retrieved_freshness_unverified", "offline_smoke_not_current"}

LEGAL_TERMS = {
    "court",
    "order",
    "motion",
    "rule",
    "statute",
    "maine",
    "parental",
    "rights",
    "responsibilities",
    "custody",
    "contact",
    "residence",
    "support",
    "divorce",
    "pfa",
    "protection",
    "abuse",
    "appeal",
    "finding",
    "findings",
    "best",
    "interest",
    "jurisdiction",
    "uccjea",
    "contempt",
    "enforce",
    "modify",
    "evidence",
    "form",
}

ISSUE_PATTERNS: dict[str, tuple[str, ...]] = {
    "divorce": ("divorce", "dissolution", "marital", "spouse"),
    "parental_rights_responsibilities": ("parental rights", "custody", "residence", "contact", "parenting"),
    "primary_residence": ("primary residence", "primary home", "reside primarily"),
    "contact_schedule": ("contact schedule", "visitation", "parenting time", "supervised contact"),
    "child_support": ("child support", "support worksheet", "guidelines", "income"),
    "parentage": ("parentage", "paternity", "de facto parent"),
    "post_judgment_motion": ("post-judgment", "post judgment", "after final", "modify", "enforce"),
    "motion_to_modify": ("motion to modify", "modify", "substantial change"),
    "motion_to_enforce": ("motion to enforce", "enforce", "compliance"),
    "motion_for_contempt": ("contempt", "failure to comply"),
    "protection_from_abuse": ("protection from abuse", "pfa", "abuse order"),
    "pfa_family_overlap": ("pfa", "parental rights", "family case"),
    "grandparent_visitation": ("grandparent", "visitation"),
    "guardianship": ("guardian", "guardianship"),
    "GAL_issue": ("guardian ad litem", "gal"),
    "UCCJEA_jurisdiction": ("uccjea", "home state", "jurisdiction"),
    "Rule_52_findings": ("rule 52", "findings", "proposed findings"),
    "best_interest_factor_gap": ("best interest", "19-a m.r.s. § 1653", "1653"),
    "appeal_preservation": ("appeal", "preserve", "law court"),
    "transcript_record_issue": ("transcript", "record on appeal"),
    "eCourts_record_access": ("ecourts", "odyssey", "record access"),
    "therapist_non_delegation": ("therapist decides", "counselor decides", "delegated contact"),
}

POSTURE_PATTERNS: dict[str, tuple[str, ...]] = {
    "initial_complaint": ("complaint", "initial filing", "summons"),
    "temporary_order": ("temporary order", "interim relief", "pendente lite"),
    "interim_order": ("interim order", "interim"),
    "final_order": ("final order", "judgment", "divorce judgment", "final hearing"),
    "post_judgment": ("post-judgment", "post judgment", "after judgment"),
    "contempt": ("contempt",),
    "appeal": ("appeal", "law court"),
    "remand": ("remand", "remanded"),
    "motion_for_findings": ("motion for findings", "rule 52"),
    "motion_to_reconsider": ("reconsider", "alter or amend"),
    "stay_pending_appeal": ("stay pending appeal", "stay"),
}

RED_FLAG_PATTERNS: dict[str, tuple[str, ...]] = {
    "missing Rule 52 findings": ("final order", "parental rights", "no findings"),
    "unsupported best-interest findings": ("best interest", "unsupported"),
    "therapist or third-party delegated contact decision": ("therapist decides", "counselor decides", "gal decides"),
    "protective-order finding imported into family case without independent analysis": ("pfa", "automatic custody"),
    "contact restriction without sourced findings": ("no contact", "supervised contact", "restriction"),
    "missing transcript or incomplete appellate record": ("appeal", "no transcript"),
    "stale court form": ("stale form", "old form"),
    "unverified citation": ("unverified citation", "fake citation"),
    "quote span not found": ("quote not found",),
    "unsupported factual claim": ("unsupported fact",),
    "wrong court or wrong procedure": ("wrong court", "wrong procedure"),
    "deadline risk": ("deadline", "tomorrow", "today", "served"),
    "service defect": ("not served", "service defect"),
    "jurisdiction defect": ("home state", "uccjea", "jurisdiction defect"),
    "privacy or sealed-record issue": ("sealed", "confidential", "minor child", "social security"),
}

CITATION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "maine_statute",
        re.compile(
            r"\b(?P<title>\d{1,2}-?[A-Z]?)\s*(?:M\.?\s*R\.?\s*S\.?|MRS|MRSA|M\.R\.S\.)\.?\s*§+\s*(?P<section>[\dA-Za-z][\dA-Za-z.\-]*)",
            re.I,
        ),
    ),
    (
        "maine_rule",
        re.compile(
            r"\bM\.?\s*R\.?\s*(?P<rule_set>Civ\.?|App\.?|Evid\.?)\s*P\.?\s*(?P<rule>\d+[A-Za-z\-]*)\b",
            re.I,
        ),
    ),
    ("maine_case", re.compile(r"\b(?P<year>20\d{2}|19\d{2})\s+ME\s+(?P<number>\d+)\b", re.I)),
    ("maine_form", re.compile(r"\bFM[-\s]?(?P<number>\d{3,4}[A-Z]?)\b", re.I)),
    (
        "federal_statute",
        re.compile(r"\b(?P<title>\d{1,2})\s*U\.?\s*S\.?\s*C\.?\s*§+\s*(?P<section>[\dA-Za-z][\dA-Za-z.\-]*)", re.I),
    ),
)

QUOTE_RE = re.compile(r"[\"“](?P<quote>.{4,800}?)[\"”]", re.S)


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def clean_pinpoint(value: str) -> str:
    return (value or "").strip().rstrip(".;,)]}")


def tokens(text: str) -> list[str]:
    return [t.lower() for t in re.findall(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)?", text or "") if len(t) > 1]


def canonical_for(kind: str, match: re.Match[str]) -> str:
    if kind == "maine_statute":
        return f"{match.group('title').upper()} M.R.S. § {clean_pinpoint(match.group('section'))}"
    if kind == "maine_rule":
        rule_set = match.group("rule_set").lower()
        label = "Civ." if rule_set.startswith("civ") else "App." if rule_set.startswith("app") else "Evid."
        return f"M.R. {label} P. {clean_pinpoint(match.group('rule'))}"
    if kind == "maine_case":
        return f"{match.group('year')} ME {match.group('number')}"
    if kind == "maine_form":
        return f"FM-{clean_pinpoint(match.group('number')).upper()}"
    if kind == "federal_statute":
        return f"{match.group('title')} U.S.C. § {clean_pinpoint(match.group('section'))}"
    return normalize_space(match.group(0))


def parse_citations(text: str) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int]] = set()
    for kind, pattern in CITATION_PATTERNS:
        for match in pattern.finditer(text or ""):
            key = (kind, match.start(), match.end())
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                {
                    "citation_text": match.group(0).rstrip(".;,"),
                    "canonical_citation": canonical_for(kind, match),
                    "citation_type": kind,
                    "start": match.start(),
                    "end": match.end(),
                    "status": "parsed_unverified",
                }
            )
    citations.sort(key=lambda row: row["start"])
    return citations


@dataclass(frozen=True)
class SourceCard:
    source_id: str
    title: str
    jurisdiction: str = "maine"
    source_class: str = "unknown"
    authority_status: str = "stale_unknown"
    freshness_status: str = "unknown"
    canonical_citation: str = ""
    url: str = ""
    text: str = ""
    snapshot_sha256: str = ""
    parser_status: str = "unknown"

    @classmethod
    def from_any(cls, value: "SourceCard | dict[str, Any]") -> "SourceCard":
        if isinstance(value, SourceCard):
            return value
        return cls(
            source_id=str(value.get("source_id", "")),
            title=str(value.get("title", "")),
            jurisdiction=str(value.get("jurisdiction", "maine")),
            source_class=str(value.get("source_class", value.get("record_type", "unknown"))),
            authority_status=str(value.get("authority_status", "stale_unknown")),
            freshness_status=str(value.get("freshness_status", "unknown")),
            canonical_citation=str(value.get("canonical_citation", "")),
            url=str(value.get("url", "")),
            text=str(value.get("text", value.get("text_span", ""))),
            snapshot_sha256=str(value.get("snapshot_sha256", "")),
            parser_status=str(value.get("parser_status", "unknown")),
        )

    def source_card(self) -> dict[str, Any]:
        data = asdict(self)
        data["text_preview"] = normalize_space(self.text[:700])
        data.pop("text", None)
        return data


@dataclass(frozen=True)
class FactEvidence:
    fact: str
    evidence_id: str = ""
    source_id: str = ""
    quote: str = ""
    confidence: float = 0.0
    span_status: str = "unverified"

    @classmethod
    def from_any(cls, value: "FactEvidence | dict[str, Any]") -> "FactEvidence":
        if isinstance(value, FactEvidence):
            return value
        return cls(
            fact=str(value.get("fact", "")),
            evidence_id=str(value.get("evidence_id", value.get("id", ""))),
            source_id=str(value.get("source_id", "")),
            quote=str(value.get("quote", value.get("text_span", ""))),
            confidence=float(value.get("confidence", 0.0) or 0.0),
            span_status=str(value.get("span_status", "unverified")),
        )


@dataclass
class GateFinding:
    finding_id: str
    severity: str
    category: str
    message: str
    blocks_filing_ready: bool = True
    evidence: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def issue_labels(text: str) -> list[str]:
    low = (text or "").lower()
    labels = [label for label, patterns in ISSUE_PATTERNS.items() if any(p in low for p in patterns)]
    return sorted(set(labels or ["general_family_law_review"]))


def posture_labels(text: str) -> list[str]:
    low = (text or "").lower()
    labels = [label for label, patterns in POSTURE_PATTERNS.items() if any(p in low for p in patterns)]
    return sorted(set(labels or ["posture_unknown"]))


def red_flags(text: str) -> list[dict[str, Any]]:
    low = (text or "").lower()
    flags: list[dict[str, Any]] = []
    for label, patterns in RED_FLAG_PATTERNS.items():
        hits = [p for p in patterns if p in low]
        if hits:
            flags.append({"red_flag": label, "matched_terms": hits, "review_required": True})
    return flags


def authority_score(card: SourceCard) -> float:
    score = {
        "verified_official_maine": 100,
        "verified_maine_law_court": 95,
        "verified_federal": 75,
        "verified_public_api": 55,
        "user_provided_only": 35,
    }.get(card.authority_status, 10)
    if "statute" in card.source_class:
        score += 8
    if "rule" in card.source_class:
        score += 7
    if "form" in card.source_class:
        score += 5
    if card.freshness_status not in FRESH_ENOUGH:
        score -= 20
    return float(score)


def authority_matrix(cards: list[SourceCard]) -> list[dict[str, Any]]:
    rows = [{**card.source_card(), "authority_score": authority_score(card)} for card in cards]
    rows.sort(key=lambda row: (-row["authority_score"], row["source_id"]))
    return rows


def build_source_lookup(cards: list[SourceCard]) -> dict[str, list[SourceCard]]:
    lookup: dict[str, list[SourceCard]] = {}
    for card in cards:
        for raw in (card.source_id, card.title, card.canonical_citation):
            key = normalize_space(raw).lower()
            if key:
                lookup.setdefault(key, []).append(card)
    return lookup


def resolve_citations(text: str, cards: list[SourceCard]) -> list[dict[str, Any]]:
    lookup = build_source_lookup(cards)
    rows: list[dict[str, Any]] = []
    for cite in parse_citations(text):
        hits = lookup.get(cite["canonical_citation"].lower(), [])
        status = "resolved" if hits else "not_found"
        rows.append(
            {
                **cite,
                "status": status,
                "resolved_source_ids": sorted({c.source_id for c in hits}),
                "resolved_authority_statuses": sorted({c.authority_status for c in hits}),
                "review_required": True,
                "blocks_filing_ready": status != "resolved",
            }
        )
    return rows


def parse_quotes(text: str) -> list[dict[str, Any]]:
    return [
        {
            "quote": normalize_space(match.group("quote")),
            "start": match.start("quote"),
            "end": match.end("quote"),
            "status": "parsed_unverified",
        }
        for match in QUOTE_RE.finditer(text or "")
    ]


def quote_overlap_score(needle: str, haystack: str) -> float:
    n_tokens = set(tokens(needle))
    h_tokens = set(tokens(haystack))
    if not n_tokens:
        return 0.0
    return len(n_tokens & h_tokens) / max(len(n_tokens), 1)


def verify_quotes(text: str, cards: list[SourceCard]) -> list[dict[str, Any]]:
    report: list[dict[str, Any]] = []
    for quote in parse_quotes(text):
        qnorm = normalize_space(quote["quote"]).lower()
        best: dict[str, Any] | None = None
        for card in cards:
            hay = normalize_space(card.text).lower()
            exact = bool(qnorm and qnorm in hay)
            fuzzy = quote_overlap_score(qnorm, hay[:4000])
            if exact or fuzzy >= 0.82:
                candidate = {
                    "source_id": card.source_id,
                    "canonical_citation": card.canonical_citation,
                    "match_type": "normalized_exact" if exact else "token_fuzzy",
                    "score": 1.0 if exact else round(fuzzy, 4),
                }
                if best is None or candidate["score"] > best["score"]:
                    best = candidate
        status = "quote_span_found" if best else "quote_span_not_found"
        report.append(
            {
                **quote,
                "status": status,
                "best_match": best,
                "review_required": True,
                "blocks_filing_ready": status != "quote_span_found",
            }
        )
    return report


def split_sentences(text: str) -> list[str]:
    normalized = normalize_space(text)
    protected = normalized
    for pattern in (
        r"M\.R\.S\.",
        r"M\.R\. Civ\. P\.",
        r"M\.R\. App\. P\.",
        r"M\.R\. Evid\. P\.",
        r"U\.S\.C\.",
    ):
        protected = re.sub(pattern, lambda match: match.group(0).replace(".", "<DOT>"), protected, flags=re.I)
    return [
        p.replace("<DOT>", ".").strip()
        for p in re.split(r"(?<=[.!?])\s+", protected)
        if len(p.replace("<DOT>", ".").strip()) >= 12
    ]


def classify_claim(sentence: str) -> str:
    low = sentence.lower()
    if parse_citations(sentence) or any(term in low for term in ("must", "shall", "may", "court", "statute", "rule", "m.r.s", "law")):
        return "legal_claim"
    concrete_fact_terms = (
        "mother",
        "father",
        "missed",
        "paid",
        "failed to pay",
        "text message",
        "email",
        "on january",
        "on february",
        "on march",
        "on april",
        "on may",
        "on june",
        "on july",
        "on august",
        "on september",
        "on october",
        "on november",
        "on december",
    )
    if any(term in low for term in concrete_fact_terms):
        return "factual_claim"
    if any(term in low for term in LEGAL_TERMS):
        return "legal_claim"
    return "narrative_or_instruction"


def extract_claims(text: str, limit: int = 100) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for sentence in split_sentences(text):
        low = sentence.lower()
        if "not legal advice" in low or "review-required" in low:
            continue
        ctype = classify_claim(sentence)
        if ctype == "narrative_or_instruction" and not any(t in low for t in LEGAL_TERMS):
            continue
        claims.append(
            {
                "claim_id": f"claim_{len(claims)+1:03d}",
                "text": sentence,
                "claim_type": ctype,
                "citations": parse_citations(sentence),
                "issue_labels": issue_labels(sentence),
            }
        )
        if len(claims) >= limit:
            break
    return claims


def fact_support_score(claim: str, evidence: FactEvidence) -> float:
    c_tokens = set(tokens(claim))
    e_tokens = set(tokens(evidence.fact + " " + evidence.quote))
    if not c_tokens:
        return 0.0
    return len(c_tokens & e_tokens) / len(c_tokens)


def claim_support_report(text: str, cards: list[SourceCard], fact_evidence: list[FactEvidence]) -> list[dict[str, Any]]:
    citation_rows = resolve_citations(text, cards)
    resolved_by_canonical: dict[str, dict[str, Any]] = {
        row["canonical_citation"]: row for row in citation_rows if row["status"] == "resolved"
    }
    report: list[dict[str, Any]] = []
    for claim in extract_claims(text):
        resolved = []
        unresolved = []
        for cite in claim["citations"]:
            match = resolved_by_canonical.get(cite["canonical_citation"])
            if match:
                resolved.append(match)
            else:
                unresolved.append(cite)

        evidence_hits = []
        if claim["claim_type"] == "factual_claim":
            for ev in fact_evidence:
                score = fact_support_score(claim["text"], ev)
                if score >= 0.25:
                    evidence_hits.append({"evidence_id": ev.evidence_id, "source_id": ev.source_id, "score": round(score, 4)})

        if claim["claim_type"] == "legal_claim":
            if unresolved:
                status = "unsupported_unresolved_citation"
            elif resolved:
                status = "supported_by_resolved_citation"
            elif resolved_by_canonical and claim["issue_labels"] != ["general_family_law_review"]:
                status = "supported_by_document_source_scope_review_required"
            else:
                status = "unsupported_no_citation"
        elif claim["claim_type"] == "factual_claim":
            status = "supported_by_evidence" if evidence_hits else "unsupported_no_evidence"
        else:
            status = "review_required"

        report.append(
            {
                **claim,
                "status": status,
                "resolved_citations": resolved,
                "unresolved_citations": unresolved,
                "evidence_hits": evidence_hits,
                "blocks_filing_ready": status.startswith("unsupported"),
                "review_required": True,
            }
        )
    return report


def best_interest_coverage(text: str) -> dict[str, Any]:
    low = (text or "").lower()
    factor_map = {
        "child_age_and_needs": ("age", "needs", "development"),
        "relationship_with_each_parent": ("relationship", "bond", "each parent"),
        "stability": ("stability", "stable", "continuity"),
        "safety_or_abuse": ("abuse", "safety", "violence", "protection"),
        "child_preference_when_relevant": ("preference", "wishes"),
        "cooperation_and_contact": ("cooperate", "cooperation", "contact", "parenting time"),
        "school_and_community": ("school", "community"),
        "medical_or_special_needs": ("medical", "therapy", "special needs"),
    }
    covered = [name for name, terms in factor_map.items() if any(term in low for term in terms)]
    return {
        "covered_factor_groups": covered,
        "missing_factor_groups": [name for name in factor_map if name not in covered],
        "coverage_ratio": round(len(covered) / len(factor_map), 4),
        "review_required": True,
    }


def form_freshness_report(forms_used: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for form in forms_used:
        freshness = str(form.get("freshness_status", "unknown"))
        status = "form_freshness_ok" if freshness in FRESH_ENOUGH else "stale_or_unknown_form"
        rows.append({**form, "status": status, "blocks_filing_ready": status != "form_freshness_ok"})
    return rows


def build_gate_report(
    draft_text: str,
    source_cards: list[SourceCard | dict[str, Any]] | None = None,
    fact_evidence: list[FactEvidence | dict[str, Any]] | None = None,
    forms_used: list[dict[str, Any]] | None = None,
    human_review_completed: bool = False,
    intended_export: str = "working_draft",
    matter_posture: str | None = None,
) -> dict[str, Any]:
    cards = [SourceCard.from_any(c) for c in (source_cards or [])]
    evidence = [FactEvidence.from_any(e) for e in (fact_evidence or [])]
    forms = forms_used or []

    citations = resolve_citations(draft_text, cards)
    quotes = verify_quotes(draft_text, cards)
    claims = claim_support_report(draft_text, cards, evidence)
    issues = issue_labels(draft_text)
    postures = posture_labels(draft_text)
    if matter_posture and matter_posture not in postures:
        postures.insert(0, matter_posture)
    flags = red_flags(draft_text)
    coverage = best_interest_coverage(draft_text)
    forms_report = form_freshness_report(forms)

    findings: list[GateFinding] = []

    def add(severity: str, category: str, message: str, blocks: bool = True, evidence_payload: dict[str, Any] | None = None) -> None:
        findings.append(
            GateFinding(
                finding_id=f"gate_{len(findings)+1:03d}",
                severity=severity,
                category=category,
                message=message,
                blocks_filing_ready=blocks,
                evidence=evidence_payload or {},
            )
        )

    if not cards:
        add("blocker", "source_scope", "No source cards were supplied; legal source scope is unknown.")

    unresolved = [c for c in citations if c["status"] != "resolved"]
    if unresolved:
        add("blocker", "citation_verification", "One or more citations did not resolve to supplied source cards.", True, {"citations": unresolved})

    if not citations and any(c["claim_type"] == "legal_claim" for c in claims):
        add("blocker", "citation_verification", "Legal claims were detected but no citations were found.")

    missing_quotes = [q for q in quotes if q["status"] != "quote_span_found"]
    if missing_quotes:
        add("blocker", "quote_verification", "One or more quoted passages were not found in supplied source text.", True, {"quotes": missing_quotes})

    unsupported_claims = [c for c in claims if c.get("blocks_filing_ready")]
    if unsupported_claims:
        add("blocker", "claim_support", "One or more legal or factual claims are unsupported.", True, {"claims": unsupported_claims[:20]})

    stale_sources = [c.source_card() for c in cards if c.freshness_status not in FRESH_ENOUGH]
    if stale_sources and re.search(r"\b(current|under maine law|maine law requires|must|shall)\b", draft_text or "", re.I):
        add("blocker", "freshness", "Current-law-style claims were made while one or more sources have stale or unknown freshness.", True, {"sources": stale_sources})

    non_maine_sources = [c.source_card() for c in cards if c.jurisdiction not in {"maine", "federal"}]
    if non_maine_sources:
        add("blocker", "jurisdiction", "A source outside Maine/federal authority was supplied for a Maine-family-law workflow.", True, {"sources": non_maine_sources})

    unsafe_authority = [c.source_card() for c in cards if c.authority_status not in SAFE_SOURCE_STATUSES]
    if unsafe_authority:
        add("warning", "authority_status", "Some sources are user-provided, unknown, stale, or otherwise not verified official authority.", False, {"sources": unsafe_authority})

    family_order_issues = {"parental_rights_responsibilities", "primary_residence", "contact_schedule", "best_interest_factor_gap", "Rule_52_findings"}
    if family_order_issues & set(issues) and coverage["coverage_ratio"] < 0.5:
        add("blocker", "best_interest_coverage", "Parental-rights/best-interest language appears, but best-interest factor coverage is thin.", True, coverage)

    if any(p in postures for p in ("final_order", "motion_for_findings")) and "Rule_52_findings" not in issues:
        add("warning", "rule_52", "Final-order or findings posture detected; confirm Rule 52/finding requirements are addressed.", False)

    stale_forms = [f for f in forms_report if f["blocks_filing_ready"]]
    if stale_forms:
        add("blocker", "form_freshness", "One or more forms are stale or have unknown freshness.", True, {"forms": stale_forms})

    if intended_export == "filing_ready" and not human_review_completed:
        add("blocker", "human_review", "Human review is incomplete; filing-ready export is blocked.")

    blockers = [f.as_dict() for f in findings if f.blocks_filing_ready]
    warnings = [f.as_dict() for f in findings if not f.blocks_filing_ready]
    filing_ready = intended_export == "filing_ready" and not blockers and human_review_completed

    return {
        "schema": GATE_SCHEMA,
        "version": VERSION,
        "generated_at": utcnow(),
        "status": "pass" if filing_ready else "blocked" if blockers else "review_required",
        "filing_ready": filing_ready,
        "review_required": not filing_ready,
        "intended_export": intended_export,
        "human_review_completed": human_review_completed,
        "issue_labels": issues,
        "posture_labels": postures,
        "authority_matrix": authority_matrix(cards),
        "citation_report": citations,
        "quote_report": quotes,
        "claim_support_report": claims,
        "red_flags": flags,
        "best_interest_coverage": coverage,
        "form_freshness_report": forms_report,
        "blockers": blockers,
        "warnings": warnings,
        "disclaimer": DISCLAIMER,
        "claims": {
            "legal_advice": False,
            "filing_ready_without_human_review": False,
            "private_data_packaged": False,
            "model_weights_packaged": False,
        },
    }


def next_actions_for_gate(gate: dict[str, Any]) -> list[dict[str, str]]:
    categories = Counter(item["category"] for item in gate.get("blockers", []))
    mapping = [
        ("source_scope", "add_source_cards", "Attach verified Maine source cards before legal review."),
        ("citation_verification", "fix_citations", "Resolve or remove citations marked not_found."),
        ("quote_verification", "fix_quotes", "Replace unmatched quotes with exact source text and offsets."),
        ("claim_support", "support_claims", "Map each legal/factual claim to authority or evidence."),
        ("best_interest_coverage", "complete_best_interest_review", "Review best-interest factor coverage and findings."),
        ("form_freshness", "update_forms", "Verify current official Maine Judicial Branch form versions."),
        ("human_review", "complete_human_review", "Complete attorney or qualified reviewer checklist."),
    ]
    actions = [{"action": action, "label": label} for category, action, label in mapping if categories.get(category)]
    return actions or [{"action": "continue_review", "label": "Continue review; do not treat as legal advice or filing-ready without signoff."}]


def build_review_packet(
    draft_text: str,
    source_cards: list[SourceCard | dict[str, Any]] | None = None,
    fact_evidence: list[FactEvidence | dict[str, Any]] | None = None,
    forms_used: list[dict[str, Any]] | None = None,
    human_review_completed: bool = False,
    intended_export: str = "working_draft",
    matter_posture: str | None = None,
) -> dict[str, Any]:
    gate = build_gate_report(
        draft_text=draft_text,
        source_cards=source_cards,
        fact_evidence=fact_evidence,
        forms_used=forms_used,
        human_review_completed=human_review_completed,
        intended_export=intended_export,
        matter_posture=matter_posture,
    )
    return {
        "schema": PACKET_SCHEMA,
        "version": VERSION,
        "generated_at": utcnow(),
        "status": "pass",
        "draft_preview": normalize_space(draft_text[:1400]),
        "gate_report": gate,
        "next_actions": next_actions_for_gate(gate),
        "export_options": {
            "working_draft": "allowed_review_required",
            "citation_report": "allowed",
            "quote_report": "allowed",
            "filing_ready": "allowed_only_when_gate_passes" if gate["filing_ready"] else "blocked",
        },
    }


def render_html_packet(packet: dict[str, Any]) -> str:
    gate = packet.get("gate_report", {})
    body = json.dumps(packet, indent=2, sort_keys=True)
    blockers = len(gate.get("blockers", []))
    return f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>Maine Family Law LLM Filing Gate Studio v{VERSION}</title>
<style>body{{font-family:system-ui;margin:0;background:#07111f;color:#0f172a}}main{{max-width:1180px;margin:32px auto;background:white;border-radius:28px;padding:26px;box-shadow:0 24px 80px #0008}}h1{{margin-top:0}}.pill{{display:inline-block;border-radius:999px;padding:7px 10px;margin:4px;background:#eff6ff;color:#1d4ed8;font-weight:800}}.bad{{background:#fef2f2;color:#991b1b}}pre{{white-space:pre-wrap;background:#f8fafc;border:1px solid #e2e8f0;padding:16px;border-radius:18px;max-height:620px;overflow:auto}}</style>
</head><body><main><h1>Maine Family Law LLM Filing Gate Studio v{VERSION}</h1>
<p><span class=\"pill bad\">filing_ready={html.escape(str(gate.get('filing_ready')))}</span><span class=\"pill bad\">blockers={blockers}</span><span class=\"pill\">review_required={html.escape(str(gate.get('review_required')))}</span></p>
<p>{html.escape(DISCLAIMER)}</p><pre>{html.escape(body)}</pre></main></body></html>"""


def sample_source_cards() -> list[dict[str, Any]]:
    return [
        {
            "source_id": "me_statute_19a_1653_smoke",
            "title": "Offline smoke source card for 19-A M.R.S. § 1653",
            "jurisdiction": "maine",
            "source_class": "statute",
            "authority_status": "verified_official_maine",
            "freshness_status": "offline_smoke_not_current",
            "canonical_citation": "19-A M.R.S. § 1653",
            "text": "OFFLINE SMOKE FIXTURE ONLY. Canonical citation marker: 19-A M.R.S. § 1653. Topics include best interest, relationship with each parent, stability, safety, abuse, school, community, medical needs, preference, and contact.",
        },
        {
            "source_id": "me_rule_52_smoke",
            "title": "Offline smoke source card for M.R. Civ. P. 52",
            "jurisdiction": "maine",
            "source_class": "court_rule",
            "authority_status": "verified_official_maine",
            "freshness_status": "offline_smoke_not_current",
            "canonical_citation": "M.R. Civ. P. 52",
            "text": "OFFLINE SMOKE FIXTURE ONLY. Canonical citation marker: M.R. Civ. P. 52. Findings and review workflow marker.",
        },
    ]


def build_sample_packet() -> dict[str, Any]:
    draft = (
        "This proposed final order addresses parental rights and responsibilities under 19-A M.R.S. § 1653. "
        "The court must consider the child best interest, stability, safety, school, medical needs, and contact. "
        "The source says \"Canonical citation marker: 19-A M.R.S. § 1653\". "
        "The draft also cites fake authority 99-A M.R.S. § 9999 and says the father missed visits without evidence."
    )
    return build_review_packet(
        draft,
        source_cards=sample_source_cards(),
        fact_evidence=[],
        forms_used=[{"form_id": "FM-001", "freshness_status": "unknown"}],
        human_review_completed=False,
        intended_export="filing_ready",
        matter_posture="final_order",
    )


def _load_json(path: str | None, default: Any) -> Any:
    if not path:
        return default
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a Maine Family Law LLM filing gate review packet")
    parser.add_argument("--draft", default="", help="Draft text file. If omitted, use smoke sample.")
    parser.add_argument("--source-cards", default="", help="JSON list of source cards")
    parser.add_argument("--fact-evidence", default="", help="JSON list of fact/evidence rows")
    parser.add_argument("--forms-used", default="", help="JSON list of forms used")
    parser.add_argument("--intended-export", default="working_draft", choices=["working_draft", "filing_ready"])
    parser.add_argument("--human-review-completed", action="store_true")
    parser.add_argument("--output", default="")
    parser.add_argument("--html", default="")
    args = parser.parse_args(argv)

    if args.draft:
        draft_text = Path(args.draft).read_text(encoding="utf-8")
        packet = build_review_packet(
            draft_text,
            source_cards=_load_json(args.source_cards, []),
            fact_evidence=_load_json(args.fact_evidence, []),
            forms_used=_load_json(args.forms_used, []),
            human_review_completed=args.human_review_completed,
            intended_export=args.intended_export,
        )
    else:
        packet = build_sample_packet()

    text = json.dumps(packet, indent=2, sort_keys=True)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    else:
        print(text)
    if args.html:
        html_path = Path(args.html)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(render_html_packet(packet), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
