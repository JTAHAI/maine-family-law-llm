from __future__ import annotations

from legal.matter.models import DocumentClassification


DOCUMENT_RULES = [
    ("affidavit", ("affidavit", "under oath", "sworn")),
    ("order", ("ordered", "judgment", "decree", "final order", "temporary order")),
    ("motion", ("motion", "moves this court", "requested relief")),
    ("pleading", ("complaint", "petition", "summons")),
    ("financial_document", ("income", "paystub", "tax return", "child support worksheet")),
    ("communication", ("text message", "email", "message", "conversation")),
    ("transcript", ("transcript", "hearing", "cross-examination", "direct examination")),
    ("exhibit", ("exhibit", "attachment", "photo", "screenshot")),
]

PRIVILEGE_TERMS = ("attorney-client", "work product", "privileged", "settlement communication")
SEALED_TERMS = ("sealed", "juvenile", "minor child", "guardian ad litem", "GAL", "protection from abuse")
CONFIDENTIALITY_TERMS = ("ssn", "social security", "date of birth", "dob", "medical", "therapy")


class RuleBasedDocumentClassifier:
    def classify(self, text: str, filename: str = "") -> DocumentClassification:
        lowered = f"{filename}\n{text}".lower()
        for document_type, terms in DOCUMENT_RULES:
            if any(term in lowered for term in terms):
                confidence = 0.85
                break
        else:
            document_type = "unknown_matter_document"
            confidence = 0.35

        privilege_flags = [term.replace(" ", "_") for term in PRIVILEGE_TERMS if term in lowered]
        confidentiality_flags = [
            term.replace(" ", "_") for term in CONFIDENTIALITY_TERMS if term in lowered
        ]
        sealed_record_warnings = [
            "sealed_or_sensitive_family_record" for term in SEALED_TERMS if term.lower() in lowered
        ]
        sealed_record_warnings = sorted(set(sealed_record_warnings))

        return DocumentClassification(
            document_type=document_type,
            confidence=confidence,
            privilege_flags=sorted(set(privilege_flags)),
            confidentiality_flags=sorted(set(confidentiality_flags)),
            sealed_record_warnings=sealed_record_warnings,
        )
