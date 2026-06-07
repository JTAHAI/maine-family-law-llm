from __future__ import annotations

from typing import Any

from legal.conversation.missing_information import MissingInformationEngine


class DocumentReviewReportBuilder:
    def __init__(self) -> None:
        self.missing = MissingInformationEngine()

    def build(self, *, filtered: dict[str, Any], findings: dict[str, Any], audience: str = "unknown") -> dict[str, Any]:
        text = str(filtered.get("document_text") or "")
        missing_information = [
            item.as_dict()
            for item in self.missing.analyze(
                workflow="document_review",
                payload={"document_type": "uploaded_text"},
                audience=audience,
                text=text,
            )
        ]
        red_flags = list(findings.get("red_flags") or [])
        if filtered.get("prompt_injection_detected"):
            red_flags.append("Prompt injection or instruction override language detected.")
        return {
            "schema": "maine_family_law_llm.document_review_report_v2",
            "document_summary": "Uploaded text reviewed as untrusted content.",
            "issue_labels": findings.get("issue_labels", []),
            "procedural_posture": findings.get("procedural_posture", "unknown"),
            "extracted_facts": findings.get("extracted_facts", []),
            "citations_found": findings.get("citations_found", []),
            "quotes_found": findings.get("quotes_found", []),
            "unsupported_claims": findings.get("unsupported_claims", []),
            "red_flags": list(dict.fromkeys(red_flags)),
            "missing_information": missing_information,
            "recommended_next_workflow": "check_citations" if findings.get("citations_found") else "review_a_document",
            "review_required": True,
            "document_text_is_untrusted": True,
        }
