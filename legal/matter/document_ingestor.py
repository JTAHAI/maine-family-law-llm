from __future__ import annotations

import hashlib
import re
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from legal.classifiers.issue_classifier import RuleBasedIssueClassifier
from legal.classifiers.posture_classifier import classify_posture
from legal.classifiers.red_flag_classifier import detect_red_flags
from legal.data_boundaries.private_data_scanner import scan_text
from legal.data_boundaries.redaction import redact_private_identifiers
from legal.data_boundaries.retention import retention_policy_for
from legal.evidence.fact_to_evidence_mapper import FactToEvidenceMapper
from legal.evidence.timeline_builder import TimelineBuilder
from legal.matter.consistency_review import SourceText, find_cross_document_conflicts
from legal.matter.document_classifier import RuleBasedDocumentClassifier
from legal.matter.models import ExtractedFact, IntakeReport, Matter, MatterDocument

DATE_RE = re.compile(
    r"\b(?:\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? \d{1,2}, \d{4})\b",
    re.IGNORECASE,
)
TEXT_EXTRACTABLE_SUFFIXES = {".txt", ".md", ".csv", ".json", ".jsonl", ".yaml", ".yml"}


def _audit(event_type: str, **metadata: Any) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata,
    }


class MatterDocumentIngestor:
    def __init__(self) -> None:
        self.document_classifier = RuleBasedDocumentClassifier()
        self.issue_classifier = RuleBasedIssueClassifier()
        self.timeline_builder = TimelineBuilder()
        self.fact_mapper = FactToEvidenceMapper()

    def extract_text_from_upload(
        self,
        *,
        filename: str,
        uploaded_bytes: bytes | None = None,
        provided_text: str | None = None,
    ) -> tuple[str, str]:
        if provided_text is not None:
            return provided_text, "provided_text"
        if uploaded_bytes is None:
            return "", "empty_upload"
        suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if suffix in TEXT_EXTRACTABLE_SUFFIXES:
            try:
                return uploaded_bytes.decode("utf-8"), "decoded_utf8_text_upload"
            except UnicodeDecodeError:
                return uploaded_bytes.decode("latin-1", errors="replace"), "decoded_latin1_text_upload"
        if suffix == ".pdf":
            return "", "binary_pdf_ocr_required_not_run_in_source_repo"
        return "", "unsupported_binary_text_extraction_required"

    def ingest_document(
        self,
        *,
        matter_id: str,
        filename: str,
        text: str | None = None,
        uploaded_bytes: bytes | None = None,
        tenant_id: str = "tenant_unassigned",
    ) -> MatterDocument:
        extracted_text, extracted_status = self.extract_text_from_upload(
            filename=filename,
            uploaded_bytes=uploaded_bytes,
            provided_text=text,
        )
        digest = hashlib.sha256(extracted_text.encode("utf-8")).hexdigest()
        document_id = f"doc_{digest[:12]}"
        classification = self.document_classifier.classify(extracted_text, filename=filename)
        redacted = redact_private_identifiers(extracted_text)
        findings = scan_text(extracted_text, path=filename)
        retention = retention_policy_for("user_provided_confidential_matter_data")
        audit_history = [
            _audit("document_received", filename=filename, matter_id=matter_id, tenant_id=tenant_id),
            _audit("text_extracted", status=extracted_status),
            _audit("private_data_scanned", finding_kinds=sorted({finding.kind for finding in findings})),
            _audit("document_classified", document_type=classification.document_type),
            _audit("redaction_applied", redaction_count=redacted.redaction_count),
            _audit("training_policy_applied", private_data_allowed_for_training=False),
        ]
        return MatterDocument(
            document_id=document_id,
            matter_id=matter_id,
            filename=filename,
            sha256=digest,
            text=extracted_text,
            redacted_text=redacted.text,
            classification=classification,
            tenant_id=tenant_id,
            parser_status="parsed_text" if extracted_text else extracted_status,
            retention_policy_id=retention.retain,
            retention_action=retention.minimum_action or "matter_policy_defined",
            pii_findings=sorted({finding.kind for finding in findings}),
            redaction_count=redacted.redaction_count,
            extracted_text_status=extracted_status,
            audit_history=audit_history,
        )

    def extract_facts(self, document: MatterDocument) -> list[ExtractedFact]:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", document.redacted_text) if s.strip()]
        facts: list[ExtractedFact] = []
        for index, sentence in enumerate(sentences):
            lowered = sentence.lower()
            if any(term in lowered for term in ("child", "parent", "support", "order", "motion", "contact", "residence", "abuse", "divorce", "hearing", "payment", "school")):
                labels = [match.label for match in self.issue_classifier.classify(sentence)]
                date_match = DATE_RE.search(sentence)
                start = document.redacted_text.find(sentence)
                span = (start, start + len(sentence)) if start >= 0 else None
                facts.append(
                    ExtractedFact(
                        fact_id=f"{document.document_id}_fact_{index}",
                        document_id=document.document_id,
                        text=sentence,
                        confidence=0.7 if labels else 0.45,
                        date=date_match.group(0) if date_match else None,
                        issue_labels=labels,
                        evidence_span=span,
                    )
                )
        return facts

    def build_intake_report(self, matter: Matter, documents: list[MatterDocument]) -> IntakeReport:
        all_text = "\n".join(document.redacted_text for document in documents)
        issue_labels = sorted({match.label for match in self.issue_classifier.classify(all_text)})
        posture = classify_posture(all_text)
        red_flags = sorted(set(detect_red_flags(all_text)))

        all_facts: list[ExtractedFact] = []
        for document in documents:
            all_facts.extend(self.extract_facts(document))

        evidence_items = [
            {
                "evidence_id": fact.fact_id,
                "document_id": fact.document_id,
                "source_document_id": fact.document_id,
                "text": fact.text,
                "date": fact.date,
                "source_class": "user_provided_confidential_matter_data",
                "span_start": fact.evidence_span[0] if fact.evidence_span else None,
                "span_end": fact.evidence_span[1] if fact.evidence_span else None,
                "confidence": fact.confidence,
            }
            for fact in all_facts
        ]
        evidence_map = self.fact_mapper.map([fact.text for fact in all_facts], evidence_items)
        timeline_events = [
            {
                "event_id": fact.fact_id,
                "matter_id": matter.matter_id,
                "date": fact.date or "unknown",
                "description": fact.text,
                "source_document_id": fact.document_id,
                "span_start": fact.evidence_span[0] if fact.evidence_span else None,
                "span_end": fact.evidence_span[1] if fact.evidence_span else None,
                "confidence": fact.confidence,
            }
            for fact in all_facts
            if fact.date
        ]
        timeline = self.timeline_builder.build(timeline_events)

        warnings = []
        for document in documents:
            warnings.extend(document.pii_findings)
            warnings.extend(document.classification.privilege_flags)
            warnings.extend(document.classification.confidentiality_flags)
            warnings.extend(document.classification.sealed_record_warnings)
            if document.extracted_text_status.endswith("required") or "required" in document.extracted_text_status:
                warnings.append(document.extracted_text_status)

        missing_record_checklist = build_missing_record_checklist(
            documents=documents,
            issue_labels=issue_labels,
            procedural_posture=posture,
            timeline=timeline,
        )

        document_labels = {
            document.document_id: list(document.classification.labels) for document in documents
        }
        conflict_records = find_cross_document_conflicts(
            SourceText(
                document_id=document.document_id,
                filename=document.filename,
                text=document.redacted_text,
            )
            for document in documents
            if document.redacted_text
        )

        return IntakeReport(
            matter=matter,
            documents=documents,
            issue_labels=issue_labels,
            procedural_posture=posture,
            red_flags=red_flags,
            timeline=timeline,
            evidence_map=evidence_map,
            missing_record_checklist=missing_record_checklist,
            warnings=sorted(set(warnings)),
            document_labels=document_labels,
            cross_document_conflicts=[item.to_dict() for item in conflict_records],
        )

    def report_as_dict(self, report: IntakeReport) -> dict[str, Any]:
        return asdict(report)


def build_missing_record_checklist(
    *,
    documents: list[MatterDocument],
    issue_labels: list[str],
    procedural_posture: str,
    timeline: list[dict[str, Any]],
) -> list[str]:
    document_types = {document.classification.document_type for document in documents}
    filenames = "\n".join(document.filename.lower() for document in documents)
    checklist: list[str] = []
    if "child_support" in issue_labels and "financial_document" not in document_types:
        checklist.append("financial_disclosure_or_child_support_worksheet_missing")
    if procedural_posture == "appeal" and "transcript" not in document_types:
        checklist.append("appeal_transcript_or_record_missing")
    if not timeline:
        checklist.append("dated_events_missing_for_timeline")
    if "order" not in document_types and procedural_posture in {"post_judgment", "contempt", "appeal", "motion_to_modify"}:
        checklist.append("underlying_order_missing")
    if "protection_from_abuse" in issue_labels and not any("pfa" in name or "protection" in name for name in filenames.splitlines()):
        checklist.append("protection_order_record_missing")
    return sorted(set(checklist))
