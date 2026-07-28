from __future__ import annotations

from legal.matter.models import DocumentClassification
from legal.matter.multi_label_classifier import MultiLabelMatterClassifier


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
    def __init__(self) -> None:
        self.multi_label_classifier = MultiLabelMatterClassifier()

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

        label_result = self.multi_label_classifier.classify(
            relative_path=filename or "unnamed-record",
            text_excerpt=text,
            readable=bool(text.strip()),
        )
        return DocumentClassification(
            document_type=document_type,
            confidence=confidence,
            privilege_flags=sorted(set(privilege_flags)),
            confidentiality_flags=sorted(set(confidentiality_flags)),
            sealed_record_warnings=sealed_record_warnings,
            labels=[item.label for item in label_result.labels],
            label_confidence={item.label: item.confidence for item in label_result.labels},
            classification_status=label_result.status,
            review_reasons=list(label_result.review_reasons),
        )
