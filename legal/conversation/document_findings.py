from __future__ import annotations

import re
from typing import Any

from legal.classifiers.issue_classifier import RuleBasedIssueClassifier
from legal.classifiers.posture_classifier import classify_posture
from legal.classifiers.red_flag_classifier import detect_red_flags
from legal.verifiers.citation_parser import extract_citations


class DocumentFindingsExtractor:
    def __init__(self) -> None:
        self.issue_classifier = RuleBasedIssueClassifier()

    def extract(self, document_text: str) -> dict[str, Any]:
        text = document_text or ""
        issue_labels = [match.label for match in self.issue_classifier.classify(text)] or ["general_family_law_question"]
        citations = [
            {"citation": citation.raw, "kind": citation.kind, "status": "citation_unverified"}
            for citation in extract_citations(text)
        ]
        quotes = re.findall(r'"([^"]{8,200})"', text)
        lowered = text.lower()
        confidentiality = [
            marker
            for marker in ["sealed", "confidential", "juvenile", "minor", "medical", "therapy", "ssn", "address"]
            if marker in lowered
        ]
        unsupported = []
        if any(word in lowered for word in ["must", "shall", "entitled"]) and not citations:
            unsupported.append("legal_or_procedural_claim_without_visible_citation")
        facts = [
            {"text": sentence.strip(), "label": "unverified"}
            for sentence in re.split(r"(?<=[.!?])\s+", text)
            if sentence.strip()
        ][:8]
        return {
            "issue_labels": issue_labels,
            "procedural_posture": str(classify_posture(text)),
            "extracted_facts": facts,
            "citations_found": citations,
            "quotes_found": [{"quote": quote, "status": "quote_span_not_found"} for quote in quotes],
            "unsupported_claims": unsupported,
            "red_flags": list(dict.fromkeys([*detect_red_flags(text), *[f"confidentiality_marker:{item}" for item in confidentiality]])),
        }
