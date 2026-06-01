"""Full corpus registry for the Maine Family Law LLM legal data product.

The registry is source-control safe: it records what must be collected and how it
should be ranked, parsed, and audited. Raw corpora built from these entries live
outside the repository in the operator's external data root.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from .source_manifest import SourceManifestEntry, validate_manifest


RETRIEVED_AT = "2026-05-24T00:00:00Z"


@dataclass(frozen=True)
class CorpusRequirement:
    id: str
    title: str
    source_type: str
    jurisdiction: str
    official: bool
    url: str
    effective_date: str
    version_label: str
    citation_hint: str
    source_priority: int
    authority_class: str
    corpus_lane: str
    parser: str
    citation_aliases: tuple[str, ...] = ()
    notes: str = ""
    required_for_ga: bool = True

    def to_manifest_entry(self) -> SourceManifestEntry:
        return SourceManifestEntry(
            id=self.id,
            title=self.title,
            source_type=self.source_type,
            jurisdiction=self.jurisdiction,
            official=self.official,
            url=self.url,
            effective_date=self.effective_date,
            retrieved_at=RETRIEVED_AT,
            version_label=self.version_label,
            citation_hint=self.citation_hint,
            license_or_terms_note="Official public legal source; verify source-site terms before redistribution.",
            source_priority=self.source_priority,
            notes=self.notes,
            authority_class=self.authority_class,
            corpus_lane=self.corpus_lane,
            citation_aliases=self.citation_aliases,
            parser=self.parser,
            freshness_status="needs_live_fetch",
            required_for_ga=self.required_for_ga,
            completion_status="manifested",
        )


def _r(
    id: str,
    title: str,
    source_type: str,
    jurisdiction: str,
    url: str,
    citation_hint: str,
    source_priority: int,
    authority_class: str,
    corpus_lane: str,
    parser: str,
    *,
    effective_date: str = "official-page-version-varies",
    version_label: str = "full corpus registry; live fetch required before user-facing use",
    citation_aliases: Iterable[str] = (),
    notes: str = "",
    official: bool = True,
    required_for_ga: bool = True,
) -> CorpusRequirement:
    return CorpusRequirement(
        id=id,
        title=title,
        source_type=source_type,
        jurisdiction=jurisdiction,
        official=official,
        url=url,
        effective_date=effective_date,
        version_label=version_label,
        citation_hint=citation_hint,
        source_priority=source_priority,
        authority_class=authority_class,
        corpus_lane=corpus_lane,
        parser=parser,
        citation_aliases=tuple(citation_aliases),
        notes=notes,
        required_for_ga=required_for_ga,
    )


FULL_CORPUS_REQUIREMENTS: tuple[CorpusRequirement, ...] = (
    _r(
        "mrs-title-19a-complete",
        "Maine Revised Statutes Title 19-A Domestic Relations - complete title",
        "statute",
        "Maine",
        "https://www.mainelegislature.org/legis/statutes/19-A/title19-Ach0sec0.html",
        "19-A M.R.S.",
        10,
        "official_maine_statute",
        "maine_family_primary_law",
        "maine_statute_title_parser",
        citation_aliases=("Title 19-A", "19-A M.R.S.", "Domestic Relations"),
        notes="Primary family-law statute corpus; must be expanded to every section record.",
    ),
    _r("mrs-title-18c-overlap", "Maine Revised Statutes Title 18-C Probate Code family overlap", "statute", "Maine", "https://www.mainelegislature.org/legis/statutes/18-C/title18-Cch0sec0.html", "18-C M.R.S.", 12, "official_maine_statute", "maine_family_overlap_law", "maine_statute_title_parser", citation_aliases=("Title 18-C", "guardianship", "adoption", "probate")),
    _r("mrs-title-22-overlap", "Maine Revised Statutes Title 22 child protection and DHHS overlap", "statute", "Maine", "https://www.mainelegislature.org/legis/statutes/22/title22ch0sec0.html", "22 M.R.S.", 13, "official_maine_statute", "maine_family_overlap_law", "maine_statute_title_parser", citation_aliases=("Title 22", "child protection", "DHHS")),
    _r("mrs-title-4-courts", "Maine Revised Statutes Title 4 courts and Family Division authority", "statute", "Maine", "https://www.mainelegislature.org/legis/statutes/4/title4ch0sec0.html", "4 M.R.S.", 14, "official_maine_statute", "maine_court_authority", "maine_statute_title_parser", citation_aliases=("Title 4", "Family Division")),
    _r("mrs-title-5-harassment-admin", "Maine Revised Statutes Title 5 administrative and harassment overlap", "statute", "Maine", "https://www.mainelegislature.org/legis/statutes/5/title5ch0sec0.html", "5 M.R.S.", 20, "official_maine_statute", "maine_family_overlap_law", "maine_statute_title_parser"),
    _r("mrs-title-14-enforcement", "Maine Revised Statutes Title 14 civil procedure, judgments, and enforcement overlap", "statute", "Maine", "https://www.mainelegislature.org/legis/statutes/14/title14ch0sec0.html", "14 M.R.S.", 20, "official_maine_statute", "maine_family_overlap_law", "maine_statute_title_parser"),
    _r("mrs-title-15-criminal-procedure-overlap", "Maine Revised Statutes Title 15 criminal procedure family-overlap", "statute", "Maine", "https://www.mainelegislature.org/legis/statutes/15/title15ch0sec0.html", "15 M.R.S.", 30, "official_maine_statute", "maine_family_overlap_law", "maine_statute_title_parser"),
    _r("mrs-title-17a-criminal-family-overlap", "Maine Revised Statutes Title 17-A domestic-violence criminal-family overlap", "statute", "Maine", "https://www.mainelegislature.org/legis/statutes/17-A/title17-Ach0sec0.html", "17-A M.R.S.", 30, "official_maine_statute", "maine_family_overlap_law", "maine_statute_title_parser"),
    _r("mrs-title-30a-records-law-enforcement", "Maine Revised Statutes Title 30-A municipal, records, and law-enforcement overlap", "statute", "Maine", "https://www.mainelegislature.org/legis/statutes/30-A/title30-Ach0sec0.html", "30-A M.R.S.", 35, "official_maine_statute", "maine_family_overlap_law", "maine_statute_title_parser"),
    _r(
        "maine-rules-index",
        "Maine Judicial Branch Court Rules and Administrative Orders index",
        "court_rule",
        "Maine",
        "https://www.courts.maine.gov/rules/index.html",
        "Maine Judicial Branch Court Rules",
        8,
        "official_maine_rules_index",
        "maine_nonlegislative_authority",
        "maine_rules_index_parser",
        effective_date="2026-05-20",
        version_label="Court Rules page updated May 20, 2026; includes June 1, 2026 civil-rule amendments.",
    ),
    _r("maine-rules-civil-family-division-complete", "Maine Rules of Civil Procedure and Family Division Rules 100-129", "court_rule", "Maine", "https://www.courts.maine.gov/rules/rules-civil.html", "M.R. Civ. P.", 11, "official_family_division_rule", "maine_nonlegislative_authority", "maine_civil_rules_parser", effective_date="2026-06-01", version_label="Maine civil rules as effective June 1, 2026 per Judicial Branch rules index.", citation_aliases=("M.R. Civ. P. 100-129", "Family Division Rules", "Rule 120")),
    _r("maine-rule-120-standing-order", "Standing Order Regarding Motions for Findings of Fact and Conclusions of Law in Family Matters", "standing_order", "Maine", "https://www.courts.maine.gov/rules/text/mr_civ_p_120_standing_order_2023-03-09.pdf", "M.R. Civ. P. 120 standing order", 9, "official_standing_order", "maine_nonlegislative_authority", "pdf_rule_order_parser", effective_date="2023-03-10", version_label="Standing order effective March 10, 2023.", citation_aliases=("Rule 52 findings", "Rule 120(c)", "post-judgment findings")),
    _r("maine-rules-evidence", "Maine Rules of Evidence", "evidence_rule", "Maine", "https://www.courts.maine.gov/rules/index.html", "M.R. Evid.", 16, "official_maine_evidence_rule", "maine_nonlegislative_authority", "maine_rules_pdf_parser", effective_date="2025-10-14", version_label="Rules index notes Evidence amendment effective October 14, 2025.", citation_aliases=("M.R. Evid.", "hearsay", "authentication", "privilege")),
    _r("maine-rules-appellate", "Maine Rules of Appellate Procedure", "appellate_rule", "Maine", "https://www.courts.maine.gov/rules/index.html", "M.R. App. P.", 17, "official_maine_appellate_rule", "maine_nonlegislative_authority", "maine_rules_pdf_parser", effective_date="2024-11", version_label="Maine rules index lists appellate rules November 2024.", citation_aliases=("M.R. App. P.", "notice of appeal", "record on appeal")),
    _r("maine-rules-electronic-court-systems", "Maine Rules of Electronic Court Systems", "ecourts_rule", "Maine", "https://www.courts.maine.gov/rules/text/mrecs.pdf", "M.R.E.C.S.", 18, "official_maine_ecourts_rule", "maine_nonlegislative_authority", "maine_rules_pdf_parser", effective_date="2026-01-31", version_label="MRECS reviewed January 28, 2026; amendments effective January 31, 2026.", citation_aliases=("MRECS", "eFileMaine", "re:SearchMaine")),
    _r("maine-professional-conduct-plus", "Maine Rules of Professional Conduct with comments and notes", "professional_conduct_rule", "Maine", "https://www.courts.maine.gov/rules/text/mr_prof_conduct_plus_2023-09-28.pdf", "M.R. Prof. Conduct", 40, "official_maine_professional_conduct", "maine_ethics_and_regulation", "maine_rules_pdf_parser", effective_date="2023-09-28", version_label="Reviewed September 28, 2023; amendments effective September 28, 2023.", citation_aliases=("Rule 1.4", "Rule 1.16", "Rule 3.3", "Rule 8.4")),
    _r("maine-bar-rules-plus", "Maine Bar Rules with advisory notes", "bar_rule", "Maine", "https://www.courts.maine.gov/rules/text/m_bar_r_plus_2025-07-14.pdf", "Maine Bar Rule", 41, "official_maine_bar_rule", "maine_ethics_and_regulation", "maine_rules_pdf_parser", effective_date="2025-07-10", version_label="As amended July 2025 per Judicial Branch rules index.", citation_aliases=("attorney regulation", "Board of Overseers")),
    _r("maine-judicial-conduct-code", "Maine Code of Judicial Conduct", "judicial_conduct_rule", "Maine", "https://www.courts.maine.gov/rules/index.html", "Maine Code Jud. Conduct", 42, "official_maine_judicial_conduct", "maine_ethics_and_regulation", "maine_rules_pdf_parser", effective_date="2024-09-23", version_label="Maine rules index lists Judicial Conduct code September 2024.", citation_aliases=("recusal", "ex parte", "bias", "impartiality")),
    _r("maine-committee-judicial-conduct", "Committee on Judicial Conduct and judicial disciplinary proceedings", "judicial_discipline", "Maine", "https://www.courts.maine.gov/rules/index.html", "Maine judicial disciplinary rules", 43, "official_maine_judicial_conduct", "maine_ethics_and_regulation", "maine_rules_pdf_parser", effective_date="2025-06-25", version_label="Rules index lists amendments effective June 25, 2025."),
    _r("maine-forms-family-catalog", "Maine Judicial Branch family forms and packets catalog", "court_form", "Maine", "https://www.courts.maine.gov/forms/index.html", "Maine Judicial Branch family forms", 19, "official_maine_form", "maine_forms_and_instructions", "maine_forms_catalog_parser", citation_aliases=("FM forms", "child support affidavit", "motion to modify", "motion to enforce")),
    _r("maine-family-process-guide", "Maine Judicial Branch court process in family matters", "court_process", "Maine", "https://www.courts.maine.gov/courts/family/process.html", "Maine Judicial Branch family process", 45, "official_maine_public_guidance", "maine_public_guidance", "html_guidance_parser"),
    _r("maine-divorce-separation-guide", "Maine Judicial Branch divorce and family separation guide", "judicial_branch_guide", "Maine", "https://www.courts.maine.gov/courts/family/divorce-separation/", "Maine Judicial Branch divorce and family separation", 45, "official_maine_public_guidance", "maine_public_guidance", "html_guidance_parser"),
    _r("maine-changing-enforcing-order-guide", "Maine Judicial Branch changing or enforcing a family order", "judicial_branch_guide", "Maine", "https://www.courts.maine.gov/courts/family/changing.html", "Maine Judicial Branch changing/enforcing orders", 45, "official_maine_public_guidance", "maine_public_guidance", "html_guidance_parser"),
    _r("maine-pfa-guide", "Maine Judicial Branch abuse and harassment protection-order information and forms", "safety_resource", "Maine", "https://www.courts.maine.gov/help/abuse/index.html", "Maine Judicial Branch abuse and harassment protection orders", 4, "official_maine_safety_resource", "maine_safety_and_emergency", "html_guidance_parser"),
    _r("maine-ecourts-access-guide", "Maine eCourts access, records, and confidentiality guidance", "judicial_branch_guide", "Maine", "https://www.courts.maine.gov/ecourts/access.html", "Maine eCourts access guidance", 44, "official_maine_public_guidance", "maine_public_guidance", "html_guidance_parser"),
    _r("maine-law-court-opinions-index", "Maine Supreme Judicial Court / Law Court published opinions index", "law_court_opinion_index", "Maine", "https://www.courts.maine.gov/courts/sjc/opinions.html", "Maine Law Court opinions", 12, "maine_law_court_opinion", "maine_case_law", "maine_law_court_index_parser", citation_aliases=("Law Court", "SJC", "published opinions")),
    _r("district-maine-local-rules", "U.S. District Court for the District of Maine Local Rules", "federal_court_rule", "Federal - District of Maine", "https://www.med.uscourts.gov/local-rules", "D. Me. Local Rules", 21, "official_federal_district_maine_local_rules", "federal_maine_intake_and_relief", "district_maine_local_rules_parser", effective_date="2025-04-01", version_label="District of Maine Local Rules effective April 1, 2025.", citation_aliases=("D. Me. Local Rule 3", "D. Me. Local Rule 7", "D. Me. Local Rule 64", "D. Me. Local Rule 65.1")),
    _r("district-maine-local-rules-pdf", "District of Maine Local Rules PDF including Appendix B electronic filing", "federal_court_rule", "Federal - District of Maine", "https://www.med.uscourts.gov/sites/med/files/LocalRules.pdf", "D. Me. Local Rules", 21, "official_federal_district_maine_local_rules", "federal_maine_intake_and_relief", "pdf_rule_order_parser", effective_date="2025-04-01", version_label="Local Rules PDF effective April 1, 2025; includes Appendix B electronic filing procedures."),
    _r("district-maine-pro-se", "District of Maine representing yourself / pro se guidance", "federal_court_guide", "Federal - District of Maine", "https://www.med.uscourts.gov/representing-yourself-pro-se", "D. Me. pro se guidance", 46, "official_federal_district_maine_pro_se_guidance", "federal_maine_intake_and_relief", "html_guidance_parser", citation_aliases=("self-represented", "pro se")),
    _r("district-maine-pro-se-handout", "District of Maine Pro Se Information Handout", "federal_court_guide", "Federal - District of Maine", "https://www.med.uscourts.gov/file/221", "D. Me. Pro Se Information Handout", 46, "official_federal_district_maine_pro_se_guidance", "federal_maine_intake_and_relief", "pdf_guidance_parser"),
    _r("district-maine-self-representation-forms", "District of Maine self-representation civil forms", "federal_court_form", "Federal - District of Maine", "https://www.med.uscourts.gov/self-representation-forms", "D. Me. self-representation forms", 32, "official_federal_district_maine_forms", "federal_maine_intake_and_relief", "federal_forms_catalog_parser", citation_aliases=("JS-44", "AO240", "AO398", "AO399", "AO440", "Motion Form")),
    _r("district-maine-electronic-filing", "District of Maine electronic filing for self-represented civil parties", "federal_ecf_guidance", "Federal - District of Maine", "https://www.med.uscourts.gov/electronic-filing", "D. Me. electronic filing guidance", 33, "official_federal_district_maine_ecf", "federal_maine_intake_and_relief", "html_guidance_parser", citation_aliases=("MaineECFIntake@med.uscourts.gov", "CM/ECF", "NEF", "PDF filing")),
    _r("district-maine-ecf-faq", "District of Maine CM/ECF frequently asked questions", "federal_ecf_guidance", "Federal - District of Maine", "https://www.med.uscourts.gov/ecf-faq", "D. Me. ECF FAQ", 34, "official_federal_district_maine_ecf", "federal_maine_intake_and_relief", "html_guidance_parser"),
    _r("district-maine-sealing-redacting-hsd", "District of Maine sealing, redacting, restricted, and highly sensitive document guidance", "federal_ecf_guidance", "Federal - District of Maine", "https://www.med.uscourts.gov/sealing-redacting-highly-sensitive-documents", "D. Me. sealing and HSD guidance", 34, "official_federal_district_maine_ecf", "federal_maine_intake_and_relief", "html_guidance_parser"),
    _r("district-maine-opinions-index", "District of Maine opinions index", "federal_case_law", "Federal - District of Maine", "https://www.med.uscourts.gov/opinions", "D. Me. opinions", 25, "official_federal_district_maine_opinion", "federal_maine_case_law", "district_maine_opinion_index_parser"),
    _r("first-circuit-opinions-index", "First Circuit opinions index", "first_circuit_opinion", "Federal - First Circuit", "https://www.ca1.uscourts.gov/opinions", "1st Cir. opinions", 22, "first_circuit_binding", "federal_binding_case_law", "first_circuit_opinion_index_parser"),
    _r("supreme-court-opinions-index", "Supreme Court opinions index", "us_supreme_court_opinion", "Federal - U.S. Supreme Court", "https://www.supremecourt.gov/opinions/opinions.aspx", "U.S. Supreme Court opinions", 5, "us_supreme_court_binding", "federal_binding_case_law", "supreme_court_opinion_index_parser"),
    _r("federal-rules-current-index", "U.S. Courts current federal rules of practice and procedure", "federal_rule", "United States", "https://www.uscourts.gov/forms-rules/current-rules-practice-procedure", "Federal Rules of Practice and Procedure", 6, "federal_rules_primary", "federal_rules_and_statutes", "federal_rules_index_parser", effective_date="2025-12-01", version_label="U.S. Courts current-rules page lists amendments effective December 1, 2025."),
    _r("federal-rules-civil-procedure", "Federal Rules of Civil Procedure", "federal_rule", "United States", "https://www.uscourts.gov/forms-rules/current-rules-practice-procedure/federal-rules-civil-procedure", "Fed. R. Civ. P.", 6, "federal_rules_primary", "federal_rules_and_statutes", "federal_rules_parser", effective_date="2025-12-01", version_label="Civil Rules 16 and 26 and new Rule 16.1 effective December 1, 2025.", citation_aliases=("FRCP 3", "FRCP 4", "FRCP 65", "FRCP 72")),
    _r("federal-rules-evidence", "Federal Rules of Evidence", "federal_rule", "United States", "https://www.uscourts.gov/forms-rules/current-rules-practice-procedure/federal-rules-evidence", "Fed. R. Evid.", 7, "federal_rules_primary", "federal_rules_and_statutes", "federal_rules_parser"),
    _r("federal-rules-appellate-procedure", "Federal Rules of Appellate Procedure", "federal_rule", "United States", "https://www.uscourts.gov/forms-rules/current-rules-practice-procedure/federal-rules-appellate-procedure", "Fed. R. App. P.", 7, "federal_rules_primary", "federal_rules_and_statutes", "federal_rules_parser", effective_date="2025-12-01", version_label="U.S. Courts page notes Appellate Rules amended in 2025."),
    _r("federal-rules-2254-2255", "Rules Governing Section 2254 Cases and Section 2255 Proceedings", "federal_rule", "United States", "https://www.uscourts.gov/forms-rules/current-rules-practice-procedure/rules-governing-section-2254-and-section-2255-proceedings", "Rules Governing 2254 and 2255 Proceedings", 28, "federal_rules_primary", "federal_rules_and_statutes", "federal_rules_parser"),
    _r("uscode-28-1915-ifp", "28 U.S.C. section 1915 proceedings in forma pauperis", "federal_statute", "United States", "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title28-section1915&num=0&edition=prelim", "28 U.S.C. § 1915", 6, "federal_statute_primary", "federal_rules_and_statutes", "uscode_section_parser", citation_aliases=("IFP", "in forma pauperis", "screening")),
    _r("uscode-28-636-magistrate", "28 U.S.C. section 636 magistrate judge authority", "federal_statute", "United States", "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title28-section636&num=0&edition=prelim", "28 U.S.C. § 636", 6, "federal_statute_primary", "federal_rules_and_statutes", "uscode_section_parser"),
    _r("uscode-42-1983-civil-rights", "42 U.S.C. section 1983 civil action for deprivation of rights", "federal_statute", "United States", "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title42-section1983&num=0&edition=prelim", "42 U.S.C. § 1983", 6, "federal_statute_primary", "federal_rules_and_statutes", "uscode_section_parser", citation_aliases=("section 1983", "civil rights")),
    _r("uscode-28-1331-federal-question", "28 U.S.C. section 1331 federal question jurisdiction", "federal_statute", "United States", "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title28-section1331&num=0&edition=prelim", "28 U.S.C. § 1331", 6, "federal_statute_primary", "federal_rules_and_statutes", "uscode_section_parser"),
    _r("uscode-28-1332-diversity", "28 U.S.C. section 1332 diversity jurisdiction", "federal_statute", "United States", "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title28-section1332&num=0&edition=prelim", "28 U.S.C. § 1332", 6, "federal_statute_primary", "federal_rules_and_statutes", "uscode_section_parser"),
    _r("uscode-28-1441-removal", "28 U.S.C. section 1441 removal of civil actions", "federal_statute", "United States", "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title28-section1441&num=0&edition=prelim", "28 U.S.C. § 1441", 6, "federal_statute_primary", "federal_rules_and_statutes", "uscode_section_parser"),
    _r("uscode-28-1446-removal-procedure", "28 U.S.C. section 1446 removal procedure", "federal_statute", "United States", "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title28-section1446&num=0&edition=prelim", "28 U.S.C. § 1446", 6, "federal_statute_primary", "federal_rules_and_statutes", "uscode_section_parser"),
    _r("uscode-28-2283-anti-injunction", "28 U.S.C. section 2283 stay of state court proceedings", "federal_statute", "United States", "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title28-section2283&num=0&edition=prelim", "28 U.S.C. § 2283", 6, "federal_statute_primary", "federal_rules_and_statutes", "uscode_section_parser", citation_aliases=("Anti-Injunction Act",)),
)


AUTHORITY_RANKING = (
    "us_supreme_court_binding",
    "constitutional_authority",
    "federal_statute_primary",
    "federal_rules_primary",
    "first_circuit_binding",
    "official_maine_statute",
    "maine_law_court_opinion",
    "official_federal_district_maine_local_rules",
    "official_family_division_rule",
    "official_standing_order",
    "official_maine_evidence_rule",
    "official_maine_appellate_rule",
    "official_maine_ecourts_rule",
    "official_maine_form",
    "official_federal_district_maine_forms",
    "official_federal_district_maine_ecf",
    "official_federal_district_maine_pro_se_guidance",
    "official_maine_professional_conduct",
    "official_maine_bar_rule",
    "official_maine_judicial_conduct",
    "official_maine_public_guidance",
    "official_federal_district_maine_opinion",
    "legal_aid_plain_language",
    "licensed_secondary",
)


REQUIRED_INDEXES = (
    "exact_citation_index",
    "statute_section_lookup",
    "rule_lookup",
    "case_name_lookup",
    "case_citation_lookup",
    "form_id_lookup",
    "bm25_lexical_index",
    "vector_index_optional",
    "hybrid_retrieval_index",
    "source_card_index",
    "authority_graph",
    "freshness_index",
)


REQUIRED_ATTORNEY_REVIEWED_EVALS = {
    "maine_rag_retrieval_gold.jsonl": 500,
    "maine_citation_validity_gold.jsonl": 500,
    "maine_quote_span_gold.jsonl": 500,
    "maine_hallucination_negative_cases.jsonl": 250,
    "maine_forms_freshness_gold.jsonl": 100,
    "maine_drafting_review_gold.jsonl": 100,
    "maine_issue_classification_gold.jsonl": 250,
    "maine_posture_classification_gold.jsonl": 150,
    "maine_authority_ranking_gold.jsonl": 250,
    "maine_fact_to_evidence_gold.jsonl": 250,
    "maine_law_court_holding_gold.jsonl": 150,
    "maine_rule_52_gap_gold.jsonl": 100,
    "federal_maine_intake_relief_gold.jsonl": 150,
    "federal_jurisdiction_blockers_gold.jsonl": 150,
}


FEDERAL_JURISDICTION_WARNINGS = (
    "domestic_relations_exception",
    "rooker_feldman",
    "younger_abstention",
    "anti_injunction_act",
    "sovereign_immunity",
    "judicial_immunity",
    "quasi_judicial_immunity",
    "qualified_immunity",
    "claim_preclusion",
    "issue_preclusion",
    "ifp_screening",
    "service_defect",
)


def full_corpus_manifest_entries() -> list[SourceManifestEntry]:
    return validate_manifest([requirement.to_manifest_entry() for requirement in FULL_CORPUS_REQUIREMENTS])


def corpus_summary() -> dict[str, object]:
    entries = full_corpus_manifest_entries()
    lanes = sorted({entry.corpus_lane for entry in entries})
    authority_classes = sorted({entry.authority_class for entry in entries})
    return {
        "schema": "maine_family_law_llm.full_corpus_registry.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "registry_ready",
        "source_count": len(entries),
        "required_for_ga_count": sum(1 for entry in entries if entry.required_for_ga),
        "lanes": lanes,
        "authority_classes": authority_classes,
        "required_indexes": list(REQUIRED_INDEXES),
        "attorney_reviewed_eval_minimums": dict(REQUIRED_ATTORNEY_REVIEWED_EVALS),
        "federal_jurisdiction_warnings": list(FEDERAL_JURISDICTION_WARNINGS),
    }
